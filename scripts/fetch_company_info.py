#!/usr/bin/env python3
"""
Fetch Wikipedia descriptions and websites for all companies

This script:
1. Gets all companies from database
2. Fetches Wikipedia description (first paragraph)
3. Fetches website from SEC submissions
4. Updates database with proper attribution
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_connection import db
from company_info_fetcher import CompanyInfoFetcher
from sec_edgar_client import SECAPIClient
import time
from datetime import datetime


def update_company_info(company_id, info):
    """Update company info in database"""
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
            info['description'],
            info['description_source'],
            info['description_license'],
            info['website'],
            datetime.now(),
            company_id
        ))
        conn.commit()


def main():
    fetcher = CompanyInfoFetcher()
    sec_client = SECAPIClient()

    # Get all companies
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute('''
            SELECT company_id, ticker, company_name, cik
            FROM companies
            WHERE is_active = TRUE
            ORDER BY ticker
        ''')
        companies = cur.fetchall()

    print(f"Fetching info for {len(companies)} companies...\n")

    success_count = 0
    partial_count = 0
    failed_count = 0

    for i, (company_id, ticker, company_name, cik) in enumerate(companies, 1):
        print(f"[{i}/{len(companies)}] {ticker} - {company_name}")

        # Get SEC submissions for website
        submissions = sec_client.get_company_submissions(cik) if cik else None

        # Fetch Wikipedia + website
        info = fetcher.fetch_all_info(company_name, submissions)

        # Update database
        update_company_info(company_id, info)

        # Report results
        if info['description'] and info['website']:
            print(f"  ✓ Description + Website")
            success_count += 1
        elif info['description'] or info['website']:
            desc_status = "✓" if info['description'] else "✗"
            web_status = "✓" if info['website'] else "✗"
            print(f"  {desc_status} Description  {web_status} Website")
            partial_count += 1
        else:
            print(f"  ✗ No info found")
            failed_count += 1

        # Rate limiting
        time.sleep(0.5)

    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Total: {len(companies)}")
    print(f"  ✓ Full info (desc + website): {success_count}")
    print(f"  ~ Partial info: {partial_count}")
    print(f"  ✗ No info: {failed_count}")


if __name__ == '__main__':
    main()
