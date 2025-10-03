"""
Scraper for 8-K filings
Extracts dividend information from 8-K Item 8.01 announcements
"""

import sys

from datetime import datetime
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from scrapers.base_scraper import BaseScraper
from parsers.filing_8k import Filing8KParser
from config import SCRAPING_CONFIG


class Scraper8K(BaseScraper):
    """
    Scraper specifically for 8-K filings
    """
    
    def __init__(self):
        super().__init__(filing_type='8-K')
        self.parser = Filing8KParser()
    
    def get_filings(self, ticker, start_year=None, end_year=None):
        """
        Get 8-K filings for a company
        """
        if not start_year:
            start_year = SCRAPING_CONFIG['start_year']
        if not end_year:
            end_year = SCRAPING_CONFIG['end_year']
        
        start_date = datetime(start_year, 1, 1)
        end_date = datetime(end_year, 12, 31)
        
        print(f"\n2. Fetching 8-K filings from {start_year} to {end_year}...")
        
        try:
            filings = self.api.get_company_filings(
                ticker=ticker,
                filing_type='8-K',
                start_date=start_date,
                end_date=end_date
            )
            return filings
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return None
    
    def process_filing(self, filing, company_id):
        """
        Process a single 8-K filing
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
        
        # Parse for dividend data
        dividend_data = self.parser.parse(content, filing['filing_date'])
        
        if not dividend_data:
            print("⊘ Mentioned but couldn't parse")
            return result
        
        print(f"✓ Found dividend: ${dividend_data['amount']}")
        result['found'] = True
        result['count'] = 1
        
        # Insert into database
        dividend_id = self.db.insert_dividend(
            company_id=company_id,
            dividend_data=dividend_data
        )
        
        if dividend_id:
            result['inserted'] = 1
            
            # Record data source
            self.db.insert_data_source(
                company_id=company_id,
                source_type='edgar_filing',
                source_url=filing['filing_url'],
                filing_type='8-K',
                filing_date=filing['filing_date'],
                accession_number=filing['accession_number']
            )
            print(f"    → Inserted as dividend_id: {dividend_id}")
        else:
            print(f"    → Duplicate, skipped")
        
        return result


if __name__ == "__main__":
    # Test the 8-K scraper
    print("Testing 8-K scraper...")
    
    scraper = Scraper8K()
    result = scraper.scrape_company('JNJ', start_year=2024, end_year=2025)
    
    if result['success']:
        print(f"\n✓ Test successful!")
        print(f"  Dividends found: {result['dividends_found']}")
    else:
        print(f"\n✗ Test failed: {result.get('error')}")