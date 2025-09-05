"""
Database initialization script for Chief of Staff.
Creates tables and optionally adds sample data for development.
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Area, Project, Task, ContextEntry, Interview
from claude_client import ClaudeClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database(add_sample_data: bool = True):
    """Initialize database with tables and optional sample data"""
    
    # Create engine and session
    DATABASE_URL = "sqlite:///./cos.db"
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
    
    if add_sample_data:
        db = SessionLocal()
        try:
            # Check if we already have data
            existing_areas = db.query(Area).count()
            if existing_areas > 0:
                logger.info("Sample data already exists, skipping...")
                return
            
            logger.info("Adding sample data...")
            
            # First, create the default Areas
            work_area = Area(
                name="Work",
                description="Work-related projects and tasks",
                color="#3B82F6",  # Blue
                is_default=True,
                is_system=True,
                sort_order=1
            )
            
            personal_area = Area(
                name="Personal", 
                description="Personal projects and tasks",
                color="#10B981",  # Green
                is_default=True,
                is_system=True,
                sort_order=2
            )
            
            db.add_all([work_area, personal_area])
            db.flush()  # Get IDs
            
            # Create catch-all projects for each area
            work_tasks = Project(
                name="Tasks",
                description="General work tasks not assigned to specific projects",
                area_id=work_area.id,
                is_catch_all=True,
                is_system=True,
                sort_order=0,  # Sort first
                priority=3
            )
            
            personal_tasks = Project(
                name="Tasks", 
                description="General personal tasks not assigned to specific projects",
                area_id=personal_area.id,
                is_catch_all=True,
                is_system=True,
                sort_order=0,  # Sort first
                priority=3
            )
            
            db.add_all([work_tasks, personal_tasks])
            db.flush()
            
            # Create sample projects under Work area
            project1 = Project(
                name="Project Alpha",
                description="Strategic initiative for Q1 focusing on client engagement",
                area_id=work_area.id,
                status="active",
                priority=1,
                sort_order=1
            )
            
            project2 = Project(
                name="Website Redesign",
                description="Complete overhaul of company website with new branding",
                area_id=work_area.id,
                status="active", 
                priority=2,
                sort_order=2
            )
            
            project3 = Project(
                name="Team Training Program",
                description="Professional development initiative for staff",
                area_id=work_area.id,
                status="paused",
                priority=3,
                sort_order=3
            )
            
            # Create a sample personal project
            personal_project1 = Project(
                name="Home Renovation",
                description="Kitchen and bathroom renovation project",
                area_id=personal_area.id,
                status="active",
                priority=2,
                sort_order=1
            )
            
            db.add_all([project1, project2, project3, personal_project1])
            db.flush()  # Get IDs
            
            # Create sample tasks
            tasks = [
                Task(
                    title="Review client feedback on proposal",
                    description="Analyze feedback from ABC Corp on our Q1 proposal",
                    status="pending",
                    priority=1,
                    project_id=project1.id,
                    due_date=datetime.utcnow() + timedelta(days=2)
                ),
                Task(
                    title="Schedule stakeholder meeting",
                    description="Coordinate calendars for project kickoff meeting",
                    status="in_progress",
                    priority=2,
                    project_id=project1.id,
                    due_date=datetime.utcnow() + timedelta(days=5)
                ),
                Task(
                    title="Design mockups for homepage",
                    description="Create initial design concepts for new homepage",
                    status="pending",
                    priority=2,
                    project_id=project2.id,
                    due_date=datetime.utcnow() + timedelta(days=7)
                ),
                Task(
                    title="Research training vendors",
                    description="Identify potential vendors for team training program",
                    status="completed",
                    priority=3,
                    project_id=project3.id,
                    completed_at=datetime.utcnow() - timedelta(days=3)
                ),
                # Tasks in catch-all buckets
                Task(
                    title="Review quarterly expense report",
                    description="Go through Q1 expenses and categorize them properly",
                    status="pending",
                    priority=2,
                    project_id=work_tasks.id,
                    due_date=datetime.utcnow() + timedelta(days=3)
                ),
                Task(
                    title="Schedule dentist appointment", 
                    description="Book routine dental cleaning",
                    status="pending",
                    priority=3,
                    project_id=personal_tasks.id
                ),
                # Personal project task
                Task(
                    title="Get contractor quotes for kitchen",
                    description="Contact 3 contractors for kitchen renovation quotes",
                    status="in_progress",
                    priority=1,
                    project_id=personal_project1.id,
                    due_date=datetime.utcnow() + timedelta(days=1)
                ),
                Task(
                    title="Pick tile for bathroom",
                    description="Choose tiles for bathroom renovation at Home Depot",
                    status="pending", 
                    priority=2,
                    project_id=personal_project1.id,
                    due_date=datetime.utcnow() + timedelta(days=10)
                )
            ]
            
            db.add_all(tasks)
            db.flush()
            
            # Email data is no longer stored in database - emails accessed directly from Outlook
            
            # Create sample context entries
            context_entries = [
                ContextEntry(
                    type="observation",
                    content="User frequently works on Project Alpha tasks in the morning",
                    source="behavior_analysis",
                    confidence=0.7,
                    project_id=project1.id
                ),
                ContextEntry(
                    type="fact",
                    content="Project Alpha deadline is critical for Q1 revenue targets",
                    source="user_input",
                    confidence=0.9,
                    project_id=project1.id
                ),
                ContextEntry(
                    type="insight",
                    content="Website redesign project has been delayed twice - may need resource reallocation",
                    source="timeline_analysis", 
                    confidence=0.6,
                    project_id=project2.id
                )
            ]
            
            db.add_all(context_entries)
            
            # Create a sample interview
            interview = Interview(
                question="What's your biggest priority for Project Alpha this week?",
                status="pending",
                trigger_source="context_gap",
                importance_score=0.8,
                project_id=project1.id
            )
            
            db.add(interview)
            
            db.commit()
            logger.info("Sample data added successfully")
            
            # Print summary
            print("\n" + "="*60)
            print("DATABASE INITIALIZED SUCCESSFULLY")
            print("="*60)
            print(f"✅ Areas: 2 (Work, Personal)")
            print(f"✅ Projects: 6 (including 2 catch-all Tasks projects)")
            print(f"   - Work Area: 4 projects")
            print(f"     - Tasks (catch-all)")
            print(f"     - Project Alpha")
            print(f"     - Website Redesign")
            print(f"     - Team Training Program")
            print(f"   - Personal Area: 2 projects")
            print(f"     - Tasks (catch-all)")
            print(f"     - Home Renovation")
            print(f"✅ Tasks: {len(tasks)}")
            print(f"✅ Emails: {len(emails)}")
            print(f"✅ Context Entries: {len(context_entries)}")
            print(f"✅ Interviews: 1")
            print("="*60)
            print("\n🎯 The hierarchy is: Area → Project → Task")
            print("   • Work and Personal are system areas (cannot be deleted)")
            print("   • Each area has a 'Tasks' catch-all project for general tasks")
            print("   • Example: 'Pick up groceries' → Personal/Tasks")
            print("   • Example: 'Review expense report' → Work/Tasks")
            print("="*60)
            
        finally:
            db.close()

if __name__ == "__main__":
    init_database(add_sample_data=True)