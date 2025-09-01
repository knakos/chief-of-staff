"""
Multi-agent system for Chief of Staff application.
Implements the COS orchestrator and specialized agents.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from models import Project, Task, ContextEntry, Interview, Digest
from claude_client import ClaudeClient
from job_queue import JobQueue
from integrations.outlook.connector import GraphAPIConnector
from integrations.outlook.auth import OutlookAuthManager
# EmailSyncService removed - no longer needed without database email storage
from integrations.outlook.folder_manager import GTDFolderManager
from integrations.outlook.extended_props import COSExtendedPropsManager
from integrations.outlook.hybrid_service import HybridOutlookService
from email_intelligence import EmailIntelligenceService

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
        self.email_intelligence = EmailIntelligenceService(claude_client)
    
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
            elif any(word in user_lower for word in ["recent", "latest", "new", "subjects", "five most recent"]):
                # User is asking about recent emails - fetch directly from Outlook
                try:
                    logger.info("Fetching live recent emails from Outlook for user request")
                    live_emails = await self.email_triage.hybrid_service.get_messages("Inbox", limit=5)
                    if live_emails:
                        context["live_recent_emails"] = []
                        for i, email in enumerate(live_emails, 1):
                            context["live_recent_emails"].append({
                                "number": i,
                                "subject": email.get("subject", "No Subject"),
                                "sender": email.get("sender_name", email.get("sender", "Unknown")),
                                "date": email.get("received_at", email.get("received_date_time", "Unknown"))
                            })
                        intent_actions.append("live_emails_fetched")
                        logger.info(f"Fetched {len(live_emails)} live emails from Outlook")
                    else:
                        context["live_recent_emails_error"] = "No emails found in Outlook"
                        logger.warning("No live emails found in Outlook")
                except Exception as e:
                    context["live_recent_emails_error"] = str(e)
                    logger.error(f"Failed to fetch live emails: {e}")
                    # Direct fetch failed, provide fallback info
                    context["outlook_fetch_error"] = str(e)
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
        # Email counts now handled directly via Outlook integration
        unprocessed_emails = 0  # Placeholder - would need Outlook query
        
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
        # Local unprocessed emails no longer stored in database
        local_unprocessed = []  # Placeholder - emails are now accessed directly from Outlook
        
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
            # Email database queries removed - emails accessed directly from Outlook
            existing = None  # Placeholder - no longer stored in database
            if not existing:
                # Email creation removed - emails accessed directly from Outlook
                logger.info(f"Processing Outlook email: {outlook_email.get('subject', 'No subject')}")
                # Email processing now handled by direct Outlook integration
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
        
        # /outlook sync removed - emails are accessed directly from Outlook, not synced to database
        
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
        
        elif "/outlook test" in command:
            # Test COM connector directly
            try:
                hybrid_service = self.email_triage.hybrid_service
                if hybrid_service.com_connector and hybrid_service.com_connector.is_connected():
                    # Test inbox access
                    folders = hybrid_service.com_connector.get_folders()
                    inbox_info = None
                    for folder in folders:
                        if folder["name"] == "Inbox":
                            inbox_info = folder
                            break
                    
                    if inbox_info:
                        # Test message retrieval
                        test_messages = hybrid_service.com_connector.get_messages(limit=5)
                        return f"COM Test Results:\n" \
                               f"- Inbox found: {inbox_info['name']}\n" \
                               f"- Inbox item count: {inbox_info['item_count']}\n" \
                               f"- Retrieved messages: {len(test_messages)}\n" \
                               f"- Message subjects: {[msg.get('subject', 'No subject')[:50] for msg in test_messages[:3]]}"
                    else:
                        return "COM Test: Inbox folder not found"
                else:
                    return "COM Test: COM connector not connected"
            except Exception as e:
                return f"COM Test failed: {str(e)}"

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
            return "Available Outlook commands: /outlook connect, /outlook setup, /outlook triage, /outlook status, /outlook info, /outlook test, /outlook disconnect"
    
    async def _build_current_context(self, db: Session) -> Dict[str, Any]:
        """Build current context for AI interactions"""
        # Get current projects, tasks, recent emails, etc.
        active_projects = db.query(Project).filter(Project.status == "active").all()
        recent_tasks = db.query(Task).filter(
            Task.created_at >= datetime.utcnow() - timedelta(days=7)
        ).all()
        # Recent email queries now handled by direct Outlook integration
        recent_emails = []  # Placeholder - emails accessed directly from Outlook
        
        context = {
            "current_time": datetime.utcnow().isoformat(),
            "active_projects": [{"id": p.id, "name": p.name, "status": p.status} for p in active_projects],
            "recent_tasks_count": len(recent_tasks),
            "recent_emails_count": len(recent_emails),
        }
        
        return context
    
    async def apply_email_action(self, email_id: str, action: str, payload: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        Apply an action to an email
        DEPRECATED: Email actions are now handled directly in app.py via handle_email_action
        This method is kept for backward compatibility but should not be used.
        """
        logger.warning("apply_email_action is deprecated - use handle_email_action in app.py instead")
        return {"success": False, "message": "Method deprecated - use direct email action handling"}
    
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
        # sync_service removed - no longer needed without database email storage
        self.folder_manager = GTDFolderManager(self.graph_connector, self.auth_manager)
        self.extended_props = COSExtendedPropsManager(self.graph_connector, self.auth_manager)
    
    async def process_email(self, email_data: dict, db: Session) -> Dict[str, Any]:
        """
        Process a single email - triage, categorize, extract info
        DEPRECATED: Email processing now handled by HybridOutlookService and app.py handlers
        """
        logger.warning("process_email is deprecated - use HybridOutlookService directly")
        return {"success": False, "message": "Method deprecated - use direct Outlook integration"}
    
    async def sync_outlook_emails(self, db: Session, user_id: str = "default", 
                                 initial_sync: bool = False) -> Dict[str, Any]:
        """
        Sync emails from Outlook 
        DEPRECATED: Email sync now handled by HybridOutlookService directly
        """
        logger.warning("sync_outlook_emails is deprecated - use HybridOutlookService.get_messages() instead")
        return {"success": False, "message": "Method deprecated - use direct Outlook integration"}
    
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
    
    async def triage_outlook_email(self, email_id: str, db: Session, 
                                  user_id: str = "default") -> Dict[str, Any]:
        """
        Triage an email with Outlook-specific actions
        DEPRECATED: Email triage now handled by HybridOutlookService with property sync
        """
        logger.warning("triage_outlook_email is deprecated - use handle_email_analyze in app.py instead")
        return {"success": False, "message": "Method deprecated - use direct Outlook integration with property sync"}
    
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
            
            # Email sync to database removed - emails accessed directly from Outlook
            synced_count = len(messages) if messages else 0
            logger.info(f"Retrieved {synced_count} emails directly from Outlook (no database storage)")
            
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
    
    async def _analyze_email_with_ai(self, email_data: dict) -> Dict[str, Any]:
        """Analyze email using AI to extract insights and suggestions"""
        context = {
            "email_subject": email_data.get("subject", ""),
            "email_content": email_data.get("body_content", "") or email_data.get("body_preview", ""),
            "sender": email_data.get("sender", ""),
            "sender_name": email_data.get("sender_name", ""),
            "received_at": email_data.get("received_at", ""),
            "importance": email_data.get("importance", "normal"),
            "has_attachments": email_data.get("has_attachments", False)
        }
        
        # Generate comprehensive email analysis
        response = await self.claude_client.generate_response(
            "system/emailtriage", 
            context=context, 
            user_input="analyze_email"
        )
        
        # Extract tasks from email content
        tasks = await self.claude_client.extract_tasks_from_text(
            email_data.get("body_content", "") or email_data.get("body_preview", "")
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