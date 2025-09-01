"""
Database initialization script for Chief of Staff.
Creates tables and optionally adds sample data for development.
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Project, Task, Email, ContextEntry, Interview
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
            existing_projects = db.query(Project).count()
            if existing_projects > 0:
                logger.info("Sample data already exists, skipping...")
                return
            
            logger.info("Adding sample data...")
            
            # Create sample projects
            project1 = Project(
                name="Project Alpha",
                description="Strategic initiative for Q1 focusing on client engagement",
                status="active",
                priority=1
            )
            
            project2 = Project(
                name="Website Redesign",
                description="Complete overhaul of company website with new branding",
                status="active", 
                priority=2
            )
            
            project3 = Project(
                name="Team Training Program",
                description="Professional development initiative for staff",
                status="paused",
                priority=3
            )
            
            db.add_all([project1, project2, project3])
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
                )
            ]
            
            db.add_all(tasks)
            db.flush()
            
            # Create sample emails
            emails = [
                Email(
                    thread_id="thread_001",
                    message_id="msg_001",
                    subject="Re: Project Alpha Proposal Feedback",
                    sender="john.smith@abccorp.com",
                    recipients='["user@company.com"]',
                    body_preview="Thanks for the proposal. We have some feedback on the timeline and budget sections...",
                    body_content="Hi,\n\nThanks for the detailed proposal for Project Alpha. Overall, we're impressed with your approach. However, we have some concerns about the timeline - can we extend the delivery by 2 weeks? Also, the budget seems a bit tight for the scope.\n\nLet's schedule a call to discuss.\n\nBest regards,\nJohn Smith",
                    received_at=datetime.utcnow() - timedelta(hours=6),
                    project_id=project1.id,
                    status="unprocessed",
                    confidence=0.9,
                    provenance="keyword_match"
                ),
                Email(
                    thread_id="thread_002", 
                    message_id="msg_002",
                    subject="Website Design Assets",
                    sender="design@agency.com",
                    recipients='["user@company.com"]',
                    body_preview="Attached are the initial design concepts for your website redesign...",
                    body_content="Hi,\n\nPlease find attached the initial design concepts for your website redesign project. We've created 3 different approaches:\n\n1. Modern minimalist\n2. Bold and colorful\n3. Professional corporate\n\nWe'd love to get your feedback on these directions.\n\nBest,\nDesign Team",
                    received_at=datetime.utcnow() - timedelta(hours=2),
                    project_id=project2.id,
                    status="unprocessed",
                    confidence=0.95,
                    provenance="sender_analysis"
                ),
                Email(
                    thread_id="thread_003",
                    message_id="msg_003", 
                    subject="Weekly Team Sync - Action Items",
                    sender="manager@company.com",
                    recipients='["user@company.com", "team@company.com"]',
                    body_preview="Follow-up from today's team meeting with action items...",
                    body_content="Hi Team,\n\nThanks for a productive team sync today. Here are the action items:\n\n- Update project timelines by Friday\n- Review Q2 budget proposals\n- Prepare client presentation for next week\n\nLet me know if you have any questions.\n\nBest,\nManager",
                    received_at=datetime.utcnow() - timedelta(hours=1),
                    status="unprocessed"
                )
            ]
            
            db.add_all(emails)
            db.flush()
            
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
            print("\n" + "="*50)
            print("DATABASE INITIALIZED SUCCESSFULLY")
            print("="*50)
            print(f"✅ Projects: {len([project1, project2, project3])}")
            print(f"✅ Tasks: {len(tasks)}")
            print(f"✅ Emails: {len(emails)}")
            print(f"✅ Context Entries: {len(context_entries)}")
            print(f"✅ Interviews: 1")
            print("="*50)
            
        finally:
            db.close()

if __name__ == "__main__":
    init_database(add_sample_data=True)