# DivScout

A Python tool for extracting dividend data from SEC EDGAR filings using the official SEC XBRL (eXtensible Business Reporting Language) JSON APIs.

## ⚠️ Important Disclaimer

**THIS SOFTWARE IS FOR INFORMATIONAL AND EDUCATIONAL PURPOSES ONLY.**

This tool extracts publicly available data from SEC filings. It is **NOT** financial advice, investment advice, or a recommendation to buy or sell any security. The data provided may contain errors, omissions, or inaccuracies.

**DO NOT** make investment decisions based solely on data from this tool. Always:
- Verify data independently from official sources
- Consult with qualified financial professionals
- Conduct your own due diligence
- Understand that past dividend payments do not guarantee future payments

The authors and contributors of this software accept **NO LIABILITY** for any financial losses, damages, or other consequences resulting from the use of this software or its output.

## What It Does

DivScout automatically:

1. **Fetches XBRL data** from the SEC's CompanyFacts API for specified stock tickers
2. **Parses dividend information** from standardized XBRL tags in company financial statements
3. **Applies data quality checks** including:
   - Detection and filtering of annual totals (which are often reported alongside quarterly dividends)
   - Statistical outlier detection using Interquartile Range (IQR)
   - Duplicate removal based on ex-dividend dates
   - Confidence scoring (0.0 to 1.0) for each dividend entry
4. **Stores structured data** in a PostgreSQL database with full audit trails
5. **Flags low-confidence entries** for manual review (confidence < 80%)

## What It Does NOT Do

- ❌ **Does not provide real-time data** - XBRL data reflects filed reports, which lag behind announcements
- ❌ **Does not scrape HTML** - uses only official SEC JSON APIs
- ❌ **Does not predict future dividends** - only historical data
- ❌ **Does not validate data accuracy** - automated quality checks are heuristic, not definitive
- ❌ **Does not handle special dividends comprehensively** - focuses on regular cash dividends
- ❌ **Does not track dividend reinvestment programs (DRIPs)**
- ❌ **Does not process stock dividends or splits**
- ❌ **Does not support all companies** - limited to those with XBRL data and known CIKs

## Known Limitations

### Ticker Coverage
- Only a small set of common tickers are hardcoded in the CIK lookup function
- For other companies, you must manually find the CIK (Central Index Key) and modify the code
- The SEC's `company_tickers.json` endpoint is sometimes unavailable

### Data Completeness
- **Declaration dates** are often missing from XBRL data
- **Record dates** and **payment dates** may be incomplete
- Some companies do not file complete XBRL dividend data
- XBRL format and tag usage varies by company

### Date Accuracy
- XBRL data typically provides period end dates, which are mapped to ex-dividend dates
- These may not perfectly match actual ex-dividend dates
- Always verify critical dates from official company sources

### Annual Total Detection
- While the tool attempts to filter out annual totals, some may slip through
- Conversely, some legitimate dividends might be incorrectly flagged
- Review all low-confidence entries manually

### Performance
- SEC enforces 10 requests/second rate limiting
- Processing large numbers of companies takes time
- No caching mechanism for API responses

## Data Quality & Confidence Scoring

Each dividend receives a confidence score based on multiple factors:

**Confidence Penalties Applied For:**
- Amount > $50.00 (very high): ×0.5
- Amount < $0.01 (very low): ×0.7
- Amount > 3× median: ×0.6
- Amount > 2× median: ×0.8
- Period duration ≈ 365 days (annual): ×0.3
- Period duration ≈ 180 days (semi-annual): ×0.5
- Missing fiscal period metadata: ×0.9
- From 10-K filing without quarter info: ×0.8

**Dividends with confidence < 0.8 are flagged for manual review.**

### Test Results

The tool has been tested against real SEC XBRL data with the following results:

#### ✅ Apple Inc. (AAPL) - CIK 0000320193
- **Dividends extracted**: 46 dividends (2012-2025)
- **Amount range**: $0.1925 - $2.6500 per share
- **Pattern detected**: Very stable quarterly dividends
- **Confidence scores**: All dividends scored 1.00 (100% confidence)
- **Annual totals**: Successfully filtered out (not present in recent data)
- **False positives**: 0 entries flagged for review
- **Data quality**: Excellent - matches official Apple dividend history

#### ✅ Built-in Parser Test (Sample XBRL Data)
- **Test data**: Apple Q1-Q2 2024 sample
- **Dividends parsed**: 2 quarterly dividends
- **Confidence**: 100% (1.00) for both entries
- **Annual total detection**: Correctly identified and removed FY entry ($0.96)
- **Coefficient of variation**: 0.0 (perfectly stable)

