"""
Database connection and operations module
Handles all PostgreSQL interactions
Enhanced with confidence scoring and review workflow
"""

import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from config import DATABASE_CONFIG


class DatabaseConnection:
    """Manages database connections and operations"""
    
    def __init__(self):
        self.config = DATABASE_CONFIG
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = psycopg2.connect(**self.config)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def test_connection(self):
        """Test database connectivity"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    version = cur.fetchone()[0]
                    print(f"✔ Database connected successfully")
                    print(f"  PostgreSQL version: {version}")
                    return True
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            return False
    
    def get_or_create_company(self, ticker, company_name=None, cik=None):
        """
        Get company_id for a ticker, or create new company entry
        Returns: company_id
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Try to find existing company
                cur.execute(
                    "SELECT company_id FROM companies WHERE ticker = %s",
                    (ticker,)
                )
                result = cur.fetchone()
                
                if result:
                    return result[0]
                
                # Create new company
                cur.execute(
                    """
                    INSERT INTO companies (ticker, company_name, cik, is_active)
                    VALUES (%s, %s, %s, true)
                    RETURNING company_id
                    """,
                    (ticker, company_name, cik)
                )
                company_id = cur.fetchone()[0]
                print(f"  Created new company: {ticker} (ID: {company_id})")
                return company_id
    
    def get_company_by_cik(self, cik):
        """
        Get company by CIK (useful for XBRL data which uses CIK)
        Returns: dict with company data or None
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM companies WHERE cik = %s",
                    (cik,)
                )
                return cur.fetchone()
    
    def insert_dividend(self, company_id, dividend_data):
        """
        Insert a dividend event with confidence scoring
        dividend_data should contain: ex_dividend_date, amount, confidence, etc.
        Returns: dividend_id or None if duplicate
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Check for duplicate
                cur.execute(
                    """
                    SELECT dividend_id FROM dividend_events
                    WHERE company_id = %s AND ex_dividend_date = %s
                    """,
                    (company_id, dividend_data['ex_dividend_date'])
                )
                
                if cur.fetchone():
                    return None  # Duplicate
                
                # Insert new dividend with confidence data
                cur.execute(
                    """
                    INSERT INTO dividend_events (
                        company_id,
                        declaration_date,
                        ex_dividend_date,
                        record_date,
                        payment_date,
                        amount,
                        frequency,
                        dividend_type,
                        fiscal_year,
                        fiscal_quarter,
                        confidence,
                        needs_review,
                        confidence_reasons,
                        period_type,
                        period_days,
                        review_status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING dividend_id
                    """,
                    (
                        company_id,
                        dividend_data.get('declaration_date'),
                        dividend_data['ex_dividend_date'],
                        dividend_data.get('record_date'),
                        dividend_data.get('payment_date'),
                        dividend_data['amount'],
                        dividend_data.get('frequency', 'quarterly'),
                        dividend_data.get('dividend_type', 'cash'),
                        dividend_data.get('fiscal_year'),
                        dividend_data.get('fiscal_quarter'),
                        dividend_data.get('confidence', 1.0),
                        dividend_data.get('needs_review', False),
                        ', '.join(dividend_data.get('confidence_reasons', [])) if dividend_data.get('confidence_reasons') else None,
                        dividend_data.get('period_type'),
                        dividend_data.get('period_days'),
                        'pending' if dividend_data.get('needs_review') else 'approved'
                    )
                )
                dividend_id = cur.fetchone()[0]
                return dividend_id
    
    def bulk_insert_dividends(self, company_id, dividends_list):
        """
        Insert multiple dividends efficiently with confidence scores
        dividends_list: list of dividend_data dictionaries
        Returns: tuple (inserted_count, skipped_count, review_count)
        """
        inserted = 0
        skipped = 0
        needs_review = 0
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                for dividend_data in dividends_list:
                    # Check for duplicate
                    cur.execute(
                        """
                        SELECT dividend_id FROM dividend_events
                        WHERE company_id = %s AND ex_dividend_date = %s
                        """,
                        (company_id, dividend_data['ex_dividend_date'])
                    )
                    
                    if cur.fetchone():
                        skipped += 1
                        continue
                    
                    # Track if needs review
                    if dividend_data.get('needs_review', False):
                        needs_review += 1
                    
                    # Insert new dividend
                    cur.execute(
                        """
                        INSERT INTO dividend_events (
                            company_id,
                            declaration_date,
                            ex_dividend_date,
                            record_date,
                            payment_date,
                            amount,
                            frequency,
                            dividend_type,
                            fiscal_year,
                            fiscal_quarter,
                            confidence,
                            needs_review,
                            confidence_reasons,
                            period_type,
                            period_days,
                            review_status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            company_id,
                            dividend_data.get('declaration_date'),
                            dividend_data['ex_dividend_date'],
                            dividend_data.get('record_date'),
                            dividend_data.get('payment_date'),
                            dividend_data['amount'],
                            dividend_data.get('frequency', 'quarterly'),
                            dividend_data.get('dividend_type', 'cash'),
                            dividend_data.get('fiscal_year'),
                            dividend_data.get('fiscal_quarter'),
                            dividend_data.get('confidence', 1.0),
                            dividend_data.get('needs_review', False),
                            ', '.join(dividend_data.get('confidence_reasons', [])) if dividend_data.get('confidence_reasons') else None,
                            dividend_data.get('period_type'),
                            dividend_data.get('period_days'),
                            'pending' if dividend_data.get('needs_review') else 'approved'
                        )
                    )
                    inserted += 1
        
        return (inserted, skipped, needs_review)
    
    def get_dividends_for_review(self, company_id=None, min_confidence=0.8):
        """
        Get dividends that need manual review
        Returns: list of dividend records needing review
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT 
                        de.dividend_id,
                        c.ticker,
                        c.company_name,
                        de.ex_dividend_date,
                        de.amount,
                        de.confidence,
                        de.confidence_reasons,
                        de.fiscal_year,
                        de.fiscal_quarter,
                        de.period_type,
                        de.review_status
                    FROM dividend_events de
                    JOIN companies c ON de.company_id = c.company_id
                    WHERE de.confidence < %s 
                      AND de.review_status = 'pending'
                """
                params = [min_confidence]
                
                if company_id:
                    query += " AND de.company_id = %s"
                    params.append(company_id)
                
                query += " ORDER BY de.confidence ASC, c.ticker, de.ex_dividend_date DESC"
                
                cur.execute(query, params)
                return cur.fetchall()
    
    def get_dividend_anomalies(self, company_id=None, threshold=3.0):
        """
        Find dividends that might be annual totals based on statistical analysis
        Returns: list of potential annual totals
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    WITH company_stats AS (
                        SELECT 
                            company_id,
                            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount) as median_amount,
                            AVG(amount) as avg_amount,
                            STDDEV(amount) as std_dev
                        FROM dividend_events
                        WHERE review_status != 'deleted'
                        GROUP BY company_id
                    )
                    SELECT 
                        c.ticker,
                        de.dividend_id,
                        de.amount,
                        de.ex_dividend_date,
                        de.confidence,
                        cs.median_amount,
                        de.amount / NULLIF(cs.median_amount, 0) as ratio_to_median
                    FROM dividend_events de
                    JOIN company_stats cs ON de.company_id = cs.company_id
                    JOIN companies c ON de.company_id = c.company_id
                    WHERE de.amount > cs.median_amount * %s
                      AND de.review_status = 'pending'
                """
                params = [threshold]
                
                if company_id:
                    query += " AND de.company_id = %s"
                    params.append(company_id)
                
                query += " ORDER BY ratio_to_median DESC"
                
                cur.execute(query, params)
                return cur.fetchall()
    
    def mark_dividend_reviewed(self, dividend_id, action='approved', notes=None, reviewer='admin'):
        """
        Mark a dividend as reviewed
        action: 'approved', 'deleted', 'reviewed'
        Returns: success boolean
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE dividend_events
                    SET 
                        review_status = %s,
                        review_notes = %s,
                        reviewed_by = %s,
                        reviewed_at = CURRENT_TIMESTAMP,
                        needs_review = FALSE
                    WHERE dividend_id = %s
                    RETURNING dividend_id
                    """,
                    (action, notes, reviewer, dividend_id)
                )
                
                result = cur.fetchone()
                
                if result:
                    # Log the review action
                    cur.execute(
                        """
                        INSERT INTO dividend_review_log 
                        (dividend_id, action, review_notes, reviewed_by)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (dividend_id, action, notes, reviewer)
                    )
                    return True
                return False
    
    def bulk_delete_annual_totals(self, company_id=None, threshold=3.0, dry_run=False):
        """
        Delete likely annual totals based on statistical analysis
        Returns: (count_deleted, total_amount_deleted)
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # First, identify candidates
                anomalies = self.get_dividend_anomalies(company_id, threshold)
                
                if not anomalies:
                    return (0, 0)
                
                if dry_run:
                    total_amount = sum(a['amount'] for a in anomalies)
                    return (len(anomalies), total_amount)
                
                # Delete the identified annual totals
                deleted_count = 0
                deleted_sum = 0.0
                
                for anomaly in anomalies:
                    if anomaly['confidence'] < 0.5:  # Only delete low confidence anomalies
                        self.mark_dividend_reviewed(
                            anomaly['dividend_id'], 
                            'deleted', 
                            f"Auto-deleted: {anomaly['ratio_to_median']:.1f}x median",
                            'system'
                        )
                        deleted_count += 1
                        deleted_sum += anomaly['amount']
                
                return (deleted_count, deleted_sum)
    
    def get_company_dividend_stats(self, ticker=None):
        """
        Get dividend statistics for companies
        Returns: list of company stats
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT 
                        c.ticker,
                        c.company_name,
                        COUNT(de.dividend_id) as total_dividends,
                        COUNT(CASE WHEN de.confidence < 0.8 THEN 1 END) as low_confidence_count,
                        AVG(de.amount) as avg_amount,
                        MIN(de.amount) as min_amount,
                        MAX(de.amount) as max_amount,
                        AVG(de.confidence) as avg_confidence,
                        COUNT(CASE WHEN de.needs_review THEN 1 END) as needs_review_count
                    FROM companies c
                    LEFT JOIN dividend_events de ON c.company_id = de.company_id
                    WHERE de.review_status != 'deleted'
                """
                params = []
                
                if ticker:
                    query += " AND c.ticker = %s"
                    params.append(ticker)
                
                query += " GROUP BY c.ticker, c.company_name ORDER BY c.ticker"
                
                cur.execute(query, params) if params else cur.execute(query)
                return cur.fetchall()
    
    def refresh_materialized_views(self):
        """Refresh materialized views for statistics"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY company_dividend_stats")
                print("✔ Refreshed company dividend statistics")
    
    def log_collection_attempt(self, company_id, ticker, data_type, 
                               status, source_url=None, error_message=None,
                               records_inserted=0, processing_time=None,
                               period_start=None, period_end=None, records_flagged=0):
        """
        Log a data collection attempt to data_collection_log table
        Enhanced with review tracking
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO data_collection_log (
                        company_id,
                        ticker,
                        data_type,
                        status,
                        source_url,
                        error_message,
                        records_inserted,
                        processing_time_seconds,
                        period_start,
                        period_end
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        company_id,
                        ticker,
                        data_type,
                        status,
                        source_url,
                        error_message,
                        records_inserted,
                        processing_time,
                        period_start,
                        period_end
                    )
                )
                
                # Log if records need review
                if records_flagged > 0:
                    print(f"  ⚠️  {records_flagged} dividends flagged for review")
    
    def insert_data_source(self, company_id, source_type, source_url,
                          filing_type=None, filing_date=None, 
                          accession_number=None, notes=None):
        """
        Record where data came from for audit trail
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO data_sources (
                        company_id,
                        source_type,
                        source_url,
                        filing_type,
                        filing_date,
                        accession_number,
                        notes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING source_id
                    """,
                    (
                        company_id,
                        source_type,
                        source_url,
                        filing_type,
                        filing_date,
                        accession_number,
                        notes
                    )
                )
                return cur.fetchone()[0]
    
    def get_collection_status(self, ticker=None, data_type=None, limit=10):
        """
        Get recent collection attempts for monitoring
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT *
                    FROM data_collection_log
                    WHERE 1=1
                """
                params = []
                
                if ticker:
                    query += " AND ticker = %s"
                    params.append(ticker)
                
                if data_type:
                    query += " AND data_type = %s"
                    params.append(data_type)
                
                query += " ORDER BY collection_date DESC LIMIT %s"
                params.append(limit)
                
                cur.execute(query, params)
                return cur.fetchall()


# Convenience function for quick database operations
db = DatabaseConnection()


if __name__ == "__main__":
    # Test database connection
    print("Testing database connection...")
    if db.test_connection():
        print("\nTesting new review functions...")
        
        # Get dividends needing review
        review_needed = db.get_dividends_for_review()
        if review_needed:
            print(f"\n✔ Found {len(review_needed)} dividends needing review")
            print(f"  Lowest confidence: {review_needed[0]['confidence']:.2%}")
        
        # Get potential annual totals
        anomalies = db.get_dividend_anomalies()
        if anomalies:
            print(f"\n✔ Found {len(anomalies)} potential annual totals")
        
        print("\n✔ All database functions ready")