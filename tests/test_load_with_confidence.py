"""
Test loading dividend data with confidence scoring
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sec_edgar_client import SECAPIClient
from parsers.xbrl_dividend_parser import XBRLDividendParser
from db_connection import DatabaseConnection
from datetime import datetime
import time


def test_load_company(ticker, cik):
    """Load one company with confidence scoring"""
    
    print(f"\n{'='*70}")
    print(f"Testing: {ticker} (CIK: {cik})")
    print('='*70)
    
    # Initialize
    client = SECAPIClient()
    parser = XBRLDividendParser()
    db = DatabaseConnection()
    
    start_time = time.time()
    
    # Step 1: Fetch XBRL data
    print(f"\n1. Fetching XBRL data...")
    facts = client.get_company_facts(cik)
    
    if not facts:
        print(f"   ERROR: Could not fetch data")
        return False
    
    company_name = facts.get('entityName', ticker)
    print(f"   Company: {company_name}")
    
    # Step 2: Parse dividends with confidence scoring
    print(f"\n2. Parsing dividends...")
    dividends = parser.parse_company_facts(facts, cik)
    
    if not dividends:
        print(f"   No dividends found")
        return False
    
    print(f"   Found {len(dividends)} dividends")
    
    # Show statistics
    stats = parser.get_summary_statistics(dividends)
    print(f"\n   Statistics:")
    print(f"   - Amount range: ${stats['amount_min']:.4f} - ${stats['amount_max']:.4f}")
    print(f"   - Average: ${stats['amount_mean']:.4f}")
    print(f"   - Pattern: {stats['pattern']}")
    print(f"   - Needs review: {stats['needs_review_count']} ({stats['needs_review_count']/len(dividends)*100:.1f}%)")
    print(f"   - Avg confidence: {stats['confidence_mean']:.2%}")
    
    # Step 3: Get or create company in database
    print(f"\n3. Database operations...")
    company_id = db.get_or_create_company(ticker, company_name, cik)
    print(f"   Company ID: {company_id}")
    
    # Step 4: Insert dividends
    print(f"\n4. Inserting dividends...")
    inserted, skipped, flagged = db.bulk_insert_dividends(company_id, dividends)
    
    elapsed = time.time() - start_time
    
    print(f"\n   Results:")
    print(f"   - Inserted: {inserted}")
    print(f"   - Skipped (duplicates): {skipped}")
    print(f"   - Flagged for review: {flagged}")
    print(f"   - Processing time: {elapsed:.2f}s")
    
    # Step 5: Log the collection
    db.log_collection_attempt(
        company_id=company_id,
        ticker=ticker,
        data_type='XBRL_dividends',
        status='success',
        source_url=f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json',
        records_inserted=inserted,
        processing_time=elapsed,
        records_flagged=flagged
    )
    
    # Step 6: Show what needs review
    if flagged > 0:
        print(f"\n5. Dividends needing review:")
        review_list = db.get_dividends_for_review(company_id=company_id)
        
        for div in review_list[:5]:  # Show first 5
            print(f"\n   ${div['amount']:.4f} on {div['ex_dividend_date']}")
            print(f"   - Confidence: {div['confidence']:.2%}")
            print(f"   - Reasons: {div['confidence_reasons']}")
    
    return True


def main():
    print("="*70)
    print("XBRL Data Loading Test with Confidence Scoring")
    print("="*70)
    
    # Test with 3 companies: clean, problematic, and high-dividend
    test_companies = [
        ('AAPL', '0000320193'),  # Apple - should be very clean
        ('JNJ', '0000200406'),   # J&J - stable, clean
        ('TGT', '0000027419'),   # Target - has known issues with annual totals
    ]
    
    db = DatabaseConnection()
    
    # Test connection first
    print("\nTesting database connection...")
    if not db.test_connection():
        print("Database connection failed. Exiting.")
        return
    
    # Load each company
    results = []
    for ticker, cik in test_companies:
        success = test_load_company(ticker, cik)
        results.append((ticker, success))
        time.sleep(0.3)  # Rate limiting
    
    # Summary
    print(f"\n\n{'='*70}")
    print("SUMMARY")
    print('='*70)
    
    for ticker, success in results:
        status = "SUCCESS" if success else "FAILED"
        print(f"  {ticker}: {status}")
    
    # Show overall statistics
    print(f"\n\nCompany Statistics:")
    stats = db.get_company_dividend_stats()
    
    for stat in stats:
        print(f"\n  {stat['ticker']} - {stat['company_name']}")
        print(f"    Total dividends: {stat['total_dividends']}")
        print(f"    Needs review: {stat['needs_review_count']}")
        print(f"    Avg confidence: {stat['avg_confidence']:.2%}")
        print(f"    Amount range: ${stat['min_amount']:.4f} - ${stat['max_amount']:.4f}")
    
    print("\n" + "="*70)
    print("Test complete!")


if __name__ == "__main__":
    main()