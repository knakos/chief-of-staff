"""
Database models for Chief of Staff application.
Core entities: Projects, Tasks, Emails, Context, Jobs
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, DateTime, Text, Integer, Float, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
import uuid

Base = declarative_base()

def new_id() -> str:
    return str(uuid.uuid4())

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=new_id)
    name = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="active")  # active, paused, completed, archived
    priority = Column(Integer, default=3)  # 1=high, 5=low
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    emails = relationship("Email", back_populates="project")
    context_entries = relationship("ContextEntry", back_populates="project")

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True, default=new_id)
    title = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="pending")  # pending, in_progress, completed, blocked
    priority = Column(Integer, default=3)
    due_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Foreign keys
    project_id = Column(String, ForeignKey("projects.id"))
    parent_task_id = Column(String, ForeignKey("tasks.id"))
    
    # Relationships
    project = relationship("Project", back_populates="tasks")
    parent_task = relationship("Task", remote_side=[id])
    subtasks = relationship("Task", cascade="all, delete-orphan")
    emails = relationship("Email", secondary="email_tasks", back_populates="tasks")

class Email(Base):
    __tablename__ = "emails"
    
    id = Column(String, primary_key=True, default=new_id)
    thread_id = Column(String)  # Outlook thread ID
    message_id = Column(String)  # Outlook message ID
    subject = Column(String)
    sender = Column(String)
    recipients = Column(Text)  # JSON array of recipients
    body_preview = Column(Text)
    body_content = Column(Text)
    received_at = Column(DateTime)
    processed_at = Column(DateTime)
    
    # COS metadata
    project_id = Column(String, ForeignKey("projects.id"))
    confidence = Column(Float)  # Confidence in project assignment
    provenance = Column(String)  # How this assignment was made
    linked_at = Column(DateTime)
    
    # Processing status
    status = Column(String, default="unprocessed")  # unprocessed, triaged, archived
    folder = Column(String)  # @Action, @Waiting, etc.
    categories = Column(Text)  # JSON array of categories
    
    # AI-generated content
    summary = Column(Text)
    extracted_tasks = Column(Text)  # JSON array of task descriptions
    suggested_actions = Column(Text)  # JSON array of suggestions
    
    # Relationships
    project = relationship("Project", back_populates="emails")
    tasks = relationship("Task", secondary="email_tasks", back_populates="emails")

# Association table for email-task many-to-many relationship
from sqlalchemy import Table
email_tasks = Table(
    'email_tasks', Base.metadata,
    Column('email_id', String, ForeignKey('emails.id'), primary_key=True),
    Column('task_id', String, ForeignKey('tasks.id'), primary_key=True)
)

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
    
    # Relationships - jobs can be related to projects/emails
    related_project_id = Column(String, ForeignKey("projects.id"))
    related_email_id = Column(String, ForeignKey("emails.id"))

class Interview(Base):
    __tablename__ = "interviews"
    
    id = Column(String, primary_key=True, default=new_id)
    status = Column(String, default="pending")  # pending, active, completed, dismissed
    question = Column(Text, nullable=False)
    answer = Column(Text)
    asked_at = Column(DateTime, default=datetime.utcnow)
    answered_at = Column(DateTime)
    dismissed_at = Column(DateTime)
    
    # Context about why this question was asked
    trigger_source = Column(String)  # email_scan, context_gap, etc.
    importance_score = Column(Float, default=0.5)
    
    # Relationships
    project_id = Column(String, ForeignKey("projects.id"))
    related_email_id = Column(String, ForeignKey("emails.id"))

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