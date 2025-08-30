"""
Multi-agent system for Chief of Staff application.
Implements the COS orchestrator and specialized agents.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from models import Project, Task, Email, ContextEntry, Interview, Digest
from claude_client import ClaudeClient
from job_queue import JobQueue

logger = logging.getLogger(__name__)

class BaseAgent:
    """Base class for all agents"""
    
    def __init__(self, claude_client: ClaudeClient):
        self.claude_client = claude_client
        self.agent_name = self.__class__.__name__

class COSOrchestrator(BaseAgent):
    """
    Master Chief of Staff orchestrator that coordinates all other agents.
    Handles high-level decision making and workflow coordination.
    """
    
    def __init__(self, claude_client: ClaudeClient, job_queue: JobQueue):
        super().__init__(claude_client)
        self.job_queue = job_queue
        
        # Initialize specialized agents
        self.contextor = ContextorAgent(claude_client)
        self.email_triage = EmailTriageAgent(claude_client)
        self.summarizer = SummarizerAgent(claude_client)
        self.writer = WriterAgent(claude_client)
    
    async def process_user_input(self, user_input: str, db: Session) -> str:
        """Process user input and coordinate appropriate responses"""
        logger.info(f"COS processing user input: {user_input}")
        
        # Analyze user intent and route to appropriate agent
        if user_input.startswith("/"):
            return await self._handle_command(user_input, db)
        else:
            return await self._handle_conversation(user_input, db)
    
    async def _handle_command(self, command: str, db: Session) -> str:
        """Handle slash commands"""
        command_lower = command.lower()
        
        if "/plan" in command_lower:
            return await self._generate_plan(db)
        elif "/summarize" in command_lower:
            return await self._generate_summary(db)
        elif "/triage" in command_lower:
            return await self._triage_inbox(db)
        elif "/digest" in command_lower:
            return await self._generate_digest(db)
        elif "/interview" in command_lower:
            return await self._start_interview(db)
        else:
            return f"Unknown command: {command}. Available commands: /plan, /summarize, /triage, /digest, /interview"
    
    async def _handle_conversation(self, user_input: str, db: Session) -> str:
        """Handle conversational input"""
        # Get current context for the user
        context = await self._build_current_context(db)
        
        # Generate response using COS orchestrator prompt
        response = await self.claude_client.generate_response(
            "system/cos",
            context=context,
            user_input=user_input
        )
        
        return response
    
    async def _generate_plan(self, db: Session) -> str:
        """Generate a work plan based on current context"""
        context = await self._build_current_context(db)
        
        # Get active projects and tasks
        active_projects = db.query(Project).filter(Project.status == "active").all()
        pending_tasks = db.query(Task).filter(Task.status.in_(["pending", "in_progress"])).all()
        unprocessed_emails = db.query(Email).filter(Email.status == "unprocessed").count()
        
        context.update({
            "active_projects_count": len(active_projects),
            "pending_tasks_count": len(pending_tasks),
            "unprocessed_emails_count": unprocessed_emails,
            "request_type": "planning"
        })
        
        return await self.claude_client.generate_response("system/cos", context=context, user_input="/plan")
    
    async def _generate_summary(self, db: Session) -> str:
        """Generate a summary of current work status"""
        context = await self._build_current_context(db)
        context["request_type"] = "summary"
        
        return await self.claude_client.generate_response("system/cos", context=context, user_input="/summarize")
    
    async def _triage_inbox(self, db: Session) -> str:
        """Trigger email triage process"""
        # Add email scan job to queue
        await self.job_queue.add_job("email_scan", {})
        
        # Get immediate results for user feedback
        unprocessed_emails = db.query(Email).filter(Email.status == "unprocessed").all()
        
        if not unprocessed_emails:
            return "Inbox is already up to date. No new emails to process."
        
        # Process a few emails immediately for demo
        processed_count = 0
        for email in unprocessed_emails[:5]:  # Process first 5
            result = await self.email_triage.process_email(email, db)
            processed_count += 1
        
        context = {
            "processed_count": processed_count,
            "total_unprocessed": len(unprocessed_emails),
            "request_type": "triage"
        }
        
        return await self.claude_client.generate_response("system/cos", context=context, user_input="/triage")
    
    async def _generate_digest(self, db: Session) -> str:
        """Generate daily/weekly digest"""
        # Add digest build job to queue
        await self.job_queue.add_job("digest_build", {"type": "daily"})
        
        context = await self._build_current_context(db)
        context["request_type"] = "digest"
        
        return await self.claude_client.generate_response("tools/digest", context=context)
    
    async def _start_interview(self, db: Session) -> str:
        """Start context interview process"""
        # Check if we've already done an interview today
        today = datetime.utcnow().date()
        recent_interview = db.query(Interview).filter(
            Interview.asked_at >= datetime.combine(today, datetime.min.time())
        ).first()
        
        if recent_interview:
            return "I've already conducted a context interview today. I'll wait until tomorrow to ask more questions to avoid interrupting your work flow."
        
        # Generate interview question
        context = await self._build_current_context(db)
        question = await self.claude_client.generate_response("tools/interview", context=context)
        
        # Create interview record
        interview = Interview(
            question=question,
            status="pending",
            trigger_source="manual_request",
            importance_score=0.7
        )
        db.add(interview)
        db.commit()
        
        return f"Context Interview Question:\n\n{question}\n\n(You can answer this later - it helps me understand your priorities better)"
    
    async def _build_current_context(self, db: Session) -> Dict[str, Any]:
        """Build current context for AI interactions"""
        # Get current projects, tasks, recent emails, etc.
        active_projects = db.query(Project).filter(Project.status == "active").all()
        recent_tasks = db.query(Task).filter(
            Task.created_at >= datetime.utcnow() - timedelta(days=7)
        ).all()
        recent_emails = db.query(Email).filter(
            Email.received_at >= datetime.utcnow() - timedelta(days=3)
        ).all()
        
        context = {
            "current_time": datetime.utcnow().isoformat(),
            "active_projects": [{"id": p.id, "name": p.name, "status": p.status} for p in active_projects],
            "recent_tasks_count": len(recent_tasks),
            "recent_emails_count": len(recent_emails),
        }
        
        return context
    
    async def apply_email_action(self, email: Email, action: str, payload: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Apply an action to an email"""
        logger.info(f"Applying action '{action}' to email {email.id}")
        
        result = {"success": False, "message": "Unknown action"}
        
        if action == "move_to_folder":
            folder = payload.get("folder", "@Action")
            email.folder = folder
            email.status = "triaged"
            result = {"success": True, "message": f"Email moved to {folder}"}
        
        elif action == "add_to_project":
            project_id = payload.get("project_id")
            if project_id:
                email.project_id = project_id
                email.linked_at = datetime.utcnow()
                result = {"success": True, "message": f"Email linked to project"}
        
        elif action == "extract_tasks":
            # Extract tasks from email content
            tasks = await self.claude_client.extract_tasks_from_text(email.body_content or email.body_preview)
            
            created_tasks = []
            for task_data in tasks:
                task = Task(
                    title=task_data["title"],
                    project_id=email.project_id,
                    description=f"Extracted from email: {email.subject}"
                )
                db.add(task)
                created_tasks.append(task_data["title"])
            
            result = {"success": True, "message": f"Created {len(created_tasks)} tasks", "tasks": created_tasks}
        
        elif action == "schedule_follow_up":
            # This would integrate with calendar system
            result = {"success": True, "message": "Follow-up scheduled (calendar integration pending)"}
        
        db.commit()
        return result
    
    async def process_interview_answer(self, interview: Interview, db: Session):
        """Process an interview answer and update context"""
        logger.info(f"Processing interview answer for question: {interview.question}")
        
        # Create context entry from the answer
        context_entry = ContextEntry(
            type="interview_answer",
            content=f"Q: {interview.question}\nA: {interview.answer}",
            source="interview",
            project_id=interview.project_id
        )
        db.add(context_entry)
        db.commit()
        
        # Trigger context analysis job
        await self.job_queue.add_job("context_scan", {"interview_id": interview.id})

