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
Smart auto-approval script for flagged dividends

Automatically approves dividends that are flagged but safe:
- Semi-annual dividends (180-day periods)
- Amounts within 3x median for the company
- Reasonable amounts ($0.01 - $50.00)

Usage:
    # Preview what would be approved
    python scripts/auto_approve_safe_dividends.py --dry-run

    # Actually approve them
    python scripts/auto_approve_safe_dividends.py --approve
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_connection import db


def is_safe_to_approve(dividend):
    """
    Determine if a flagged dividend is safe to auto-approve

    Criteria:
    - Semi-annual period (confidence penalty only for period)
    - Amount within 3x median (not extreme outliers)
    - Reasonable amount range ($0.01 - $50.00)
    """
    reasons = dividend.get('confidence_reasons', '')
    amount = dividend.get('amount', 0)

    # Safe pattern 1: Semi-annual period only
    if 'Semi-annual period' in reasons:
        # Check if this is the ONLY reason or combined with minor issues
        if 'Above median (2.' in reasons or 'Above median (3.' in reasons:
            # Semi-annual + slightly above median = safe
            return True
        elif reasons == 'Semi-annual period':
            # Only semi-annual flag = safe
            return True

    # Safe pattern 2: Reasonable amounts flagged for annual period
    if 'Annual period duration' in reasons and amount > 0.01 and amount < 50.0:
        # Not an extreme outlier, just flagged for period
        if 'Above median (2.' in reasons or 'Above median (3.' in reasons:
            return True

    # Safe pattern 3: Very minor outliers (2.x - 3.x median)
    if ('Above median (2.' in reasons or 'Above median (3.' in reasons) and amount > 0.01 and amount < 50.0:
        # Not extreme, just slightly above average
        if 'High vs median' not in reasons:  # Exclude "High vs median (5x+)"
            return True

    return False


def main():
    parser = argparse.ArgumentParser(
        description='Auto-approve safe flagged dividends',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be approved without making changes'
    )

    parser.add_argument(
        '--approve',
        action='store_true',
        help='Actually approve the safe dividends'
    )

    args = parser.parse_args()

    if not args.dry_run and not args.approve:
        print("Error: Must specify either --dry-run or --approve")
        return 1

    # Get all flagged dividends
    print("Fetching flagged dividends...")
    flagged = db.get_dividends_for_review(min_confidence=0.8)

    print(f"\nTotal flagged dividends: {len(flagged)}")

    # Filter for safe ones
    safe_to_approve = []
    keep_flagged = []

    for div in flagged:
        if is_safe_to_approve(div):
            safe_to_approve.append(div)
        else:
            keep_flagged.append(div)

    print(f"Safe to auto-approve: {len(safe_to_approve)}")
    print(f"Keep flagged for manual review: {len(keep_flagged)}")

    # Show breakdown
    print("\n" + "="*70)
    print("SAFE TO APPROVE (by ticker):")
    print("="*70)

    by_ticker = {}
    for div in safe_to_approve:
        ticker = div['ticker']
        if ticker not in by_ticker:
            by_ticker[ticker] = []
        by_ticker[ticker].append(div)

    for ticker in sorted(by_ticker.keys()):
        count = len(by_ticker[ticker])
        reasons = by_ticker[ticker][0].get('confidence_reasons', 'Unknown')
        print(f"  {ticker}: {count} dividends - ({reasons})")

    print("\n" + "="*70)
    print("KEEP FLAGGED (extreme outliers/special dividends):")
    print("="*70)

    by_ticker_keep = {}
    for div in keep_flagged:
        ticker = div['ticker']
        if ticker not in by_ticker_keep:
            by_ticker_keep[ticker] = []
        by_ticker_keep[ticker].append(div)

    for ticker in sorted(by_ticker_keep.keys()):
        count = len(by_ticker_keep[ticker])
        reasons = by_ticker_keep[ticker][0].get('confidence_reasons', 'Unknown')
        print(f"  {ticker}: {count} dividends - ({reasons})")

    # Execute approval if requested
    if args.approve:
        print("\n" + "="*70)
        print("APPROVING SAFE DIVIDENDS...")
        print("="*70)

        approved_count = 0
        for div in safe_to_approve:
            dividend_id = div['dividend_id']
            ticker = div['ticker']

            try:
                db.mark_dividend_reviewed(
                    dividend_id=dividend_id,
                    action='approved',
                    notes='Auto-approved: Safe semi-annual/minor variance',
                    reviewer='auto_approval_script'
                )
                approved_count += 1
                print(f"  ✓ Approved {ticker} dividend (ID: {dividend_id})")
            except Exception as e:
                print(f"  ✗ Error approving {ticker}: {e}")

        print(f"\n✓ Successfully approved {approved_count} dividends")
        print(f"⚠️  {len(keep_flagged)} dividends still flagged for manual review")

    elif args.dry_run:
        print("\n*** DRY RUN - No changes made ***")
        print(f"Would approve {len(safe_to_approve)} dividends")
        print(f"Would keep {len(keep_flagged)} flagged for manual review")

    return 0


if __name__ == "__main__":
    sys.exit(main())
