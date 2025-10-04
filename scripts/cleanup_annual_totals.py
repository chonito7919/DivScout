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
Cleanup script to identify and remove annual totals that slipped through
the initial filtering during parsing
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_connection import db
import argparse


def find_annual_totals():
    """Find dividends that are likely annual totals"""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT
                    de.dividend_id,
                    c.ticker,
                    de.ex_dividend_date,
                    de.amount,
                    de.confidence,
                    de.period_type,
                    de.period_days,
                    de.confidence_reasons
                FROM dividend_events de
                JOIN companies c ON de.company_id = c.company_id
                WHERE de.review_status = 'pending'
                  AND (
                    -- Annual period duration
                    (de.period_days >= 355 AND de.period_days <= 375)
                    OR
                    -- Period type is annual
                    de.period_type = 'annual'
                  )
                ORDER BY c.ticker, de.ex_dividend_date
            ''')

            return cur.fetchall()


def delete_annual_totals(dry_run=True, auto_confirm=False):
    """Delete identified annual totals"""
    candidates = find_annual_totals()

    if not candidates:
        print("No annual totals found to delete.")
        return 0

    print(f"Found {len(candidates)} potential annual totals:")
    print("="*100)
    print(f"{'Ticker':<8} {'Date':<12} {'Amount':<10} {'Conf':<8} {'Period':<15} {'Days':<6} {'Reasons'}")
    print("-"*100)

    for row in candidates:
        dividend_id, ticker, date, amount, conf, period_type, period_days, reasons = row
        print(f"{ticker:<8} {str(date):<12} ${amount:<9.4f} {conf:.0%}    {period_type or 'N/A':<15} {period_days or 0:<6} {reasons or ''}")

    print("="*100)

    if dry_run:
        print(f"\n*** DRY RUN - Would delete {len(candidates)} dividends ***")
        return len(candidates)

    # Confirm deletion
    if not auto_confirm:
        response = input(f"\nDelete these {len(candidates)} dividends? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return 0

    # Delete the dividends
    deleted = 0
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            for row in candidates:
                dividend_id = row[0]
                cur.execute('''
                    UPDATE dividend_events
                    SET review_status = 'deleted',
                        review_notes = 'Annual total - auto-deleted by cleanup script',
                        reviewed_by = 'system',
                        reviewed_at = CURRENT_TIMESTAMP
                    WHERE dividend_id = %s
                ''', (dividend_id,))
                deleted += 1

    print(f"\n✓ Deleted {deleted} annual totals")
    return deleted


def review_other_flagged():
    """Show other flagged dividends that aren't annual totals"""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT
                    c.ticker,
                    COUNT(*) as count,
                    AVG(de.confidence) as avg_conf,
                    string_agg(DISTINCT de.confidence_reasons, '; ') as reasons
                FROM dividend_events de
                JOIN companies c ON de.company_id = c.company_id
                WHERE de.review_status = 'pending'
                  AND de.needs_review = true
                  AND NOT (de.period_days >= 355 AND de.period_days <= 375)
                  AND NOT (de.period_type = 'annual')
                GROUP BY c.ticker
                ORDER BY count DESC
            ''')

            results = cur.fetchall()

            if not results:
                print("\nNo other flagged dividends found.")
                return

            print(f"\nOther Flagged Dividends (non-annual):")
            print("="*100)
            print(f"{'Ticker':<8} {'Count':<8} {'Avg Conf':<10} {'Reasons'}")
            print("-"*100)

            for row in results:
                ticker, count, avg_conf, reasons = row
                print(f"{ticker:<8} {count:<8} {avg_conf:.0%}     {reasons[:70]}")

            print("="*100)
            print(f"\nTotal: {sum(r[1] for r in results)} dividends from {len(results)} companies")


def main():
    parser = argparse.ArgumentParser(
        description='Cleanup annual totals from dividend data',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without making changes'
    )

    parser.add_argument(
        '--show-other',
        action='store_true',
        help='Show other flagged dividends that are not annual totals'
    )

    parser.add_argument(
        '--yes',
        action='store_true',
        help='Auto-confirm deletion without prompting'
    )

    args = parser.parse_args()

    # Test database connection
    print("Testing database connection...")
    if not db.test_connection():
        print("✗ Cannot connect to database")
        return 1

    print()

    # Delete annual totals
    deleted = delete_annual_totals(dry_run=args.dry_run, auto_confirm=args.yes)

    # Show other flagged items if requested
    if args.show_other:
        review_other_flagged()

    return 0


if __name__ == "__main__":
    sys.exit(main())
