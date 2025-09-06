"""
Database models for Chief of Staff application.
Core entities: Projects, Tasks, Context, Jobs
Note: Emails are accessed directly from Outlook COM integration, not stored in database
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, DateTime, Date, Time, Text, Integer, Float, Boolean, ForeignKey, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
import uuid

Base = declarative_base()

def new_id() -> str:
    return str(uuid.uuid4())

class Area(Base):
    __tablename__ = "areas"
    
    id = Column(String, primary_key=True, default=new_id)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text)
    color = Column(String, default="#3B82F6")  # Hex color for UI
    is_default = Column(Boolean, default=False, index=True)  # Work/Personal are defaults
    is_system = Column(Boolean, default=False)  # System areas cannot be deleted
    sort_order = Column(Integer, default=0, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    projects = relationship("Project", back_populates="area", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_area_name', 'name'),
        Index('idx_area_system_default', 'is_system', 'is_default'),
    )
    
    def __repr__(self):
        return f"<Area(name='{self.name}', is_system={self.is_system})>"

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=new_id)
    name = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="active", index=True)  # active, paused, completed, archived
    priority = Column(Integer, default=3)  # 1=high, 5=low
    is_catch_all = Column(Boolean, default=False, index=True)  # True for [Area]Tasks projects
    is_system = Column(Boolean, default=False)  # System projects cannot be deleted
    sort_order = Column(Integer, default=0, index=True)
    color = Column(String)  # Hex color, defaults to area color if not set
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    area_id = Column(String, ForeignKey("areas.id"), nullable=False, index=True)
    
    # Relationships
    area = relationship("Area", back_populates="projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    context_entries = relationship("ContextEntry", back_populates="project")
    
    __table_args__ = (
        Index('idx_project_area_status', 'area_id', 'status'),
        Index('idx_project_catch_all', 'is_catch_all', 'area_id'),
    )
    
    def __repr__(self):
        return f"<Project(name='{self.name}', area='{self.area.name if self.area else None}', is_catch_all={self.is_catch_all})>"

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True, default=new_id)
    title = Column(String, nullable=False)
    objective = Column(Text)  # Specific goal/outcome for this task
    status = Column(String, default="not_started", index=True)  # not_started, active, blocked, completed, dropped, archived
    priority = Column(Integer, default=3)
    due_date = Column(DateTime)
    sponsor_email = Column(String)  # Who wants this task, who will be updated when complete
    owner_email = Column(String)    # Who is responsible for completing this task
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    parent_task_id = Column(String, ForeignKey("tasks.id"))
    
    # Relationships
    project = relationship("Project", back_populates="tasks")
    parent_task = relationship("Task", remote_side=[id])
    subtasks = relationship("Task", cascade="all, delete-orphan", overlaps="parent_task")
    
    # Convenience properties
    @property
    def area_id(self) -> Optional[str]:
        """Get the area ID through the project relationship"""
        return self.project.area_id if self.project else None
    
    @property 
    def area_name(self) -> Optional[str]:
        """Get the area name through the project relationship"""
        return self.project.area.name if self.project and self.project.area else None
    
    def __repr__(self):
        return f"<Task(title='{self.title}', project='{self.project.name if self.project else None}', status='{self.status}')>"

# Email model removed - emails are accessed directly from Outlook, not stored in database

class ContextEntry(Base):
    __tablename__ = "context_entries"
    
    id = Column(String, primary_key=True, default=new_id)
    type = Column(String, nullable=False)  # interview_answer, observation, insight, fact
    content = Column(Text, nullable=False)
    source = Column(String)  # interview, email_scan, user_input, etc.
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # For time-sensitive context
    
    # Relationships
    project_id = Column(String, ForeignKey("projects.id"))
    project = relationship("Project", back_populates="context_entries")
    
    # Metadata
    extra_data = Column(SQLiteJSON)  # Additional structured data

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(String, primary_key=True, default=new_id)
    type = Column(String, nullable=False)  # email_scan, context_scan, digest_build, etc.
    status = Column(String, default="pending")  # pending, running, completed, failed
    priority = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Job data
    input_data = Column(SQLiteJSON)  # Input parameters
    result_data = Column(SQLiteJSON)  # Job results
    error_message = Column(Text)
    progress = Column(Float, default=0.0)  # 0.0 to 1.0
    
    __table_args__ = (
        Index('idx_job_status_type', 'status', 'type'),
        Index('idx_job_created', 'created_at'),
    )
    
    # Relationships - jobs can be related to projects
    related_project_id = Column(String, ForeignKey("projects.id"))
    # Note: Email IDs are Outlook IDs, not database foreign keys
    related_email_outlook_id = Column(String)  # Reference to Outlook email ID

class Interview(Base):
    __tablename__ = "interviews"
    
    id = Column(String, primary_key=True, default=new_id)
    status = Column(String, default="pending", index=True)  # pending, active, completed, dismissed
    question = Column(Text, nullable=False)
    answer = Column(Text)
    asked_at = Column(DateTime, default=datetime.utcnow)
    answered_at = Column(DateTime)
    dismissed_at = Column(DateTime)
    
    # Context about why this question was asked
    trigger_source = Column(String)  # email_scan, context_gap, etc.
    importance_score = Column(Float, default=0.5)
    
    # Relationships
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    # Note: Email IDs are Outlook IDs, not database foreign keys
    related_email_outlook_id = Column(String)  # Reference to Outlook email ID

class Digest(Base):
    __tablename__ = "digests"
    
    id = Column(String, primary_key=True, default=new_id)
    type = Column(String, nullable=False)  # daily, weekly, project_summary
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)  # Markdown content
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Time period covered
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    
    # Relationships
    project_id = Column(String, ForeignKey("projects.id"))  # For project-specific digests
    
    # Summary data
    highlights = Column(SQLiteJSON)  # Key points
    stats = Column(SQLiteJSON)  # Metrics and counts

# User Context and Profile Models
class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, nullable=False, unique=True, index=True)  # Default: "primary"
    
    # Personal Information
    display_name = Column(String)
    email_address = Column(String)
    date_of_birth = Column(Date)
    work_location = Column(String)  # Office, remote, hybrid
    time_zone = Column(String, default="UTC")
    
    # Work Context
    job_title = Column(String)
    department = Column(String)
    division = Column(String)
    start_date = Column(Date)
    work_hours_start = Column(Time)  # Preferred work start time
    work_hours_end = Column(Time)    # Preferred work end time
    
    # Communication Preferences
    communication_style = Column(String)  # formal, casual, direct, collaborative
    meeting_preference = Column(String)   # minimal, frequent, scheduled, adhoc
    notification_frequency = Column(String)  # immediate, hourly, daily, weekly
    
    # Personal Productivity Patterns
    peak_hours = Column(String)  # morning, afternoon, evening
    focus_blocks = Column(SQLiteJSON)  # Preferred deep work time blocks
    break_preferences = Column(SQLiteJSON)  # Break patterns and preferences
    
    # Goals and Objectives
    current_goals = Column(SQLiteJSON)  # Personal and professional goals
    success_metrics = Column(SQLiteJSON)  # How success is measured
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    onboarding_completed = Column(Boolean, default=False)
    
    __table_args__ = (
        Index('idx_user_profile_user', 'user_id'),
    )

class Contact(Base):
    __tablename__ = "contacts"
    
    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("user_profiles.user_id"), nullable=False, index=True)
    
    # Basic Information
    display_name = Column(String, nullable=False)
    email_address = Column(String, nullable=False, index=True)
    phone_number = Column(String)
    job_title = Column(String)
    company = Column(String)
    department = Column(String)
    
    # Relationship Context
    relationship_type = Column(String, nullable=False, index=True)  # boss, peer, direct_report, client, vendor, etc.
    reporting_relationship = Column(String)  # reports_to_me, i_report_to, peer, external
    team = Column(String)  # Team or group association
    
    # Communication Preferences
    preferred_communication = Column(String)  # email, teams, phone, in_person
    communication_style = Column(String)     # formal, casual, direct, detailed
    response_time_expectation = Column(String)  # immediate, hours, days
    availability_pattern = Column(String)    # business_hours, flexible, specific_times
    escalation_path = Column(String)         # How to escalate issues involving this contact
    
    # Interaction History
    last_interaction = Column(DateTime)
    interaction_frequency = Column(String)   # daily, weekly, monthly, occasional
    interaction_count = Column(Integer, default=0)
    
    # Context and Notes
    role_in_projects = Column(SQLiteJSON)    # Projects and their role in each
    decision_authority = Column(SQLiteJSON)  # What they can approve/decide
    expertise_areas = Column(SQLiteJSON)     # Their areas of expertise
    notes = Column(Text)                     # Free-form notes about this contact
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    source = Column(String)  # outlook, manual, import
    
    # Relationships
    user_profile = relationship("UserProfile", foreign_keys=[user_id])
    
    __table_args__ = (
        Index('idx_contact_email', 'email_address'),
        Index('idx_contact_relationship', 'relationship_type'),
        Index('idx_contact_user', 'user_id'),
    )

class UserContext(Base):
    __tablename__ = "user_contexts"
    
    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("user_profiles.user_id"), nullable=False, index=True)
    
    # Context Type and Source
    context_type = Column(String, nullable=False, index=True)  # behavior, preference, decision, pattern
    source = Column(String)  # interaction, interview, observation, manual
    
    # Context Data
    key = Column(String, nullable=False)     # e.g., "preferred_meeting_duration", "decision_speed"
    value = Column(String)                   # The learned value
    confidence_score = Column(Float, default=0.5)  # How confident we are (0.0-1.0)
    
    # Context Metadata
    learned_from = Column(String)            # Description of how this was learned
    example_instances = Column(SQLiteJSON)   # Examples that support this context
    last_reinforced = Column(DateTime)       # When this context was last confirmed
    reinforcement_count = Column(Integer, default=1)
    
    # Temporal Context
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_until = Column(DateTime)           # For time-sensitive context
    seasonal_pattern = Column(String)        # daily, weekly, monthly, quarterly patterns
    
    # Usage and Effectiveness
    applied_count = Column(Integer, default=0)  # How many times this context was used
    success_rate = Column(Float)             # Effectiveness when applied
    
    # Relationships
    related_project_id = Column(String, ForeignKey("projects.id"))
    related_contact_id = Column(String, ForeignKey("contacts.id"))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_user_context_type', 'context_type'),
        Index('idx_user_context_key', 'key'),
        Index('idx_user_context_user', 'user_id'),
        Index('idx_user_context_composite', 'user_id', 'context_type', 'key'),
    )

class DecisionHistory(Base):
    __tablename__ = "decision_history"
    
    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("user_profiles.user_id"), nullable=False, index=True)
    
    # Decision Context
    decision_type = Column(String, nullable=False, index=True)  # project, task, email, meeting, etc.
    decision_description = Column(Text, nullable=False)
    context_snapshot = Column(SQLiteJSON)    # Relevant context at time of decision
    
    # Decision Details
    options_considered = Column(SQLiteJSON)  # What alternatives were considered
    chosen_option = Column(String, nullable=False)
    rationale = Column(Text)                 # Why this was chosen
    decision_speed = Column(String)          # immediate, quick, deliberated, researched
    
    # Decision Outcome
    outcome_description = Column(Text)
    success_rating = Column(Float)           # 0.0-1.0 how well this worked out
    lessons_learned = Column(Text)
    would_decide_same_way = Column(Boolean)
    
    # Context
    related_project_id = Column(String, ForeignKey("projects.id"))
    related_task_id = Column(String, ForeignKey("tasks.id"))
    related_email_outlook_id = Column(String)  # Reference to Outlook email ID
    stakeholders_involved = Column(SQLiteJSON)  # Who was consulted/impacted
    
    # Metadata
    decision_date = Column(DateTime, nullable=False, index=True)
    outcome_date = Column(DateTime)          # When outcome was evaluated
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_decision_type', 'decision_type'),
        Index('idx_decision_date', 'decision_date'),
        Index('idx_decision_user', 'user_id'),
    )


# Email model removed - emails are accessed directly from Outlook COM integration, not stored in database