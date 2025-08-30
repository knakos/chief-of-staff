"""
Background job queue system for Chief of Staff.
Handles asynchronous processing of emails, context scanning, digest generation, etc.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
import json

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from models import Job

logger = logging.getLogger(__name__)

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"

class JobQueue:
    """Simple in-memory job queue with persistent storage"""
    
    def __init__(self):
        self.workers: Dict[str, Callable] = {}
        self.running_jobs: Dict[str, asyncio.Task] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Database setup
        DATABASE_URL = "sqlite:///./cos.db"
        self.engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Register built-in job types
        self._register_builtin_jobs()
    
    def _register_builtin_jobs(self):
        """Register built-in job types"""
        self.workers.update({
            "email_scan": self._job_email_scan,
            "context_scan": self._job_context_scan,
            "digest_build": self._job_digest_build,
            "interview_seed": self._job_interview_seed,
            "link_suggest": self._job_link_suggest,
            "email_triage": self._job_email_triage,
            "task_extract": self._job_task_extract,
            "project_summary": self._job_project_summary,
        })
    
    async def start(self):
        """Start the job queue worker"""
        if self.is_running:
            return
            
        self.is_running = True
        self.worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Job queue started")
        
        # Load pending jobs from database
        await self._load_pending_jobs()
    
    async def stop(self):
        """Stop the job queue worker"""
        self.is_running = False
        
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        
        # Cancel running jobs
        for job_id, task in self.running_jobs.items():
            task.cancel()
        
        logger.info("Job queue stopped")
    
    async def add_job(self, job_type: str, data: Dict[str, Any], priority: int = 3) -> Job:
        """Add a new job to the queue"""
        db = self.SessionLocal()
        try:
            # Create job record
            job = Job(
                type=job_type,
                status=JobStatus.PENDING.value,
                priority=priority,
                input_data=data
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            
            # Add to in-memory queue
            await self.queue.put(job.id)
            
            logger.info(f"Added job {job.id} of type {job_type}")
            return job
            
        finally:
            db.close()
    
    async def _load_pending_jobs(self):
        """Load pending jobs from database on startup"""
        db = self.SessionLocal()
        try:
            pending_jobs = db.query(Job).filter(Job.status == JobStatus.PENDING.value).all()
            
            for job in pending_jobs:
                await self.queue.put(job.id)
            
            logger.info(f"Loaded {len(pending_jobs)} pending jobs")
            
        finally:
            db.close()
    
    async def _worker_loop(self):
        """Main worker loop that processes jobs"""
        while self.is_running:
            try:
                # Get next job (with timeout to allow graceful shutdown)
                try:
                    job_id = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # Process the job
                await self._process_job(job_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_job(self, job_id: str):
        """Process a single job"""
        db = self.SessionLocal()
        try:
            # Get job from database
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.warning(f"Job {job_id} not found in database")
                return
            
            # Check if worker exists for this job type
            worker = self.workers.get(job.type)
            if not worker:
                job.status = JobStatus.FAILED.value
                job.error_message = f"No worker found for job type: {job.type}"
                db.commit()
                logger.error(f"No worker for job type: {job.type}")
                return
            
            # Update job status to running
            job.status = JobStatus.RUNNING.value
            job.started_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Processing job {job_id} of type {job.type}")
            
            try:
                # Run the job
                task = asyncio.create_task(worker(job, db))
                self.running_jobs[job_id] = task
                
                result = await task
                
                # Update job as completed
                job.status = JobStatus.COMPLETED.value
                job.completed_at = datetime.utcnow()
                job.progress = 1.0
                job.result_data = result if isinstance(result, dict) else {"result": result}
                db.commit()
                
                logger.info(f"Job {job_id} completed successfully")
                
            except asyncio.CancelledError:
                job.status = JobStatus.FAILED.value
                job.error_message = "Job was cancelled"
                db.commit()
                logger.info(f"Job {job_id} was cancelled")
                
            except Exception as e:
                job.status = JobStatus.FAILED.value
                job.error_message = str(e)
                db.commit()
                logger.error(f"Job {job_id} failed: {e}")
            
            finally:
                self.running_jobs.pop(job_id, None)
                
        finally:
            db.close()
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a job"""
        db = self.SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return None
            
            return {
                "id": job.id,
                "type": job.type,
                "status": job.status,
                "progress": job.progress,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "error_message": job.error_message,
            }
        finally:
            db.close()
    
    # Built-in job workers
    async def _job_email_scan(self, job: Job, db: Session) -> Dict[str, Any]:
        """Scan emails for new content to process"""
        logger.info("Starting email scan job")
        
        # Simulate email scanning
        await asyncio.sleep(2)
        
        # Update progress
        job.progress = 0.5
        db.commit()
        
        await asyncio.sleep(1)
        
        return {
            "emails_scanned": 15,
            "new_emails": 3,
            "action_required": 1
        }
    
    async def _job_context_scan(self, job: Job, db: Session) -> Dict[str, Any]:
        """Scan context for stale or uncertain information"""
        logger.info("Starting context scan job")
        
        await asyncio.sleep(3)
        
        return {
            "context_entries_reviewed": 45,
            "stale_entries": 2,
            "uncertainty_flags": 1
        }
    
    async def _job_digest_build(self, job: Job, db: Session) -> Dict[str, Any]:
        """Build daily/weekly digest"""
        logger.info("Starting digest build job")
        
        digest_type = job.input_data.get("type", "daily")
        
        await asyncio.sleep(4)
        
        return {
            "digest_type": digest_type,
            "sections_generated": 5,
            "word_count": 350
        }
    
    async def _job_interview_seed(self, job: Job, db: Session) -> Dict[str, Any]:
        """Generate interview questions based on context gaps"""
        logger.info("Starting interview seed job")
        
        await asyncio.sleep(2)
        
        return {
            "questions_generated": 3,
            "high_priority": 1,
            "context_gaps_identified": 5
        }
    
    async def _job_link_suggest(self, job: Job, db: Session) -> Dict[str, Any]:
        """Suggest links between emails, tasks, and projects"""
        logger.info("Starting link suggestion job")
        
        await asyncio.sleep(3)
        
        return {
            "potential_links": 8,
            "high_confidence": 3,
            "emails_analyzed": 20
        }
    
    async def _job_email_triage(self, job: Job, db: Session) -> Dict[str, Any]:
        """Triage emails into appropriate folders and categories"""
        logger.info("Starting email triage job")
        
        email_id = job.input_data.get("email_id")
        
        await asyncio.sleep(2)
        
        return {
            "email_id": email_id,
            "folder_assigned": "@Action",
            "categories": ["COS/Project", "COS/Urgent"],
            "confidence": 0.85
        }
    
    async def _job_task_extract(self, job: Job, db: Session) -> Dict[str, Any]:
        """Extract tasks from email or other content"""
        logger.info("Starting task extraction job")
        
        content_type = job.input_data.get("content_type", "email")
        
        await asyncio.sleep(2)
        
        return {
            "content_type": content_type,
            "tasks_extracted": 2,
            "tasks": [
                {"title": "Review proposal", "priority": 2},
                {"title": "Schedule follow-up meeting", "priority": 3}
            ]
        }
    
    async def _job_project_summary(self, job: Job, db: Session) -> Dict[str, Any]:
        """Generate summary for a project"""
        logger.info("Starting project summary job")
        
        project_id = job.input_data.get("project_id")
        
        await asyncio.sleep(3)
        
        return {
            "project_id": project_id,
            "summary_generated": True,
            "sections": ["overview", "recent_activity", "next_steps"],
            "word_count": 280
        }