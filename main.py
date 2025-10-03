"""
Main entry point for EDGAR dividend scraper
Coordinates scraping of different filing types
"""

import sys
import argparse
from datetime import datetime

from db_connection import db
from config import SCRAPING_CONFIG


def main():
    """
    Main entry point - parse arguments and run appropriate scraper
    """
    parser = argparse.ArgumentParser(
        description='Scrape dividend data from SEC EDGAR filings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape 8-K filings for JNJ
  python main.py --filing-type 8-K JNJ
  
  # Scrape 10-K filings for multiple companies
  python main.py --filing-type 10-K JNJ KO PEP
  
  # Scrape both 8-K and 10-K for a date range
  python main.py --filing-type both JNJ --start-year 2020 --end-year 2024
  
  # Scrape with custom date range
  python main.py --filing-type 10-K AAPL --start-year 2015
        """
    )
    
    parser.add_argument(
        'tickers',
        nargs='+',
        help='Stock ticker symbols (e.g., AAPL MSFT JNJ)'
    )
    
    parser.add_argument(
        '--filing-type',
        choices=['8-K', '10-K', 'both'],
        default='both',
        help='Type of filings to scrape (default: both)'
    )
    
    parser.add_argument(
        '--start-year',
        type=int,
        default=SCRAPING_CONFIG['start_year'],
        help=f"Start year (default: {SCRAPING_CONFIG['start_year']})"
    )
    
    parser.add_argument(
        '--end-year',
        type=int,
        default=SCRAPING_CONFIG['end_year'],
        help=f"End year (default: {SCRAPING_CONFIG['end_year']})"
    )
    
    args = parser.parse_args()
    
    # Test database connection
    print("Testing database connection...")
    if not db.test_connection():
        print("✗ Cannot connect to database. Check your .env configuration.")
        return 1
    
    print()
    
    # Import scrapers (done here to avoid circular imports)
    from scrapers.scraper_8k import Scraper8K
    from scrapers.scraper_10k import Scraper10K
    
    # Determine which scrapers to run
    scrapers_to_run = []
    
    if args.filing_type in ['8-K', 'both']:
        scrapers_to_run.append(('8-K', Scraper8K()))
    
    if args.filing_type in ['10-K', 'both']:
        scrapers_to_run.append(('10-K', Scraper10K()))
    
    # Run scrapers
    overall_stats = {
        'companies_processed': 0,
        'total_filings_checked': 0,
        'total_dividends_found': 0,
        'total_dividends_inserted': 0,
        'total_errors': 0
    }
    
    for filing_type, scraper in scrapers_to_run:
        print(f"\n{'='*70}")
        print(f"Running {filing_type} Scraper")
        print(f"{'='*70}\n")
        
        if len(args.tickers) == 1:
            result = scraper.scrape_company(
                args.tickers[0],
                start_year=args.start_year,
                end_year=args.end_year
            )
            
            if result.get('success'):
                overall_stats['companies_processed'] += 1
                overall_stats['total_filings_checked'] += result.get('filings_checked', 0)
                overall_stats['total_dividends_found'] += result.get('dividends_found', 0)
                overall_stats['total_dividends_inserted'] += result.get('dividends_inserted', 0)
            else:
                overall_stats['total_errors'] += 1
        else:
            results = scraper.scrape_multiple_companies(
                args.tickers,
                start_year=args.start_year,
                end_year=args.end_year
            )
            
            stats = results.get('stats', {})
            overall_stats['companies_processed'] += stats.get('companies_processed', 0)
            overall_stats['total_filings_checked'] += stats.get('filings_checked', 0)
            overall_stats['total_dividends_found'] += stats.get('dividends_found', 0)
            overall_stats['total_dividends_inserted'] += stats.get('dividends_inserted', 0)
            overall_stats['total_errors'] += stats.get('errors', 0)
    
    # Print overall summary if multiple scraper types
    if len(scrapers_to_run) > 1:
        print(f"\n{'='*70}")
        print("OVERALL SUMMARY")
        print(f"{'='*70}")
        print(f"Companies processed: {overall_stats['companies_processed']}")
        print(f"Total filings checked: {overall_stats['total_filings_checked']}")
        print(f"Total dividends found: {overall_stats['total_dividends_found']}")
        print(f"Total dividends inserted: {overall_stats['total_dividends_inserted']}")
        print(f"Total errors: {overall_stats['total_errors']}")
        print(f"{'='*70}\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())