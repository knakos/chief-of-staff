#!/usr/bin/env python3
"""
Database optimization script for Chief of Staff.
Applies indexes, optimizations, and maintains database health.
"""
import sqlite3
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def optimize_database(db_path: str = "./cos.db"):
    """Apply optimizations to the SQLite database."""
    
    if not Path(db_path).exists():
        logger.info(f"Database {db_path} does not exist yet. Skipping optimization.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        logger.info("Starting database optimization...")
        
        # Enable WAL mode for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        
        # Set optimal SQLite settings
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=10000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=268435456")  # 256MB memory map
        
        # Create additional indexes if they don't exist
        indexes = [
            # Projects table indexes
            "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)",
            "CREATE INDEX IF NOT EXISTS idx_projects_created ON projects(created_at)",
            
            # Tasks table indexes  
            "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project_id, status)",
            
            # Emails table indexes
            "CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status)",
            "CREATE INDEX IF NOT EXISTS idx_emails_thread_id ON emails(thread_id)",
            "CREATE INDEX IF NOT EXISTS idx_emails_project_id ON emails(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_emails_received ON emails(received_at)",
            "CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender)",
            "CREATE INDEX IF NOT EXISTS idx_emails_project_status ON emails(project_id, status)",
            
            # Context entries indexes
            "CREATE INDEX IF NOT EXISTS idx_context_type ON context_entries(type)",
            "CREATE INDEX IF NOT EXISTS idx_context_project ON context_entries(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_context_created ON context_entries(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_context_expires ON context_entries(expires_at)",
            
            # Jobs table indexes
            "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(type)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_status_type ON jobs(status, type)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority, created_at)",
            
            # Interviews table indexes
            "CREATE INDEX IF NOT EXISTS idx_interviews_status ON interviews(status)",
            "CREATE INDEX IF NOT EXISTS idx_interviews_asked ON interviews(asked_at)",
            "CREATE INDEX IF NOT EXISTS idx_interviews_project ON interviews(project_id)",
            
            # Digests table indexes
            "CREATE INDEX IF NOT EXISTS idx_digests_type ON digests(type)",
            "CREATE INDEX IF NOT EXISTS idx_digests_created ON digests(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_digests_project ON digests(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_digests_period ON digests(period_start, period_end)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
            logger.info(f"Applied: {index_sql.split()[:4]}")
        
        # Update table statistics for query optimizer
        cursor.execute("ANALYZE")
        
        # Vacuum to reclaim space and optimize layout
        cursor.execute("VACUUM")
        
        conn.commit()
        logger.info("Database optimization completed successfully!")
        
        # Show database info
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes_count = len(cursor.fetchall())
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables_count = len(cursor.fetchall())
        
        # Get database size
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]
        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]
        db_size_mb = (page_count * page_size) / 1024 / 1024
        
        logger.info(f"Database stats: {tables_count} tables, {indexes_count} indexes, {db_size_mb:.2f} MB")
        
    except sqlite3.Error as e:
        logger.error(f"Database optimization failed: {e}")
        conn.rollback()
    finally:
        conn.close()

def cleanup_old_data(db_path: str = "./cos.db", days: int = 30):
    """Clean up old data to maintain performance."""
    
    if not Path(db_path).exists():
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        logger.info(f"Cleaning up data older than {days} days...")
        
        # Delete old completed jobs
        cursor.execute("""
            DELETE FROM jobs 
            WHERE status = 'completed' 
            AND completed_at < datetime('now', '-{} days')
        """.format(days))
        completed_jobs_deleted = cursor.rowcount
        
        # Delete old dismissed interviews  
        cursor.execute("""
            DELETE FROM interviews 
            WHERE status = 'dismissed' 
            AND dismissed_at < datetime('now', '-{} days')
        """.format(days))
        interviews_deleted = cursor.rowcount
        
        # Delete expired context entries
        cursor.execute("""
            DELETE FROM context_entries 
            WHERE expires_at IS NOT NULL 
            AND expires_at < datetime('now')
        """)
        context_deleted = cursor.rowcount
        
        # Delete old processed emails (keep for 90 days)
        cursor.execute("""
            DELETE FROM emails 
            WHERE status = 'archived' 
            AND processed_at < datetime('now', '-90 days')
        """)
        emails_deleted = cursor.rowcount
        
        conn.commit()
        logger.info(f"Cleanup completed: {completed_jobs_deleted} jobs, {interviews_deleted} interviews, {context_deleted} context entries, {emails_deleted} emails deleted")
        
    except sqlite3.Error as e:
        logger.error(f"Cleanup failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    optimize_database()
    cleanup_old_data()