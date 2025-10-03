"""
Test XBRL dividend parser with real Apple data
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sec_edgar_client import SECAPIClient
from parsers.xbrl_dividend_parser import XBRLDividendParser


def main():
    print("Testing XBRL Parser with Real Apple Data")
    print("="*70)
    
    # Initialize client and parser
    client = SECAPIClient()
    parser = XBRLDividendParser()
    
    # Get Apple's CIK
    apple_cik = '0000320193'
    
    print(f"\n1. Fetching Apple company facts from SEC API...")
    facts = client.get_company_facts(apple_cik)
    
    if not facts:
        print("✗ Failed to fetch company facts")
        return 1
    
    print(f"✓ Retrieved company facts for {facts.get('entityName')}")
    
    # Parse dividends
    print(f"\n2. Parsing dividend data...")
    dividends = parser.parse_company_facts(facts)

    if not dividends:
        print("✗ No dividends found")
        return 1
    
    print(f"✓ Found {len(dividends)} dividends")
    
    # Show summary statistics
    print(f"\n3. Summary:")
    print(f"   Total dividends: {len(dividends)}")
    
    if dividends:
        amounts = [d['amount'] for d in dividends]
        print(f"   Amount range: ${min(amounts):.4f} - ${max(amounts):.4f}")
        
        years = set(d['fiscal_year'] for d in dividends if d['fiscal_year'])
        print(f"   Years covered: {min(years)} - {max(years)}")
    
    # Show most recent 10 dividends
    print(f"\n4. Most Recent 10 Dividends:")
    print(f"   {'Date':<12} {'Amount':<10} {'Fiscal Period':<15} {'Form':<8}")
    print(f"   {'-'*12} {'-'*10} {'-'*15} {'-'*8}")
    
    for div in dividends[-10:]:
        fiscal = f"Q{div['fiscal_quarter']} {div['fiscal_year']}" if div['fiscal_quarter'] else str(div['fiscal_year'])
        print(f"   {div['ex_dividend_date']} ${div['amount']:<9.4f} {fiscal:<15} {div['source_form']:<8}")
    
    print("\n" + "="*70)
    
    return 0


if __name__ == "__main__":
    exit(main())