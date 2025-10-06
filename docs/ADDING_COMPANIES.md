# Adding New Companies to DivScout

## Quick Start

To add new dividend-paying companies to DivScout, simply edit the CSV file:

### 1. Edit `data/companies.csv`

Add a new line with the ticker and CIK:

```csv
ticker,cik
AAPL,0000320193
MSFT,0000789019
YOUR_NEW_TICKER,0000123456
```

### 2. Find the CIK

**Option A: Use SEC's Company Search**
- Go to https://www.sec.gov/edgar/searchedgar/companysearch
- Search for the company name
- Copy the 10-digit CIK number (with leading zeros)

**Option B: Use SEC's Ticker JSON**
- Download https://www.sec.gov/files/company_tickers.json
- Search for your ticker
- Use the `cik_str` value (pad with zeros to 10 digits if needed)

### 3. Run the populate script

```bash
# Populate ALL companies from CSV
.venv/bin/python scripts/populate_all_companies.py

# Or populate specific new tickers
.venv/bin/python scripts/populate_all_companies.py --tickers YOUR_NEW_TICKER

# Test first with dry-run
.venv/bin/python scripts/populate_all_companies.py --tickers YOUR_NEW_TICKER --dry-run
```

### 4. Done!

The weekly refresh timer will automatically include the new company in future updates.

## Example: Adding Starbucks (SBUX)

1. **Find CIK**: Search for "Starbucks" on SEC EDGAR → CIK: 0000829224

2. **Add to CSV**:
```csv
ticker,cik
...existing companies...
SBUX,0000829224
```

3. **Populate**:
```bash
.venv/bin/python scripts/populate_all_companies.py --tickers SBUX
```

4. **Result**:
```
Processing: SBUX
  ✓ Found: STARBUCKS CORP
  ✓ CIK: 0000829224
  ✓ Found 46 dividends
  ✓ Inserted: 46 new dividends
```

## Important Notes

### CSV Format

- **Header required**: First line must be `ticker,cik`
- **No spaces**: `AAPL,0000320193` not `AAPL, 0000320193`
- **10-digit CIKs**: Pad with leading zeros: `0000320193` not `320193`
- **Uppercase tickers**: Recommended but not required (script converts automatically)

### What Gets Updated

**`populate_all_companies.py`** reads from CSV:
- Processes companies listed in `data/companies.csv`
- Adds new companies to database
- Inserts dividend history

**`refresh_dividends.py`** reads from database:
- Refreshes existing companies already in database
- Runs weekly via systemd timer
- Automatically picks up new companies after they're populated

### Removing Companies

To stop tracking a company:
- **Option 1**: Delete the row from `data/companies.csv` (prevents future additions)
- **Option 2**: Leave in CSV, set `is_active=false` in database

**Note**: Removing from CSV does NOT delete from database. Historical data stays intact.

## Troubleshooting

### "Ticker not in companies.csv"

✅ **Solution**: Add the ticker to `data/companies.csv` with correct CIK

### "No XBRL data found"

This means the company doesn't report dividends in XBRL format. Some possibilities:
- Company doesn't pay dividends
- Company uses non-standard reporting
- CIK is incorrect

✅ **Solution**: Verify the company pays dividends and CIK is correct

### "Duplicate CIK"

Multiple tickers map to same CIK (e.g., GOOG and GOOGL both = Alphabet).

✅ **Solution**: This is normal, script will skip the duplicate

## Batch Adding Companies

To add many companies at once:

1. **Create a list** of tickers and CIKs
2. **Append to CSV** (don't remove existing entries!)
3. **Run populate** for all new ones:

```bash
# Option A: Process all companies (slower, includes existing)
.venv/bin/python scripts/populate_all_companies.py

# Option B: Process specific tickers
.venv/bin/python scripts/populate_all_companies.py --tickers TICK1 TICK2 TICK3
```

## Automation

Once companies are in `data/companies.csv` and populated into the database:

- **Weekly refresh** runs automatically (systemd timer)
- **No manual intervention** needed for updates
- **New dividends** get fetched each Sunday at 2 AM

Check timer status:
```bash
systemctl --user status divscout-refresh.timer
```

## File Locations

- **Company list**: `/home/sean/Python/DivScout/data/companies.csv`
- **Populate script**: `/home/sean/Python/DivScout/scripts/populate_all_companies.py`
- **Refresh script**: `/home/sean/Python/DivScout/scripts/refresh_dividends.py`
- **Logs**: `/home/sean/Python/DivScout/logs/`

## Best Practices

✅ **Do:**
- Add companies with established dividend histories
- Verify CIK before adding
- Test with `--dry-run` first
- Keep CSV sorted alphabetically (optional but clean)

❌ **Don't:**
- Add companies that don't pay dividends (they'll just show "no dividends found")
- Modify existing CIKs unless correcting an error
- Delete rows from CSV to remove from database (just stops tracking new additions)

## Questions?

See the main README or check existing companies in `data/companies.csv` for examples.
