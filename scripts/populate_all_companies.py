#!/usr/bin/env python3
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
Batch script to populate all known companies into the database
Respects SEC rate limits and provides progress tracking
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sec_edgar_client import SECAPIClient
from parsers.xbrl_dividend_parser import XBRLDividendParser
from company_info_fetcher import CompanyInfoFetcher
from db_connection import db
import argparse
import csv
from datetime import datetime


def load_tickers_from_csv():
    """
    Load all tickers from data/companies.csv
    Returns: list of ticker symbols
    """
    csv_path = Path(__file__).parent.parent / 'data' / 'companies.csv'
    tickers = []

    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                tickers.append(row['ticker'].upper())
    except FileNotFoundError:
        print(f"✗ Error: companies.csv not found at {csv_path}")
        print(f"  Create it with format: ticker,cik,company_name")
        return []
    except Exception as e:
        print(f"✗ Error loading companies.csv: {e}")
        return []

    return sorted(tickers)


# All tickers are now loaded from data/companies.csv
# No hardcoded lists needed - just edit the CSV to add new companies


def process_company(ticker, client, parser, info_fetcher, dry_run=False):
    """Process a single company"""
    ticker = ticker.upper()

    print(f"\n{'='*70}")
    print(f"Processing: {ticker}")
    print(f"{'='*70}")

    try:
        # Look up CIK
        company_info = client.lookup_ticker_to_cik(ticker)

        if not company_info:
            return {'ticker': ticker, 'status': 'failed', 'error': 'CIK lookup failed'}

        cik = company_info['cik']
        company_name = company_info['name']

        print(f"  ✓ Found: {company_name}")
        print(f"  ✓ CIK: {cik}")

        # Get sector/industry info
        submissions = client.get_company_submissions(cik)
        sector = None
        industry = None

        if submissions:
            industry = submissions.get('sicDescription')
            sic = submissions.get('sic')

            if sic:
                sic_str = str(sic)
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

        if dry_run:
            print(f"  [DRY RUN] Would create/update company")
            return {'ticker': ticker, 'status': 'dry_run', 'company_name': company_name}

        # Get or create company
        try:
            company_id = db.get_or_create_company(
                ticker=ticker,
                company_name=company_name,
                cik=cik,
                sector=sector,
                industry=industry
            )
            print(f"  ✓ Company ID: {company_id}")
        except Exception as e:
            if 'duplicate key' in str(e) and 'cik' in str(e):
                print(f"  ⊘ CIK already exists (likely alternate ticker)")
                return {'ticker': ticker, 'status': 'duplicate_cik', 'cik': cik}
            raise

        # Fetch company description and website
        print(f"  Fetching company info...")
        company_extra_info = info_fetcher.fetch_all_info(company_name, submissions)
        if company_extra_info['description'] or company_extra_info['website']:
            with db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute('''
                    UPDATE companies
                    SET description = %s,
                        description_source = %s,
                        description_license = %s,
                        website = %s,
                        info_updated_at = %s
                    WHERE company_id = %s
                ''', (
                    company_extra_info['description'],
                    company_extra_info['description_source'],
                    company_extra_info['description_license'],
                    company_extra_info['website'],
                    datetime.now(),
                    company_id
                ))
                conn.commit()
            desc_mark = "✓" if company_extra_info['description'] else "✗"
            web_mark = "✓" if company_extra_info['website'] else "✗"
            print(f"  {desc_mark} Description  {web_mark} Website")

        # Fetch XBRL data
        print(f"  Fetching XBRL data...")
        facts = client.get_company_facts(cik)

        if not facts:
            print(f"  ✗ Could not fetch XBRL data")
            return {'ticker': ticker, 'status': 'no_xbrl', 'company_id': company_id}

        # Parse dividends
        print(f"  Parsing dividends...")
        dividends = parser.parse_company_facts(facts, cik)

        if not dividends:
            print(f"  ⊘ No dividends found")
            return {'ticker': ticker, 'status': 'no_dividends', 'company_id': company_id}

        print(f"  ✓ Found {len(dividends)} dividends")

        # Insert into database
        inserted, skipped, needs_review = db.bulk_insert_dividends(company_id, dividends)

        print(f"  ✓ Inserted: {inserted}")
        print(f"  ⊘ Skipped: {skipped}")
        if needs_review > 0:
            print(f"  ⚠️  Needs review: {needs_review}")

        return {
            'ticker': ticker,
            'status': 'success',
            'company_id': company_id,
            'dividends_found': len(dividends),
            'dividends_inserted': inserted,
            'needs_review': needs_review
        }

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return {'ticker': ticker, 'status': 'error', 'error': str(e)}


def main():
    parser = argparse.ArgumentParser(
        description='Populate all known companies into DivScout database',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of companies to process (for testing)'
    )

    parser.add_argument(
        '--tickers',
        nargs='*',
        help='Specific ticker(s) to process (overrides CSV)'
    )

    parser.add_argument(
        '--skip-existing',
        action='store_true',
        help='Skip companies already in database'
    )

    args = parser.parse_args()

    # Load tickers from CSV or use command-line specified tickers
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
        print(f"Processing {len(tickers)} ticker(s) from command line: {', '.join(tickers)}")
    else:
        tickers = load_tickers_from_csv()
        if not tickers:
            print("✗ No tickers loaded from CSV. Exiting.")
            return
        print(f"Processing {len(tickers)} tickers from data/companies.csv")

    if args.limit:
        tickers = tickers[:args.limit]

    # Test database connection
    print("\nTesting database connection...")
    if not db.test_connection():
        print("✗ Cannot connect to database")
        return 1

    print(f"\nProcessing {len(tickers)} companies...")
    if args.dry_run:
        print("*** DRY RUN MODE - No changes will be made ***\n")

    # Initialize client, parser, and info fetcher
    client = SECAPIClient()
    xbrl_parser = XBRLDividendParser()
    info_fetcher = CompanyInfoFetcher()

    # Process companies
    results = []
    start_time = time.time()

    for i, ticker in enumerate(tickers, 1):
        print(f"\n[{i}/{len(tickers)}]", end=' ')

        result = process_company(ticker, client, xbrl_parser, info_fetcher, args.dry_run)
        results.append(result)

        # Small delay to respect rate limits
        if i < len(tickers):
            time.sleep(0.5)

    # Summary
    elapsed = time.time() - start_time

    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    by_status = {}
    for r in results:
        status = r['status']
        by_status[status] = by_status.get(status, 0) + 1

    print(f"Total companies processed: {len(results)}")
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")

    total_dividends = sum(r.get('dividends_inserted', 0) for r in results)
    total_review = sum(r.get('needs_review', 0) for r in results)

    if not args.dry_run:
        print(f"\nTotal dividends inserted: {total_dividends}")
        print(f"Total flagged for review: {total_review}")

    print(f"\nTime elapsed: {elapsed:.1f}s")
    print(f"API requests: {client.get_stats()['requests_made']}")
    print(f"{'='*70}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
