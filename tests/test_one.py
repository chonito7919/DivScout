"""
Test enhanced XBRL parser with problematic companies
Focus on companies that showed issues in previous tests
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sec_edgar_client import SECAPIClient
from parsers.xbrl_dividend_parser import XBRLDividendParser
from datetime import datetime
import time


def test_company_detailed(client, parser, ticker, cik, company_name=None):
    """Test with detailed output including confidence scores"""
    
    print(f"\n{'='*70}")
    print(f"Testing {ticker} - {company_name if company_name else 'Unknown'}")
    print(f"CIK: {cik}")
    print('='*70)
    
    # Fetch data
    facts = client.get_company_facts(cik)
    
    if not facts:
        print(f"ERROR: Could not fetch data for {ticker}")
        return None
    
    # Parse with enhanced parser
    dividends = parser.parse_company_facts(facts, cik)
    
    if not dividends:
        print(f"No dividends found for {ticker}")
        return None
    
    # Filter to recent years for analysis
    cutoff = datetime(2018, 1, 1).date()
    recent = [d for d in dividends if d['ex_dividend_date'] >= cutoff]
    
    # Get statistics
    stats = parser.get_summary_statistics(recent)
    
    print(f"\n## Summary Statistics (2018-2025):")
    print(f"  Total dividends: {stats['count']}")
    print(f"  Amount range: ${stats['amount_min']:.4f} - ${stats['amount_max']:.4f}")
    print(f"  Mean: ${stats['amount_mean']:.4f}, Median: ${stats['amount_median']:.4f}")
    print(f"  Pattern: {stats.get('pattern', 'Unknown')}")
    print(f"  Average confidence: {stats.get('confidence_mean', 0):.2%}")
    print(f"  Needs review: {stats.get('needs_review_count', 0)} entries")
    
    # Show low confidence entries
    low_confidence = [d for d in recent if d.get('confidence', 1) < 0.8]
    if low_confidence:
        print(f"\n## ⚠️  Low Confidence Entries ({len(low_confidence)}):")
        for div in low_confidence[:5]:  # Show max 5
            print(f"\n  Date: {div['ex_dividend_date']}, Amount: ${div['amount']:.4f}")
            print(f"  Confidence: {div['confidence']:.2%}")
            print(f"  Reasons: {', '.join(div.get('confidence_reasons', []))}")
            print(f"  Source: {div.get('source_form')} ({div.get('fiscal_period', 'No period')})")
    
    # Check for potential annual totals
    high_amounts = [d for d in recent if d['amount'] > stats['amount_median'] * 3]
    if high_amounts:
        print(f"\n## 🔍 Potential Annual Totals ({len(high_amounts)}):")
        for div in high_amounts:
            ratio = div['amount'] / stats['amount_median']
            print(f"  {div['ex_dividend_date']}: ${div['amount']:.4f} ({ratio:.1f}x median)")
    
    # Show most recent dividends
    print(f"\n## Recent Dividends (last 8):")
    print(f"  {'Date':<12} {'Amount':<10} {'Confidence':<12} {'Review?':<8}")
    print(f"  {'-'*12} {'-'*10} {'-'*12} {'-'*8}")
    
    for div in recent[-8:]:
        review = "YES" if div.get('needs_review') else ""
        print(f"  {div['ex_dividend_date']} ${div['amount']:<9.4f} {div['confidence']:<11.2%} {review}")
    
    return {
        'ticker': ticker,
        'company': facts.get('entityName'),
        'total': len(dividends),
        'recent': len(recent),
        'stats': stats,
        'low_confidence_count': len(low_confidence),
        'potential_annuals': len(high_amounts)
    }


def main():
    # Test problematic companies identified in your review
    test_cases = [
        # Known problematic companies
        ('TGT', '0000027419', 'Target'),  # Has fiscal year-end annual totals
        ('WMT', '0000104169', 'Walmart'),  # Incorrectly showing as "declining"
        ('CAT', '0000018230', 'Caterpillar'),  # High legitimate dividends
        ('MO', '0000764180', 'Altria'),  # Has annual totals
        ('GS', '0000886982', 'Goldman Sachs'),  # High variance
        
        # Good baseline companies for comparison
        ('JNJ', '0000200406', 'Johnson & Johnson'),  # Should be clean
        ('AAPL', '0000320193', 'Apple'),  # Should be clean
        
        # Monthly payer
        ('O', '0000726728', 'Realty Income'),  # Monthly dividends
    ]
    
    print("# Enhanced XBRL Parser Test - Problematic Companies")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nFocus: Testing enhanced parser with confidence scoring")
    print("Goal: Identify which dividends need manual review")
    
    client = SECAPIClient()
    parser = XBRLDividendParser()
    
    results = []
    
    for ticker, cik, name in test_cases:
        result = test_company_detailed(client, parser, ticker, cik, name)
        if result:
            results.append(result)
        time.sleep(0.2)
    
    # Summary report
    print("\n\n" + "="*70)
    print("FINAL SUMMARY REPORT")
    print("="*70)
    
    print("\n## Companies Tested:")
    print(f"  {'Ticker':<8} {'Company':<30} {'Total':<7} {'Review':<7} {'Status'}")
    print(f"  {'-'*8} {'-'*30} {'-'*7} {'-'*7} {'-'*20}")
    
    for r in results:
        status = "✅ Clean" if r['low_confidence_count'] == 0 else f"⚠️  {r['low_confidence_count']} issues"
        name_short = r['company'][:28] + ".." if len(r['company']) > 30 else r['company']
        print(f"  {r['ticker']:<8} {name_short:<30} {r['recent']:<7} {r['low_confidence_count']:<7} {status}")
    
    # Calculate overall accuracy
    total_dividends = sum(r['recent'] for r in results)
    total_needs_review = sum(r['low_confidence_count'] for r in results)
    
    print(f"\n## Overall Statistics:")
    print(f"  Total dividends extracted: {total_dividends}")
    print(f"  Dividends needing review: {total_needs_review}")
    print(f"  Automatic accuracy: {((total_dividends - total_needs_review) / total_dividends * 100):.1f}%")
    print(f"  Manual review needed: {(total_needs_review / total_dividends * 100):.1f}%")
    
    print(f"\n## Recommendations:")
    if total_needs_review > 0:
        print(f"  1. Review {total_needs_review} flagged entries")
        print(f"  2. Most issues are potential annual totals or cumulative amounts")
        print(f"  3. Use admin tools to bulk review entries with confidence < 0.8")
    else:
        print(f"  ✅ All dividends have high confidence!")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()