"""
Wipe all data from database tables
USE WITH CAUTION - THIS DELETES EVERYTHING!
"""

import sys
import os
import psycopg2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_connection import db

def wipe_database():
    """Wipe all data from database"""
    
    print("="*70)
    print("DATABASE WIPE UTILITY")
    print("="*70)
    print("\nThis will permanently delete ALL data from:")
    print("  - Companies")
    print("  - Dividend events")
    print("  - Data collection logs")
    print("  - Data sources")
    print("  - Company fundamentals")
    print("  - Dividend metrics")
    print("  - Stock splits")
    print("  - Company notes")
    print("\nThis action CANNOT be undone!")
    print("="*70)
    
    response = input("\nType 'Confirm' to proceed: ")
    
    if response != "Confirm":
        print("\nCancelled - database not modified")
        return False
    
    try:
        conn = psycopg2.connect(**db.config)
        cursor = conn.cursor()
        
        print("\nDeleting all data...")
        
        cursor.execute("TRUNCATE TABLE dividend_events CASCADE")
        print("  ✓ Cleared dividend_events")
        
        cursor.execute("TRUNCATE TABLE data_collection_log CASCADE")
        print("  ✓ Cleared data_collection_log")
        
        cursor.execute("TRUNCATE TABLE data_sources CASCADE")
        print("  ✓ Cleared data_sources")
        
        cursor.execute("TRUNCATE TABLE company_fundamentals CASCADE")
        print("  ✓ Cleared company_fundamentals")
        
        cursor.execute("TRUNCATE TABLE dividend_metrics CASCADE")
        print("  ✓ Cleared dividend_metrics")
        
        cursor.execute("TRUNCATE TABLE stock_splits CASCADE")
        print("  ✓ Cleared stock_splits")
        
        cursor.execute("TRUNCATE TABLE company_notes CASCADE")
        print("  ✓ Cleared company_notes")
        
        cursor.execute("TRUNCATE TABLE companies CASCADE")
        print("  ✓ Cleared companies")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n✓ All data deleted successfully")
        print("Database is now empty and ready for fresh scraping\n")
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        if conn:
            conn.rollback()
        return False

if __name__ == "__main__":
    if not wipe_database():
        sys.exit(1)