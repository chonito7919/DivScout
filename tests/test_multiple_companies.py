"""
Test XBRL dividend parser across multiple companies
Outputs results in markdown format for easy review
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sec_edgar_client import SECAPIClient
from parsers.xbrl_dividend_parser import XBRLDividendParser
from datetime import datetime, timedelta
import time


def test_company(client, parser, ticker, cik, start_year=2020):
    """Test dividend extraction for one company"""
    print(f"\n## {ticker} - Testing")
    
    # Fetch data
    facts = client.get_company_facts(cik)
    
    if not facts:
        print(f"ERROR: Could not fetch data for {ticker}")
        return None
    
    # Parse dividends
    all_dividends = parser.parse_company_facts(facts)
    
    if not all_dividends:
        print(f"WARNING: No dividends found for {ticker}")
        return None
    
    # Filter to last 5 years
    cutoff_date = datetime(start_year, 1, 1).date()
    recent_dividends = [d for d in all_dividends if d['ex_dividend_date'] >= cutoff_date]
    
    return {
        'ticker': ticker,
        'company_name': facts.get('entityName'),
        'total_dividends': len(all_dividends),
        'recent_dividends': len(recent_dividends),
        'dividends': recent_dividends
    }


def main():
    # Companies to test (ticker, CIK)
    companies = [
        ('AAPL', '0000320193'),  # Apple
        ('MSFT', '0000789019'),  # Microsoft
        ('JNJ', '0000200406'),   # Johnson & Johnson
        ('KO', '0000021344'),    # Coca-Cola
        ('PG', '0000080424'),    # Procter & Gamble
        ('JPM', '0000019617'),   # JPMorgan Chase
        ('O', '0000726728'),     # Realty Income (monthly dividends)
        ('T', '0000732717'),     # AT&T
        ('VZ', '0000732712'),    # Verizon
        ('XOM', '0000034088'),   # Exxon Mobil
    ]
    
    print("# XBRL Dividend Parser - Multi-Company Test")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing last 5 years of dividend data (2020-2025)")
    print(f"Companies: {len(companies)}")
    print("\n" + "="*70)
    
    client = SECAPIClient()
    parser = XBRLDividendParser()
    
    results = []
    
    for ticker, cik in companies:
        result = test_company(client, parser, ticker, cik, start_year=2020)
        if result:
            results.append(result)
        time.sleep(0.2)  # Rate limiting
    
    # Summary table
    print("\n\n# Summary Table")
    print("\n| Ticker | Company | Total Dividends | Recent (2020+) |")
    print("|--------|---------|-----------------|----------------|")
    
    for r in results:
        print(f"| {r['ticker']:<6} | {r['company_name'][:30]:<30} | {r['total_dividends']:>15} | {r['recent_dividends']:>14} |")
    
    # Detailed results
    print("\n\n# Detailed Results (Last 5 Years)")
    
    for r in results:
        print(f"\n## {r['ticker']} - {r['company_name']}")
        print(f"Recent dividends: {r['recent_dividends']}")
        
        if r['recent_dividends'] > 0:
            divs = r['dividends']
            
            # Stats
            amounts = [d['amount'] for d in divs]
            print(f"\n**Statistics:**")
            print(f"- Amount range: ${min(amounts):.4f} - ${max(amounts):.4f}")
            print(f"- Average: ${sum(amounts)/len(amounts):.4f}")
            
            # Show last 10
            print(f"\n**Last 10 dividends:**")
            print("\n| Date | Amount | Fiscal Period | Form |")
            print("|------|--------|---------------|------|")
            
            for div in divs[-10:]:
                fiscal = f"Q{div['fiscal_quarter']} {div['fiscal_year']}" if div['fiscal_quarter'] else str(div['fiscal_year'])
                print(f"| {div['ex_dividend_date']} | ${div['amount']:.4f} | {fiscal} | {div['source_form']} |")
    
    # API usage stats
    print(f"\n\n# Test Statistics")
    print(f"- Companies tested: {len(results)}")
    print(f"- Total API requests: {client.get_stats()['requests_made']}")
    print(f"- Success rate: {len(results)}/{len(companies)} ({len(results)/len(companies)*100:.1f}%)")
    
    print("\n" + "="*70)
    print("\n**Test complete. You can copy this entire output to share with other LLMs.**")


if __name__ == "__main__":
    main()