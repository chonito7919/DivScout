"""
Admin tool for finding and cleaning up bad data
Detects: duplicates, anomalies, inconsistencies

Usage:
    python admin_cleanup.py --find-duplicates
    python admin_cleanup.py --find-anomalies
    python admin_cleanup.py --find-all
    python admin_cleanup.py --fix-duplicates --dry-run
"""

import argparse
import sys
import os
from datetime import datetime, timedelta
import psycopg2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_connection import db


class AdminCleanup:
    """
    Tool for finding and fixing data quality issues
    """
    
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.conn = None
        self.cursor = None
        self.issues_found = []
    
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**db.config)
            self.cursor = self.conn.cursor()
            print("✓ Connected to database\n")
            return True
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            return False
    
    def find_duplicate_dividends(self):
        """
        Find potential duplicate dividend records
        Same company, same amount, similar dates
        """
        if not self.cursor:
            print("✗ No database connection")
            return

        print("="*70)
        print("SEARCHING FOR DUPLICATE DIVIDENDS")
        print("="*70)
        
        query = """
            SELECT 
                c.ticker,
                c.company_name,
                de1.dividend_id as id1,
                de2.dividend_id as id2,
                de1.amount,
                de1.ex_dividend_date as date1,
                de2.ex_dividend_date as date2,
                ABS(de2.ex_dividend_date - de1.ex_dividend_date) as days_apart
            FROM dividend_events de1
            JOIN dividend_events de2 ON 
                de1.company_id = de2.company_id
                AND de1.dividend_id < de2.dividend_id
                AND de1.amount = de2.amount
                AND ABS(de2.ex_dividend_date - de1.ex_dividend_date) <= 7
            JOIN companies c ON de1.company_id = c.company_id
            ORDER BY c.ticker, de1.ex_dividend_date
        """
        
        self.cursor.execute(query)
        results = self.cursor.fetchall()
        
        if not results:
            print("✓ No duplicate dividends found\n")
            return []
        
        duplicates = []
        print(f"⚠️  Found {len(results)} potential duplicates:\n")
        
        for row in results:
            ticker, name, id1, id2, amount, date1, date2, days_apart = row
            
            print(f"{ticker} - ${amount:.4f}")
            print(f"  ID {id1}: {date1}")
            print(f"  ID {id2}: {date2}")
            print(f"  Days apart: {days_apart:.1f}")
            print()
            
            duplicates.append({
                'ticker': ticker,
                'id1': id1,
                'id2': id2,
                'amount': amount,
                'date1': date1,
                'date2': date2
            })
            
            self.issues_found.append(f"Duplicate: {ticker} ID {id1} and {id2}")
        
        return duplicates
    
    def find_anomalous_amounts(self):
        """
        Find dividends with unusual amounts
        - Too high (>$50)
        - Too low (<$0.01)
        - Big jumps (>200% increase)
        """
        if not self.cursor:
            print("✗ No database connection")
            return []
    
        print("="*70)
        print("SEARCHING FOR ANOMALOUS DIVIDEND AMOUNTS")
        print("="*70)
    
        anomalies = []
    
        # Find amounts outside normal range
        self.cursor.execute("""
            SELECT 
                c.ticker,
                c.company_name,
                de.dividend_id,
                de.amount,
                de.ex_dividend_date
            FROM dividend_events de
            JOIN companies c ON de.company_id = c.company_id
            WHERE de.amount > 50 OR de.amount < 0.01
            ORDER BY de.amount DESC
        """)
    
        results = self.cursor.fetchall()
    
        if results:
            print(f"\n⚠️  Found {len(results)} dividends with unusual amounts:\n")
            for row in results:
                ticker, name, div_id, amount, date = row
                reason = "Too high" if amount > 50 else "Too low"
                print(f"{ticker} (ID {div_id}): ${amount:.4f} on {date} - {reason}")
            
                anomalies.append({
                    'ticker': ticker,
                    'id': div_id,
                    'amount': amount,
                    'date': date,
                    'reason': reason
                })
            
                self.issues_found.append(f"Anomaly: {ticker} ${amount:.4f} - {reason}")
        else:
            print("✓ No amount anomalies found")
    
        # Find big jumps (>200% increase)
        print("\n" + "-"*70)
        print("Checking for large dividend increases (>200%)...")
        print("-"*70)
    
        self.cursor.execute("""
            SELECT 
                c.ticker,
                de1.dividend_id,
                de1.amount as old_amount,
                de1.ex_dividend_date as old_date,
                de2.dividend_id,
                de2.amount as new_amount,
                de2.ex_dividend_date as new_date,
                ((de2.amount - de1.amount) / de1.amount * 100) as pct_change
            FROM dividend_events de1
            JOIN dividend_events de2 ON 
                de1.company_id = de2.company_id
                AND de2.ex_dividend_date > de1.ex_dividend_date
                AND de2.ex_dividend_date < de1.ex_dividend_date + INTERVAL '365 days'
            JOIN companies c ON de1.company_id = c.company_id
            WHERE ((de2.amount - de1.amount) / de1.amount) > 2.0
            ORDER BY pct_change DESC
        """)
    
        results = self.cursor.fetchall()
    
        if results:
            print(f"\n⚠️  Found {len(results)} large increases:\n")
            for row in results:
                ticker, id1, old_amt, old_date, id2, new_amt, new_date, pct = row
                print(f"{ticker}:")
                print(f"  {old_date}: ${old_amt:.4f} → {new_date}: ${new_amt:.4f}")
                print(f"  Increase: {pct:.1f}%")
                print()
            
                anomalies.append({
                    'ticker': ticker,
                    'id': id2,
                    'amount': new_amt,
                    'date': new_date,
                    'reason': f'Large increase ({pct:.1f}%)'
                })
            
                self.issues_found.append(f"Large jump: {ticker} +{pct:.1f}%")
        else:
            print("✓ No large increases found")
    
        print()
        return anomalies
    
    def find_date_inconsistencies(self):
        """
        Find dividends with illogical dates
        - Ex-date after payment date
        - Record date before ex-date
        - Dates far in the future
        """
        if not self.cursor:
            print("✗ No database connection")
            return
        
        print("="*70)
        print("SEARCHING FOR DATE INCONSISTENCIES")
        print("="*70)
        
        inconsistencies = []
        today = datetime.now().date()
        
        # Find ex-date after payment date
        self.cursor.execute("""
            SELECT 
                c.ticker,
                de.dividend_id,
                de.amount,
                de.ex_dividend_date,
                de.payment_date
            FROM dividend_events de
            JOIN companies c ON de.company_id = c.company_id
            WHERE de.payment_date IS NOT NULL
            AND de.ex_dividend_date > de.payment_date
        """)
        
        results = self.cursor.fetchall()
        
        if results:
            print(f"\n⚠️  Found {len(results)} dividends with ex-date after payment date:\n")
            for row in results:
                ticker, div_id, amount, ex_date, pay_date = row
                print(f"{ticker} (ID {div_id}): Ex {ex_date} > Pay {pay_date}")
                
                inconsistencies.append({
                    'ticker': ticker,
                    'id': div_id,
                    'reason': 'Ex-date after payment date'
                })
                
                self.issues_found.append(f"Date error: {ticker} ID {div_id}")
        else:
            print("✓ No ex-date/payment-date inconsistencies")
        
        # Find dates far in the future (>1 year)
        future_limit = today + timedelta(days=365)
        
        self.cursor.execute("""
            SELECT 
                c.ticker,
                de.dividend_id,
                de.amount,
                de.ex_dividend_date
            FROM dividend_events de
            JOIN companies c ON de.company_id = c.company_id
            WHERE de.ex_dividend_date > %s
        """, (future_limit,))
        
        results = self.cursor.fetchall()
        
        if results:
            print(f"\n⚠️  Found {len(results)} dividends with dates far in future:\n")
            for row in results:
                ticker, div_id, amount, ex_date = row
                days_future = (ex_date - today).days
                print(f"{ticker} (ID {div_id}): {ex_date} ({days_future} days from now)")
                
                inconsistencies.append({
                    'ticker': ticker,
                    'id': div_id,
                    'reason': 'Date far in future'
                })
                
                self.issues_found.append(f"Future date: {ticker} ID {div_id}")
        else:
            print("✓ No far-future dates found")
        
        print()
        return inconsistencies
    
    def fix_duplicates(self, duplicates):
        """
        Fix duplicate dividends by keeping the earlier one
        """
        if not self.cursor or not self.conn:
            print("✗ No database connection")
            return
        if not duplicates:
            print("No duplicates to fix")
            return
        
        print("="*70)
        print("FIXING DUPLICATE DIVIDENDS")
        print("="*70)
        
        if self.dry_run:
            print("[DRY RUN MODE - No changes will be made]\n")
        
        fixed_count = 0
        
        for dup in duplicates:
            # Keep the earlier dividend (lower ID), delete the later one
            id_to_delete = dup['id2']
            id_to_keep = dup['id1']
            
            print(f"Deleting {dup['ticker']} ID {id_to_delete} (keeping ID {id_to_keep})")
            
            if not self.dry_run:
                try:
                    self.cursor.execute(
                        "DELETE FROM dividend_events WHERE dividend_id = %s",
                        (id_to_delete,)
                    )
                    fixed_count += 1
                except Exception as e:
                    print(f"  ✗ Failed: {e}")
        
        if not self.dry_run and fixed_count > 0:
            self.conn.commit()
            print(f"\n✓ Fixed {fixed_count} duplicate dividends")
        elif self.dry_run:
            print(f"\n[DRY RUN] Would delete {len(duplicates)} duplicates")
    
    def generate_report(self):
        """
        Generate summary report of all issues found
        """
        print("\n" + "="*70)
        print("CLEANUP REPORT SUMMARY")
        print("="*70)
        
        if not self.issues_found:
            print("✓ No data quality issues found!")
        else:
            print(f"⚠️  Found {len(self.issues_found)} issues:\n")
            
            # Group by type
            issue_types = {}
            for issue in self.issues_found:
                issue_type = issue.split(':')[0]
                if issue_type not in issue_types:
                    issue_types[issue_type] = 0
                issue_types[issue_type] += 1
            
            for issue_type, count in sorted(issue_types.items()):
                print(f"  {issue_type}: {count}")
        
        print("="*70 + "\n")
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Find and fix data quality issues',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find all issues
  python admin_cleanup.py --find-all
  
  # Find only duplicates
  python admin_cleanup.py --find-duplicates
  
  # Find and fix duplicates (preview first)
  python admin_cleanup.py --fix-duplicates --dry-run
  
  # Actually fix duplicates
  python admin_cleanup.py --fix-duplicates
        """
    )
    
    parser.add_argument('--find-duplicates', action='store_true',
                        help='Find duplicate dividends')
    parser.add_argument('--find-anomalies', action='store_true',
                        help='Find unusual dividend amounts')
    parser.add_argument('--find-dates', action='store_true',
                        help='Find date inconsistencies')
    parser.add_argument('--find-all', action='store_true',
                        help='Find all issues')
    parser.add_argument('--fix-duplicates', action='store_true',
                        help='Fix duplicate dividends')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview without making changes')
    
    args = parser.parse_args()
    
    # Default to find-all if nothing specified
    if not any([args.find_duplicates, args.find_anomalies, args.find_dates, 
                args.find_all, args.fix_duplicates]):
        args.find_all = True
    
    # Create cleanup tool
    cleanup = AdminCleanup(dry_run=args.dry_run)
    
    if not cleanup.connect():
        return 1
    
    try:
        duplicates = []
        
        # Find issues
        if args.find_all or args.find_duplicates or args.fix_duplicates:
            duplicates = cleanup.find_duplicate_dividends()
        
        if args.find_all or args.find_anomalies:
            cleanup.find_anomalous_amounts()
        
        if args.find_all or args.find_dates:
            cleanup.find_date_inconsistencies()
        
        # Fix issues
        if args.fix_duplicates and duplicates:
            cleanup.fix_duplicates(duplicates)
        
        # Generate report
        cleanup.generate_report()
        
        return 0
        
    finally:
        cleanup.close()


if __name__ == "__main__":
    sys.exit(main())