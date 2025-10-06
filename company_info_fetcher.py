#!/usr/bin/env python3
"""
Fetch company descriptions from Wikipedia and websites from SEC

Uses:
- Wikipedia API for company descriptions (first paragraph)
- SEC submissions API for official websites

License compliance:
- Wikipedia content: CC BY-SA 3.0 (with attribution)
- SEC data: Public domain
"""

import requests
import time
from typing import Optional, Dict
from config import SEC_CONFIG


class CompanyInfoFetcher:
    """Fetch company descriptions and websites"""

    def __init__(self):
        self.wikipedia_base = "https://en.wikipedia.org/api/rest_v1/page/summary/"
        self.user_agent = SEC_CONFIG['user_agent']

    def get_wikipedia_summary(self, company_name: str) -> Optional[Dict[str, str]]:
        """
        Get first paragraph from Wikipedia

        Returns:
            dict with 'description', 'source_url', 'license' or None
        """
        # Try exact company name first
        result = self._fetch_wikipedia(company_name)
        if result:
            return result

        # Try without Inc/Corp/Ltd suffixes
        cleaned_name = company_name
        for suffix in [' Inc.', ' Inc', ' Corp.', ' Corp', ' Corporation',
                       ' Ltd.', ' Ltd', ' Limited', ' Company', ' Co.', ' Co']:
            cleaned_name = cleaned_name.replace(suffix, '')

        if cleaned_name != company_name:
            result = self._fetch_wikipedia(cleaned_name)
            if result:
                return result

        return None

    def _fetch_wikipedia(self, search_term: str) -> Optional[Dict[str, str]]:
        """Fetch from Wikipedia API"""
        url = self.wikipedia_base + search_term.replace(' ', '_')

        try:
            headers = {'User-Agent': self.user_agent}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Get first paragraph (extract field)
                description = data.get('extract')
                if not description:
                    return None

                # Get only first paragraph (split on double newline or first period + newline)
                first_para = description.split('\n\n')[0].split('\n')[0]

                return {
                    'description': first_para,
                    'source_url': data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                    'license': 'CC BY-SA 3.0'
                }

            return None

        except Exception as e:
            print(f"  Wikipedia fetch error for '{search_term}': {e}")
            return None

    def get_company_website(self, submissions_data: dict) -> Optional[str]:
        """
        Extract company website from SEC submissions data

        Args:
            submissions_data: Response from SEC submissions API

        Returns:
            Website URL or None
        """
        if not submissions_data:
            return None

        # SEC provides 'website' in the addresses section
        addresses = submissions_data.get('addresses', {})

        # Try business address first
        business = addresses.get('business', {})
        if business:
            # Sometimes in 'phone' field there's a website reference
            # More commonly we need to check entityType or look for website pattern
            pass

        # Check for website in the main data
        website = submissions_data.get('website')
        if website:
            # Ensure it has http/https
            if not website.startswith('http'):
                website = 'https://' + website
            return website

        return None

    def fetch_all_info(self, company_name: str, submissions_data: dict = None) -> Dict[str, any]:
        """
        Fetch both Wikipedia description and company website

        Args:
            company_name: Company name to search
            submissions_data: Optional SEC submissions data

        Returns:
            dict with description, description_source, description_license, website
        """
        result = {
            'description': None,
            'description_source': None,
            'description_license': None,
            'website': None
        }

        # Get Wikipedia info
        wiki_info = self.get_wikipedia_summary(company_name)
        if wiki_info:
            result['description'] = wiki_info['description']
            result['description_source'] = wiki_info['source_url']
            result['description_license'] = wiki_info['license']

        # Get website from SEC
        if submissions_data:
            website = self.get_company_website(submissions_data)
            if website:
                result['website'] = website

        return result


def test_fetcher():
    """Test the fetcher with a few companies"""
    fetcher = CompanyInfoFetcher()

    test_companies = [
        "Apple Inc.",
        "Microsoft Corporation",
        "Coca-Cola Company",
        "Johnson & Johnson"
    ]

    for company in test_companies:
        print(f"\nTesting: {company}")
        info = fetcher.fetch_all_info(company)
        if info['description']:
            print(f"  ✓ Description: {info['description'][:100]}...")
            print(f"  ✓ Source: {info['description_source']}")
        else:
            print(f"  ✗ No description found")


if __name__ == '__main__':
    test_fetcher()
