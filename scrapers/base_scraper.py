"""
Base scraper class with common functionality
All specific filing type scrapers inherit from this
"""

import time
from datetime import datetime

from db_connection import db
from sec_edgar_client import EDGARToolsClient


class BaseScraper:
    """
    Base class for all filing scrapers
    Contains common methods used across different filing types
    """
    
    def __init__(self, filing_type):
        self.filing_type = filing_type
        self.db = db
        self.api = EDGARToolsClient()
        self.stats = {
            'companies_processed': 0,
            'filings_checked': 0,
            'dividends_found': 0,
            'dividends_inserted': 0,
            'errors': 0
        }
    
    def get_company_info(self, ticker):
        """
        Get company information from SEC
        Returns: dict with company_id, cik, name or None
        """
        try:
            print(f"1. Looking up company info for {ticker}...")
            company_info = self.api.get_company_info(ticker)
            
            if not company_info:
                error_msg = f"Could not find company info for ticker {ticker}"
                print(f"  ✗ {error_msg}")
                self.db.log_collection_attempt(
                    company_id=None,
                    ticker=ticker,
                    data_type=self.filing_type,
                    status='failed',
                    error_message=error_msg
                )
                self.stats['errors'] += 1
                return None
            
            cik = company_info['cik']
            company_name = company_info['name']
            
            print(f"  ✓ Found: {company_name}")
            print(f"  ✓ CIK: {cik}")
            
            # Get or create company record
            company_id = self.db.get_or_create_company(
                ticker=ticker,
                company_name=company_name,
                cik=cik
            )
            print(f"  ✓ Company ID: {company_id}")
            
            return {
                'company_id': company_id,
                'cik': cik,
                'name': company_name,
                'ticker': ticker
            }
            
        except Exception as e:
            error_msg = f"Error setting up company: {str(e)}"
            print(f"  ✗ {error_msg}")
            self.stats['errors'] += 1
            return None
    
    def get_filings(self, ticker, start_year, end_year):
        """
        Get filings for a company
        Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement get_filings()")
    
    def process_filing(self, filing, company_id):
        """
        Process a single filing
        Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement process_filing()")
    
    def scrape_company(self, ticker, start_year=None, end_year=None):
        """
        Scrape dividend data for a single company
        This method orchestrates the scraping process
        """
        start_time = time.time()
        ticker = ticker.upper()
        
        print(f"\n{'='*60}")
        print(f"Processing: {ticker}")
        print(f"{'='*60}")
        
        # Get company info
        company = self.get_company_info(ticker)
        if not company:
            return {'success': False, 'error': 'Company lookup failed'}
        
        # Get filings
        try:
            filings = self.get_filings(
                ticker=ticker,
                start_year=start_year,
                end_year=end_year
            )
            
            if filings is None:
                return {'success': False, 'error': 'Failed to fetch filings'}
            
            print(f"  ✓ Found {len(filings)} {self.filing_type} filings")
            self.stats['filings_checked'] += len(filings)
            
        except Exception as e:
            error_msg = f"Error fetching filings: {str(e)}"
            print(f"  ✗ {error_msg}")
            self.stats['errors'] += 1
            return {'success': False, 'error': error_msg}
        
        # Process each filing
        print(f"\n3. Processing filings for dividend information...")
        dividends_found = 0
        dividends_inserted = 0
        
        for i, filing in enumerate(filings, 1):
            print(f"  [{i}/{len(filings)}] {filing['filing_date']} - ", end='')
            
            try:
                result = self.process_filing(filing, company['company_id'])
                
                if result['found']:
                    dividends_found += result['count']
                    dividends_inserted += result['inserted']
                    self.stats['dividends_found'] += result['count']
                    self.stats['dividends_inserted'] += result['inserted']
                
            except Exception as e:
                print(f"✗ Error: {str(e)}")
                self.stats['errors'] += 1
                continue
        
        # Calculate processing time
        processing_time = int(time.time() - start_time)
        
        # Log collection attempt
        status = 'success' if dividends_found > 0 else 'not_available'
        self.db.log_collection_attempt(
            company_id=company['company_id'],
            ticker=ticker,
            data_type=self.filing_type,
            status=status,
            records_inserted=dividends_inserted,
            processing_time=processing_time
        )
        
        # Summary
        print(f"\n{'='*60}")
        print(f"Summary for {ticker} ({self.filing_type}):")
        print(f"  Filings checked: {len(filings)}")
        print(f"  Dividends found: {dividends_found}")
        print(f"  Dividends inserted: {dividends_inserted}")
        print(f"  Processing time: {processing_time}s")
        print(f"{'='*60}")
        
        self.stats['companies_processed'] += 1
        
        return {
            'success': True,
            'ticker': ticker,
            'company_id': company['company_id'],
            'filings_checked': len(filings),
            'dividends_found': dividends_found,
            'dividends_inserted': dividends_inserted,
            'processing_time': processing_time
        }
    
    def scrape_multiple_companies(self, tickers, start_year=None, end_year=None):
        """
        Scrape dividend data for multiple companies
        """
        print(f"\n{'#'*60}")
        print(f"Starting batch scrape for {len(tickers)} companies")
        print(f"Filing type: {self.filing_type}")
        print(f"{'#'*60}\n")
        
        overall_start = time.time()
        results = []
        
        for ticker in tickers:
            result = self.scrape_company(ticker, start_year, end_year)
            results.append(result)
            
            # Small delay between companies
            time.sleep(1)
        
        overall_time = int(time.time() - overall_start)
        
        # Print overall summary
        print(f"\n{'#'*60}")
        print(f"BATCH SCRAPING COMPLETE ({self.filing_type})")
        print(f"{'#'*60}")
        print(f"Companies processed: {self.stats['companies_processed']}")
        print(f"Total filings checked: {self.stats['filings_checked']}")
        print(f"Dividends found: {self.stats['dividends_found']}")
        print(f"Dividends inserted: {self.stats['dividends_inserted']}")
        print(f"Errors: {self.stats['errors']}")
        print(f"Total time: {overall_time}s")
        print(f"API requests made: {self.api.get_stats()['requests_made']}")
        print(f"{'#'*60}\n")
        
        return {
            'results': results,
            'stats': self.stats,
            'total_time': overall_time
        }
    
    def get_stats(self):
        """Return current scraping statistics"""
        return self.stats