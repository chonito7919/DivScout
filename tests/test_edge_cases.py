"""
Test XBRL dividend parser with edge case companies
- Companies with dividend cuts
- Companies that started/stopped paying dividends
- Companies with special dividends
- REITs with monthly payments
- Foreign companies with ADRs
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sec_edgar_client import SECAPIClient
from parsers.xbrl_dividend_parser import XBRLDividendParser
from datetime import datetime
import time


def test_company(client, parser, ticker, cik, start_year=2020):
    """Test dividend extraction for one company"""
    print(f"\n## {ticker} - Testing")
    
    facts = client.get_company_facts(cik)
    
    if not facts:
        print(f"ERROR: Could not fetch data for {ticker}")
        return None
    
    all_dividends = parser.parse_company_facts(facts)
    
    if not all_dividends:
        print(f"WARNING: No dividends found for {ticker}")
        return None
    
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
    # Edge case companies to test
    companies = [
        # Dividend cuts/suspensions
        ('GE', '0000040545'),      # GE - cut dividend drastically
        ('F', '0000037996'),       # Ford - suspended then resumed
        ('DIS', '0001744489'),     # Disney - suspended COVID, resumed
        
        # High-yield / monthly payers
        ('STAG', '0001447169'),    # STAG Industrial (monthly REIT)
        ('GLAD', '0001410636'),    # Gladstone Capital (monthly BDC)
        
        # Stable aristocrats
        ('MMM', '0000066740'),     # 3M - dividend aristocrat
        ('CL', '0000021665'),      # Colgate - very stable
        ('ED', '0001047862'),      # Con Edison - utility
        
        # Recent IPOs / growth
        ('ABNB', '0001559720'),    # Airbnb - may not have dividends
        ('UBER', '0001543151'),    # Uber - no dividends expected
    ]
    
    print("# XBRL Dividend Parser - Edge Case Test")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing last 5 years (2020-2025)")
    print(f"Edge Cases: dividend cuts, suspensions, REITs, non-payers")
    print("\n" + "="*70)
    
    client = SECAPIClient()
    parser = XBRLDividendParser()
    
    results = []
    
    for ticker, cik in companies:
        result = test_company(client, parser, ticker, cik, start_year=2020)
        if result:
            results.append(result)
        time.sleep(0.2)
    
    # Summary
    print("\n\n# Summary Table")
    print("\n| Ticker | Company | Total | Recent (2020+) | Notes |")
    print("|--------|---------|-------|----------------|-------|")
    
    for r in results:
        recent = r['recent_dividends']
        note = ""
        if recent == 0:
            note = "No dividends"
        elif recent < 10:
            note = "Few dividends"
        elif recent > 40:
            note = "Monthly payer"
        
        print(f"| {r['ticker']:<6} | {r['company_name'][:25]:<25} | {r['total_dividends']:>5} | {recent:>14} | {note:<20} |")
    
    # Detailed results
    print("\n\n# Detailed Results")
    
    for r in results:
        print(f"\n## {r['ticker']} - {r['company_name']}")
        
        if r['recent_dividends'] == 0:
            print("No dividends paid in last 5 years")
            continue
        
        divs = r['dividends']
        amounts = [d['amount'] for d in divs]
        
        print(f"\n**Statistics:**")
        print(f"- Total recent dividends: {r['recent_dividends']}")
        print(f"- Amount range: ${min(amounts):.4f} - ${max(amounts):.4f}")
        print(f"- Average: ${sum(amounts)/len(amounts):.4f}")
        
        # Check for patterns
        if len(divs) >= 2:
            first_amount = divs[0]['amount']
            last_amount = divs[-1]['amount']
            change_pct = ((last_amount - first_amount) / first_amount) * 100
            
            if change_pct < -20:
                print(f"- **⚠ Dividend CUT: {change_pct:.1f}%**")
            elif change_pct > 20:
                print(f"- **✓ Dividend GROWTH: {change_pct:.1f}%**")
        
        # Check for gaps (suspension)
        if len(divs) >= 2:
            dates = [d['ex_dividend_date'] for d in divs]
            dates.sort()
            
            max_gap = 0
            for i in range(1, len(dates)):
                gap_days = (dates[i] - dates[i-1]).days
                if gap_days > max_gap:
                    max_gap = gap_days
            
            if max_gap > 180:
                print(f"- **⚠ Longest gap between dividends: {max_gap} days (possible suspension)**")
        
        # Show last 10
        print(f"\n**Last 10 dividends:**")
        print("\n| Date | Amount | Fiscal Period | Form |")
        print("|------|--------|---------------|------|")
        
        for div in divs[-10:]:
            fiscal = f"Q{div['fiscal_quarter']} {div['fiscal_year']}" if div['fiscal_quarter'] else str(div['fiscal_year'])
            print(f"| {div['ex_dividend_date']} | ${div['amount']:.4f} | {fiscal} | {div['source_form']} |")
    
    # Summary stats
    print(f"\n\n# Test Statistics")
    print(f"- Companies tested: {len(results)}")
    print(f"- Companies with dividends: {sum(1 for r in results if r['recent_dividends'] > 0)}")
    print(f"- Companies without dividends: {sum(1 for r in results if r['recent_dividends'] == 0)}")
    print(f"- Total API requests: {client.get_stats()['requests_made']}")
    
    print("\n" + "="*70)
    print("\n**Test complete. Copy to share with other LLMs.**")


if __name__ == "__main__":
    main()