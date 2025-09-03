"""
Main FastAPI application for Chief of Staff backend.
Handles WebSocket communication and provides REST API endpoints.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from pydantic import BaseModel

from models import Base, Area, Project, Task, ContextEntry, Job, Interview, Digest
from job_queue import JobQueue
from claude_client import ClaudeClient
from agents import COSOrchestrator

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables explicitly
import os
from dotenv import load_dotenv

# Load .env file
env_loaded = load_dotenv()
logger.info(f"Environment file loading: {'SUCCESS' if env_loaded else 'FAILED'}")

# Debug environment variables loading
logger.info("Environment variables check:")
logger.info(f"  MICROSOFT_CLIENT_ID: {'SET' if os.getenv('MICROSOFT_CLIENT_ID') else 'NOT SET'}")
logger.info(f"  MICROSOFT_CLIENT_SECRET: {'SET' if os.getenv('MICROSOFT_CLIENT_SECRET') else 'NOT SET'}")
logger.info(f"  MICROSOFT_TENANT_ID: {os.getenv('MICROSOFT_TENANT_ID', 'NOT SET')}")
logger.info(f"  Current working directory: {os.getcwd()}")
logger.info(f"  .env file exists: {os.path.exists('.env')}")

# Try to load .env file manually if it exists
if os.path.exists('.env'):
    logger.info("Found .env file, checking contents...")
    try:
        with open('.env', 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines, 1):
                if 'MICROSOFT_CLIENT_ID' in line and not line.strip().startswith('#'):
                    logger.info(f"  Line {i}: {line.strip()}")
                elif 'MICROSOFT_CLIENT_SECRET' in line and not line.strip().startswith('#'):
                    logger.info(f"  Line {i}: MICROSOFT_CLIENT_SECRET=[REDACTED] (length: {len(line.split('=', 1)[1].strip()) if '=' in line else 0})")
    except Exception as e:
        logger.error(f"Error reading .env file: {e}")
else:
    logger.warning("No .env file found in current directory")

# Database setup with optimizations
DATABASE_URL = "sqlite:///./cos.db"
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}, 
    poolclass=StaticPool,
    pool_pre_ping=True,
    echo=False  # Set to True for SQL debugging
)

# SQLite optimizations disabled for WSL compatibility
# @event.listens_for(engine, "connect")
# def set_sqlite_pragma(dbapi_connection, connection_record):
#     cursor = dbapi_connection.cursor()
#     cursor.execute("PRAGMA journal_mode=DELETE")
#     cursor.execute("PRAGMA synchronous=NORMAL") 
#     cursor.execute("PRAGMA cache_size=10000")
#     cursor.execute("PRAGMA temp_store=MEMORY")
#     cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Global instances
job_queue = JobQueue()
claude_client = ClaudeClient()
cos_orchestrator = COSOrchestrator(claude_client, job_queue)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
    
    # Start job queue
    await job_queue.start()
    logger.info("Job queue started")
    
    # Auto-connect to Outlook
    try:
        connection_result = await cos_orchestrator.email_triage.hybrid_service.connect()
        logger.info(f"Outlook auto-connection: {connection_result}")
    except Exception as e:
        logger.warning(f"Failed to auto-connect to Outlook: {e}")
    
    yield
    
    # Cleanup
    await job_queue.stop()
    logger.info("Job queue stopped")

app = FastAPI(title="Chief of Staff API", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        connection_id = str(id(websocket))
        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            "connected_at": datetime.utcnow(),
            "last_ping": datetime.utcnow()
        }
        logger.info(f"WebSocket connected: {connection_id}. Total: {len(self.active_connections)}")
        return connection_id

    def disconnect(self, websocket: WebSocket):
        connection_id = str(id(websocket))
        self.active_connections.pop(connection_id, None)
        self.connection_metadata.pop(connection_id, None)
        logger.info(f"WebSocket disconnected: {connection_id}. Total: {len(self.active_connections)}")

    async def send_to_all(self, event: str, data: Any):
        """Send message to all connected clients with improved error handling"""
        if not self.active_connections:
            return
            
        message_text = json.dumps({"event": event, "data": data}, default=str)
        disconnected_ids = []
        
        # Use asyncio.gather for concurrent sending
        send_tasks = []
        for connection_id, connection in self.active_connections.items():
            send_tasks.append(self._send_safe(connection_id, connection, message_text))
        
        results = await asyncio.gather(*send_tasks, return_exceptions=True)
        
        # Clean up failed connections
        for i, (connection_id, result) in enumerate(zip(self.active_connections.keys(), results)):
            if isinstance(result, Exception):
                disconnected_ids.append(connection_id)
        
        for conn_id in disconnected_ids:
            self.active_connections.pop(conn_id, None)
            self.connection_metadata.pop(conn_id, None)
    
    async def _send_safe(self, connection_id: str, connection: WebSocket, message: str):
        """Safely send message to a single connection"""
        try:
            await connection.send_text(message)
        except Exception as e:
            logger.error(f"Error sending to WebSocket {connection_id}: {e}")
            raise

    async def send_to_client(self, websocket: WebSocket, event: str, data: Any):
        """Send message to specific client"""
        message = {"event": event, "data": data}
        try:
            await websocket.send_text(json.dumps(message, default=str))
        except Exception as e:
            logger.error(f"Error sending to specific WebSocket: {e}")
            # Try with simplified error response
            try:
                error_message = {"event": "error", "data": {"message": str(e)}}
                await websocket.send_text(json.dumps(error_message, default=str))
            except:
                pass  # If even error sending fails, give up gracefully
    
    async def broadcast_to_all(self, event: str, data: Any):
        """Broadcast message to all connected clients"""
        message = {"event": event, "data": data}
        message_str = json.dumps(message, default=str)
        
        disconnected = []
        for connection_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message_str)
            except Exception as e:
                logger.warning(f"Failed to send to connection {connection_id}: {e}")
                disconnected.append(connection_id)
        
        # Clean up disconnected clients
        for conn_id in disconnected:
            self.active_connections.pop(conn_id, None)
            self.connection_metadata.pop(conn_id, None)

manager = ConnectionManager()

# Global function to broadcast usage updates
async def broadcast_usage_update():
    """Broadcast usage statistics to all connected clients"""
    try:
        usage_stats = claude_client.get_usage_stats()
        await manager.broadcast_to_all("status:usage", usage_stats)
    except Exception as e:
        logger.error(f"Error broadcasting usage update: {e}")

# Set the usage callback on claude_client
claude_client.usage_update_callback = broadcast_usage_update

# WebSocket message handlers
class WSMessageHandler:
    def __init__(self, websocket: WebSocket, db: Session):
        self.websocket = websocket
        self.db = db

    async def handle_message(self, event: str, data: Dict[str, Any]):
        """Route WebSocket messages to appropriate handlers"""
        handlers = {
            "thread:send": self.handle_thread_send,
            "email:apply_action": self.handle_email_action,
            "interview:answer": self.handle_interview_answer,
            "interview:dismiss": self.handle_interview_dismiss,
            "project:create": self.handle_project_create,
            "project:load_dashboard": self.handle_load_dashboard,
            "project:insight_action": self.handle_insight_action,
            "task:create": self.handle_task_create,
            "task:update": self.handle_task_update,
            "email:analyze": self.handle_email_analyze,
            "email:get_recent": self.handle_get_recent_emails,
            "status:request": self.handle_status_request,
        }
        
        logger.info(f"Received WebSocket event: {event}")
        handler = handlers.get(event)
        if handler:
            try:
                await handler(data)
            except Exception as e:
                logger.error(f"Error handling {event}: {e}")
                await manager.send_to_client(
                    self.websocket, 
                    "error", 
                    {"message": f"Error processing {event}: {str(e)}"}
                )
        else:
            logger.warning(f"Unknown WebSocket event: {event}")

    async def handle_thread_send(self, data: Dict[str, Any]):
        """Handle chat messages from user"""
        text = data.get("text", "").strip()
        if not text:
            return

        # Update Claude client activity tracking
        cos_orchestrator.claude_client.update_activity()
        
        # Don't echo user message - frontend handles it immediately

        # Process with COS orchestrator
        response = await cos_orchestrator.process_user_input(text, self.db)
        
        # Send agent response
        await manager.send_to_client(
            self.websocket,
            "thread:append",
            {
                "message": {
                    "id": str(datetime.utcnow().timestamp()),
                    "role": "agent",
                    "content": response
                }
            }
        )

    async def handle_email_action(self, data: Dict[str, Any]):
        """Handle email action application"""
        email_id = data.get("email_id")  # Changed from thread_id to email_id
        action = data.get("action")
        payload = data.get("payload")
        
        if not email_id or not action:
            await manager.send_to_client(
                self.websocket,
                "email:action_error",
                {"message": "Email ID and action required"}
            )
            return
        
        try:
            # Get email directly from Outlook using hybrid service
            hybrid_service = cos_orchestrator.email_triage.hybrid_service
            email_schema = await hybrid_service.load_email_with_cos_data(email_id)
            
            if not email_schema:
                await manager.send_to_client(
                    self.websocket,
                    "email:action_error",
                    {"message": "Email not found in Outlook"}
                )
                return
            
            # Apply action based on type
            result = {"success": False, "message": "Unknown action"}
            
            if action == "move_to_folder":
                folder_name = payload.get("folder_name")
                if folder_name:
                    success = await hybrid_service.move_email(email_id, folder_name)
                    result = {"success": success, "message": f"Email {'moved to' if success else 'failed to move to'} {folder_name}"}
            
            elif action == "mark_read":
                # This would require implementing mark_read in hybrid service
                result = {"success": True, "message": "Action noted (implementation pending)"}
            
            elif action == "extract_tasks":
                # Extract tasks and potentially create them in the system
                if email_schema.analysis and email_schema.analysis.extracted_tasks:
                    result = {"success": True, "tasks": email_schema.analysis.extracted_tasks, "message": "Tasks extracted"}
                else:
                    result = {"success": False, "message": "No tasks found to extract"}
            
            # Send result back
            await manager.send_to_client(
                self.websocket,
                "email:action_applied",
                {"email_id": email_id, "action": action, "result": result}
            )
            
        except Exception as e:
            logger.error(f"Error applying email action: {e}")
            await manager.send_to_client(
                self.websocket,
                "email:action_error", 
                {"message": f"Action failed: {str(e)}"}
            )

    async def handle_interview_answer(self, data: Dict[str, Any]):
        """Handle interview question answer"""
        interview_id = data.get("interview_id")
        answer = data.get("answer")
        
        if not interview_id or not answer:
            return
        
        interview = self.db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            return
        
        # Record answer
        interview.answer = answer
        interview.answered_at = datetime.utcnow()
        interview.status = "completed"
        self.db.commit()
        
        # Process answer with COS orchestrator
        await cos_orchestrator.process_interview_answer(interview, self.db)

    async def handle_interview_dismiss(self, data: Dict[str, Any]):
        """Handle interview dismissal"""
        interview_id = data.get("interview_id")
        
        if not interview_id:
            return
        
        interview = self.db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            return
        
        interview.status = "dismissed"
        interview.dismissed_at = datetime.utcnow()
        self.db.commit()

    async def handle_project_create(self, data: Dict[str, Any]):
        """Create new project"""
        name = data.get("name")
        description = data.get("description", "")
        
        if not name:
            return
        
        project = Project(name=name, description=description)
        self.db.add(project)
        self.db.commit()
        
        await manager.send_to_client(
            self.websocket,
            "project:created",
            {"id": project.id, "name": project.name}
        )

    async def handle_task_create(self, data: Dict[str, Any]):
        """Create new task"""
        title = data.get("title")
        project_id = data.get("project_id")
        description = data.get("description", "")
        
        if not title:
            return
        
        task = Task(title=title, project_id=project_id, description=description)
        self.db.add(task)
        self.db.commit()
        
        await manager.send_to_client(
            self.websocket,
            "task:created",
            {"id": task.id, "title": task.title}
        )

    async def handle_status_request(self, data: Dict[str, Any]):
        """Handle status request from frontend"""
        logger.info("Received status request from frontend")
        try:
            # AI Status - only perform connection check after idle timeout
            if claude_client and hasattr(claude_client, 'client') and claude_client.should_check_connection():
                # Only check AI connection after idle timeout to prevent rate limiting
                try:
                    # Quick health check - use cached response to avoid API call
                    ai_status = {
                        "status": "connected",
                        "provider": "Anthropic", 
                        "model": "Claude-3.5-Sonnet",
                        "last_check": "idle_timeout_reached"
                    }
                    logger.info("AI status: Connection check allowed after idle period")
                except Exception as e:
                    ai_status = {
                        "status": "error",
                        "error": str(e),
                        "provider": "Anthropic",
                        "model": "Claude-3.5-Sonnet"
                    }
                    logger.error(f"AI connection check failed: {e}")
            else:
                # Skip connection check if not idle long enough or no client
                ai_status = {
                    "status": "connected" if claude_client and hasattr(claude_client, 'client') else "no_client",
                    "provider": "Anthropic",
                    "model": "Claude-3.5-Sonnet",
                    "check_status": "skipped_idle_timeout" if claude_client else "no_client"
                }
            
            # Outlook Status - lightweight check without establishing new connections
            outlook_status = {"status": "disconnected", "method": None}
            try:
                # Check existing connection state without calling connect()
                hybrid_service = cos_orchestrator.email_triage.hybrid_service
                
                # Check if there's an active connection method
                if hasattr(hybrid_service, '_connection_method') and hybrid_service._connection_method:
                    logger.info(f"Status check: Found existing {hybrid_service._connection_method} connection")
                    outlook_status = {
                        "status": "connected",
                        "method": hybrid_service._connection_method
                    }
                else:
                    # Lightweight COM test without full connection
                    from integrations.outlook.com_connector import COM_AVAILABLE
                    if COM_AVAILABLE:
                        try:
                            import win32com.client
                            # Quick test - try to get Outlook object without full connection
                            outlook_app = win32com.client.GetActiveObject("Outlook.Application")
                            if outlook_app:
                                logger.info("Status check: Outlook application is running")
                                outlook_status = {
                                    "status": "connected",
                                    "method": "com"
                                }
                        except:
                            logger.info("Status check: Outlook application not accessible")
                        
            except Exception as e:
                logger.info(f"Outlook status check failed: {e}")
            
            # Send status updates
            await manager.send_to_client(self.websocket, "status:ai", ai_status)
            await manager.send_to_client(self.websocket, "status:outlook", outlook_status)
            
            # Send usage statistics update
            usage_stats = claude_client.get_usage_stats()
            await manager.send_to_client(self.websocket, "status:usage", usage_stats)
            
            logger.info(f"Status update sent - AI: {ai_status['status']}, Outlook: {outlook_status['status']}, Usage: {usage_stats['calls_today']} calls today")
            
        except Exception as e:
            logger.error(f"Error handling status request: {e}")

    async def handle_load_dashboard(self, data: Dict[str, Any]):
        """Load project dashboard data"""
        try:
            from models import Area, Project, Task
            
            # Load areas with project counts
            areas = []
            for area in self.db.query(Area).order_by(Area.sort_order).all():
                project_count = self.db.query(Project).filter_by(area_id=area.id).count()
                active_task_count = self.db.query(Task).join(Project).filter(
                    Project.area_id == area.id,
                    Task.status.in_(['pending', 'in_progress'])
                ).count()
                
                areas.append({
                    "id": area.id,
                    "name": area.name,
                    "description": area.description,
                    "color": area.color,
                    "is_system": area.is_system,
                    "is_default": area.is_default,
                    "sort_order": area.sort_order,
                    "project_count": project_count,
                    "active_tasks": active_task_count
                })

            # Load projects with task counts and health scores
            projects = []
            for project in self.db.query(Project).join(Area).order_by(Area.sort_order, Project.sort_order).all():
                task_count = self.db.query(Task).filter_by(project_id=project.id).count()
                completed_count = self.db.query(Task).filter_by(project_id=project.id, status='completed').count()
                
                # Simple health score calculation (completion rate + activity)
                completion_rate = (completed_count / task_count * 100) if task_count > 0 else 100
                health_score = int(completion_rate)  # Simplified for now
                
                # Get next due task
                next_due_task = None
                next_task = self.db.query(Task).filter_by(project_id=project.id)\
                    .filter(Task.status.in_(['pending', 'in_progress']))\
                    .filter(Task.due_date.isnot(None))\
                    .order_by(Task.due_date).first()
                
                if next_task:
                    next_due_task = {
                        "id": next_task.id,
                        "title": next_task.title,
                        "due_date": next_task.due_date.isoformat() if next_task.due_date else None
                    }

                projects.append({
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "area_id": project.area_id,
                    "area_name": project.area.name,
                    "status": project.status,
                    "priority": project.priority,
                    "is_catch_all": project.is_catch_all,
                    "is_system": project.is_system,
                    "color": project.color or project.area.color,
                    "task_count": task_count,
                    "completed_tasks": completed_count,
                    "health_score": health_score,
                    "next_due_task": next_due_task
                })

            # Load tasks
            tasks = []
            for task in self.db.query(Task).join(Project).join(Area).all():
                tasks.append({
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "status": task.status,
                    "priority": task.priority,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "project_id": task.project_id,
                    "project_name": task.project.name,
                    "area_id": task.project.area_id,
                    "area_name": task.project.area.name,
                    "suggested_next": False  # TODO: Add AI suggestion logic
                })

            await manager.send_to_client(
                self.websocket,
                "project:data_update",
                {
                    "areas": areas,
                    "projects": projects,
                    "tasks": tasks
                }
            )
            
        except Exception as e:
            logger.error(f"Error loading dashboard data: {e}")
            await manager.send_to_client(
                self.websocket,
                "error",
                {"message": f"Failed to load dashboard: {str(e)}"}
            )

    async def handle_task_update(self, data: Dict[str, Any]):
        """Handle task status updates"""
        task_id = data.get("task_id")
        updates = {k: v for k, v in data.items() if k != "task_id"}
        
        if not task_id:
            return

        try:
            task = self.db.query(Task).filter_by(id=task_id).first()
            if not task:
                return

            # Apply updates
            for key, value in updates.items():
                if hasattr(task, key):
                    setattr(task, key, value)

            # Set completed_at if status changed to completed
            if updates.get("status") == "completed" and task.completed_at is None:
                task.completed_at = datetime.utcnow()
            elif updates.get("status") != "completed":
                task.completed_at = None

            self.db.commit()

            # Broadcast task status change
            await manager.send_to_all(
                "task:status_change",
                {"task_id": task_id, "status": task.status}
            )

        except Exception as e:
            logger.error(f"Error updating task {task_id}: {e}")
            self.db.rollback()

    async def handle_insight_action(self, data: Dict[str, Any]):
        """Handle insight action execution"""
        insight_id = data.get("insight_id")
        action = data.get("action")
        action_data = data.get("data", {})
        
        logger.info(f"Executing insight action: {action} for insight {insight_id}")
        
        # TODO: Implement actual insight action logic
        # For now, just acknowledge the action
        await manager.send_to_client(
            self.websocket,
            "insight:action_completed",
            {"insight_id": insight_id, "action": action, "success": True}
        )

    async def handle_email_analyze(self, data: Dict[str, Any]):
        """Handle email analysis request"""
        try:
            email_id = data.get("email_id")
            subject = data.get("subject", "Unknown")
            logger.info(f"🔄 Starting email analysis for: {email_id} - '{subject[:50]}' [UPDATED]")
            
            if not email_id:
                logger.error("Email analysis failed: No email ID provided")
                await manager.send_to_client(
                    self.websocket,
                    "email:analysis_error", 
                    {"message": "Email ID required"}
                )
                return
            
            # Use EmailIntelligenceService directly with the provided data
            subject = data.get("subject", "")
            content = data.get("content", "")
            sender = data.get("sender", "")
            
            # Create email data for analysis
            email_data = {
                "id": email_id,
                "subject": subject,
                "body_content": content,
                "body_preview": content[:200] if content else "",
                "sender_name": sender,
                "sender": sender,
                "received_at": "now"
            }
            
            # Analyze email with intelligence service
            logger.info(f"📧 Calling email intelligence service for analysis...")
            from email_intelligence import EmailIntelligenceService
            from claude_client import ClaudeClient
            
            claude_client = ClaudeClient()
            intel_service = EmailIntelligenceService(claude_client)
            analysis = await intel_service.analyze_email(email_data)
            logger.info(f"✅ Analysis completed: {analysis.get('priority', 'N/A')}/{analysis.get('tone', 'N/A')}/{analysis.get('urgency', 'N/A')}")
            
            # Try to sync analysis to Outlook properties via COM
            try:
                from integrations.outlook.com_connector import OutlookCOMConnector
                from integrations.outlook.property_sync import OutlookPropertySync
                
                com_connector = OutlookCOMConnector()
                if com_connector.connect():
                    outlook_item = com_connector.namespace.GetItemFromID(email_id)
                    if outlook_item:
                        # Create a simple object to hold analysis for property sync
                        class SimpleEmailSchema:
                            def __init__(self):
                                self.id = email_id
                                self.subject = subject
                                self.analysis = analysis
                                self.project_id = None
                                self.confidence = analysis.get('confidence', 0.8)
                                self.provenance = 'ai_analysis'
                        
                        email_schema = SimpleEmailSchema()
                        
                        prop_sync = OutlookPropertySync()
                        prop_sync.com_connector = com_connector
                        sync_success = prop_sync.write_cos_data_to_outlook(email_schema, outlook_item)
                        
                        if sync_success:
                            logger.info(f"Successfully synced analysis to Outlook for email: {subject[:50]}")
                        else:
                            logger.warning(f"Failed to sync analysis to Outlook for email: {subject[:50]}")
                    else:
                        logger.warning(f"Could not find Outlook item for email: {email_id}")
                else:
                    logger.warning("Could not connect to Outlook for property sync")
            except Exception as sync_e:
                logger.error(f"Error syncing analysis to Outlook: {sync_e}")
            
            # Send analysis result
            logger.info(f"📤 Sending analysis result to frontend: {email_id}")
            await manager.send_to_client(
                self.websocket,
                "email:analyzed",
                {"email_id": email_id, "analysis": analysis}
            )
            
            # Send usage stats update
            try:
                usage_stats = {
                    "calls_today": getattr(claude_client, 'calls_today', 0) + 1,
                    "last_call": "now",
                    "status": "active"
                }
                await manager.send_to_client(
                    self.websocket,
                    "status:usage",
                    usage_stats
                )
            except Exception as usage_e:
                logger.warning(f"Failed to send usage stats update: {usage_e}")
            
        except Exception as e:
            logger.error(f"Error analyzing email: {e}")
            await manager.send_to_client(
                self.websocket,
                "email:analysis_error",
                {"message": f"Analysis failed: {str(e)}"}
            )

    async def handle_get_recent_emails(self, data: Dict[str, Any]):
        """Handle request for recent emails - fetch only, no analysis"""
        try:
            limit = data.get("limit", 10)
            logger.info(f"Getting recent emails with limit: {limit}")
            
            # Get recent emails directly from Outlook using LEGACY METHOD ONLY
            hybrid_service = cos_orchestrator.email_triage.hybrid_service
            logger.info(f"Hybrid service connection method: {hybrid_service._connection_method}")
            logger.info(f"Hybrid service connected: {hybrid_service._connection_method is not None}")
            
            # ALWAYS use COM legacy method directly to ensure COS properties are included
            if hybrid_service._connection_method == "com" and hybrid_service.com_connector:
                emails = hybrid_service.com_connector._get_messages_legacy("Inbox", limit)
                logger.info(f"Retrieved {len(emails) if emails else 0} emails from COM legacy method (includes COS data)")
            else:
                # Fallback to hybrid method for non-COM connections
                emails = await hybrid_service.get_messages("Inbox", limit=limit)
                logger.info(f"Retrieved {len(emails) if emails else 0} emails from hybrid service fallback")
            
            if emails:
                from schemas.email_schema import EmailSchema, validate_email_schema
                
                # Convert to simple JSON-safe format - legacy method already includes COS analysis
                formatted_emails = []
                for email_data in emails:
                    try:
                        # Legacy method already includes analysis, just use it directly
                        body_content_raw = email_data.get("body_content", "")
                        body_preview_raw = email_data.get("body_preview", "")
                        
                        # DEBUG LOGGING FOR BODY CONTENT
                        logger.info(f"📧 WEBSOCKET BODY DEBUG - Subject: {email_data.get('subject', 'Unknown')[:30]}")
                        logger.info(f"   Raw body_content length: {len(body_content_raw) if body_content_raw else 0}")
                        logger.info(f"   Raw body_preview length: {len(body_preview_raw) if body_preview_raw else 0}")
                        logger.info(f"   Body content type: {type(body_content_raw)}")
                        if body_content_raw:
                            logger.info(f"   First 100 chars: {body_content_raw[:100]}")
                        
                        simple_email = {
                            "id": email_data.get("id", "unknown"),
                            "subject": email_data.get("subject", "No Subject"),
                            "sender_name": email_data.get("sender_name", "Unknown Sender"),
                            "sender_email": email_data.get("sender_email", ""),
                            "sender": email_data.get("sender", ""),
                            "to_recipients": email_data.get("to_recipients", []),
                            "cc_recipients": email_data.get("cc_recipients", []),
                            "bcc_recipients": email_data.get("bcc_recipients", []),
                            "body_content": body_content_raw or "",  # Full body content for detail view
                            "body_preview": body_preview_raw or "",
                            "received_at": str(email_data.get("received_at", "")),
                            "is_read": email_data.get("is_read", False),
                            "has_attachments": email_data.get("has_attachments", False),
                            "importance": email_data.get("importance", "normal"),
                            "analysis": email_data.get("analysis")  # Legacy method includes this
                        }
                        
                        # Extract analysis properties for backward compatibility
                        analysis = simple_email.get("analysis")
                        if analysis and isinstance(analysis, dict):
                            simple_email["priority"] = analysis.get("priority", "Unassessed")
                            simple_email["tone"] = analysis.get("tone", "Unassessed") 
                            simple_email["urgency"] = analysis.get("urgency", "Unassessed")
                            logger.info(f"✅ COS analysis found for {email_data.get('subject', 'Unknown')[:30]}: Priority={analysis.get('priority')}, Tone={analysis.get('tone')}, Urgency={analysis.get('urgency')}")
                        else:
                            simple_email["priority"] = "Unassessed"
                            simple_email["tone"] = "Unassessed" 
                            simple_email["urgency"] = "Unassessed"
                            if analysis is not None:
                                logger.info(f"Analysis not dict for {email_data.get('subject', 'Unknown')[:30]}: {type(analysis)} = {analysis}")
                        
                        formatted_emails.append(simple_email)
                        
                        # Debug body content length
                        body_content_len = len(simple_email.get("body_content", ""))
                        body_preview_len = len(simple_email.get("body_preview", ""))
                        logger.info(f"📧 Email '{simple_email.get('subject', 'No subject')[:30]}': body_content={body_content_len} chars, body_preview={body_preview_len} chars (will send to WebSocket)")
                        
                    except Exception as e:
                        logger.error(f"Failed to process email: {e}")
                        continue
                
                logger.info(f"Sending {len(formatted_emails)} emails to frontend")
                
                # Log recipient data for debugging
                for i, email in enumerate(formatted_emails[:2]):  # Log first 2 emails
                    to_recips = email.get("to_recipients", [])
                    cc_recips = email.get("cc_recipients", [])
                    logger.info(f"Email {i+1} recipients debug:")
                    logger.info(f"  Subject: {email.get('subject', 'No subject')[:40]}")
                    logger.info(f"  Sender: {email.get('sender', 'No sender')[:40]}")
                    logger.info(f"  Sender Name: {email.get('sender_name', 'No sender name')[:30]}")
                    logger.info(f"  TO Recipients ({len(to_recips)}): {to_recips}")
                    logger.info(f"  CC Recipients ({len(cc_recips)}): {cc_recips}")
                
                try:
                    await manager.send_to_client(
                        self.websocket,
                        "email:recent_list",
                        {"emails": formatted_emails}
                    )
                    logger.info("Email list sent successfully")
                except Exception as e:
                    logger.error(f"Failed to send email list: {e}")
                    # Send empty list as fallback
                    await manager.send_to_client(
                        self.websocket,
                        "email:recent_list",
                        {"emails": [], "error": "Failed to serialize email data"}
                    )
            else:
                await manager.send_to_client(
                    self.websocket,
                    "email:recent_list",
                    {"emails": [], "message": "No recent emails found"}
                )
                
        except Exception as e:
            logger.error(f"Error getting recent emails: {e}")
            await manager.send_to_client(
                self.websocket,
                "email:fetch_error",
                {"message": f"Failed to get recent emails: {str(e)}"}
            )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    """Main WebSocket endpoint for real-time communication"""
    logger.info("=== NEW WEBSOCKET CONNECTION ATTEMPT ===")
    connection_id = await manager.connect(websocket)
    logger.info(f"WebSocket connected with ID: {connection_id}")
    handler = WSMessageHandler(websocket, db)
    logger.info("WebSocket handler created successfully")
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            logger.info(f"Received WebSocket message: {data}")
            
            try:
                message = json.loads(data)
                event = message.get("event")
                msg_data = message.get("data", {})
                
                if event:
                    await handler.handle_message(event, msg_data)
                    
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {data}")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# REST API endpoints for external integrations

@app.get("/api/projects")
async def get_projects(db: Session = Depends(get_db)):
    """Get all projects with optimized query"""
    projects = db.query(Project).options(
        # Only load needed columns to reduce memory
    ).all()
    return [{"id": p.id, "name": p.name, "status": p.status} for p in projects]

@app.get("/api/projects/{project_id}/tasks")
async def get_project_tasks(project_id: str, db: Session = Depends(get_db)):
    """Get tasks for a project with index optimization"""
    tasks = db.query(Task).filter(
        Task.project_id == project_id
    ).order_by(Task.created_at.desc()).all()
    return [{"id": t.id, "title": t.title, "status": t.status} for t in tasks]

@app.get("/api/interviews/active")
async def get_active_interviews(db: Session = Depends(get_db)):
    """Get pending interviews"""
    interviews = db.query(Interview).filter(Interview.status == "pending").all()
    return [{"id": i.id, "question": i.question, "importance_score": i.importance_score} for i in interviews]

@app.post("/api/jobs/{job_type}")
async def trigger_job(job_type: str, data: Dict[str, Any] = None, db: Session = Depends(get_db)):
    """Manually trigger a background job"""
    job = await job_queue.add_job(job_type, data or {})
    return {"job_id": job.id, "status": job.status}

@app.get("/api/jobs/{job_id}/status")
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Get job status"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job.id,
        "type": job.type,
        "status": job.status,
        "progress": job.progress,
        "error": job.error_message
    }

@app.get("/debug/prompts")
async def debug_prompts():
    """Debug endpoint to show loaded prompts and their timestamps"""
    prompt_info = {}
    for key, content in claude_client.prompts_cache.items():
        # Extract timestamp from content
        lines = content.split('\n')
        if lines[0].startswith('<!-- Last saved:'):
            timestamp = lines[0].replace('<!-- Last saved:', '').replace(' -->', '').strip()
            preview = lines[1][:100] + "..." if len(lines) > 1 else ""
        else:
            timestamp = "Unknown"
            preview = content[:100] + "..."
        
        prompt_info[key] = {
            "last_saved": timestamp,
            "preview": preview,
            "size": len(content)
        }
    
    return {
        "total_prompts": len(prompt_info),
        "prompts": prompt_info
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/usage/stats")
async def get_usage_stats():
    """Get AI usage statistics for cost monitoring"""
    return claude_client.get_usage_stats()

@app.post("/api/usage/reset")
async def reset_usage_stats():
    """Reset AI usage statistics (admin only)"""
    return claude_client.reset_usage_stats()

# OAuth callback endpoint for Outlook integration
@app.get("/auth/callback")
async def oauth_callback(request: Request, code: str = None, state: str = None, error: str = None):
    """Handle OAuth2 callback from Microsoft"""
    if error:
        return HTMLResponse(f"""
        <html>
            <head><title>Authorization Error</title></head>
            <body>
                <h1>Authorization Failed</h1>
                <p>Error: {error}</p>
                <p>Please try again or check your app configuration.</p>
                <script>
                    setTimeout(() => window.close(), 3000);
                </script>
            </body>
        </html>
        """)
    
    if not code or not state:
        return HTMLResponse("""
        <html>
            <head><title>Invalid Request</title></head>
            <body>
                <h1>Invalid Authorization Request</h1>
                <p>Missing authorization code or state parameter.</p>
                <script>
                    setTimeout(() => window.close(), 3000);
                </script>
            </body>
        </html>
        """)
    
    try:
        # Exchange authorization code for token
        from integrations.outlook.auth import OutlookAuthManager
        auth_manager = OutlookAuthManager()
        
        logger.info(f"OAuth callback - code: {code[:20]}..., state: {state}")
        token_data = await auth_manager.exchange_code_for_token(code, state)
        
        return HTMLResponse("""
        <html>
            <head><title>Authorization Successful</title></head>
            <body>
                <h1>✅ Outlook Connected Successfully!</h1>
                <p>You can now close this window and return to Chief of Staff.</p>
                <p>Try typing <code>/outlook status</code> to confirm the connection.</p>
                <script>
                    setTimeout(() => window.close(), 5000);
                </script>
            </body>
        </html>
        """)
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return HTMLResponse(f"""
        <html>
            <head><title>Authorization Error</title></head>
            <body>
                <h1>Authorization Failed</h1>
                <p>Error exchanging authorization code: {str(e)}</p>
                <p>Please try again or check your configuration.</p>
                <script>
                    setTimeout(() => window.close(), 3000);
                </script>
            </body>
        </html>
        """)

@app.get("/auth/status")
async def auth_status():
    """Check Outlook authentication status"""
    try:
        from integrations.outlook.auth import OutlookAuthManager
        auth_manager = OutlookAuthManager()
        
        if auth_manager.is_authenticated():
            token_info = auth_manager.get_token_info()
            return {
                "authenticated": True,
                "expires_at": token_info.get("expires_at"),
                "token_type": token_info.get("token_type")
            }
        else:
            auth_url, state = auth_manager.get_authorization_url()
            return {
                "authenticated": False,
                "auth_url": auth_url
            }
            
    except Exception as e:
        return {"authenticated": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8787, reload=True)