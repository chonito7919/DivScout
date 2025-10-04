# Copyright 2025 DivScout Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Main entry point for DivScout - Dividend data extraction tool
Uses XBRL data from SEC CompanyFacts API
"""

import sys
import argparse
import time
from datetime import datetime

from db_connection import db
from config import COLLECTION_CONFIG
from sec_edgar_client import SECAPIClient
from parsers.xbrl_dividend_parser import XBRLDividendParser


def process_company(ticker, client, parser):
    """
    Process a single company using XBRL data

    Args:
        ticker: Stock ticker symbol
        client: SECAPIClient instance
        parser: XBRLDividendParser instance

    Returns:
        dict with success status and statistics
    """
    start_time = time.time()
    ticker = ticker.upper()

    print(f"\n{'='*70}")
    print(f"Processing: {ticker}")
    print(f"{'='*70}")

    # Step 1: Look up CIK
    print(f"1. Looking up company info...")
    company_info = client.lookup_ticker_to_cik(ticker)

    if not company_info:
        print(f"  ✗ Could not find CIK for ticker {ticker}")
        db.log_collection_attempt(
            company_id=None,
            ticker=ticker,
            data_type='xbrl',
            status='failed',
            error_message=f"Could not find CIK for {ticker}"
        )
        return {
            'success': False,
            'ticker': ticker,
            'error': 'CIK lookup failed'
        }

    cik = company_info['cik']
    company_name = company_info['name']

    print(f"  ✓ Found: {company_name}")
    print(f"  ✓ CIK: {cik}")

    # Fetch company submissions to get sector/industry info
    print(f"  Fetching sector/industry info...")
    submissions = client.get_company_submissions(cik)

    sector = None
    industry = None

    if submissions:
        # Use SIC description as industry
        industry = submissions.get('sicDescription')

        # Map SIC code to sector (simplified mapping)
        sic = submissions.get('sic')
        if sic:
            sic_str = str(sic)
            # Basic sector mapping based on SIC division
            if sic_str.startswith(('01', '02', '07', '08', '09')):
                sector = 'Agriculture, Forestry & Fishing'
            elif sic_str.startswith(('10', '11', '12', '13', '14')):
                sector = 'Mining'
            elif sic_str.startswith(('15', '16', '17')):
                sector = 'Construction'
            elif sic_str.startswith(('20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39')):
                sector = 'Manufacturing'
            elif sic_str.startswith(('40', '41', '42', '43', '44', '45', '46', '47', '48', '49')):
                sector = 'Transportation & Public Utilities'
            elif sic_str.startswith(('50', '51')):
                sector = 'Wholesale Trade'
            elif sic_str.startswith(('52', '53', '54', '55', '56', '57', '58', '59')):
                sector = 'Retail Trade'
            elif sic_str.startswith(('60', '61', '62', '63', '64', '65', '66', '67')):
                sector = 'Finance, Insurance & Real Estate'
            elif sic_str.startswith(('70', '72', '73', '75', '76', '78', '79', '80', '81', '82', '83', '84', '86', '87', '88', '89')):
                sector = 'Services'
            elif sic_str.startswith('99'):
                sector = 'Public Administration'

            if sector and industry:
                print(f"  ✓ Sector: {sector}")
                print(f"  ✓ Industry: {industry}")

    # Get or create company in database
    company_id = db.get_or_create_company(
        ticker=ticker,
        company_name=company_name,
        cik=cik,
        sector=sector,
        industry=industry
    )
    print(f"  ✓ Company ID: {company_id}")

    # Step 2: Fetch XBRL company facts
    print(f"\n2. Fetching XBRL company facts from SEC...")
    facts = client.get_company_facts(cik)

    if not facts:
        print(f"  ✗ Could not fetch XBRL data")
        db.log_collection_attempt(
            company_id=company_id,
            ticker=ticker,
            data_type='xbrl',
            status='failed',
            error_message='Failed to fetch XBRL company facts'
        )
        return {
            'success': False,
            'ticker': ticker,
            'company_id': company_id,
            'error': 'XBRL fetch failed'
        }

    print(f"  ✓ Retrieved company facts")

    # Step 3: Parse dividend data
    print(f"\n3. Parsing dividend data with confidence scoring...")
    dividends = parser.parse_company_facts(facts, cik)

    if not dividends:
        print(f"  ⊘ No dividends found in XBRL data")
        processing_time = int(time.time() - start_time)
        db.log_collection_attempt(
            company_id=company_id,
            ticker=ticker,
            data_type='xbrl',
            status='not_available',
            records_inserted=0,
            processing_time=processing_time
        )
        return {
            'success': True,
            'ticker': ticker,
            'company_id': company_id,
            'dividends_found': 0,
            'dividends_inserted': 0,
            'processing_time': processing_time
        }

    print(f"  ✓ Found {len(dividends)} dividends")

    # Show confidence summary
    low_confidence = sum(1 for d in dividends if d.get('confidence', 1.0) < 0.8)
    avg_confidence = sum(d.get('confidence', 1.0) for d in dividends) / len(dividends)
    print(f"  ✓ Average confidence: {avg_confidence:.2%}")
    if low_confidence > 0:
        print(f"  ⚠️  {low_confidence} dividends need review (confidence < 80%)")

    # Step 4: Insert into database
    print(f"\n4. Inserting dividends into database...")
    inserted, skipped, needs_review = db.bulk_insert_dividends(company_id, dividends)

    print(f"  ✓ Inserted: {inserted}")
    print(f"  ⊘ Skipped (duplicates): {skipped}")
    if needs_review > 0:
        print(f"  ⚠️  Flagged for review: {needs_review}")

    # Step 5: Log completion
    processing_time = int(time.time() - start_time)
    status = 'success' if inserted > 0 else 'not_available'

    db.log_collection_attempt(
        company_id=company_id,
        ticker=ticker,
        data_type='xbrl',
        status=status,
        records_inserted=inserted,
        processing_time=processing_time,
        records_flagged=needs_review
    )

    # Summary
    print(f"\n{'='*70}")
    print(f"Summary for {ticker}:")
    print(f"  Dividends found: {len(dividends)}")
    print(f"  Dividends inserted: {inserted}")
    print(f"  Duplicates skipped: {skipped}")
    print(f"  Flagged for review: {needs_review}")
    print(f"  Processing time: {processing_time}s")
    print(f"{'='*70}")

    return {
        'success': True,
        'ticker': ticker,
        'company_id': company_id,
        'dividends_found': len(dividends),
        'dividends_inserted': inserted,
        'duplicates_skipped': skipped,
        'needs_review': needs_review,
        'processing_time': processing_time
    }


def main():
    """
    Main entry point - parse arguments and process companies
    """
    parser = argparse.ArgumentParser(
        description='Extract dividend data from SEC XBRL filings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process single company
  python main.py AAPL

  # Process multiple companies
  python main.py AAPL MSFT JNJ KO

  # Note: This tool uses XBRL data from SEC CompanyFacts API.
  # The --filing-type option is deprecated (XBRL contains all data).
        """
    )

    parser.add_argument(
        'tickers',
        nargs='+',
        help='Stock ticker symbols (e.g., AAPL MSFT JNJ)'
    )

    # Keep for backward compatibility but ignore
    parser.add_argument(
        '--filing-type',
        choices=['8-K', '10-K', 'both', 'xbrl'],
        default='xbrl',
        help='[DEPRECATED] Now uses XBRL data only'
    )

    parser.add_argument(
        '--start-year',
        type=int,
        help='[DEPRECATED] XBRL data includes all available years'
    )

    parser.add_argument(
        '--end-year',
        type=int,
        help='[DEPRECATED] XBRL data includes all available years'
    )

    args = parser.parse_args()

    # Warn about deprecated options
    if args.filing_type != 'xbrl':
        print("⚠️  WARNING: --filing-type is deprecated. Using XBRL data.")
    if args.start_year or args.end_year:
        print("⚠️  WARNING: --start-year and --end-year are deprecated.")
        print("   XBRL data includes all available dividend history.")

    # Test database connection
    print("\nTesting database connection...")
    if not db.test_connection():
        print("✗ Cannot connect to database. Check your .env configuration.")
        return 1

    print()

    # Initialize client and parser
    client = SECAPIClient()
    parser = XBRLDividendParser()

    # Process companies
    overall_start = time.time()
    results = []
    overall_stats = {
        'companies_processed': 0,
        'total_dividends_found': 0,
        'total_dividends_inserted': 0,
        'total_duplicates_skipped': 0,
        'total_needs_review': 0,
        'total_errors': 0
    }

    for ticker in args.tickers:
        result = process_company(ticker, client, parser)
        results.append(result)

        if result['success']:
            overall_stats['companies_processed'] += 1
            overall_stats['total_dividends_found'] += result.get('dividends_found', 0)
            overall_stats['total_dividends_inserted'] += result.get('dividends_inserted', 0)
            overall_stats['total_duplicates_skipped'] += result.get('duplicates_skipped', 0)
            overall_stats['total_needs_review'] += result.get('needs_review', 0)
        else:
            overall_stats['total_errors'] += 1

        # Small delay between companies to respect rate limits
        if ticker != args.tickers[-1]:  # Don't delay after last one
            time.sleep(0.5)

    overall_time = int(time.time() - overall_start)

    # Print overall summary if multiple companies
    if len(args.tickers) > 1:
        print(f"\n{'='*70}")
        print("OVERALL SUMMARY")
        print(f"{'='*70}")
        print(f"Companies processed: {overall_stats['companies_processed']}")
        print(f"Total dividends found: {overall_stats['total_dividends_found']}")
        print(f"Total dividends inserted: {overall_stats['total_dividends_inserted']}")
        print(f"Total duplicates skipped: {overall_stats['total_duplicates_skipped']}")
        print(f"Total flagged for review: {overall_stats['total_needs_review']}")
        print(f"Errors: {overall_stats['total_errors']}")
        print(f"Total time: {overall_time}s")
        print(f"API requests made: {client.get_stats()['requests_made']}")
        print(f"{'='*70}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
