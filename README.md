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

## Live Demo

**Visit [divscout.app](https://divscout.app)** to see DivScout in action!

The web interface provides:
- 📊 **Dashboard** with dividend statistics overview
- 🏢 **Company browser** with sector and industry filtering
- 📅 **Payment calendar** showing upcoming dividends
- 📈 **Dividend histories** with confidence scores
- 🔍 **High-confidence data** (≥0.8 confidence threshold)

**Current dataset**: 4,643 verified dividend records across 109 companies with 100% confidence scoring (all low-confidence entries removed).

**Tech stack**: Flask API + Vanilla JavaScript frontend hosted on Namecheap Stellar with PostgreSQL on DigitalOcean.

**Repository**: [github.com/chonito7919/divscout-web](https://github.com/chonito7919/divscout-web)

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
- **111+ tickers** are hardcoded in the CIK lookup function across all major sectors:
  - Technology (14 companies): AAPL, MSFT, NVDA, CSCO, ORCL, IBM, INTC, TXN, QCOM, ADI, etc.
  - Healthcare (10 companies): JNJ, UNH, LLY, ABBV, MRK, TMO, ABT, PFE, AMGN, CVS
  - Financials (15 companies): JPM, BAC, WFC, MS, GS, BLK, C, USB, PNC, V, MA, etc.
  - Consumer Staples (14 companies): KO, PEP, PG, WMT, COST, PM, MO, CL, KMB, GIS, etc.
  - Consumer Discretionary (10 companies): HD, MCD, NKE, SBUX, TGT, LOW, F, GM, etc.
  - Energy (10 companies): XOM, CVX, COP, SLB, EOG, PSX, VLO, OXY, KMI, WMB
  - Industrials (10 companies): BA, CAT, GE, LMT, RTX, UNP, HON, UPS, DE, MMM
  - Utilities (9 companies): NEE, DUK, SO, D, AEP, EXC, SRE, XEL, PCG
  - REITs (10 companies): O, AMT, PLD, CCI, EQIX, PSA, WELL, DLR, SPG, AVB
  - Materials (6 companies): LIN, APD, SHW, FCX, NEM, ECL
  - Telecom (3 companies): T, VZ, TMUS
- For other companies, you must manually find the CIK and add to `sec_edgar_client.py`
- The SEC's `company_tickers.json` endpoint is sometimes unavailable

### Data Completeness
- **Declaration dates**, **record dates**, and **payment dates** are **NOT available** in XBRL CompanyFacts API
  - The API only provides period start/end dates for financial reporting
  - Ex-dividend dates are approximated from period end dates
  - To get these dates, you would need to parse 8-K filings separately
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

#### ✅ Production Database Statistics

**As of October 2025:**
- **Companies**: 109 companies across all major sectors
- **Total dividends extracted**: 4,909 dividend records
- **Clean data**: 4,643 verified dividends (94.6% after quality filtering)
- **Annual totals filtered**: 64 cumulative totals removed
- **Low confidence removed**: 202 dividends with confidence < 0.8 deleted
- **Date range**: Historical data from 2008-2025 depending on company
- **Average per company**: ~43 dividend records

**Sample Companies:**
- **AAPL**: 46 dividends (2012-2025), 100% confidence
- **JNJ**: 52 dividends, stable quarterly pattern
- **MSFT**: 51 dividends, consistent growth
- **KO**: 43 dividends, long dividend history
- **O** (Realty Income): Monthly dividend payer

#### ✅ Built-in Parser Test (Sample XBRL Data)
- **Test data**: Apple Q1-Q2 2024 sample
- **Dividends parsed**: 2 quarterly dividends
- **Confidence**: 100% (1.00) for both entries
- **Annual total detection**: Correctly identified and removed FY entry ($0.96)
- **Coefficient of variation**: 0.0 (perfectly stable)

#### Test Coverage Summary

Available test files:
- ✅ **`tests/test_apple_dividends.py`**: Apple Inc. (AAPL) - stable quarterly dividend payer
- ✅ **`tests/test_us_market_diverse.py`**: Diverse set of US companies with varying dividend patterns
- ✅ **`tests/test_edge_cases.py`**: Special cases, suspensions, and irregular patterns
- ✅ **`tests/test_multiple_companies.py`**: Batch processing of multiple tickers
- ✅ **`tests/test_load_with_confidence.py`**: Confidence scoring and quality metrics
- ✅ **`tests/test_one.py`**: Single company quick test

Feature coverage:
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

### Running Tests

```bash
# Run all tests
python tests/test_apple_dividends.py
python tests/test_us_market_diverse.py
python tests/test_edge_cases.py
python tests/test_multiple_companies.py
python tests/test_load_with_confidence.py

# Quick single company test
python tests/test_one.py
```

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

## Quick Start

Want to see it in action quickly? Try this:

```bash
# After installation (see below)
python main.py AAPL

# Expected output:
# ✔ Database connected successfully
# Processing AAPL (Apple Inc. - CIK: 0000320193)
# ✔ Found 46 dividends from XBRL data
# ✔ Inserted 46 new dividends (0 duplicates skipped)
#
# Confidence Summary:
#   Average: 1.00 (100%)
#   Range: $0.1925 - $2.6500
#   0 dividends flagged for review
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

3. Set up PostgreSQL database and create required tables:
```bash
psql -U your_user -d your_database -f schema.sql
```

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

## Troubleshooting

### Common Issues

**"SEC API returned 403 Forbidden"**
- Make sure `SEC_USER_AGENT` is set in your `.env` file
- Format must be: `YourName your.email@domain.com`
- The SEC blocks requests without proper identification

**"Ticker not found" or "Unknown ticker"**
- Only a limited set of tickers are hardcoded in `sec_edgar_client.py`
- Find the company's CIK manually at https://www.sec.gov/edgar/searchedgar/companysearch
- Modify the `lookup_ticker_to_cik()` function to add your ticker

**"Database connection failed"**
- Verify PostgreSQL is running: `systemctl status postgresql` or `brew services list`
- Check `.env` file has correct DB credentials
- Test connection: `psql -U your_user -d your_database`
- For SSL errors, try `DB_SSLMODE=disable` (not recommended for production)

**"Rate limit exceeded"**
- SEC enforces 10 requests/second
- The client handles this automatically with rate limiting
- If you see this error, wait 60 seconds and try again
- Don't make direct `requests.get()` calls - always use `SECAPIClient`

**"No dividends found for [ticker]"**
- Not all companies report dividends in XBRL format
- Some companies don't pay dividends
- Try a known dividend payer first (AAPL, JNJ, KO) to verify setup
- Check if the company actually pays dividends on their investor relations page

**"Too many annual totals detected"**
- Some companies report cumulative amounts in their filings
- The parser attempts to filter these automatically
- Review flagged entries: `python admin/admin_stats.py --company TICKER`
- Manual review: use `db.get_dividends_for_review()`

**"Low confidence scores on valid dividends"**
- Confidence scoring is heuristic-based, not perfect
- Review flagged entries and approve if valid
- Adjust thresholds in `parsers/xbrl_dividend_parser.py` if needed
- Some edge cases (special dividends, stock dividends) may score low

**"Tests failing"**
- Ensure database is set up: `psql -U your_user -d your_database -f schema.sql`
- Check `.env` file exists and has all required variables
- Verify internet connection (tests fetch live SEC data)
- Some tests may fail if SEC API is temporarily unavailable

### Getting Help

If you encounter issues not covered here:
1. Check existing [GitHub Issues](https://github.com/chonito7919/DivScout/issues)
2. Review CLAUDE.md for detailed implementation notes
3. Run component tests to isolate the problem:
   - `python sec_edgar_client.py` - Test API client
   - `python parsers/xbrl_dividend_parser.py` - Test parser
   - `python db_connection.py` - Test database
4. Open a new issue with error messages and steps to reproduce

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
