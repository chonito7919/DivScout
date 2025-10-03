"""
Test diverse US companies across different sectors and patterns
- Dividend aristocrats (25+ years of increases)
- Cyclical companies (variable dividends)
- High-yield companies
- Low-yield growth companies
- Financial sector
- Utilities (stable)
- Energy sector (volatile)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sec_edgar_client import SECAPIClient
from parsers.xbrl_dividend_parser import XBRLDividendParser
from datetime import datetime
import time


def test_company(client, parser, ticker, cik, start_year=2018):
    """Test dividend extraction - 7 year window for more data"""
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


def analyze_dividend_pattern(dividends):
    """Analyze dividend payment pattern"""
    if not dividends or len(dividends) < 4:
        return "Insufficient data"
    
    amounts = [d['amount'] for d in dividends[-12:]]  # Last 12 payments
    
    # Check consistency
    if max(amounts) == min(amounts):
        return "Perfectly stable"
    
    # Check for growth
    first_half = sum(amounts[:len(amounts)//2]) / (len(amounts)//2)
    second_half = sum(amounts[len(amounts)//2:]) / (len(amounts) - len(amounts)//2)
    
    if second_half > first_half * 1.05:
        return "Growing"
    elif second_half < first_half * 0.95:
        return "Declining"
    else:
        return "Stable"


def main():
    # Diverse US companies
    companies = [
        # Dividend Aristocrats
        ('WMT', '0000104169'),    # Walmart - retail
        ('TGT', '0000027419'),    # Target
        ('LOW', '0000060667'),    # Lowe's
        ('CAT', '0000018230'),    # Caterpillar - industrial
        ('EMR', '0000032604'),    # Emerson Electric
        
        # Financials
        ('BAC', '0000070858'),    # Bank of America
        ('WFC', '0000072971'),    # Wells Fargo
        ('C', '0000831001'),      # Citigroup
        ('GS', '0000886982'),     # Goldman Sachs
        
        # Energy (volatile)
        ('CVX', '0000093410'),    # Chevron
        ('COP', '0001163165'),    # ConocoPhillips
        ('OXY', '0000797468'),    # Occidental Petroleum
        
        # High-yield
        ('MO', '0000764180'),     # Altria - tobacco
        ('BTI', '0001138118'),    # British American Tobacco ADR
        ('PM', '0001413329'),     # Philip Morris
        
        # Tech (low/no yield)
        ('GOOGL', '0001652044'),  # Alphabet
        ('META', '0001326801'),   # Meta
        ('NFLX', '0001065280'),   # Netflix
    ]
    
    print("# XBRL Dividend Parser - Diverse US Market Test")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing last 7 years (2018-2025)")
    print(f"Focus: Aristocrats, Financials, Energy, High-yield, Tech")
    print("\n" + "="*70)
    
    client = SECAPIClient()
    parser = XBRLDividendParser()
    
    results = []
    
    for ticker, cik in companies:
        result = test_company(client, parser, ticker, cik, start_year=2018)
        if result:
            results.append(result)
        time.sleep(0.2)
    
    # Summary
    print("\n\n# Summary Table")
    print("\n| Ticker | Company | Total | Recent (2018+) | Avg Amount | Pattern |")
    print("|--------|---------|-------|----------------|------------|---------|")
    
    for r in results:
        if r['recent_dividends'] > 0:
            avg_amt = sum(d['amount'] for d in r['dividends']) / len(r['dividends'])
            pattern = analyze_dividend_pattern(r['dividends'])
        else:
            avg_amt = 0
            pattern = "No dividends"
        
        print(f"| {r['ticker']:<6} | {r['company_name'][:22]:<22} | {r['total_dividends']:>5} | {r['recent_dividends']:>14} | ${avg_amt:>9.4f} | {pattern:<15} |")
    
    # Detailed results by category
    print("\n\n# Detailed Results by Category")
    
    categories = {
        'Dividend Aristocrats': ['WMT', 'TGT', 'LOW', 'CAT', 'EMR'],
        'Financial Sector': ['BAC', 'WFC', 'C', 'GS'],
        'Energy Sector': ['CVX', 'COP', 'OXY'],
        'High-Yield': ['MO', 'BTI', 'PM'],
        'Tech (Low/No Yield)': ['GOOGL', 'META', 'NFLX']
    }
    
    for category, tickers in categories.items():
        print(f"\n## {category}")
        
        for r in results:
            if r['ticker'] not in tickers:
                continue
            
            print(f"\n### {r['ticker']} - {r['company_name']}")
            
            if r['recent_dividends'] == 0:
                print("No dividends in test period")
                continue
            
            divs = r['dividends']
            amounts = [d['amount'] for d in divs]
            
            print(f"- Recent dividends: {r['recent_dividends']}")
            print(f"- Amount range: ${min(amounts):.4f} - ${max(amounts):.4f}")
            print(f"- Average: ${sum(amounts)/len(amounts):.4f}")
            print(f"- Pattern: {analyze_dividend_pattern(divs)}")
            
            # Check for anomalies
            if len(amounts) >= 4:
                # Calculate std deviation
                mean = sum(amounts) / len(amounts)
                variance = sum((x - mean) ** 2 for x in amounts) / len(amounts)
                std_dev = variance ** 0.5
                
                if std_dev / mean > 0.3:  # High variability
                    print(f"- **⚠ High variability detected (CV: {(std_dev/mean)*100:.1f}%)**")
            
            # Show last 5 only (condensed)
            print(f"\n**Last 5 dividends:**")
            for div in divs[-5:]:
                fiscal = f"Q{div['fiscal_quarter']} {div['fiscal_year']}" if div['fiscal_quarter'] else str(div['fiscal_year'])
                print(f"- {div['ex_dividend_date']}: ${div['amount']:.4f} ({fiscal})")
    
    # Summary stats
    print(f"\n\n# Test Statistics")
    print(f"- Companies tested: {len(results)}")
    print(f"- Companies with dividends: {sum(1 for r in results if r['recent_dividends'] > 0)}")
    print(f"- Companies without dividends: {sum(1 for r in results if r['recent_dividends'] == 0)}")
    print(f"- Total API requests: {client.get_stats()['requests_made']}")
    
    # Data quality checks
    print(f"\n## Data Quality Checks")
    total_divs = sum(r['recent_dividends'] for r in results)
    print(f"- Total dividends extracted: {total_divs}")
    print(f"- Average per company: {total_divs/len(results):.1f}")
    
    # Check for potential issues
    issues = []
    for r in results:
        if r['recent_dividends'] > 0:
            amounts = [d['amount'] for d in r['dividends']]
            if max(amounts) > 5.0:
                issues.append(f"{r['ticker']}: Unusually high dividend (${max(amounts):.2f})")
            if min(amounts) < 0.05:
                issues.append(f"{r['ticker']}: Very low dividend (${min(amounts):.4f})")
    
    if issues:
        print(f"\n**Potential Issues Found:**")
        for issue in issues:
            print(f"- {issue}")
    else:
        print(f"\n**✓ No data quality issues detected**")
    
    print("\n" + "="*70)
    print("\n**Test complete.**")


if __name__ == "__main__":
    main()