#!/usr/bin/env python3
"""
Migration script to add recipient fields to emails table.
Fixes the recipient extraction issue by adding proper schema.
"""
import sqlite3
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_email_schema():
    """Add recipient fields to emails table"""
    conn = None
    try:
        # Connect to database
        conn = sqlite3.connect('cos.db')
        cursor = conn.cursor()
        
        logger.info("Starting email schema migration...")
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(emails)")
        columns = [row[1] for row in cursor.fetchall()]
        logger.info(f"Current email table columns: {columns}")
        
        migrations_needed = []
        
        # Check for missing recipient columns
        if 'to_recipients' not in columns:
            migrations_needed.append("ADD COLUMN to_recipients TEXT")
            
        if 'cc_recipients' not in columns:
            migrations_needed.append("ADD COLUMN cc_recipients TEXT")
            
        if 'bcc_recipients' not in columns:
            migrations_needed.append("ADD COLUMN bcc_recipients TEXT")
            
        # Check for other missing columns from the new Email model
        missing_columns = {
            'thread_id': 'ADD COLUMN thread_id VARCHAR',
            'message_id': 'ADD COLUMN message_id VARCHAR', 
            'outlook_id': 'ADD COLUMN outlook_id VARCHAR',
            'sender_name': 'ADD COLUMN sender_name VARCHAR',
            'body_content_type': 'ADD COLUMN body_content_type VARCHAR DEFAULT "text"',
            'processed_at': 'ADD COLUMN processed_at DATETIME',
            'last_synced_at': 'ADD COLUMN last_synced_at DATETIME',
            'created_at': 'ADD COLUMN created_at DATETIME',
            'updated_at': 'ADD COLUMN updated_at DATETIME',
            'is_read': 'ADD COLUMN is_read BOOLEAN DEFAULT 0',
            'conversation_id': 'ADD COLUMN conversation_id VARCHAR',
            'internet_message_id': 'ADD COLUMN internet_message_id VARCHAR',
            'web_link': 'ADD COLUMN web_link VARCHAR',
            'project_id': 'ADD COLUMN project_id VARCHAR',
            'confidence': 'ADD COLUMN confidence FLOAT',
            'provenance': 'ADD COLUMN provenance VARCHAR',
            'linked_at': 'ADD COLUMN linked_at DATETIME',
            'status': 'ADD COLUMN status VARCHAR DEFAULT "unprocessed"',
            'folder': 'ADD COLUMN folder VARCHAR',
            'summary': 'ADD COLUMN summary TEXT',
            'extracted_tasks': 'ADD COLUMN extracted_tasks TEXT',
            'suggested_actions': 'ADD COLUMN suggested_actions TEXT'
        }
        
        for column, migration in missing_columns.items():
            if column not in columns:
                migrations_needed.append(migration)
        
        if not migrations_needed:
            logger.info("Email schema is already up to date!")
            return True
            
        logger.info(f"Applying {len(migrations_needed)} schema migrations...")
        
        # Apply migrations
        for migration in migrations_needed:
            try:
                sql = f"ALTER TABLE emails {migration}"
                logger.info(f"Executing: {sql}")
                cursor.execute(sql)
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to apply migration '{migration}': {e}")
                conn.rollback()
                return False
        
        # Add indexes for performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_email_outlook_id ON emails(outlook_id)",
            "CREATE INDEX IF NOT EXISTS idx_email_sender ON emails(sender)",
            "CREATE INDEX IF NOT EXISTS idx_email_received_at ON emails(received_at)", 
            "CREATE INDEX IF NOT EXISTS idx_email_is_read ON emails(is_read)",
            "CREATE INDEX IF NOT EXISTS idx_email_status ON emails(status)",
            "CREATE INDEX IF NOT EXISTS idx_email_project_id ON emails(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_email_conversation_id ON emails(conversation_id)",
            "CREATE INDEX IF NOT EXISTS idx_email_folder ON emails(folder)"
        ]
        
        logger.info("Adding performance indexes...")
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
                conn.commit()
            except Exception as e:
                logger.warning(f"Index creation failed (may already exist): {e}")
        
        # Set default timestamps for existing records
        current_time = datetime.utcnow().isoformat()
        cursor.execute(f"""
            UPDATE emails 
            SET created_at = ?, updated_at = ?, status = 'unprocessed'
            WHERE created_at IS NULL
        """, (current_time, current_time))
        conn.commit()
        
        logger.info("✅ Email schema migration completed successfully!")
        
        # Verify the schema
        cursor.execute("PRAGMA table_info(emails)")
        new_columns = [row[1] for row in cursor.fetchall()]
        logger.info(f"Updated email table columns: {sorted(new_columns)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = migrate_email_schema()
    if success:
        print("✅ Migration completed successfully!")
    else:
        print("❌ Migration failed!")
        exit(1)