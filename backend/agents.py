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
from integrations.outlook.connector import GraphAPIConnector
from integrations.outlook.auth import OutlookAuthManager
from integrations.outlook.sync_service import EmailSyncService
from integrations.outlook.folder_manager import GTDFolderManager
from integrations.outlook.extended_props import COSExtendedPropsManager
from integrations.outlook.hybrid_service import HybridOutlookService

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
        
        # Check for explicit slash commands (for debugging/power users)
        if user_input.startswith("/"):
            return await self._handle_command(user_input, db)
        
        # For natural language, analyze intent and respond conversationally
        return await self._handle_conversation(user_input, db)
    
    async def _handle_command(self, command: str, db: Session) -> str:
        """Handle slash commands"""
        command_lower = command.lower()
        logger.info(f"_handle_command received: '{command_lower}'")
        
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
        elif "/outlook" in command_lower:
            return await self._handle_outlook_command(command_lower, db)
        else:
            return f"Unknown command: {command}. Available commands: /plan, /summarize, /triage, /digest, /interview, /outlook"
    
    async def _handle_conversation(self, user_input: str, db: Session) -> str:
        """Handle conversational input with intent detection"""
        # Get current context for the user
        context = await self._build_current_context(db)
        user_lower = user_input.lower()
        
        # Detect intent and potentially execute actions behind the scenes
        intent_actions = []
        
        # Email/Outlook related intents
        if any(word in user_lower for word in ["email", "inbox", "outlook", "mail", "triage"]):
            # Always ensure we're connected when user asks about emails
            if not self.email_triage.hybrid_service.is_connected():
                logger.info("User asked about emails but not connected - attempting connection")
                connect_result = await self.email_triage.hybrid_service.connect()
                context["outlook_connection"] = connect_result
                intent_actions.append("outlook_auto_connected")
                if connect_result.get("connected"):
                    logger.info("Auto-connection successful - folders should be created")
            
            # Check specific email intents and delegate to EmailTriageAgent
            if any(word in user_lower for word in ["inbox", "messages", "what's in"]):
                # Delegate to EmailTriageAgent to view inbox
                inbox_result = await self.email_triage.view_inbox_messages(db, limit=20)
                context["inbox_messages"] = inbox_result
                intent_actions.append("inbox_retrieved")
            elif any(word in user_lower for word in ["connect", "setup", "configure"]):
                connect_result = await self.email_triage.hybrid_service.connect()
                context["outlook_connection"] = connect_result
                intent_actions.append(f"outlook_connect_attempted")
            elif any(word in user_lower for word in ["sync", "get", "download", "fetch"]):
                sync_result = await self.email_triage.hybrid_service.sync_emails(db)
                context["outlook_sync"] = sync_result
                intent_actions.append(f"outlook_sync_attempted")
            elif any(word in user_lower for word in ["organize", "triage", "sort", "process"]):
                # Trigger email triage in background
                await self.job_queue.add_job("email_scan", {})
                intent_actions.append("email_triage_started")
        
        # Planning related intents
        elif any(word in user_lower for word in ["plan", "planning", "organize", "schedule", "prioritize"]):
            # Add planning context
            active_projects = db.query(Project).filter(Project.status == "active").all()
            pending_tasks = db.query(Task).filter(Task.status.in_(["pending", "in_progress"])).all()
            context.update({
                "active_projects_count": len(active_projects),
                "pending_tasks_count": len(pending_tasks),
                "request_type": "planning",
                "user_wants_planning": True
            })
            intent_actions.append("planning_context_added")
        
        # Summary related intents  
        elif any(word in user_lower for word in ["summary", "summarize", "status", "update", "what's happening"]):
            context["request_type"] = "summary"
            context["user_wants_summary"] = True
            intent_actions.append("summary_context_added")
        
        # Add detected actions to context
        if intent_actions:
            context["detected_actions"] = intent_actions
        
        # Generate conversational response using COS orchestrator prompt
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
        """Trigger email triage process for both local and Outlook emails"""
        # Add email scan job to queue
        await self.job_queue.add_job("email_scan", {})
        
        # Get local unprocessed emails
        local_unprocessed = db.query(Email).filter(Email.status == "unprocessed").all()
        
        # Get Outlook unprocessed emails if authenticated
        outlook_unprocessed = []
        if self.email_triage.auth_manager.is_authenticated():
            outlook_unprocessed = await self.email_triage.get_unprocessed_outlook_emails()
        
        total_unprocessed = len(local_unprocessed) + len(outlook_unprocessed)
        
        if total_unprocessed == 0:
            return "Inbox is already up to date. No new emails to process."
        
        # Process local emails
        processed_count = 0
        for email in local_unprocessed[:5]:  # Process first 5 local emails
            if hasattr(email, 'outlook_id') and email.outlook_id:
                # Use Outlook-enhanced triage for emails with Outlook ID
                result = await self.email_triage.triage_outlook_email(email, db)
            else:
                # Use standard triage for local-only emails
                result = await self.email_triage.process_email(email, db)
            processed_count += 1
        
        # Process some Outlook emails
        for outlook_email in outlook_unprocessed[:3]:  # Process first 3 Outlook emails
            # Check if email already exists locally
            existing = db.query(Email).filter(Email.outlook_id == outlook_email["id"]).first()
            if not existing:
                # Create local email record
                local_email = Email(
                    outlook_id=outlook_email["id"],
                    subject=outlook_email.get("subject", ""),
                    sender=outlook_email.get("from", {}).get("emailAddress", {}).get("address", ""),
                    body_preview=outlook_email.get("bodyPreview", ""),
                    received_at=datetime.utcnow()
                )
                db.add(local_email)
                db.commit()
                
                # Triage with Outlook integration
                await self.email_triage.triage_outlook_email(local_email, db)
                processed_count += 1
        
        context = {
            "processed_count": processed_count,
            "total_unprocessed": total_unprocessed,
            "outlook_connected": self.email_triage.auth_manager.is_authenticated(),
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
    
    async def _handle_outlook_command(self, command: str, db: Session) -> str:
        """Handle Outlook-specific commands"""
        logger.info(f"_handle_outlook_command called with: {command}")
        
        if "/outlook connect" in command:
            # Try hybrid connection (COM first, then Graph API)
            try:
                result = await self.email_triage.hybrid_service.connect()
                return f"Connection attempt: {result['message']} (Method: {result.get('method', 'None')})"
            except Exception as e:
                logger.error(f"Hybrid connection failed: {e}")
                return f"Connection failed: {str(e)}"
        
        elif "/outlook sync" in command:
            # Sync emails from Outlook using hybrid service
            try:
                result = await self.email_triage.hybrid_service.sync_emails(db)
                if result["success"]:
                    return f"Outlook sync completed: {result['synced_count']} emails processed via {result['method']}"
                else:
                    return f"Outlook sync failed: {result.get('error', 'Unknown error')}"
            except Exception as e:
                logger.error(f"Outlook sync error: {e}")
                return f"Outlook sync failed: {str(e)}"
        
        elif "/outlook setup" in command:
            # Setup GTD folders using hybrid service
            try:
                result = await self.email_triage.hybrid_service.setup_gtd_folders()
                if result["success"]:
                    folders = ', '.join(result["folders_created"].keys()) if "folders_created" in result else "GTD folders"
                    return f"GTD folder structure created in Outlook via {result.get('method', 'unknown method')}: {folders}"
                else:
                    return f"Folder setup failed: {result.get('error', 'Unknown error')}"
            except Exception as e:
                logger.error(f"Outlook setup error: {e}")
                return f"Folder setup failed: {str(e)}"
        
        elif "/outlook triage" in command:
            # Triage unprocessed Outlook emails
            unprocessed = await self.email_triage.get_unprocessed_outlook_emails()
            if not unprocessed:
                return "No unprocessed emails found in Outlook"
            
            processed_count = 0
            for outlook_email in unprocessed[:10]:  # Process first 10
                # Convert Outlook email to local Email object for processing
                local_email = Email(
                    outlook_id=outlook_email["id"],
                    subject=outlook_email.get("subject", ""),
                    sender=outlook_email.get("from", {}).get("emailAddress", {}).get("address", ""),
                    body_preview=outlook_email.get("bodyPreview", ""),
                    received_at=datetime.utcnow()
                )
                db.add(local_email)
                db.commit()
                
                # Triage with Outlook integration
                await self.email_triage.triage_outlook_email(local_email, db)
                processed_count += 1
            
            return f"Processed {processed_count} unprocessed emails with GTD categorization and COS properties"
        
        elif "/outlook disconnect" in command:
            # Disconnect current Outlook account
            try:
                self.email_triage.auth_manager.revoke_tokens()
                return "Outlook account disconnected. Use /outlook status to connect a different account."
            except Exception as e:
                logger.error(f"Error disconnecting Outlook: {e}")
                return f"Error disconnecting Outlook: {str(e)}"
        
        elif "/outlook info" in command:
            # Get detailed connection info
            try:
                connection_info = self.email_triage.hybrid_service.get_connection_info()
                return f"Connection Info:\nMethod: {connection_info['method']}\nStatus: {connection_info['status']}\n{connection_info.get('help', '')}"
            except Exception as e:
                logger.error(f"Error getting connection info: {e}")
                return f"Error getting connection info: {str(e)}"
        
        elif "/outlook status" in command:
            # Get Outlook integration status (legacy Graph API)
            logger.info("Processing /outlook status command")
            try:
                is_authenticated = self.email_triage.auth_manager.is_authenticated()
                logger.info(f"Authentication status: {is_authenticated}")
                
                if is_authenticated:
                    token_info = self.email_triage.auth_manager.get_token_info()
                    logger.info(f"Token info retrieved: {token_info}")
                    return f"Graph API connected. Token expires: {token_info['expires_at']}\n\nTip: Use '/outlook connect' to try COM connection first."
                else:
                    auth_url, state = self.email_triage.auth_manager.get_authorization_url()
                    logger.info(f"Generated auth URL: {auth_url[:100]}...")
                    response_message = f"Graph API not connected. Please visit: {auth_url}\n\nAlternatively, use '/outlook connect' to try COM connection if Outlook is running locally."
                    logger.info(f"Returning response message (first 200 chars): {response_message[:200]}...")
                    return response_message
            except Exception as e:
                logger.error(f"Error processing /outlook status: {e}")
                return f"Error checking Outlook status: {str(e)}"
        
        else:
            return "Available Outlook commands: /outlook connect, /outlook sync, /outlook setup, /outlook triage, /outlook status, /outlook info, /outlook disconnect"
    
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
            folder = payload.get("folder", "COS_Actions")
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
    """Agent responsible for email processing and triage with Outlook integration"""
    
    def __init__(self, claude_client: ClaudeClient):
        super().__init__(claude_client)
        
        # Initialize Outlook services (hybrid with COM fallback)
        self.hybrid_service = HybridOutlookService()
        
        # Legacy services (still available for direct Graph API access)
        self.graph_connector = GraphAPIConnector()
        self.auth_manager = OutlookAuthManager()
        self.sync_service = EmailSyncService(self.graph_connector, self.auth_manager)
        self.folder_manager = GTDFolderManager(self.graph_connector, self.auth_manager)
        self.extended_props = COSExtendedPropsManager(self.graph_connector, self.auth_manager)
    
    async def process_email(self, email: Email, db: Session) -> Dict[str, Any]:
        """Process a single email - triage, categorize, extract info"""
        logger.info(f"Processing email: {email.subject}")
        
        # Generate email analysis using AI
        email_analysis = await self._analyze_email_with_ai(email)
        
        # Update email with AI-generated content
        email.summary = email_analysis.get("summary", "")
        email.status = "triaged"
        
        # Store suggested actions
        import json
        email.suggested_actions = json.dumps(email_analysis.get("suggestions", []))
        
        db.commit()
        
        return {
            "email_id": email.id,
            "analysis": email_analysis,
            "outlook_integration_ready": hasattr(email, 'outlook_id') and email.outlook_id is not None
        }
    
    async def sync_outlook_emails(self, db: Session, user_id: str = "default", 
                                 initial_sync: bool = False) -> Dict[str, Any]:
        """Sync emails from Outlook"""
        try:
            if initial_sync:
                synced_emails = await self.sync_service.initial_sync(db, user_id)
            else:
                synced_emails = await self.sync_service.delta_sync(db, user_id)
            
            return {
                "success": True,
                "synced_count": len(synced_emails),
                "emails": synced_emails
            }
        except Exception as e:
            logger.error(f"Outlook sync failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def setup_outlook_folders(self, user_id: str = "default") -> Dict[str, Any]:
        """Setup GTD folder structure in Outlook"""
        try:
            folder_ids = await self.folder_manager.setup_gtd_folders(user_id)
            return {
                "success": True,
                "folders_created": folder_ids
            }
        except Exception as e:
            logger.error(f"Folder setup failed: {e}")
            return {
                "success": False, 
                "error": str(e)
            }
    
    async def triage_outlook_email(self, email: Email, db: Session, 
                                  user_id: str = "default") -> Dict[str, Any]:
        """Triage an email with Outlook-specific actions"""
        if not hasattr(email, 'outlook_id') or not email.outlook_id:
            return await self.process_email(email, db)
        
        # Analyze email with AI
        email_analysis = await self._analyze_email_with_ai(email)
        
        # Get GTD recommendation
        gtd_category = self.folder_manager.get_gtd_recommendation(email_analysis)
        
        # Apply Outlook actions based on analysis
        outlook_actions = []
        
        try:
            # Move to appropriate GTD folder
            move_result = await self.folder_manager.move_email_to_gtd_folder(
                email.outlook_id, gtd_category, user_id
            )
            if move_result:
                outlook_actions.append(f"moved_to_{gtd_category}_folder")
            
            # Set COS extended properties
            cos_props = {}
            
            # Link to project if identified
            if email_analysis.get("project_id"):
                cos_props["COS.ProjectId"] = email_analysis["project_id"]
            
            # Link to tasks if extracted
            if email_analysis.get("extracted_tasks"):
                task_ids = [str(task.get("id", "")) for task in email_analysis["extracted_tasks"]]
                cos_props["COS.TaskIds"] = task_ids
            
            # Set confidence and processing metadata
            cos_props.update({
                "COS.Confidence": email_analysis.get("confidence", 0.8),
                "COS.Provenance": "AI"
            })
            
            if cos_props:
                props_result = await self.extended_props.set_cos_properties(
                    email.outlook_id, cos_props, user_id
                )
                if props_result:
                    outlook_actions.append("set_cos_properties")
            
        except Exception as e:
            logger.error(f"Outlook actions failed for email {email.id}: {e}")
        
        # Update local email record
        email.summary = email_analysis.get("summary", "")
        email.status = "triaged"
        email.folder = gtd_category
        
        if email_analysis.get("project_id"):
            email.project_id = email_analysis["project_id"]
            email.linked_at = datetime.utcnow()
        
        import json
        email.suggested_actions = json.dumps(email_analysis.get("suggestions", []))
        
        db.commit()
        
        return {
            "email_id": email.id,
            "analysis": email_analysis,
            "gtd_category": gtd_category,
            "outlook_actions": outlook_actions,
            "success": True
        }
    
    async def search_outlook_emails_by_project(self, project_id: str, 
                                              user_id: str = "default") -> List[Dict]:
        """Search for emails linked to a project in Outlook"""
        try:
            return await self.extended_props.search_by_project(project_id, user_id)
        except Exception as e:
            logger.error(f"Project email search failed: {e}")
            return []
    
    async def search_outlook_emails_by_task(self, task_id: str, 
                                           user_id: str = "default") -> List[Dict]:
        """Search for emails linked to a task in Outlook"""
        try:
            return await self.extended_props.search_by_task(task_id, user_id)
        except Exception as e:
            logger.error(f"Task email search failed: {e}")
            return []
    
    async def get_unprocessed_outlook_emails(self, user_id: str = "default") -> List[Dict]:
        """Get emails that haven't been processed by COS"""
        try:
            return await self.extended_props.get_unprocessed_emails(user_id)
        except Exception as e:
            logger.error(f"Unprocessed emails search failed: {e}")
            return []
    
    async def view_inbox_messages(self, db: Session, limit: int = 20) -> Dict[str, Any]:
        """Get and display inbox messages using the hybrid service"""
        try:
            # Ensure connection (this will also create folders if needed)
            if not self.hybrid_service.is_connected():
                connect_result = await self.hybrid_service.connect()
                if not connect_result.get("connected"):
                    return {
                        "success": False,
                        "message": connect_result.get("message", "Failed to connect to Outlook"),
                        "connection_help": connect_result.get("help")
                    }
            
            # Get messages from inbox
            messages = await self.hybrid_service.get_messages("Inbox", limit)
            
            if not messages:
                return {
                    "success": True,
                    "message": "Your inbox is empty or no messages could be retrieved.",
                    "messages": [],
                    "count": 0
                }
            
            # Sync retrieved messages to database if not already present
            synced_count = 0
            for msg_data in messages:
                existing = db.query(Email).filter(
                    Email.outlook_id == msg_data.get("id")
                ).first()
                
                if not existing and msg_data.get("id"):
                    new_email = Email(
                        outlook_id=msg_data["id"],
                        subject=msg_data.get("subject", ""),
                        sender=msg_data.get("sender", ""),
                        sender_name=msg_data.get("sender_name", ""),
                        body_content=msg_data.get("body_content", ""),
                        body_preview=msg_data.get("body_preview", ""),
                        received_at=msg_data.get("received_at"),
                        sent_at=msg_data.get("sent_at"),
                        is_read=msg_data.get("is_read", False),
                        importance=msg_data.get("importance", "normal"),
                        has_attachments=msg_data.get("has_attachments", False)
                    )
                    db.add(new_email)
                    synced_count += 1
            
            if synced_count > 0:
                db.commit()
            
            return {
                "success": True,
                "messages": messages,
                "count": len(messages),
                "synced_new": synced_count,
                "connection_method": self.hybrid_service._connection_method
            }
            
        except Exception as e:
            logger.error(f"Failed to view inbox messages: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to retrieve inbox messages"
            }
    
    async def _analyze_email_with_ai(self, email: Email) -> Dict[str, Any]:
        """Analyze email using AI to extract insights and suggestions"""
        context = {
            "email_subject": email.subject or "",
            "email_content": email.body_content or email.body_preview or "",
            "sender": email.sender or "",
            "sender_name": email.sender_name or "",
            "received_at": email.received_at.isoformat() if email.received_at else "",
            "importance": email.importance or "normal",
            "has_attachments": email.has_attachments or False
        }
        
        # Generate comprehensive email analysis
        response = await self.claude_client.generate_response(
            "system/emailtriage", 
            context=context, 
            user_input="analyze_email"
        )
        
        # Extract tasks from email content
        tasks = await self.claude_client.extract_tasks_from_text(
            email.body_content or email.body_preview or ""
        )
        
        # Generate action suggestions
        suggestions = await self.claude_client.generate_suggestions(context)
        
        return {
            "summary": response,
            "extracted_tasks": tasks,
            "suggestions": suggestions,
            "requires_action": "action" in response.lower(),
            "waiting_for_response": "waiting" in response.lower(),
            "is_meeting_related": any(word in (email.subject or "").lower() 
                                    for word in ["meeting", "calendar", "schedule"]),
            "is_reference": "reference" in response.lower(),
            "contains_tasks": len(tasks) > 0,
            "confidence": 0.8,  # Default confidence, could be enhanced with more AI analysis
            "project_id": None  # Would be determined by project matching logic
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