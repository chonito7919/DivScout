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
Configuration module for dividend data collection
Loads environment variables and provides configuration constants
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database Configuration
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'sslmode': os.getenv('DB_SSLMODE', 'require')
}

# SEC API Configuration
SEC_CONFIG = {
    'user_agent': os.getenv('SEC_USER_AGENT', 'Anonymous User no-reply@example.com'),
    # SEC Fair Access: 10 requests per second maximum
    'rate_limit_requests': 10,
    'rate_limit_period': 1.0,  # seconds
    
    # API Endpoints
    'base_url': 'https://data.sec.gov',
    'api_base': 'https://data.sec.gov/api/xbrl',
    'submissions_api': 'https://data.sec.gov/submissions',
    
    # Bulk Downloads
    'bulk_companyfacts': 'https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip',
    'bulk_submissions': 'https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip',
    'ticker_mapping': 'https://www.sec.gov/files/company_tickers.json'  # CHANGED: added /files/
}

# XBRL Configuration
XBRL_CONFIG = {
    # ... existing tags ...
    
    # Data quality thresholds
    'max_reasonable_dividend': 50.0,  # Flag dividends above this
    'min_reasonable_dividend': 0.01,  # Flag dividends below this
    'annual_total_multiplier': 3.0,   # Flag if >3x median as potential annual total
    'duplicate_window_days': 30,      # Days to check for duplicates
    
    # Company-specific overrides (for known edge cases)
    'company_overrides': {
        '0000018230': {'max_reasonable_dividend': 10.0},  # Caterpillar
        '0000027419': {'fiscal_year_end_month': 1},       # Target
    }
}

# Data Collection Configuration
COLLECTION_CONFIG = {
    'start_year': int(os.getenv('START_YEAR', 2020)),
    'end_year': int(os.getenv('END_YEAR', 2025)),

    # Bulk download settings
    'download_dir': os.getenv('DOWNLOAD_DIR', './data/downloads'),
    'extract_dir': os.getenv('EXTRACT_DIR', './data/extracted'),

    # Processing settings
    'batch_size': 100,  # Companies to process in one batch
    'retry_attempts': 3,
    'retry_delay': 5  # seconds between retries
}

# Alias for backward compatibility (deprecated)
SCRAPING_CONFIG = COLLECTION_CONFIG

# Validation
if SEC_CONFIG['user_agent'] == 'Anonymous User no-reply@example.com':
    print("WARNING: Please set SEC_USER_AGENT in .env file with your name and email")
    print("SEC requires proper identification per their Fair Access policy")
    print("Example: 'YourName your.email@domain.com'")

if not DATABASE_CONFIG['password']:
    print("ERROR: DB_PASSWORD not set in .env file")
    exit(1)

# Create directories if they don't exist
os.makedirs(COLLECTION_CONFIG['download_dir'], exist_ok=True)
os.makedirs(COLLECTION_CONFIG['extract_dir'], exist_ok=True)