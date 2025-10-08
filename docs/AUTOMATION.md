# DivScout Automation Guide

## Overview

This guide covers automated dividend data collection and refresh workflows for DivScout.

## Quick Start

### One-Time Initial Load

Load all 175 companies into the database:

```bash
# Load all companies at once
.venv/bin/python scripts/populate_all_companies.py

# Or load by sector
.venv/bin/python scripts/populate_all_companies.py --sector financials
.venv/bin/python scripts/populate_all_companies.py --sector healthcare
```

### Incremental Updates (Recommended for Automation)

Refresh existing companies to get new dividends:

```bash
# Refresh all companies
.venv/bin/python scripts/refresh_dividends.py

# Refresh specific companies
.venv/bin/python scripts/refresh_dividends.py --tickers AAPL MSFT JNJ

# Test before running
.venv/bin/python scripts/refresh_dividends.py --dry-run
```

## Automation Methods

### Method 1: Cron (Linux/Mac)

#### Weekly Refresh (Recommended)

Run every Sunday at 2 AM:

```bash
# Edit crontab
crontab -e

# Add this line:
0 2 * * 0 cd /home/sean/Python/DivScout && .venv/bin/python scripts/refresh_dividends.py >> logs/refresh.log 2>&1
```

#### Monthly Full Cleanup

Run first Sunday of each month:

```bash
# Add to crontab:
0 3 1-7 * 0 cd /home/sean/Python/DivScout && .venv/bin/python scripts/cleanup_annual_totals.py --yes >> logs/cleanup.log 2>&1
```

#### Create log directory

```bash
mkdir -p logs
```

### Method 2: Systemd Timer (Linux)

#### Create Service File

`/etc/systemd/system/divscout-refresh.service`:

```ini
[Unit]
Description=DivScout Dividend Refresh
After=network.target

[Service]
Type=oneshot
User=sean
WorkingDirectory=/home/sean/Python/DivScout
Environment="PATH=/home/sean/Python/DivScout/.venv/bin"
ExecStart=/home/sean/Python/DivScout/.venv/bin/python scripts/refresh_dividends.py
StandardOutput=append:/home/sean/Python/DivScout/logs/refresh.log
StandardError=append:/home/sean/Python/DivScout/logs/refresh.log
```

#### Create Timer File

`/etc/systemd/system/divscout-refresh.timer`:

```ini
[Unit]
Description=Run DivScout refresh weekly
Requires=divscout-refresh.service

[Timer]
OnCalendar=Sun *-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

#### Enable Timer

```bash
sudo systemctl daemon-reload
sudo systemctl enable divscout-refresh.timer
sudo systemctl start divscout-refresh.timer

# Check status
sudo systemctl status divscout-refresh.timer
```

### Method 3: Python Script with Schedule Library

For development or testing:

```python
#!/usr/bin/env python3
import schedule
import time
import subprocess

def run_refresh():
    """Run the refresh script"""
    result = subprocess.run([
        '.venv/bin/python',
        'scripts/refresh_dividends.py'
    ], capture_output=True, text=True)

    print(result.stdout)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")

# Schedule weekly refresh
schedule.every().sunday.at("02:00").do(run_refresh)

# Keep running
while True:
    schedule.run_pending()
    time.sleep(3600)  # Check every hour
```

## Recommended Automation Schedule

### Weekly Refresh (Primary)

**When**: Every Sunday at 2 AM
**Script**: `refresh_dividends.py`
**Purpose**: Get new quarterly dividends

Most companies announce dividends quarterly, so weekly checks ensure you catch new announcements within a few days.

### Monthly Cleanup (Optional)

**When**: First Sunday of each month at 3 AM
**Script**: `cleanup_annual_totals.py --yes`
**Purpose**: Remove any low-confidence entries that slipped through

This is optional since the initial load already filters annual totals, but provides an extra safety layer.

### Annual Full Reload (Optional)

**When**: January 1st at 4 AM
**Script**: `populate_all_companies.py`
**Purpose**: Complete data refresh

This is rarely needed since incremental updates handle everything, but can be useful for:
- Catching corrections to historical data
- Verifying data integrity
- Resetting after major schema changes

## Monitoring & Logs

### Log Files

All scripts support output redirection:

```bash
# Redirect to log file
.venv/bin/python scripts/refresh_dividends.py >> logs/refresh.log 2>&1

