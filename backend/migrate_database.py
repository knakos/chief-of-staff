#!/usr/bin/env python3
"""
Database migration script to add Outlook integration fields to Email model
"""
import sqlite3
import os
from datetime import datetime

def migrate_database():
    """Add new columns to emails table for Outlook integration"""
    
    db_path = "./cos.db"
    
    if not os.path.exists(db_path):
        print("Database not found - will be created on next startup")
        return
    
    print(f"Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get current table schema
    cursor.execute("PRAGMA table_info(emails)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    # Define new columns to add
    new_columns = [
        ("outlook_id", "TEXT"),
        ("sender_name", "TEXT"),
        ("body_content_type", "TEXT DEFAULT 'text'"),
        ("sent_at", "DATETIME"),
        ("last_synced_at", "DATETIME"),
        ("is_read", "BOOLEAN DEFAULT 0"),
        ("importance", "TEXT DEFAULT 'normal'"),
        ("has_attachments", "BOOLEAN DEFAULT 0"),
        ("conversation_id", "TEXT"),
        ("internet_message_id", "TEXT"),
        ("web_link", "TEXT")
    ]
    
    added_columns = []
    for column_name, column_def in new_columns:
        if column_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE emails ADD COLUMN {column_name} {column_def}")
                added_columns.append(column_name)
                print(f"✓ Added column: {column_name}")
            except sqlite3.OperationalError as e:
                print(f"✗ Failed to add column {column_name}: {e}")
    
    # Add indexes for new columns
    indexes_to_create = [
        ("idx_emails_outlook_id", "emails", "outlook_id"),
        ("idx_emails_conversation_id", "emails", "conversation_id"),
    ]
    
    for index_name, table_name, column_name in indexes_to_create:
        if column_name in added_columns or column_name in existing_columns:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})")
                print(f"✓ Created index: {index_name}")
            except sqlite3.OperationalError as e:
                print(f"✗ Failed to create index {index_name}: {e}")
    
    conn.commit()
    conn.close()
    
    if added_columns:
        print(f"\n✅ Migration completed successfully! Added {len(added_columns)} columns.")
        print("The application will now work with Outlook integration.")
    else:
        print("\n✅ Database is already up to date.")

if __name__ == "__main__":
    migrate_database()