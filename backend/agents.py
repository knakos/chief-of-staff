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
from integrations.outlook.com_service import OutlookCOMService
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
    
    async def process_user_input(self, user_input: str, db: Session) -> Dict[str, Any]:
        """Process user input and coordinate appropriate responses"""
        logger.info(f"COS processing user input: {user_input}")
        
        # Check for explicit slash commands (for debugging/power users)
        if user_input.startswith("/"):
            return await self._handle_command(user_input, db)
        
        # For natural language, analyze intent and respond conversationally
        return await self._handle_conversation(user_input, db)
    
    async def _handle_command(self, command: str, db: Session) -> Dict[str, Any]:
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
            return {
                "text": f"Unknown command: {command}. Available commands: /plan, /summarize, /triage, /digest, /interview, /outlook",
                "actions": []
            }
    
    async def _handle_conversation(self, user_input: str, db: Session) -> Dict[str, Any]:
        """Handle conversational input with intent detection"""
        # Get current context for the user
        context = await self._build_current_context(db)
        user_lower = user_input.lower()
        
        # Detect intent and potentially execute actions behind the scenes
        intent_actions = []
        
        # Only handle explicit connection requests - don't automatically load data
        if any(word in user_lower for word in ["connect", "setup", "configure"]) and any(word in user_lower for word in ["outlook", "email"]):
            # Handle explicit Outlook connection requests
            connect_result = self.email_triage.com_service.connect()
            context["outlook_connection"] = connect_result
            intent_actions.append("outlook_connect_attempted")
        
        # Only load emails when specifically requested (not just navigation)
        elif any(phrase in user_lower for phrase in ["show me my emails", "what emails do I have", "recent emails", "latest emails", "my inbox messages"]):
            # User specifically requested email content - load it
            try:
                logger.info("User specifically requested email content - loading from Outlook")
                live_emails = self.email_triage.com_service.get_recent_emails("Inbox", limit=5)
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
        
        # Only trigger background jobs when explicitly requested
        elif any(word in user_lower for word in ["triage", "organize", "process"]) and any(word in user_lower for word in ["email", "inbox"]):
            # Explicit request to process/triage emails
            await self.job_queue.add_job("email_scan", {})
            intent_actions.append("email_triage_started")
        
        # Navigation related intents - use AI to detect navigation intent
        navigation_result = await self._detect_navigation_intent_ai(user_input, context)
        if navigation_result.get("wants_navigation") and navigation_result.get("confidence", 0) > 0.7:
            navigation_target = navigation_result.get("target")
            context["navigation_action"] = navigation_target
            intent_actions.append(f"navigate_to_{navigation_target}")
            logger.info(f"AI detected navigation intent: {navigation_target} (confidence: {navigation_result.get('confidence')})")
        
        # Add detected actions to context
        if intent_actions:
            context["detected_actions"] = intent_actions
        
        # Generate conversational response using COS orchestrator prompt
        text_response = await self.claude_client.generate_response(
            "system/cos",
            context=context,
            user_input=user_input
        )
        
        # Create structured response
        response = {
            "text": text_response,
            "actions": []
        }
        
        # Add navigation action if detected
        if "navigation_action" in context:
            response["actions"].append({
                "type": "navigate",
                "target": context["navigation_action"]
            })
        
        return response
    
    async def _detect_navigation_intent_ai(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to detect navigation intent in user input"""
        try:
            # Prepare context for navigation analysis
            nav_context = {
                "user_input": user_input,
                "current_context": context.get("request_type", "general"),
                "available_areas": ["inbox", "emails", "projects", "profile", "contacts"]
            }
            
            # Get AI analysis of navigation intent
            response = await self.claude_client.generate_response(
                "tools/navigation",
                context=nav_context,
                user_input=user_input
            )
            
            # Parse JSON response
            import json
            try:
                result = json.loads(response.strip())
                logger.info(f"Navigation AI analysis: {result}")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse navigation response as JSON: {e}")
                logger.error(f"Raw response: {response}")
                # Fallback to no navigation
                return {
                    "wants_navigation": False,
                    "target": None,
                    "confidence": 0.0,
                    "reasoning": "Failed to parse AI response"
                }
                
        except Exception as e:
            logger.error(f"Error in AI navigation detection: {e}")
            # Fallback to no navigation
            return {
                "wants_navigation": False,
                "target": None,
                "confidence": 0.0,
                "reasoning": f"Error: {str(e)}"
            }
    
    async def _generate_plan(self, db: Session) -> Dict[str, Any]:
        """Generate a work plan based on current context"""
        context = await self._build_current_context(db)
        
        # Get active projects and tasks
        active_projects = db.query(Project).filter(Project.status == "active").all()
        pending_tasks = db.query(Task).filter(Task.status.in_(["not_started", "active"])).all()
        # Email counts now handled directly via Outlook integration
        unprocessed_emails = 0  # Placeholder - would need Outlook query
        
        context.update({
            "active_projects_count": len(active_projects),
            "pending_tasks_count": len(pending_tasks),
            "unprocessed_emails_count": unprocessed_emails,
            "request_type": "planning"
        })
        
        text_response = await self.claude_client.generate_response("system/cos", context=context, user_input="/plan")
        return {"text": text_response, "actions": []}
    
    async def _generate_summary(self, db: Session) -> Dict[str, Any]:
        """Generate a summary of current work status"""
        context = await self._build_current_context(db)
        context["request_type"] = "summary"
        
        text_response = await self.claude_client.generate_response("system/cos", context=context, user_input="/summarize")
        return {"text": text_response, "actions": []}
    
    async def _triage_inbox(self, db: Session) -> Dict[str, Any]:
        """Trigger email triage process for both local and Outlook emails"""
        # Add email scan job to queue
        await self.job_queue.add_job("email_scan", {})
        
        # Get local unprocessed emails
        # Local unprocessed emails no longer stored in database
        local_unprocessed = []  # Placeholder - emails are now accessed directly from Outlook
        
        # Get Outlook unprocessed emails if connected
        outlook_unprocessed = []
        if self.email_triage.com_service.is_connected():
            outlook_unprocessed = self.email_triage.com_service.get_recent_emails("Inbox", limit=10)
        
        total_unprocessed = len(local_unprocessed) + len(outlook_unprocessed)
        
        if total_unprocessed == 0:
            return {"text": "Inbox is already up to date. No new emails to process.", "actions": []}
        
        # In COM-only mode, emails are processed directly via Outlook COM interface
        # No additional processing needed - COM service handles email operations
        processed_count = len(outlook_unprocessed)
        
        if processed_count > 0:
            logger.info(f"Found {processed_count} emails in Outlook inbox - processing handled via COM interface")
        
        context = {
            "processed_count": processed_count,
            "total_unprocessed": total_unprocessed,
            "outlook_connected": self.email_triage.com_service.is_connected(),
            "request_type": "triage"
        }
        
        text_response = await self.claude_client.generate_response("system/cos", context=context, user_input="/triage")
        
        # Add navigation to emails view for triage
        actions = [{"type": "navigate", "target": "emails"}]
        
        return {"text": text_response, "actions": actions}
    
    async def _generate_digest(self, db: Session) -> Dict[str, Any]:
        """Generate daily/weekly digest"""
        # Add digest build job to queue
        await self.job_queue.add_job("digest_build", {"type": "daily"})
        
        context = await self._build_current_context(db)
        context["request_type"] = "digest"
        
        text_response = await self.claude_client.generate_response("tools/digest", context=context)
        return {"text": text_response, "actions": []}
    
    async def _start_interview(self, db: Session) -> Dict[str, Any]:
        """Start context interview process"""
        # Check if we've already done an interview today
        today = datetime.utcnow().date()
        recent_interview = db.query(Interview).filter(
            Interview.asked_at >= datetime.combine(today, datetime.min.time())
        ).first()
        
        if recent_interview:
            return {"text": "I've already conducted a context interview today. I'll wait until tomorrow to ask more questions to avoid interrupting your work flow.", "actions": []}
        
        # Generate interview question
        context = await self._build_current_context(db)
        question = await self.claude_client.generate_response("tools/interview", context=context)
        
        # Create interview record
        interview = Interview(
            question=question,
            status="not_started",
            trigger_source="manual_request",
            importance_score=0.7
        )
        db.add(interview)
        db.commit()
        
        return {"text": f"Context Interview Question:\n\n{question}\n\n(You can answer this later - it helps me understand your priorities better)", "actions": []}
    
    async def _handle_outlook_command(self, command: str, db: Session) -> Dict[str, Any]:
        """Handle Outlook-specific commands using COM-only service"""
        logger.info(f"_handle_outlook_command called with: {command}")
        
        if "/outlook connect" in command:
            # Connect via COM service
            try:
                com_service = self.email_triage.com_service
                result = com_service.connect()
                
                if result.get('connected'):
                    account_info = result.get('account_info', {})
                    primary_account = account_info.get('primary_account', {})
                    account_name = primary_account.get('name', 'Unknown Account')
                    primary_email = primary_account.get('email', '')
                    
                    # Initialize task suggester with user context
                    if primary_email:
                        from email_intelligence import task_suggester
                        task_suggester.set_user_context(primary_email)
                        logger.info(f"🧠 Initialized task suggester with user context: {primary_email}")
                    
                    return {"text": f"✅ Connected to Outlook via COM\nAccount: {account_name}\nMethod: {result.get('method')}", "actions": []}
                else:
                    return {"text": f"❌ Connection failed: {result.get('message', 'Unknown error')}", "actions": []}
                    
            except Exception as e:
                logger.error(f"COM connection failed: {e}")
                return {"text": f"❌ Connection failed: {str(e)}", "actions": []}
        
        # /outlook sync removed - emails are accessed directly from Outlook, not synced to database
        
        elif "/outlook setup" in command:
            # Setup GTD folders using COM service
            try:
                com_service = self.email_triage.com_service
                
                # Ensure connection
                if not com_service.is_connected():
                    connection_result = com_service.connect()
                    if not connection_result.get('connected'):
                        return {"text": f"❌ Cannot setup folders: {connection_result.get('message', 'Connection failed')}", "actions": []}
                
                # Setup GTD folders
                folder_results = com_service.setup_gtd_folders()
                
                successful_folders = [name for name, success in folder_results.items() if success]
                failed_folders = [name for name, success in folder_results.items() if not success]
                
                result_msg = f"✅ GTD Folder Setup Complete!\n"
                if successful_folders:
                    result_msg += f"Created/Found: {', '.join(successful_folders)}\n"
                if failed_folders:
                    result_msg += f"❌ Failed: {', '.join(failed_folders)}"
                    
                return result_msg
                
            except Exception as e:
                logger.error(f"Outlook setup error: {e}")
                return {"text": f"❌ Folder setup failed: {str(e)}", "actions": []}
        
        elif "/outlook test" in command:
            # Test COM service functionality
            try:
                com_service = self.email_triage.com_service
                
                # Test connection
                if not com_service.is_connected():
                    connection_result = com_service.connect()
                    if not connection_result.get('connected'):
                        return {"text": f"❌ COM Test Failed: {connection_result.get('message', 'Connection failed')}", "actions": []}
                
                # Test folder access
                folders = com_service.get_folders()
                inbox_info = None
                for folder in folders:
                    if folder["name"] == "Inbox":
                        inbox_info = folder
                        break
                
                if not inbox_info:
                    return {"text": "❌ COM Test Failed: Inbox folder not found", "actions": []}
                
                # Test email retrieval with analysis
                test_emails = await com_service.get_recent_emails_with_analysis("Inbox", 3)
                
                result = f"✅ COM Test Results:\n"
                result += f"- Connection: Active\n"
                result += f"- Inbox found: {inbox_info['name']} ({inbox_info['item_count']} items)\n"
                result += f"- Retrieved emails: {len(test_emails)}\n"
                
                if test_emails:
                    result += f"- Sample subjects:\n"
                    for i, email in enumerate(test_emails[:3], 1):
                        subject = email.get('subject', 'No subject')[:40]
                        analysis = email.get('analysis', {})
                        priority = analysis.get('priority', 'None') if analysis else 'None'
                        result += f"  {i}. {subject} (Priority: {priority})\n"
                
                return result
                
            except Exception as e:
                logger.error(f"COM test failed: {e}")
                return {"text": f"❌ COM Test failed: {str(e)}", "actions": []}

        elif "/outlook triage" in command:
            # Email triage now handled directly via COM integration without database storage
            return {"text": "Email triage functionality has been simplified - emails are processed directly from Outlook without database storage. Use email analysis features in the UI instead.", "actions": []}
        
        elif "/outlook disconnect" in command:
            # COM connection doesn't require explicit disconnect
            return {"text": "COM connection automatically manages Outlook connection. No manual disconnect needed.", "actions": []}
        
        elif "/outlook info" in command:
            # Get connection info from COM service
            try:
                com_service = self.email_triage.get_com_service()
                connection_info = com_service.get_connection_info()
                if connection_info['connected']:
                    return {"text": f"✅ Connected via COM\nAccount: {connection_info.get('account_info', {}).get('display_name', 'Unknown')}", "actions": []}
                else:
                    return {"text": "❌ Not connected to Outlook. Use '/outlook connect' to connect.", "actions": []}
            except Exception as e:
                logger.error(f"Error getting connection info: {e}")
                return {"text": f"Error getting connection info: {str(e)}", "actions": []}
        
        elif "/outlook status" in command:
            # Get COM connection status 
            logger.info("Processing /outlook status command")
            try:
                com_service = self.email_triage.get_com_service()
                if com_service.is_connected():
                    return {"text": "✅ Outlook connected via COM. Ready to process emails.", "actions": []}
                else:
                    return {"text": "❌ Not connected to Outlook. Use '/outlook connect' to connect.", "actions": []}
            except Exception as e:
                logger.error(f"Error processing /outlook status: {e}")
                return {"text": f"Error checking Outlook status: {str(e)}", "actions": []}
        
        else:
            return {"text": "Available Outlook commands: /outlook connect, /outlook setup, /outlook triage, /outlook status, /outlook info, /outlook test, /outlook disconnect", "actions": []}
    
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
    """Agent responsible for email processing and triage with COM-only Outlook integration"""
    
    def __init__(self, claude_client: ClaudeClient):
        super().__init__(claude_client)
        
        # Initialize COM-only Outlook service
        self.com_service = OutlookCOMService()
        
        # Initialize and inject intelligence service
        self.intelligence_service = EmailIntelligenceService(claude_client)
        self.com_service.intelligence_service = self.intelligence_service
    
    def setup_outlook_folders(self) -> Dict[str, Any]:
        """Setup GTD folder structure in Outlook using COM service"""
        try:
            results = self.com_service.setup_gtd_folders()
            return {
                "success": True,
                "folders_created": results
            }
        except Exception as e:
            logger.error(f"Folder setup failed: {e}")
            return {
                "success": False, 
                "error": str(e)
            }
    
    
    
    
    def get_com_service(self) -> OutlookCOMService:
        """Get the COM service instance for direct email operations"""
        return self.com_service
    

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