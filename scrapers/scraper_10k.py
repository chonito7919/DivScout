"""
Scraper for 10-K filings
Extracts dividend information from 10-K Item 5 (Market for Registrant's Common Equity)
"""

import sys

from datetime import datetime
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from scrapers.base_scraper import BaseScraper
from parsers.filing_10k import Filing10KParser
from config import SCRAPING_CONFIG


class Scraper10K(BaseScraper):
    """
    Scraper specifically for 10-K filings
    """
    
    def __init__(self):
        super().__init__(filing_type='10-K')
        self.parser = Filing10KParser()
    
    def get_filings(self, ticker, start_year=None, end_year=None):
        """
        Get 10-K filings for a company
        10-Ks are annual, so we'll get fewer than 8-Ks
        """
        if not start_year:
            start_year = SCRAPING_CONFIG['start_year']
        if not end_year:
            end_year = SCRAPING_CONFIG['end_year']
        
        start_date = datetime(start_year, 1, 1)
        end_date = datetime(end_year, 12, 31)
        
        print(f"\n2. Fetching 10-K filings from {start_year} to {end_year}...")
        
        try:
            filings = self.api.get_company_filings(
                ticker=ticker,
                filing_type='10-K',
                start_date=start_date,
                end_date=end_date
            )
            return filings
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return None
    
    def process_filing(self, filing, company_id):
        """
        Process a single 10-K filing
        Returns: dict with 'found', 'count', 'inserted'
        """
        result = {
            'found': False,
            'count': 0,
            'inserted': 0
        }
        
        # Download filing content
        content = self.api.get_filing_content(filing)
        
        if not content:
            print("✗ Failed to download")
            return result
        
        # Check if it mentions dividends
        if not self.parser.is_dividend_related(content):
            print("⊘ No dividend mention")
            return result
        
        # Parse for dividend data (returns list of dividends)
        dividends = self.parser.parse(content, filing['filing_date'])
        
        if not dividends or len(dividends) == 0:
            print("⊘ Mentioned but couldn't parse")
            return result
        
        print(f"✓ Found {len(dividends)} dividend(s)")
        result['found'] = True
        result['count'] = len(dividends)
        
        # Insert each dividend into database
        for dividend_data in dividends:
            # 10-K dividends often don't have exact dates, use filing date
            if not dividend_data.get('declaration_date'):
                dividend_data['declaration_date'] = filing['filing_date']
            if not dividend_data.get('ex_dividend_date'):
                dividend_data['ex_dividend_date'] = filing['filing_date']
            
            dividend_id = self.db.insert_dividend(
                company_id=company_id,
                dividend_data=dividend_data
            )
            
            if dividend_id:
                result['inserted'] += 1
        
        # Record data source once for the filing
        if result['inserted'] > 0:
            self.db.insert_data_source(
                company_id=company_id,
                source_type='edgar_filing',
                source_url=filing['filing_url'],
                filing_type='10-K',
                filing_date=filing['filing_date'],
                accession_number=filing['accession_number'],
                notes=f"Extracted {result['inserted']} dividend records"
            )
            print(f"    → Inserted {result['inserted']} dividend(s)")
        else:
            print(f"    → All duplicates, skipped")
        
        return result


if __name__ == "__main__":
    # Test the 10-K scraper
    print("Testing 10-K scraper...")
    
    scraper = Scraper10K()
    result = scraper.scrape_company('JNJ', start_year=2023, end_year=2024)
    
    if result['success']:
        print(f"\n✓ Test successful!")
        print(f"  Dividends found: {result['dividends_found']}")
    else:
        print(f"\n✗ Test failed: {result.get('error')}")