#### Test Coverage Summary
- ✅ **Quarterly dividend extraction**: Working correctly
- ✅ **Annual total filtering**: Successfully removes cumulative amounts
- ✅ **Confidence scoring**: Assigns appropriate scores based on data quality
- ✅ **Duplicate detection**: Prevents duplicate entries for same date
- ✅ **XBRL tag parsing**: Correctly processes CommonStockDividendsPerShareDeclared
- ✅ **Fiscal period mapping**: Accurately maps Q1-Q4 periods
- ⚠️ **Edge cases**: Companies with irregular patterns may need manual review
- ⚠️ **Limited ticker coverage**: Only works for companies in hardcoded CIK list

#### Known Test Limitations
- Tests primarily focused on stable, quarterly dividend payers
- Limited testing with monthly dividend payers (e.g., REITs)
- Limited testing with companies that have dividend suspensions/resumptions
- Special dividends and irregular payments need more test coverage

**Note**: Test results demonstrate the tool works for its intended use case but do not guarantee accuracy for all companies or time periods. Always verify extracted data against official sources before use.

## Requirements

- Python 3.8+
- PostgreSQL database
- SEC API access (requires proper User-Agent identification per SEC Fair Access policy)

### Dependencies

```
requests>=2.31.0
psycopg2-binary>=2.9.9
python-dotenv>=1.0.0
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/chonito7919/DivScout.git
cd DivScout
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up PostgreSQL database and create required tables (schema not included - see `db_connection.py` for expected structure)

4. Create a `.env` file with required configuration:
```env
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_user
DB_PASSWORD=your_password
DB_SSLMODE=require

# SEC API Configuration (REQUIRED - SEC will reject requests without proper identification)
SEC_USER_AGENT=YourName your.email@domain.com

# Optional
START_YEAR=2020
END_YEAR=2025
```

**IMPORTANT**: You **must** set `SEC_USER_AGENT` to your real name and email address. The SEC requires proper identification per their [Fair Access policy](https://www.sec.gov/os/accessing-edgar-data).

## Usage

### Basic Usage

```bash
# Process a single company
python main.py AAPL

# Process multiple companies
python main.py AAPL MSFT JNJ KO
```

### Database Administration

```bash
# View statistics
python admin/admin_stats.py

# View specific company details
python admin/admin_stats.py --company AAPL

# View recent activity
python admin/admin_stats.py --recent --days 30

# Preview cleanup of low-confidence entries
python admin/admin_cleanup.py --dry-run

# Delete low-confidence entries
python admin/admin_cleanup.py --confidence 0.5
```

### Testing Components

```bash
# Test XBRL parser
python parsers/xbrl_dividend_parser.py

# Test SEC API client
python sec_edgar_client.py

# Test database connection
python db_connection.py
```

## Architecture

The tool follows a simple pipeline:

1. **Ticker → CIK Lookup**: Convert stock ticker to SEC Central Index Key
2. **Fetch XBRL Data**: Retrieve company facts from SEC API
3. **Parse Dividends**: Extract dividend data using XBRL parser with quality checks
4. **Database Storage**: Store with confidence scores and audit trails
5. **Review Workflow**: Flag low-confidence entries for manual verification

### Key Components

- **`main.py`**: Entry point and pipeline orchestration
- **`sec_edgar_client.py`**: SEC API wrapper with rate limiting
- **`parsers/xbrl_dividend_parser.py`**: XBRL parsing and quality analysis
- **`db_connection.py`**: PostgreSQL interface and admin functions
- **`config.py`**: Configuration management
- **`admin/`**: Database administration utilities

## Data Sources

All data is sourced from:
- **SEC EDGAR CompanyFacts API**: https://data.sec.gov/api/xbrl/companyfacts/
- **SEC EDGAR Submissions API**: https://data.sec.gov/submissions/

This tool does **NOT**:
- Scrape HTML pages
- Use unofficial APIs or data sources
- Cache or redistribute SEC data

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Before contributing, please understand:**
- This tool is for educational and informational purposes only
- Contributors must agree that their contributions will not be used to provide financial advice
- All contributions must comply with SEC data usage policies
- Code quality and data accuracy are critical - all PRs must include tests

## License

This project is licensed under the **Apache License 2.0**.

See [LICENSE](LICENSE) for full details.

### Key License Points

- ✅ You may use, modify, and distribute this software freely
- ✅ You may use this software for commercial purposes
- ✅ Includes explicit patent grant protection
- ✅ Can be used in proprietary software
- ⚠️ Must include copy of license and notice of any modifications
- ⚠️ No warranty is provided - use at your own risk

## Final Disclaimer

**THIS SOFTWARE IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.**

**This is not financial advice. This is not investment advice. Do not make financial decisions based on this software.**

---

**Developed for educational and informational purposes only.**
