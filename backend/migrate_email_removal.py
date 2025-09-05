#!/usr/bin/env python3
"""
Database migration script to update schema after removing Email table.
- Drops emails table if it exists
- Updates jobs table: related_email_id -> related_email_outlook_id
- Updates interviews table: related_email_id -> related_email_outlook_id
"""
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """Migrate database schema to remove email table dependencies"""
    
    # Get database URL
    DATABASE_URL = "sqlite:///./cos.db"
    engine = create_engine(DATABASE_URL)
    
    logger.info("Starting database migration for email table removal...")
    
    with engine.connect() as conn:
        # Start a transaction
        trans = conn.begin()
        
        try:
            # 1. Check if emails table exists and drop it
            logger.info("1. Dropping emails table if it exists...")
            conn.execute(text("DROP TABLE IF EXISTS emails"))
            logger.info("✅ Emails table dropped")
            
            # 2. Check if old columns exist in jobs table and migrate
            logger.info("2. Migrating jobs table...")
            
            # Check if related_email_id exists
            result = conn.execute(text("PRAGMA table_info(jobs)"))
            columns = [row[1] for row in result]
            
            if 'related_email_id' in columns:
                logger.info("Found old related_email_id column, migrating...")
                
                # SQLite doesn't support dropping columns directly, so we need to recreate the table
                # First, get the current data
                jobs_data = conn.execute(text("SELECT * FROM jobs")).fetchall()
                
                # Get current schema (without related_email_id)
                conn.execute(text("""
                    CREATE TABLE jobs_new (
                        id TEXT PRIMARY KEY,
                        type TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        priority INTEGER DEFAULT 3,
                        created_at DATETIME,
                        started_at DATETIME,
                        completed_at DATETIME,
                        input_data TEXT,
                        result_data TEXT,
                        error_message TEXT,
                        progress REAL DEFAULT 0.0,
                        related_project_id TEXT,
                        related_email_outlook_id TEXT
                    )
                """))
                
                # Copy data from old table to new table
                for row in jobs_data:
                    # Map the data, converting related_email_id to related_email_outlook_id
                    conn.execute(text("""
                        INSERT INTO jobs_new 
                        (id, type, status, priority, created_at, started_at, completed_at, 
                         input_data, result_data, error_message, progress, related_project_id, related_email_outlook_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """), (
                        row[0], row[1], row[2], row[3], row[4], row[5], row[6],
                        row[7], row[8], row[9], row[10], row[11], row[12] if len(row) > 12 else None
                    ))
                
                # Replace old table with new table
                conn.execute(text("DROP TABLE jobs"))
                conn.execute(text("ALTER TABLE jobs_new RENAME TO jobs"))
                
                # Recreate indexes
                conn.execute(text("CREATE INDEX idx_job_status_type ON jobs(status, type)"))
                conn.execute(text("CREATE INDEX idx_job_created ON jobs(created_at)"))
                
                logger.info("✅ Jobs table migrated successfully")
            else:
                logger.info("Jobs table already has correct schema")
            
            # 3. Check if old columns exist in interviews table and migrate
            logger.info("3. Migrating interviews table...")
            
            result = conn.execute(text("PRAGMA table_info(interviews)"))
            columns = [row[1] for row in result]
            
            if 'related_email_id' in columns:
                logger.info("Found old related_email_id column in interviews, migrating...")
                
                # Get current data
                interviews_data = conn.execute(text("SELECT * FROM interviews")).fetchall()
                
                # Create new table structure
                conn.execute(text("""
                    CREATE TABLE interviews_new (
                        id TEXT PRIMARY KEY,
                        status TEXT DEFAULT 'pending',
                        question TEXT NOT NULL,
                        answer TEXT,
                        asked_at DATETIME,
                        answered_at DATETIME,
                        dismissed_at DATETIME,
                        trigger_source TEXT,
                        importance_score REAL DEFAULT 0.5,
                        project_id TEXT,
                        related_email_outlook_id TEXT
                    )
                """))
                
                # Copy data
                for row in interviews_data:
                    conn.execute(text("""
                        INSERT INTO interviews_new 
                        (id, status, question, answer, asked_at, answered_at, dismissed_at,
                         trigger_source, importance_score, project_id, related_email_outlook_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """), (
                        row[0], row[1], row[2], row[3], row[4], row[5], row[6],
                        row[7], row[8], row[9], row[10] if len(row) > 10 else None
                    ))
                
                # Replace tables
                conn.execute(text("DROP TABLE interviews"))
                conn.execute(text("ALTER TABLE interviews_new RENAME TO interviews"))
                
                logger.info("✅ Interviews table migrated successfully")
            else:
                logger.info("Interviews table already has correct schema")
            
            # 4. Recreate all tables with current schema to ensure consistency
            logger.info("4. Ensuring all tables match current schema...")
            
            # Import and recreate all tables
            import sys
            sys.path.append('.')
            from models import Base
            
            # This will create any missing tables and ensure schema is up to date
            Base.metadata.create_all(bind=engine)
            logger.info("✅ All tables updated to current schema")
            
            # Commit the transaction
            trans.commit()
            logger.info("✅ Database migration completed successfully!")
            
        except Exception as e:
            trans.rollback()
            logger.error(f"❌ Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate_database()