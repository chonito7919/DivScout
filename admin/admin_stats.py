"""
Admin tool for viewing database statistics
Provides overview before making deletion decisions

Usage:
    python admin_stats.py                  # Show all stats
    python admin_stats.py --company JNJ    # Show company details
    python admin_stats.py --recent         # Show recent activity
"""

import argparse
import sys
import os
import psycopg2
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_connection import db


class AdminStats:
    """
    Display database statistics and insights
    """
    
    def __init__(self):
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Establish database connection"""
        try:
            # Use the context manager to get a connection
            self.conn = psycopg2.connect(**db.config)
            self.cursor = self.conn.cursor()
            return True
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            return False
    
    def show_overview(self):
        """
        Show high-level database statistics
        """
        if not self.cursor:
            print("✗ No database connection")
            return
    
        print("\n" + "="*70)
        print("DATABASE OVERVIEW")
        print("="*70 + "\n")
                
        # Company counts
        self.cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN NOT is_active THEN 1 ELSE 0 END) as inactive
            FROM companies
        """)
        
        result = self.cursor.fetchone()
        print(f"Companies:")
        print(f"  Total: {result[0]}")
        print(f"  Active: {result[1]}")
        print(f"  Inactive: {result[2]}")
        
        # Dividend counts
        self.cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT company_id) as companies_with_dividends,
                MIN(ex_dividend_date) as earliest,
                MAX(ex_dividend_date) as latest
            FROM dividend_events
        """)
        
        result = self.cursor.fetchone()
        print(f"\nDividends:")
        print(f"  Total records: {result[0]}")
        print(f"  Companies with dividends: {result[1]}")
        print(f"  Date range: {result[2]} to {result[3]}")
        
        # Dividend amounts
        self.cursor.execute("""
            SELECT 
                MIN(amount) as min_amount,
                AVG(amount) as avg_amount,
                MAX(amount) as max_amount
            FROM dividend_events
        """)
        
        result = self.cursor.fetchone()
        print(f"\nDividend Amounts:")
        print(f"  Minimum: ${result[0]:.4f}")
        print(f"  Average: ${result[1]:.4f}")
        print(f"  Maximum: ${result[2]:.4f}")
        
        # Scraping activity
        self.cursor.execute("""
            SELECT 
                COUNT(*) as total_runs,
                MAX(collection_date) as last_scrape,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successes,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
            FROM data_collection_log
        """)
        
        result = self.cursor.fetchone()
        if result[0] > 0:
            print(f"\nScraping Activity:")
            print(f"  Total runs: {result[0]}")
            print(f"  Last scrape: {result[1]}")
            print(f"  Successes: {result[2]}")
            print(f"  Errors: {result[3]}")
    
    def show_company_details(self, ticker):
        """
        Show detailed information for a specific company
        """
        if not self.cursor:
            print("✗ No database connection")
            return
    
        print("\n" + "="*70)
        print("DATABASE OVERVIEW")
        print("="*70 + "\n")

        ticker = ticker.upper()
    
        # Get company info
        self.cursor.execute("""
            SELECT 
                company_id,
                company_name,
                cik,
                sector,
                industry,
                is_active
            FROM companies
            WHERE ticker = %s
        """, (ticker,))
    
        result = self.cursor.fetchone()
    
        if not result:
            print(f"✗ Company {ticker} not found")
            return
    
        company_id, name, cik, sector, industry, is_active = result
    
        print("\n" + "="*70)
        print(f"COMPANY DETAILS: {ticker}")
        print("="*70 + "\n")
    
        print(f"Name: {name}")
        print(f"CIK: {cik}")
        print(f"Sector: {sector if sector else 'N/A'}")
        print(f"Industry: {industry if industry else 'N/A'}")
        print(f"Status: {'Active' if is_active else 'Inactive'}")
    
        # Dividend statistics
        self.cursor.execute("""
            SELECT 
                COUNT(*) as total,
                MIN(ex_dividend_date) as earliest,
                MAX(ex_dividend_date) as latest,
                AVG(amount) as avg_amount,
                MIN(amount) as min_amount,
                MAX(amount) as max_amount
            FROM dividend_events
            WHERE company_id = %s
        """, (company_id,))
    
        result = self.cursor.fetchone()
    
        print(f"\nDividend History:")
        print(f"  Total records: {result[0]}")
    
        if result[0] > 0:
            print(f"  Date range: {result[1]} to {result[2]}")
            print(f"  Average amount: ${result[3]:.4f}")
            print(f"  Range: ${result[4]:.4f} - ${result[5]:.4f}")
        
            # Recent dividends
            print(f"\nRecent Dividends (last 10):")
            self.cursor.execute("""
                SELECT 
                    dividend_id,
                    amount,
                    ex_dividend_date,
                    payment_date,
                    frequency
                FROM dividend_events
                WHERE company_id = %s
                ORDER BY ex_dividend_date DESC
                LIMIT 10
            """, (company_id,))
        
            results = self.cursor.fetchall()
        
            print(f"  {'ID':<6} {'Amount':<10} {'Ex-Date':<12} {'Pay Date':<12} {'Frequency':<12}")
            print(f"  {'-'*6} {'-'*10} {'-'*12} {'-'*12} {'-'*12}")
        
            for row in results:
                div_id, amount, ex_date, pay_date, freq = row
                pay_str = str(pay_date) if pay_date else 'N/A'
                print(f"  {div_id:<6} ${amount:<9.4f} {ex_date} {pay_str:<12} {freq:<12}")
        else:
            print("  No dividend records found")
    
        # Scraping history
        self.cursor.execute("""
            SELECT 
                collection_date,
                data_type,
                records_inserted,
                status
            FROM data_collection_log
            WHERE ticker = %s
            ORDER BY collection_date DESC
            LIMIT 5
        """, (ticker,))
    
        results = self.cursor.fetchall()
    
        if results:
            print(f"\nRecent Scraping Activity (last 5):")
            print(f"  {'Date':<20} {'Type':<6} {'Found':<6} {'Status':<10}")
            print(f"  {'-'*20} {'-'*6} {'-'*6} {'-'*10}")
        
            for row in results:
                scrape_date, data_type, found, status = row
                print(f"  {str(scrape_date):<20} {data_type:<6} {found:<6} {status:<10}")
    
    def show_recent_activity(self, days=7):
        """
        Show recent scraping and dividend activity
        """
        if not self.cursor:
            print("✗ No database connection")
            return
    
        print("\n" + "="*70)
        print("DATABASE OVERVIEW")
        print("="*70 + "\n")

        cutoff_date = datetime.now().date() - timedelta(days=days)
        
        print("\n" + "="*70)
        print(f"RECENT ACTIVITY (Last {days} days)")
        print("="*70 + "\n")
        
        # Recent scraping
        self.cursor.execute("""
            SELECT 
                collection_date,
                ticker,
                data_type,
                records_inserted,
                status
            FROM data_collection_log
            WHERE collection_date >= %s
            ORDER BY collection_date DESC
        """, (cutoff_date,))
        
        results = self.cursor.fetchall()
        
        if results:
            print(f"Recent Scraping Runs ({len(results)} total):")
            print(f"  {'Date':<20} {'Ticker':<8} {'Type':<6} {'Found':<6} {'Status':<10}")
            print(f"  {'-'*20} {'-'*8} {'-'*6} {'-'*6} {'-'*10}")
            
            for row in results[:20]:  # Show max 20
                scrape_date, ticker, data_type, found, status = row
                print(f"  {str(scrape_date):<20} {ticker:<8} {data_type:<6} {found:<6} {status:<10}")
            
            if len(results) > 20:
                print(f"  ... and {len(results) - 20} more")
        else:
            print("No recent scraping activity")
        
        # Recent dividends added
        self.cursor.execute("""
            SELECT 
                c.ticker,
                c.company_name,
                de.amount,
                de.ex_dividend_date,
                de.created_at
            FROM dividend_events de
            JOIN companies c ON de.company_id = c.company_id
            WHERE de.created_at >= %s
            ORDER BY de.created_at DESC
            LIMIT 20
        """, (cutoff_date,))
        
        results = self.cursor.fetchall()
        
        if results:
            print(f"\nRecently Added Dividends ({len(results)}):")
            print(f"  {'Ticker':<8} {'Company':<30} {'Amount':<10} {'Ex-Date':<12} {'Added':<12}")
            print(f"  {'-'*8} {'-'*30} {'-'*10} {'-'*12} {'-'*12}")
            
            for row in results:
                ticker, name, amount, ex_date, created = row
                name_short = name[:27] + "..." if len(name) > 30 else name
                created_str = str(created)[:10]  # Just the date part
                print(f"  {ticker:<8} {name_short:<30} ${amount:<9.4f} {ex_date} {created_str}")
        else:
            print("\nNo dividends added recently")
    
    def show_top_dividend_payers(self, limit=10):
        """
        Show companies with highest dividend amounts
        """
        if not self.cursor:
            print("✗ No database connection")
            return
    
        print("\n" + "="*70)
        print(f"TOP {limit} DIVIDEND PAYERS (by average amount)")
        print("="*70 + "\n")
        
        self.cursor.execute("""
            SELECT 
                c.ticker,
                c.company_name,
                COUNT(de.dividend_id) as dividend_count,
                AVG(de.amount) as avg_amount,
                MAX(de.amount) as max_amount,
                MAX(de.ex_dividend_date) as latest_date
            FROM companies c
            JOIN dividend_events de ON c.company_id = de.company_id
            GROUP BY c.ticker, c.company_name
            HAVING COUNT(de.dividend_id) >= 4
            ORDER BY avg_amount DESC
            LIMIT %s
        """, (limit,))
        
        results = self.cursor.fetchall()
        
        if results:
            print(f"  {'Rank':<5} {'Ticker':<8} {'Company':<25} {'Count':<7} {'Avg $':<10} {'Max $':<10} {'Latest':<12}")
            print(f"  {'-'*5} {'-'*8} {'-'*25} {'-'*7} {'-'*10} {'-'*10} {'-'*12}")
            
            for i, row in enumerate(results, 1):
                ticker, name, count, avg, max_amt, latest = row
                name_short = name[:22] + "..." if len(name) > 25 else name
                print(f"  {i:<5} {ticker:<8} {name_short:<25} {count:<7} ${avg:<9.4f} ${max_amt:<9.4f} {latest}")
        else:
            print("No data available")
    
    def show_sectors(self):
        """
        Show breakdown by sector
        """
        if not self.cursor:
               print("✗ No database connection")
               return


        print("\n" + "="*70)
        print("COMPANIES BY SECTOR")
        print("="*70 + "\n")
        
        self.cursor.execute("""
            SELECT 
                sector,
                COUNT(*) as company_count,
                SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active_count
            FROM companies
            WHERE sector IS NOT NULL
            GROUP BY sector
            ORDER BY company_count DESC
        """)
        
        results = self.cursor.fetchall()
        
        if results:
            print(f"  {'Sector':<30} {'Total':<10} {'Active':<10}")
            print(f"  {'-'*30} {'-'*10} {'-'*10}")
            
            for row in results:
                sector, total, active = row
                print(f"  {sector:<30} {total:<10} {active:<10}")
        else:
            print("No sector data available")
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='View database statistics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show all statistics
  python admin_stats.py
  
  # Show specific company details
  python admin_stats.py --company JNJ
  
  # Show recent activity (last 7 days)
  python admin_stats.py --recent
  
  # Show recent activity (last 30 days)
  python admin_stats.py --recent --days 30
  
  # Show top dividend payers
  python admin_stats.py --top-payers
  
  # Show sector breakdown
  python admin_stats.py --sectors
        """
    )
    
    parser.add_argument('--company', help='Show details for specific company')
    parser.add_argument('--recent', action='store_true', help='Show recent activity')
    parser.add_argument('--days', type=int, default=7, help='Number of days for recent activity')
    parser.add_argument('--top-payers', action='store_true', help='Show top dividend payers')
    parser.add_argument('--sectors', action='store_true', help='Show sector breakdown')
    parser.add_argument('--all', action='store_true', help='Show all statistics')
    
    args = parser.parse_args()
    
    # Create stats viewer
    stats = AdminStats()
    
    if not stats.connect():
        return 1
    
    try:
        # If no specific option chosen, show overview
        if not any([args.company, args.recent, args.top_payers, args.sectors, args.all]):
            stats.show_overview()
        
        # Show requested stats
        if args.all:
            stats.show_overview()
            stats.show_recent_activity(args.days)
            stats.show_top_dividend_payers()
            stats.show_sectors()
        else:
            if args.company:
                stats.show_company_details(args.company)
            
            if args.recent:
                stats.show_recent_activity(args.days)
            
            if args.top_payers:
                stats.show_top_dividend_payers()
            
            if args.sectors:
                stats.show_sectors()
        
        print()  # Blank line at end
        return 0
        
    finally:
        stats.close()


if __name__ == "__main__":
    sys.exit(main())