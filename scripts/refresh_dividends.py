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
Automated dividend refresh script

Refreshes dividend data for all companies in the database.
Only inserts NEW dividends (skips duplicates automatically).

Usage:
    # Refresh all companies
    python scripts/refresh_dividends.py

    # Refresh specific companies
    python scripts/refresh_dividends.py --tickers AAPL MSFT JNJ

    # Dry run to see what would be updated
    python scripts/refresh_dividends.py --dry-run

    # Scheduled automation (e.g., via cron)
    0 2 * * 0  cd /path/to/DivScout && .venv/bin/python scripts/refresh_dividends.py
    # Runs every Sunday at 2 AM
"""

import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_connection import db
from sec_edgar_client import SECAPIClient
from parsers.xbrl_dividend_parser import XBRLDividendParser


def get_companies_to_refresh(tickers=None):
    """
    Get list of companies to refresh from database

    Args:
        tickers: Optional list of specific tickers to refresh

    Returns:
        List of dicts with company info
    """
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            if tickers:
                # Refresh specific tickers
                placeholders = ','.join(['%s'] * len(tickers))
                cur.execute(f'''
                    SELECT company_id, ticker, cik, company_name
                    FROM companies
                    WHERE ticker IN ({placeholders})
                    AND is_active = TRUE
                    ORDER BY ticker
                ''', tuple(tickers))
            else:
                # Refresh all active companies
                cur.execute('''
                    SELECT company_id, ticker, cik, company_name
                    FROM companies
                    WHERE is_active = TRUE
                    ORDER BY ticker
                ''')

            companies = []
            for row in cur.fetchall():
                companies.append({
                    'company_id': row[0],
                    'ticker': row[1],
                    'cik': row[2],
                    'company_name': row[3]
                })

            return companies


def refresh_company(company, client, parser, dry_run=False):
    """
    Refresh dividend data for a single company

    Args:
        company: Dict with company info
        client: SECAPIClient instance
        parser: XBRLDividendParser instance
        dry_run: If True, don't insert data

    Returns:
        Dict with results
    """
    ticker = company['ticker']
    cik = company['cik']
    company_id = company['company_id']

    print(f"\n[{ticker}] Refreshing...")

    try:
        # Fetch latest XBRL data
        facts = client.get_company_facts(cik)

        if not facts:
            print(f"  ⊘ No XBRL data available")
            return {'ticker': ticker, 'status': 'no_data', 'new_dividends': 0}

        # Parse dividends
        dividends = parser.parse_company_facts(facts, cik)

        if not dividends:
            print(f"  ⊘ No dividends found")
            return {'ticker': ticker, 'status': 'no_dividends', 'new_dividends': 0}

        print(f"  ✓ Found {len(dividends)} total dividends from XBRL")

        if dry_run:
            print(f"  [DRY RUN] Would check for new dividends")
            return {'ticker': ticker, 'status': 'dry_run', 'new_dividends': len(dividends)}

        # Insert dividends (bulk_insert automatically skips duplicates)
        inserted, skipped, needs_review = db.bulk_insert_dividends(company_id, dividends)

        print(f"  ✓ Inserted {inserted} new dividends")
        if skipped > 0:
            print(f"  ⊘ Skipped {skipped} existing dividends")
        if needs_review > 0:
            print(f"  ⚠️  {needs_review} flagged for review")

        # Log the refresh
        db.log_collection_attempt(
            company_id=company_id,
            ticker=ticker,
            data_type='xbrl',
            status='success',
            records_inserted=inserted,
            processing_time=0,
            records_flagged=needs_review
        )

        return {
            'ticker': ticker,
            'status': 'success',
            'new_dividends': inserted,
            'skipped': skipped,
            'needs_review': needs_review
        }

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return {'ticker': ticker, 'status': 'error', 'error': str(e), 'new_dividends': 0}


def main():
    parser = argparse.ArgumentParser(
        description='Refresh dividend data for companies in database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Refresh all companies
  python scripts/refresh_dividends.py

  # Refresh specific tickers
  python scripts/refresh_dividends.py --tickers AAPL MSFT

  # Dry run
  python scripts/refresh_dividends.py --dry-run

  # For automation (crontab):
  0 2 * * 0  cd /path/to/DivScout && .venv/bin/python scripts/refresh_dividends.py
        """
    )

    parser.add_argument(
        '--tickers',
        nargs='+',
        help='Specific tickers to refresh (default: all)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    args = parser.parse_args()

    # Test database connection
    print("Testing database connection...")
    if not db.test_connection():
        print("✗ Cannot connect to database")
        return 1

    print()

    # Get companies to refresh
    companies = get_companies_to_refresh(args.tickers)

    if not companies:
        print("No companies found to refresh")
        return 1

    print(f"Refreshing {len(companies)} companies...")
    if args.dry_run:
        print("*** DRY RUN MODE - No changes will be made ***\n")

    # Initialize client and parser
    client = SECAPIClient()
    xbrl_parser = XBRLDividendParser()

    # Refresh companies
    start_time = time.time()
    results = []

    for i, company in enumerate(companies, 1):
        print(f"[{i}/{len(companies)}]", end=' ')
        result = refresh_company(company, client, xbrl_parser, args.dry_run)
        results.append(result)

        # Small delay to respect rate limits
        if i < len(companies):
            time.sleep(0.5)

    elapsed = time.time() - start_time

    # Summary
    print(f"\n{'='*70}")
    print("REFRESH SUMMARY")
    print(f"{'='*70}")

    total_new = sum(r.get('new_dividends', 0) for r in results)
    total_review = sum(r.get('needs_review', 0) for r in results)

    by_status = {}
    for r in results:
        status = r['status']
        by_status[status] = by_status.get(status, 0) + 1

    print(f"Companies processed: {len(results)}")
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")

    if not args.dry_run:
        print(f"\nNew dividends inserted: {total_new}")
        print(f"Flagged for review: {total_review}")

    print(f"\nTime elapsed: {elapsed:.1f}s")
    print(f"API requests: {client.get_stats()['requests_made']}")
    print(f"{'='*70}\n")

    # Show companies with new dividends
    if total_new > 0 and not args.dry_run:
        print("Companies with new dividends:")
        for r in results:
            if r.get('new_dividends', 0) > 0:
                print(f"  {r['ticker']}: {r['new_dividends']} new")

    return 0


if __name__ == "__main__":
    sys.exit(main())