# View latest logs
tail -f logs/refresh.log

# View errors only
grep "✗" logs/refresh.log
```

### Email Notifications (Optional)

Add to your cron job:

```bash
# Install mail utils
sudo apt-get install mailutils

# Cron will email output if MAILTO is set
MAILTO=your.email@domain.com
0 2 * * 0 cd /home/sean/Python/DivScout && .venv/bin/python scripts/refresh_dividends.py
```

### Database Monitoring

Check refresh status:

```sql
-- See recent collection attempts
SELECT ticker, data_type, status, records_inserted, collected_at
FROM data_collection_log
ORDER BY collected_at DESC
LIMIT 20;

-- Check for companies not updated recently
SELECT c.ticker, c.company_name, MAX(dcl.collected_at) as last_update
FROM companies c
LEFT JOIN data_collection_log dcl ON c.company_id = dcl.company_id
GROUP BY c.ticker, c.company_name
HAVING MAX(dcl.collected_at) < NOW() - INTERVAL '30 days'
OR MAX(dcl.collected_at) IS NULL;
```

## Adding New Companies

When new companies are added to `sec_edgar_client.py`:

```bash
# 1. Update the ticker list in sec_edgar_client.py
# 2. Update the ticker list in scripts/populate_all_companies.py

# 3. Load the new companies
.venv/bin/python scripts/populate_all_companies.py --tickers NEW1 NEW2 NEW3

# 4. The next scheduled refresh will include them automatically
```

## Troubleshooting

### Script Fails to Run

**Check permissions:**
```bash
chmod +x scripts/refresh_dividends.py
chmod +x scripts/populate_all_companies.py
```

**Check virtual environment:**
```bash
source .venv/bin/activate
python -c "import requests; print('OK')"
```

**Check database connection:**
```bash
.venv/bin/python -c "from db_connection import db; db.test_connection()"
```

### No New Dividends Found

This is normal! Companies only announce dividends quarterly (or monthly for REITs).

**Expected behavior:**
- Most weeks: 0-5 new dividends across all 175 companies
- Dividend season (Feb, May, Aug, Nov): 20-50 new dividends

### Rate Limiting

If you see "Rate limit exceeded":

```bash
# The scripts already handle this automatically with 0.5s delays
# If you're running manually in parallel, wait and retry:
sleep 60
.venv/bin/python scripts/refresh_dividends.py
```

### Duplicate Detection

The `bulk_insert_dividends()` function automatically skips duplicates based on `(company_id, ex_dividend_date)`, so running the refresh multiple times is safe.

## Performance

**Refresh time estimates:**
- 10 companies: ~30 seconds
- 50 companies: ~2 minutes
- 175 companies: ~6-8 minutes

**API usage:**
- 2-3 requests per company (CIK lookup, submissions, company facts)
- Rate limited to 10 req/sec
- ~350-525 requests for full refresh

## Integration with divscout-web

After automation runs, the frontend will automatically see new data since it queries the same PostgreSQL database.

**No additional steps needed** - the web app reads from `dividend_events` table which is automatically updated by the refresh script.

## Best Practices

1. **Use weekly refresh** - catches new dividends within days
2. **Monitor logs** - set up log rotation and occasional review
3. **Test dry-run first** - always test with `--dry-run` before scheduling
4. **Keep backups** - regular PostgreSQL backups of the database
5. **Update incrementally** - don't do full reloads unless necessary

6. **Don't run refresh daily** - unnecessary API load, companies don't announce that often
7. **Don't run multiple instances** - can hit rate limits
8. **Don't skip error handling** - always redirect stderr to logs

## Example Full Setup

```bash
# 1. Initial setup
cd /home/sean/Python/DivScout
mkdir -p logs

# 2. Initial data load (one time)
.venv/bin/python scripts/populate_all_companies.py

# 3. Clean up low confidence
.venv/bin/python scripts/cleanup_annual_totals.py --yes

# 4. Test refresh
.venv/bin/python scripts/refresh_dividends.py --dry-run
.venv/bin/python scripts/refresh_dividends.py

# 5. Set up automation
crontab -e
# Add: 0 2 * * 0 cd /home/sean/Python/DivScout && .venv/bin/python scripts/refresh_dividends.py >> logs/refresh.log 2>&1

# 6. Verify cron is set
crontab -l

# Done! Automation is now running.
```
