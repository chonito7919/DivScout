#!/usr/bin/env python3
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
8-K Filing Enhancer - PROOF OF CONCEPT
Extracts declaration, record, and payment dates from 8-K filings
to enhance existing XBRL dividend data.

IMPORTANT: This is additive only - never modifies XBRL amounts or ex-dividend dates.
"""

import re
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Filing8KEnhancer:
    """
    Enhances existing dividend records with dates from 8-K filings.
    XBRL data remains the source of truth for amounts and ex-dividend dates.
    """

    def __init__(self, sec_client):
        """
        Args:
            sec_client: Instance of SECAPIClient for rate-limited requests
        """
        self.client = sec_client

        # Common date formats in 8-K filings
        self.date_patterns = [
            # "January 15, 2024" or "January 15th, 2024"
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})',
            # "01/15/2024" or "1/15/24"
            r'(\d{1,2})/(\d{1,2})/(\d{2,4})',
            # "2024-01-15"
            r'(\d{4})-(\d{2})-(\d{2})',
        ]

        # Keywords that indicate date type
        self.declaration_keywords = ['declared', 'board of directors', 'announced', 'board declared']
        self.record_keywords = ['record date', 'shareholders of record', 'holder of record']
        self.payment_keywords = ['payable', 'payment date', 'will be paid', 'paid on']
        self.ex_dividend_keywords = ['ex-dividend date', 'ex dividend']

    def find_8k_filings(self, cik: str, start_year: int = 2020) -> List[Dict]:
        """
        Find 8-K filings for a company that might contain dividend announcements.

        Args:
            cik: Company CIK
            start_year: Only get filings from this year forward

        Returns:
            List of dicts with filing metadata
        """
        submissions = self.client.get_company_submissions(cik)
        if not submissions:
            return []

        recent = submissions.get('filings', {}).get('recent', {})
        forms = recent.get('form', [])
        dates = recent.get('filingDate', [])
        accessions = recent.get('accessionNumber', [])
        primary_docs = recent.get('primaryDocument', [])

        # Filter for 8-K filings from start_year onward
        filings = []
        for i, form in enumerate(forms):
            if form == '8-K':
                filing_date = dates[i]
                year = int(filing_date.split('-')[0])

                if year >= start_year:
                    filings.append({
                        'accession': accessions[i],
                        'filing_date': filing_date,
                        'form': form,
                        'primary_document': primary_docs[i] if i < len(primary_docs) else None
                    })

        logger.info(f"Found {len(filings)} 8-K filings since {start_year}")
        return filings

    def fetch_8k_content(self, cik: str, accession: str, primary_document: str = None) -> Optional[str]:
        """
        Fetch the text content of an 8-K filing.

        Args:
            cik: Company CIK (without leading zeros for URL)
            accession: Accession number
            primary_document: Primary document filename (e.g., 'aapl-20250501.htm')

        Returns:
            Text content of the filing or None
        """
        # Remove leading zeros from CIK for URL
        cik_int = str(int(cik))

        # Try primary document first if provided
        if primary_document:
            url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{primary_document}"
        else:
            # Fallback to .txt file
            accession_nodash = accession.replace('-', '')
            url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{accession_nodash}.txt"

        try:
            self.client._rate_limit()  # Respect SEC rate limits
            response = requests.get(url, headers=self.client.headers, timeout=15)
            response.raise_for_status()

            return response.text

        except Exception as e:
            logger.error(f"Error fetching 8-K {accession}: {e}")
            return None

    def parse_dates_from_text(self, text: str) -> List[Dict]:
        """
        Extract potential dividend-related dates from 8-K text.

        Returns:
            List of dicts with {date, context, type}
        """
        if not text or 'dividend' not in text.lower():
            return []

        # Split into sections to get context
        # Look for dividend-related paragraphs
        paragraphs = text.split('\n\n')

        dividend_dates = []

        for paragraph in paragraphs:
            if 'dividend' not in paragraph.lower():
                continue

            # Clean up paragraph
            clean_para = ' '.join(paragraph.split())

            # Extract all dates from this paragraph
            dates = self._extract_dates(clean_para)

            for date_str, date_obj in dates:
                # Determine date type from context
                date_type = self._classify_date(clean_para, date_str)

                if date_type:
                    dividend_dates.append({
                        'date': date_obj,
                        'date_str': date_str,
                        'type': date_type,
                        'context': clean_para[:200]  # First 200 chars of context
                    })

        return dividend_dates

    def _extract_dates(self, text: str) -> List[tuple]:
        """
        Extract all dates from text using multiple patterns.

        Returns:
            List of (date_string, date_object) tuples
        """
        dates = []

        # Try each pattern
        for pattern in self.date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                try:
                    date_str = match.group(0)
                    date_obj = self._parse_date_string(match)

                    if date_obj:
                        dates.append((date_str, date_obj))

                except Exception as e:
                    logger.debug(f"Error parsing date '{match.group(0)}': {e}")
                    continue

        return dates

    def _parse_date_string(self, match: re.Match) -> Optional[datetime]:
        """
        Convert regex match to datetime object.
        """
        groups = match.groups()

        # "January 15, 2024" format
        if len(groups) == 3 and groups[0] in ['January', 'February', 'March', 'April', 'May', 'June',
                                                'July', 'August', 'September', 'October', 'November', 'December']:
            month_name = groups[0]
            day = int(groups[1])
            year = int(groups[2])

            return datetime.strptime(f"{month_name} {day} {year}", "%B %d %Y")

        # "01/15/2024" format
        elif len(groups) == 3 and groups[0].isdigit():
            month = int(groups[0])
            day = int(groups[1])
            year = int(groups[2])

            # Handle 2-digit years
            if year < 100:
                year += 2000

            return datetime(year, month, day)

        # "2024-01-15" format
        elif len(groups) == 3 and len(groups[0]) == 4:
            year = int(groups[0])
            month = int(groups[1])
            day = int(groups[2])

            return datetime(year, month, day)

        return None

    def _classify_date(self, context: str, date_str: str) -> Optional[str]:
        """
        Determine what type of dividend date this is based on context.

        Returns:
            'declaration', 'record', 'payment', 'ex_dividend', or None
        """
        context_lower = context.lower()

        # Get text around the date for better context
        date_index = context_lower.find(date_str.lower())
        if date_index > 0:
            nearby = context_lower[max(0, date_index-100):min(len(context_lower), date_index+100)]
        else:
            nearby = context_lower

        # Check for keywords
        if any(kw in nearby for kw in self.record_keywords):
            return 'record'
        elif any(kw in nearby for kw in self.payment_keywords):
            return 'payment'
        elif any(kw in nearby for kw in self.ex_dividend_keywords):
            return 'ex_dividend'
        elif any(kw in nearby for kw in self.declaration_keywords):
            return 'declaration'

        return None

    def extract_dividend_amount(self, text: str) -> List[float]:
        """
        Extract dividend amounts from text for matching purposes.

        Returns:
            List of amounts found (e.g., [0.24, 0.25])
        """
        if 'dividend' not in text.lower():
            return []

        # Pattern: $0.24 per share, $0.24/share, etc.
        amount_pattern = r'\$(\d+\.\d{2,4})\s*(?:per share|/share)?'

        amounts = []
        matches = re.finditer(amount_pattern, text, re.IGNORECASE)

        for match in matches:
            try:
                amount = float(match.group(1))
                if 0.01 <= amount <= 50.0:  # Reasonable dividend range
                    amounts.append(amount)
            except:
                continue

        return amounts

    def match_to_existing_dividend(self, filing_data: Dict, existing_dividends: List[Dict]) -> Optional[Dict]:
        """
        Match extracted 8-K data to an existing XBRL dividend record.

        Args:
            filing_data: Dict with {amounts, dates, filing_date}
            existing_dividends: List of dividend records from database

        Returns:
            Matched dividend dict or None
        """
        filing_amounts = filing_data.get('amounts', [])
        filing_dates = filing_data.get('dates', [])
        filing_date = filing_data.get('filing_date')

        if not filing_amounts or not existing_dividends:
            return None

        # Try to match by amount and date proximity
        for dividend in existing_dividends:
            div_amount = float(dividend['amount'])
            div_ex_date = dividend['ex_dividend_date']

            # Check if amounts match (within $0.01)
            for filing_amount in filing_amounts:
                if abs(div_amount - filing_amount) <= 0.01:
                    # Check date proximity (8-K should be filed around dividend announcement)
                    # Usually 8-K filed within 30 days before ex-dividend date
                    if filing_date:
                        filing_dt = datetime.strptime(filing_date, '%Y-%m-%d').date()
                        days_diff = (div_ex_date - filing_dt).days

                        if -5 <= days_diff <= 60:  # Filed 5 days after to 60 days before
                            return dividend

        return None


if __name__ == "__main__":
    # Test with Apple
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from sec_edgar_client import SECAPIClient

    print("Testing 8-K Enhancer - Proof of Concept")
    print("="*80)

    client = SECAPIClient()
    enhancer = Filing8KEnhancer(client)

    # Test: Find recent 8-Ks for Apple
    apple_cik = '0000320193'
    filings = enhancer.find_8k_filings(apple_cik, start_year=2024)

    print(f"\nFound {len(filings)} recent 8-K filings")

    # Test with a known filing that contains dividend info
    # Use first filing from list
    if len(filings) >= 10:
        test_filing = filings[9]  # Get an older one that should exist
    else:
        test_filing = filings[-1] if filings else None

    if not test_filing:
        print("No filings to test")
        exit(1)

    print(f"\nTesting with filing: {test_filing['accession']} ({test_filing['filing_date']})")

    content = enhancer.fetch_8k_content(
        apple_cik,
        test_filing['accession'],
        test_filing.get('primary_document')
    )

    if content:
        print(f"  ✓ Retrieved {len(content)} characters")

        # Extract dividend info
        dates = enhancer.parse_dates_from_text(content)
        amounts = enhancer.extract_dividend_amount(content)

        print(f"\n  Extracted data:")
        print(f"    Amounts found: {amounts}")
        print(f"    Dates found: {len(dates)}")

        for date_info in dates[:5]:  # Show first 5
            print(f"      {date_info['type']}: {date_info['date'].strftime('%Y-%m-%d')}")
            print(f"        Context: {date_info['context'][:100]}...")
    else:
        print("  ✗ Could not retrieve filing")

    print("\n" + "="*80)
