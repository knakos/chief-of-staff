#!/usr/bin/env python3
"""
Direct database test to isolate database vs API issue.
This script bypasses the API layer and tests database updates directly.
"""
import sys
import os

# Add the backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Project

# Database connection
DATABASE_URL = "sqlite:///./cos.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_project_update():
    """Test direct database project update"""
    project_id = "a64bb0f3-66c3-4bfd-b5fe-513aeacaeb71"
    test_name = "DIRECT DB TEST UPDATE"
    
    print("=" * 60)
    print("DIRECT DATABASE UPDATE TEST")
    print("=" * 60)
    
    # Create database session
    db = SessionLocal()
    
    try:
        # 1. Get current project state
        project = db.query(Project).filter_by(id=project_id).first()
        if not project:
            print(f"[ERROR] Project not found: {project_id}")
            return
        
        print(f"[INFO] Current project name: '{project.name}'")
        print(f"[INFO] Current project description: '{project.description}'")
        
        # 2. Update project name
        old_name = project.name
        project.name = test_name
        project.description = "Updated via direct database access for testing"
        
        print(f"[UPDATE] Updating project name from '{old_name}' to '{test_name}'...")
        
        # 3. Commit changes
        db.commit()
        print("[SUCCESS] Database commit successful")
        
        # 4. Refresh from database to verify changes
        db.refresh(project)
        print(f"[AFTER] After commit - project name: '{project.name}'")
        print(f"[AFTER] After commit - project description: '{project.description}'")
        
        # 5. Create new session and query again to verify persistence
        db.close()
        db = SessionLocal()
        project_check = db.query(Project).filter_by(id=project_id).first()
        
        if project_check:
            print(f"[VERIFY] Fresh query - project name: '{project_check.name}'")
            print(f"[VERIFY] Fresh query - project description: '{project_check.description}'")
            
            if project_check.name == test_name:
                print("[SUCCESS] Direct database update is working correctly!")
                print("[CONCLUSION] The issue is likely in the API layer, not the database layer.")
            else:
                print("[FAILURE] Direct database update failed!")
                print("[CONCLUSION] The issue is at the database level.")
        else:
            print("[FAILURE] Could not retrieve project after update")
        
    except Exception as e:
        print(f"[ERROR] Error during database update: {e}")
        db.rollback()
        
    finally:
        db.close()
        
    print("=" * 60)

if __name__ == "__main__":
    test_project_update()