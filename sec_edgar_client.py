# Copyright 2025 DivScout Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
SEC EDGAR API client for XBRL data
Uses official SEC JSON APIs - no HTML scraping
"""

import requests
import time
import json
from datetime import datetime
from pathlib import Path
from config import SEC_CONFIG, COLLECTION_CONFIG


class SECAPIClient:
    """
    Client for SEC's official XBRL JSON APIs
    Handles rate limiting and proper headers
    """
    
    def __init__(self):
        self.user_agent = SEC_CONFIG['user_agent']
        
        if 'example.com' in self.user_agent:
            raise ValueError(
                "Please set SEC_USER_AGENT in .env with your real name and email."
            )
        
        self.headers = {
            'User-Agent': self.user_agent,
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'data.sec.gov'
        }
        
        self.rate_limit_requests = SEC_CONFIG['rate_limit_requests']
        self.rate_limit_period = SEC_CONFIG['rate_limit_period']
        self.request_times = []
        self.request_count = 0
    
    def _rate_limit(self):
        """
        Enforce SEC rate limiting: 10 requests per second
        """
        now = time.time()
        
        # Remove requests older than rate_limit_period
        self.request_times = [
            t for t in self.request_times 
            if now - t < self.rate_limit_period
        ]
        
        # If at limit, wait
        if len(self.request_times) >= self.rate_limit_requests:
            sleep_time = self.rate_limit_period - (now - self.request_times[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        self.request_times.append(time.time())
        self.request_count += 1
    
    def get_company_tickers(self):
        """
        Get CIK to ticker mapping from SEC
        Returns: dict mapping CIK to company info
        """
        self._rate_limit()
        
        url = SEC_CONFIG['ticker_mapping']
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            # Response format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
            data = response.json()
            
            # Reformat to CIK-keyed dict
            ticker_map = {}
            for entry in data.values():
                cik = str(entry['cik_str']).zfill(10)
                ticker_map[cik] = {
                    'ticker': entry['ticker'],
                    'name': entry['title']
                }
            
            return ticker_map
            
        except Exception as e:
            print(f"✗ Error fetching ticker mapping: {e}")
            return {}
        
    def lookup_ticker_to_cik(self, ticker):
        """
        Look up CIK for a ticker using submissions API
        This works even if ticker mapping file is unavailable
    
        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
    
        Returns: dict with CIK and company info, or None
        """
        ticker = ticker.upper()
    
        # Known CIKs for dividend-paying stocks
        # Organized by sector for easier maintenance
        known_ciks = {
            # Technology
            'AAPL': '0000320193',  # Apple Inc.
            'MSFT': '0000789019',  # Microsoft Corporation
            'GOOGL': '0001652044', # Alphabet Inc.
            'GOOG': '0001652044',  # Alphabet Inc. (Class C)
            'META': '0001326801',  # Meta Platforms
            'NVDA': '0001045810',  # NVIDIA Corporation
            'AVGO': '0001730168',  # Broadcom Inc.
            'CSCO': '0000858877',  # Cisco Systems
            'ORCL': '0001341439',  # Oracle Corporation
            'IBM': '0000051143',   # IBM
            'INTC': '0000050863',  # Intel Corporation
            'TXN': '0000097476',   # Texas Instruments
            'QCOM': '0000804328',  # Qualcomm
            'ADI': '0000006281',   # Analog Devices

            # Healthcare
            'JNJ': '0000200406',   # Johnson & Johnson
            'UNH': '0000731766',   # UnitedHealth Group
            'LLY': '0000059478',   # Eli Lilly
            'ABBV': '0001551152',  # AbbVie
            'MRK': '0000310158',   # Merck & Co
            'TMO': '0000097745',   # Thermo Fisher Scientific
            'ABT': '0000001800',   # Abbott Laboratories
            'PFE': '0000078003',   # Pfizer
            'AMGN': '0000318154',  # Amgen
            'CVS': '0000064803',   # CVS Health

            # Financials
            'JPM': '0000019617',   # JPMorgan Chase
            'BAC': '0000070858',   # Bank of America
            'WFC': '0000072971',   # Wells Fargo
            'MS': '0000895421',    # Morgan Stanley
            'GS': '0000886982',    # Goldman Sachs
            'BLK': '0001364742',   # BlackRock
            'C': '0000831001',     # Citigroup
            'USB': '0000036104',   # U.S. Bancorp
            'PNC': '0000713676',   # PNC Financial
            'TFC': '0000092230',   # Truist Financial
            'BK': '0001390777',    # Bank of New York Mellon
            'AXP': '0000004962',   # American Express
            'V': '0001403161',     # Visa
            'MA': '0001141391',    # Mastercard
            'SPGI': '0000064040',  # S&P Global

            # Consumer Staples
            'KO': '0000021344',    # Coca-Cola
            'PEP': '0000077476',   # PepsiCo
            'PG': '0000080424',    # Procter & Gamble
            'WMT': '0000104169',   # Walmart
            'COST': '0000909832',  # Costco
            'PM': '0001413329',    # Philip Morris
            'MO': '0000764180',    # Altria Group
            'CL': '0000021665',    # Colgate-Palmolive
            'KMB': '0000055785',   # Kimberly-Clark
            'GIS': '0000040704',   # General Mills
            'K': '0000055067',     # Kellogg
            'HSY': '0000047111',   # Hershey
            'MDLZ': '0001103982',  # Mondelez
            'KHC': '0001637459',   # Kraft Heinz

            # Consumer Discretionary
            'AMZN': '0001018724',  # Amazon
            'TSLA': '0001318605',  # Tesla
            'HD': '0000354950',    # Home Depot
            'MCD': '0000063908',   # McDonald's
            'NKE': '0000320187',   # Nike
            'SBUX': '0000829224',  # Starbucks
            'TGT': '0000027419',   # Target
            'LOW': '0000060667',   # Lowe's
            'F': '0000037996',     # Ford
            'GM': '0001467858',    # General Motors

            # Energy
            'XOM': '0000034088',   # Exxon Mobil
            'CVX': '0000093410',   # Chevron
            'COP': '0001163165',   # ConocoPhillips
            'SLB': '0000087347',   # Schlumberger
            'EOG': '0001101215',   # EOG Resources
            'PSX': '0001534701',   # Phillips 66
            'VLO': '0001035002',   # Valero Energy
            'OXY': '0000797468',   # Occidental Petroleum
            'KMI': '0001506307',   # Kinder Morgan
            'WMB': '0000107263',   # Williams Companies

            # Industrials
            'BA': '0000012927',    # Boeing
            'CAT': '0000018230',   # Caterpillar
            'GE': '0000040545',    # General Electric
            'LMT': '0000936468',   # Lockheed Martin
            'RTX': '0000101829',   # Raytheon Technologies
            'UNP': '0000100885',   # Union Pacific
            'HON': '0000773840',   # Honeywell
            'UPS': '0001090727',   # United Parcel Service
            'DE': '0000315189',    # Deere & Company
            'MMM': '0000066740',   # 3M Company

            # Utilities
            'NEE': '0000753308',   # NextEra Energy
            'DUK': '0001326160',   # Duke Energy
            'SO': '0000092122',    # Southern Company
            'D': '0000715957',     # Dominion Energy
            'AEP': '0000004904',   # American Electric Power
            'EXC': '0001109357',   # Exelon
            'SRE': '0000086521',   # Sempra Energy
            'XEL': '0000072903',   # Xcel Energy
            'PCG': '0001004980',   # PG&E Corporation

            # Real Estate / REITs
            'O': '0000726728',     # Realty Income
            'AMT': '0001053507',   # American Tower
            'PLD': '0001045609',   # Prologis
            'CCI': '0001051470',   # Crown Castle
            'EQIX': '0001101239',  # Equinix
            'PSA': '0001393311',   # Public Storage
            'WELL': '0000957494',  # Welltower
            'DLR': '0001297996',   # Digital Realty
            'SPG': '0001063761',   # Simon Property Group
            'AVB': '0000915912',   # AvalonBay Communities

            # Materials
            'LIN': '0001707925',   # Linde
            'APD': '0000002969',   # Air Products & Chemicals
            'SHW': '0000089800',   # Sherwin-Williams
            'FCX': '0000831259',   # Freeport-McMoRan
            'NEM': '0001164727',   # Newmont Corporation
            'ECL': '0000031462',   # Ecolab

            # Telecommunications
            'T': '0000732717',     # AT&T
            'VZ': '0000732712',    # Verizon
            'TMUS': '0001283699',  # T-Mobile
        }
    
        if ticker in known_ciks:
            cik = known_ciks[ticker]
            # Verify by getting submissions
            submissions = self.get_company_submissions(cik)
            if submissions:
                return {
                    'cik': cik,
                    'ticker': ticker,
                    'name': submissions.get('name', 'Unknown')
                }
    
        print(f"  ✗ Ticker {ticker} not in known list. Please use CIK directly.")
        return None
    
    def get_company_facts(self, cik):
        """
        Get all XBRL facts for a company
        This returns ALL financial data including dividends
        
        Args:
            cik: 10-digit CIK string or int
        
        Returns: dict with XBRL facts or None
        """
        self._rate_limit()
        
        # Ensure CIK is 10 digits
        cik = str(cik).zfill(10)
        
        url = f"{SEC_CONFIG['api_base']}/companyfacts/CIK{cik}.json"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"  ✗ No XBRL data found for CIK {cik}")
            else:
                print(f"  ✗ HTTP error {e.response.status_code} for CIK {cik}")
            return None
        except Exception as e:
            print(f"  ✗ Error fetching company facts: {e}")
            return None
    
    def get_company_submissions(self, cik):
        """
        Get filing history and metadata for a company
        
        Args:
            cik: 10-digit CIK string or int
        
        Returns: dict with submission history or None
        """
        self._rate_limit()
        
        cik = str(cik).zfill(10)
        
        url = f"{SEC_CONFIG['submissions_api']}/CIK{cik}.json"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            print(f"  ✗ Error fetching submissions: {e}")
            return None
        
    def get_company_fiscal_info(self, cik):
        """
        Get fiscal year end info from submissions
        """
        submissions = self.get_company_submissions(cik)
        if not submissions:
            return None
    
        # Extract fiscal year end from recent filings
        recent = submissions.get('filings', {}).get('recent', {})
        if recent and 'fiscalYearEnd' in recent:
            # Some companies report fiscal year end
            fye = recent.get('fiscalYearEnd', [])[0] if recent.get('fiscalYearEnd') else None
            return {'fiscal_year_end': fye}
    
        return None
    
    def download_bulk_companyfacts(self, output_path=None):
        """
        Download the complete companyfacts.zip bulk file
        Contains ALL company XBRL data (large file ~3-4GB)
        
        Args:
            output_path: Where to save the file
        
        Returns: Path to downloaded file or None
        """
        if output_path is None:
            output_path = Path(COLLECTION_CONFIG['download_dir']) / 'companyfacts.zip'
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Downloading companyfacts.zip (this may take several minutes)...")
        
        url = SEC_CONFIG['bulk_companyfacts']
        
        try:
            # Don't rate limit bulk downloads (different endpoint)
            response = requests.get(url, headers=self.headers, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(output_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        print(f"\r  Progress: {pct:.1f}%", end='')
            
            print(f"\n✓ Downloaded to {output_path}")
            return output_path
            
        except Exception as e:
            print(f"\n✗ Error downloading bulk file: {e}")
            return None
    
    def download_bulk_submissions(self, output_path=None):
        """
        Download the complete submissions.zip bulk file
        Contains filing history for all companies
        
        Args:
            output_path: Where to save the file
        
        Returns: Path to downloaded file or None
        """
        if output_path is None:
            output_path = Path(COLLECTION_CONFIG['download_dir']) / 'submissions.zip'
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Downloading submissions.zip...")
        
        url = SEC_CONFIG['bulk_submissions']
        
        try:
            response = requests.get(url, headers=self.headers, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"✓ Downloaded to {output_path}")
            return output_path
            
        except Exception as e:
            print(f"✗ Error downloading bulk file: {e}")
            return None
    
    def get_stats(self):
        """Return API usage statistics"""
        return {
            'requests_made': self.request_count,
            'rate_limit': f"{self.rate_limit_requests} per {self.rate_limit_period}s"
        }


if __name__ == "__main__":
    # Test the client
    print("Testing SEC API client...")
    print("="*70)
    
    client = SECAPIClient()
    
    # Test 1: Try ticker mapping (may fail during shutdown)
    print("\n1. Testing ticker mapping...")
    tickers = client.get_company_tickers()
    
    if len(tickers) > 0:
        print(f"✓ Loaded {len(tickers)} companies")
        # Find Apple's CIK from mapping
        apple_cik = None
        for cik, info in tickers.items():
            if info['ticker'] == 'AAPL':
                apple_cik = cik
                break
    else:
        print("✗ Ticker mapping unavailable (SEC may be down)")
        print("  Using fallback lookup method...")
        info = client.lookup_ticker_to_cik('AAPL')
        if info:
            apple_cik = info['cik']
            print(f"✓ Found Apple via fallback: CIK {apple_cik}")
    
    if not apple_cik:
        print("✗ Could not find Apple")
        exit(1)
    
    if not apple_cik:
        print("✗ Could not find Apple")
        exit(1)
    
    # Test 2: Get company facts
    print(f"\n2. Testing company facts API for Apple (CIK {apple_cik})...")
    facts = client.get_company_facts(apple_cik)
    
    if facts:
        print(f"✓ Retrieved company facts")
        print(f"  Entity name: {facts.get('entityName', 'N/A')}")
        print(f"  CIK: {facts.get('cik', 'N/A')}")
        
        # Check for dividend data
        us_gaap = facts.get('facts', {}).get('us-gaap', {})
        
        dividend_tags = [
            'CommonStockDividendsPerShareDeclared',
            'CommonStockDividendsPerShareCashPaid',
            'DividendsCommonStock'
        ]
        
        print(f"\n  Checking for dividend tags:")
        for tag in dividend_tags:
            if tag in us_gaap:
                units = us_gaap[tag].get('units', {})
                # Try different unit types
                data_points = 0
                for unit_type in ['USD/shares', 'USD', 'pure']:
                    if unit_type in units:
                        data_points = len(units[unit_type])
                        break
                
                if data_points > 0:
                    print(f"    ✓ {tag}: {data_points} data points")
                else:
                    print(f"    ✓ {tag}: found but no data")
            else:
                print(f"    ✗ {tag}: not found")
    else:
        print("✗ Could not retrieve company facts")
    
    # Test 3: Get submissions
    print(f"\n3. Testing submissions API for Apple...")
    submissions = client.get_company_submissions(apple_cik)
    
    if submissions:
        print(f"✓ Retrieved submissions")
        recent = submissions.get('filings', {}).get('recent', {})
        if recent:
            filing_count = len(recent.get('accessionNumber', []))
            print(f"  Recent filings: {filing_count}")
            
            # Show most recent 8-K
            forms = recent.get('form', [])
            dates = recent.get('filingDate', [])
            for i, form in enumerate(forms):
                if form == '8-K':
                    print(f"  Most recent 8-K: {dates[i]}")
                    break
    else:
        print("✗ Could not retrieve submissions")
    
    print(f"\n{client.get_stats()}")
    print("="*70)