class ContextorAgent(BaseAgent):
    """Agent responsible for context interviews and context management"""
    
    async def generate_interview_questions(self, context: Dict[str, Any], db: Session) -> List[str]:
        """Generate context interview questions based on current state"""
        questions = []
        
        # Analyze context gaps and generate questions
        response = await self.claude_client.generate_response("tools/interview", context=context)
        questions.append(response)
        
        return questions

class EmailTriageAgent(BaseAgent):
    """Agent responsible for email processing and triage"""
    
    async def process_email(self, email: Email, db: Session) -> Dict[str, Any]:
        """Process a single email - triage, categorize, extract info"""
        logger.info(f"Processing email: {email.subject}")
        
        # Generate email summary
        summary_data = await self.claude_client.generate_email_summary(
            email.body_content or email.body_preview or "",
            email.subject or ""
        )
        
        # Update email with AI-generated content
        email.summary = summary_data["summary"]
        email.status = "triaged"
        
        # Generate suggestions
        suggestions = await self.claude_client.generate_suggestions({
            "email_subject": email.subject,
            "email_content": email.body_preview,
            "sender": email.sender
        })
        
        import json
        email.suggested_actions = json.dumps(suggestions)
        
        db.commit()
        
        return {
            "email_id": email.id,
            "summary": summary_data,
            "suggestions": suggestions
        }

class SummarizerAgent(BaseAgent):
    """Agent responsible for content summarization and task extraction"""
    
    async def summarize_content(self, content: str, content_type: str = "general") -> Dict[str, Any]:
        """Summarize any content and extract tasks"""
        context = {
            "content": content,
            "content_type": content_type
        }
        
        summary = await self.claude_client.generate_response("system/summarizer", context=context)
        tasks = await self.claude_client.extract_tasks_from_text(content)
        
        return {
            "summary": summary,
            "extracted_tasks": tasks
        }

class WriterAgent(BaseAgent):
    """Agent responsible for generating written content"""
    
    async def generate_draft(self, content_type: str, context: Dict[str, Any]) -> str:
        """Generate written content like emails, summaries, etc."""
        return await self.claude_client.generate_response("system/writer", context=context)