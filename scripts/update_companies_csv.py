#!/usr/bin/env python3
"""
Auto-fill missing data in companies.csv

Scans data/companies.csv and fills in any missing fields:
- If ticker provided: looks up CIK and company name from SEC
- If CIK provided: looks up company name (ticker must be manual)
- Skips rows with all fields already filled

Usage:
    python scripts/update_companies_csv.py
"""

import sys
import csv
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sec_edgar_client import SECAPIClient
import time


def load_csv():
    """Load current CSV file"""
    csv_path = Path(__file__).parent.parent / 'data' / 'companies.csv'
    rows = []

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    return rows, csv_path


def save_csv(rows, csv_path):
    """Save updated CSV file"""
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['ticker', 'cik', 'company_name'])
        writer.writeheader()
        writer.writerows(rows)


def fill_missing_data(rows, client):
    """Fill in missing ticker, CIK, or company name"""
    updated_count = 0

    for i, row in enumerate(rows, 1):
        ticker = row.get('ticker', '').strip().upper()
        cik = row.get('cik', '').strip()
        name = row.get('company_name', '').strip()

        needs_update = False

        # Case 1: Have ticker, need CIK/name
        if ticker and not cik:
            print(f"[{i}] {ticker}: Looking up CIK and name...")
            info = client.lookup_ticker_to_cik(ticker)
            if info:
                row['cik'] = info['cik']
                row['company_name'] = info['name']
                print(f"     ✓ Found: {info['name']} (CIK: {info['cik']})")
                needs_update = True
            else:
                print(f"     ✗ Could not find {ticker}")
            time.sleep(0.5)

        # Case 2: Have CIK, need ticker/name
        elif cik and not ticker:
            print(f"[{i}] CIK {cik}: Looking up ticker and name...")
            submissions = client.get_company_submissions(cik)
            if submissions:
                row['ticker'] = submissions.get('tickers', [''])[0].upper() if submissions.get('tickers') else ''
                row['company_name'] = submissions.get('name', '')
                print(f"     ✓ Found: {row['company_name']} ({row['ticker']})")
                needs_update = True
            else:
                print(f"     ✗ Could not find CIK {cik}")
            time.sleep(0.5)

        # Case 3: Have both ticker and CIK, just need name
        elif ticker and cik and not name:
            print(f"[{i}] {ticker}: Looking up company name...")
            submissions = client.get_company_submissions(cik)
            if submissions:
                row['company_name'] = submissions.get('name', '')
                print(f"     ✓ Found: {row['company_name']}")
                needs_update = True
            else:
                print(f"     ✗ Could not find company name")
            time.sleep(0.5)

        if needs_update:
            updated_count += 1

    return updated_count


def main():
    client = SECAPIClient()

    print("Loading companies.csv...")
    rows, csv_path = load_csv()
    print(f"Found {len(rows)} companies\n")

    # Check if company_name column exists
    if 'company_name' not in rows[0]:
        print("Adding company_name column...")
        for row in rows:
            row['company_name'] = ''

    updated_count = fill_missing_data(rows, client)

    if updated_count > 0:
        print(f"\nSaving {updated_count} updates to {csv_path}...")
        save_csv(rows, csv_path)
        print("✓ Done!")
    else:
        print("\n✓ No updates needed - all data is complete")


if __name__ == '__main__':
    main()
