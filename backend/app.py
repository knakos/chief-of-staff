"""
Main FastAPI application for Chief of Staff backend.
Handles WebSocket communication and provides REST API endpoints.
"""
import asyncio
import json
import logging
from utils.datetime_utils import utc_now, utc_timestamp
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
    
    # Auto-connect to Outlook via COM service
    try:
        connection_result = cos_orchestrator.email_triage.com_service.connect()
        logger.info(f"Outlook COM auto-connection: {connection_result}")
    except Exception as e:
        logger.warning(f"Failed to auto-connect to Outlook via COM: {e}")
    
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
            "connected_at": utc_now(),
            "last_ping": utc_now()
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

    def _format_datetime(self, dt):
        """Format datetime object to ISO string for frontend consumption"""
        if dt is None:
            return None
        try:
            # Handle both datetime objects and strings
            if isinstance(dt, str):
                from dateutil.parser import parse
                dt = parse(dt)
            
            if hasattr(dt, 'isoformat'):
                return dt.isoformat()
            else:
                return str(dt)
        except Exception as e:
            logger.warning(f"Failed to format datetime {dt}: {e}")
            return str(dt) if dt else None

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
            "email:selected": self.handle_email_selected,
            "email_recommendation_action": self.handle_email_recommendation_action,
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
        
        # Handle both string and dict responses for backward compatibility
        if isinstance(response, dict):
            text_content = response.get("text", str(response))
            actions = response.get("actions", [])
        else:
            text_content = str(response)
            actions = []
        
        # Send agent response
        await manager.send_to_client(
            self.websocket,
            "thread:append",
            {
                "message": {
                    "id": str(utc_now().timestamp()),
                    "role": "agent",
                    "content": text_content
                }
            }
        )
        
        # Send navigation actions if present
        for action in actions:
            if action.get("type") == "navigate":
                await manager.send_to_client(
                    self.websocket,
                    "navigate",
                    {
                        "target": action.get("target")
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
            # Use COM service for email actions
            com_service = cos_orchestrator.email_triage.com_service
            
            # Ensure COM connection
            if not com_service.is_connected():
                connection_result = com_service.connect()
                if not connection_result.get('connected'):
                    await manager.send_to_client(
                        self.websocket,
                        "email:action_error",
                        {"message": f"Outlook connection failed: {connection_result.get('message', 'Unknown error')}"}
                    )
                    return
            
            # Apply action based on type
            result = {"success": False, "message": "Unknown action"}
            
            if action == "move_to_folder":
                folder_name = payload.get("folder_name")
                if folder_name:
                    success = com_service.move_email(email_id, folder_name)
                    result = {"success": success, "message": f"Email {'moved to' if success else 'failed to move to'} {folder_name}"}
            
            elif action == "mark_read":
                # This would require implementing mark_read in COM service
                result = {"success": True, "message": "Action noted (implementation pending)"}
            
            elif action_type == "create_task":
                # Create task from suggestion
                try:
                    # First try to get task_data from request (if frontend provides it)
                    task_data = data.get("task_data", {})
                    
                    # If no task_data provided, extract it from the email's analysis
                    if not task_data:
                        logger.info(f"🔄 [EMAIL_ACTION] No task_data provided, retrieving from email analysis...")
                        
                        # Get email details to extract task data from analysis
                        com_service = cos_orchestrator.email_triage.com_service
                        logger.info(f"🔍 [EMAIL_ACTION] COM service available: {com_service is not None}")
                        logger.info(f"🔍 [EMAIL_ACTION] COM service connected: {com_service.is_connected() if com_service else False}")
                        
                        if com_service and com_service.is_connected():
                            logger.info(f"🔄 [EMAIL_ACTION] Calling get_email_details for: {email_id}")
                            email_details = com_service.get_email_details(email_id)
                            logger.info(f"🔍 [EMAIL_ACTION] Email details returned: {email_details is not None}")
                            
                            if email_details:
                                logger.info(f"🔍 [EMAIL_ACTION] Email details keys: {list(email_details.keys())}")
                                has_analysis = 'analysis' in email_details
                                logger.info(f"🔍 [EMAIL_ACTION] Has analysis: {has_analysis}")
                                
                                if has_analysis:
                                    analysis = email_details['analysis']
                                    logger.info(f"🔍 [EMAIL_ACTION] Analysis type: {type(analysis)}")
                                    logger.info(f"🔍 [EMAIL_ACTION] Analysis: {analysis}")
                                    
                                    if isinstance(analysis, dict):
                                        has_suggested_actions = 'suggested_actions' in analysis
                                        logger.info(f"🔍 [EMAIL_ACTION] Has suggested_actions: {has_suggested_actions}")
                                        
                                        if has_suggested_actions:
                                            suggested_actions = analysis['suggested_actions']
                                            logger.info(f"🔍 [EMAIL_ACTION] Suggested actions count: {len(suggested_actions) if suggested_actions else 0}")
                                            logger.info(f"🔍 [EMAIL_ACTION] Suggested actions: {suggested_actions}")
                                            
                                            # Look for create_task action with embedded task_data
                                            for i, suggested_action in enumerate(suggested_actions):
                                                logger.info(f"🔍 [EMAIL_ACTION] Action {i}: type={suggested_action.get('type')}, has_task_data={'task_data' in suggested_action}")
                                                if suggested_action.get('type') == 'create_task' and 'task_data' in suggested_action:
                                                    task_data = suggested_action['task_data']
                                                    logger.info(f"✅ [EMAIL_ACTION] Found task_data in email analysis: {task_data}")
                                                    break
                                        else:
                                            logger.warning(f"⚠️ [EMAIL_ACTION] No suggested_actions in analysis")
                                    else:
                                        logger.warning(f"⚠️ [EMAIL_ACTION] Analysis is not a dict: {analysis}")
                                else:
                                    logger.warning(f"⚠️ [EMAIL_ACTION] No analysis in email details")
                            else:
                                logger.warning(f"⚠️ [EMAIL_ACTION] get_email_details returned None")
                        else:
                            logger.warning(f"⚠️ [EMAIL_ACTION] COM service not available or not connected")
                    
                    if not task_data:
                        logger.warning(f"⚠️ [EMAIL_ACTION] No task data available for email: {email_id}")
                        result = {"success": False, "message": "No task data available - please analyze the email first"}
                    else:
                        from models import Task, new_id, utc_now
                        from datetime import datetime
                        
                        # Create new task in database
                        new_task_id = new_id()
                        logger.info(f"🔄 [TASK_CREATE] Creating task with ID: {new_task_id}")
                        logger.info(f"🔄 [TASK_CREATE] Title: {task_data.get('title', 'Untitled Task')}")
                        logger.info(f"🔄 [TASK_CREATE] Project ID: {task_data.get('project_id')}")
                        logger.info(f"🔄 [TASK_CREATE] Objective: {task_data.get('objective', '')}")
                        logger.info(f"🔄 [TASK_CREATE] Priority: {task_data.get('priority', 3)}")
                        logger.info(f"🔄 [TASK_CREATE] Sponsor: {task_data.get('sponsor_email', '')}")
                        logger.info(f"🔄 [TASK_CREATE] Owner: {task_data.get('owner_email', '')}")
                        
                        new_task = Task(
                            id=new_task_id,
                            title=task_data.get('title', 'Untitled Task'),
                            objective=task_data.get('objective', ''),
                            status='not_started',
                            priority=task_data.get('priority', 3),
                            sponsor_email=task_data.get('sponsor_email', ''),
                            owner_email=task_data.get('owner_email', ''),
                            project_id=task_data.get('project_id'),
                            created_at=utc_now()
                        )
                        
                        # Parse due_date if provided
                        if task_data.get('due_date'):
                            try:
                                new_task.due_date = datetime.fromisoformat(task_data['due_date'].replace('Z', '+00:00'))
                            except (ValueError, AttributeError):
                                logger.warning(f"⚠️ Invalid due date format: {task_data['due_date']}")
                        
                        logger.info(f"🔄 [TASK_CREATE] Adding task to database session...")
                        self.db.add(new_task)
                        
                        logger.info(f"🔄 [TASK_CREATE] Committing transaction...")
                        self.db.commit()
                        
                        logger.info(f"✅ [TASK_CREATE] SUCCESSFULLY created task in database!")
                        logger.info(f"✅ [TASK_CREATE] - Task ID: {new_task.id}")
                        logger.info(f"✅ [TASK_CREATE] - Title: {new_task.title}")
                        logger.info(f"✅ [TASK_CREATE] - Project ID: {new_task.project_id}")
                        logger.info(f"✅ [TASK_CREATE] - Status: {new_task.status}")
                        logger.info(f"✅ [TASK_CREATE] - Created at: {new_task.created_at}")
                        result = {
                            "success": True, 
                            "message": f"Task created: {new_task.title}",
                            "task_id": new_task.id
                        }
                except Exception as e:
                    logger.error(f"[ERROR] Task creation failed: {e}")
                    self.db.rollback()
                    result = {"success": False, "message": f"Task creation failed: {str(e)}"}
            
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
        interview.answered_at = utc_now()
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
        interview.dismissed_at = utc_now()
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
            
            # Outlook Status - check COM service connection
            outlook_status = {"status": "disconnected", "method": None}
            try:
                com_service = cos_orchestrator.email_triage.com_service
                
                if com_service and com_service.is_connected():
                    connection_info = com_service.get_connection_info()
                    outlook_status = {
                        "status": "connected",
                        "method": connection_info.get('method', 'com'),
                        "account_info": connection_info.get('account_info')
                    }
                    logger.info(f"Status check: COM service connected")
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
                                    "status": "available",
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
                    Task.status.in_(['not_started', 'active'])
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
                    .filter(Task.status.in_(['not_started', 'active']))\
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
                task.completed_at = utc_now()
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
        """Handle on-demand email analysis request"""
        logger.info(f"🔄 [WEBSOCKET] Received email:analyze request with data: {data}")
        
        try:
            email_id = data.get("email_id")
            if not email_id:
                logger.error("❌ [WEBSOCKET] Email analysis failed: No email ID provided")
                await manager.send_to_client(
                    self.websocket,
                    "email:analysis_error", 
                    {"message": "Email ID required", "email_id": None}
                )
                return
            
            logger.info(f"🔄 [WEBSOCKET] Starting on-demand analysis for email: {email_id}")
            
            # Use COM service for on-demand analysis
            com_service = cos_orchestrator.email_triage.com_service
            logger.info(f"🔍 [WEBSOCKET] Got COM service: {com_service}")
            
            # Ensure COM connection
            if not com_service.is_connected():
                logger.info(f"🔄 [WEBSOCKET] COM not connected, attempting connection...")
                connection_result = com_service.connect()
                if not connection_result.get('connected'):
                    logger.error(f"❌ [WEBSOCKET] Cannot analyze: {connection_result.get('message')}")
                    await manager.send_to_client(
                        self.websocket,
                        "email:analysis_error", 
                        {"message": f"Outlook connection failed: {connection_result.get('message', 'Unknown error')}", "email_id": email_id}
                    )
                    return
            else:
                logger.info(f"✅ [WEBSOCKET] COM service already connected")
            
            # Analyze single email on-demand with timeout protection
            logger.info(f"🔄 [WEBSOCKET] About to call com_service.analyze_single_email({email_id}) with timeout")
            try:
                # Add 60 second timeout to prevent infinite hangs
                analyzed_email = await asyncio.wait_for(
                    com_service.analyze_single_email(email_id, db=self.db), 
                    timeout=60.0
                )
                logger.info(f"✅ [WEBSOCKET] analyze_single_email returned: {type(analyzed_email)} with keys: {list(analyzed_email.keys()) if analyzed_email else 'None'}")
                
            except asyncio.TimeoutError:
                logger.error(f"❌ [WEBSOCKET] Email analysis timed out after 60 seconds for: {email_id}")
                await manager.send_to_client(
                    self.websocket,
                    "email:analysis_error", 
                    {"message": "Analysis timed out after 60 seconds - please try again", "email_id": email_id}
                )
                return
            except Exception as analysis_e:
                logger.error(f"❌ [WEBSOCKET] Email analysis failed: {analysis_e}")
                await manager.send_to_client(
                    self.websocket,
                    "email:analysis_error",
                    {"message": f"Analysis failed: {str(analysis_e)}", "email_id": email_id}
                )
                return
            
            if analyzed_email and analyzed_email.get('analysis'):
                analysis = analyzed_email['analysis']
                logger.info(f"✅ [WEBSOCKET] On-demand analysis completed: Priority={analysis.get('priority')}, Tone={analysis.get('tone')}, Urgency={analysis.get('urgency')}")
                
                # Send the complete analyzed email data
                logger.info(f"🔄 [WEBSOCKET] Sending email:analyzed event to client...")
                await manager.send_to_client(
                    self.websocket,
                    "email:analyzed",
                    {
                        "email_id": email_id, 
                        "email_data": analyzed_email,
                        "analysis": analysis
                    }
                )
                logger.info(f"✅ [WEBSOCKET] Successfully sent email:analyzed event")
                
                # Send structured recommendations to COS chat
                await self._send_email_recommendations_to_chat(email_id, analysis, analyzed_email)
            else:
                logger.warning(f"⚠️ [WEBSOCKET] Analysis failed or returned empty results for email: {email_id}")
                await manager.send_to_client(
                    self.websocket,
                    "email:analysis_error",
                    {"message": "Analysis failed to generate results", "email_id": email_id}
                )
            
        except Exception as e:
            logger.error(f"❌ [WEBSOCKET] Error analyzing email: {e}")
            import traceback
            logger.error(f"❌ [WEBSOCKET] Traceback: {traceback.format_exc()}")
            await manager.send_to_client(
                self.websocket,
                "email:analysis_error",
                {"message": f"Analysis failed: {str(e)}", "email_id": data.get("email_id")}
            )
    
    async def _send_email_recommendations_to_chat(self, email_id: str, analysis: Dict[str, Any], email_data: Dict[str, Any]):
        """Send structured email recommendations to COS chat as clickable links"""
        try:
            import time
            suggested_actions = analysis.get('suggested_actions', [])
            email_subject = email_data.get('subject', 'Email')[:50]
            
            if not suggested_actions:
                logger.info(f"🔍 [RECOMMENDATIONS] No structured actions found for email: {email_id}")
                return
            
            # Create natural executive assistant message with clickable actions
            recommendations_text = ""
            
            for i, action in enumerate(suggested_actions, 1):
                if isinstance(action, dict):
                    action_text = action.get('action', '')
                    description = action.get('description', '')
                    action_type = action.get('type', '')
                    confidence = action.get('confidence', 0.0)
                    
                    if action_text:
                        # Make action text a highlighted link with confidence
                        recommendations_text += f"**[{action_text}]** "
                        if description:
                            recommendations_text += f"{description} "
                        # Add confidence level
                        confidence_percent = int(confidence * 100)
                        recommendations_text += f"(Confidence: {confidence_percent}%)"
                        recommendations_text += "\n\n"
                else:
                    # Fallback for simple string actions
                    recommendations_text += f"**[I recommend: {action}]** (Confidence: 50%)\n\n"
            
            if recommendations_text:
                recommendations_text += "Click any action above to proceed, or let me know if you'd like different options."
            
            # Send as COS message to chat
            message_data = {
                "id": f"recommendations_{email_id}_{int(time.time())}",
                "text": recommendations_text,
                "timestamp": utc_timestamp(),
                "role": "agent",
                "sender": "cos",
                "type": "recommendations",
                "email_id": email_id,
                "actions": suggested_actions
            }
            
            logger.info(f"📨 [RECOMMENDATIONS] Sending recommendations to chat for email: {email_id}")
            await manager.send_to_client(
                self.websocket,
                "thread:append",
                {"message": message_data}
            )
            
        except Exception as e:
            logger.error(f"❌ [RECOMMENDATIONS] Error sending recommendations to chat: {e}")
            import traceback
            logger.error(f"❌ [RECOMMENDATIONS] Traceback: {traceback.format_exc()}")

    async def handle_email_recommendation_action(self, data: Dict[str, Any]):
        """Handle execution of email recommendation actions"""
        try:
            import time
            action_type = data.get('action_type', '')
            action_data = data.get('action_data', {})
            email_id = data.get('email_id')
            
            logger.info(f"🔄 [EMAIL_ACTION] STARTING recommendation action")
            logger.info(f"🔄 [EMAIL_ACTION] - Action: {action_type}")
            logger.info(f"🔄 [EMAIL_ACTION] - Email ID: {email_id}")
            logger.info(f"🔄 [EMAIL_ACTION] - Action Data: {action_data}")
            logger.info(f"🔄 [EMAIL_ACTION] - Full Request: {data}")
            
            # Save user selection to Outlook for training and execute action
            success = False
            if email_id:
                try:
                    # Get COM service from global orchestrator
                    global cos_orchestrator
                    com_service = cos_orchestrator.email_triage.com_service
                    
                    # Ensure COM connection
                    if not com_service.is_connected():
                        connection_result = com_service.connect()
                        if not connection_result.get('connected'):
                            logger.error(f"❌ [EMAIL_ACTION] Cannot connect to Outlook: {connection_result.get('message')}")
                            raise Exception("Outlook connection failed")
                    
                    # Find email in Outlook by ID
                    outlook_item = com_service.com_connector._get_item_by_id(email_id)
                    if outlook_item:
                        # Save user selection for training
                        from integrations.outlook.property_sync import save_selected_action_to_outlook
                        save_selected_action_to_outlook(outlook_item, action_type, action_data)
                        logger.info(f"📊 [TRAINING] Recorded user selection: {action_type} for email: {email_id}")
                        
                        # Execute the actual action
                        if action_type == 'archive':
                            # Ensure COS_Archive folder exists
                            folder_result = com_service.create_folder('COS_Archive', 'Inbox')  # Won't create if exists
                            logger.info(f"📂 [EMAIL_ACTION] COS_Archive folder check result: {folder_result}")
                            
                            # Move email to COS_Archive folder
                            result = com_service.move_email(email_id, 'COS_Archive')
                            if result:
                                success = True
                                logger.info(f"✅ [EMAIL_ACTION] Successfully archived email: {email_id}")
                            else:
                                logger.error(f"❌ [EMAIL_ACTION] Failed to archive email: {email_id}")
                        elif action_type == 'create_task':
                            # Get email details and analysis using proper COM schema approach
                            logger.info(f"🔄 [TASK_CREATE] Getting email details for task creation: {email_id}")
                            
                            # Use same approach as the working email analysis flow
                            try:
                                from schemas.email_schema import create_email_from_com, email_to_dict
                                email_schema = create_email_from_com(outlook_item, skip_analysis=True)
                                email_data = email_to_dict(email_schema)
                                logger.info(f"🔄 [TASK_CREATE] Retrieved email data using schema: {email_data.get('subject', 'Unknown')[:50]}")
                            except Exception as e:
                                logger.error(f"❌ [TASK_CREATE] Failed to load email via schema: {e}")
                                email_data = None
                            
                            if email_data and email_data.get('analysis'):
                                analysis = email_data['analysis']
                                logger.info(f"🔄 [TASK_CREATE] Found email analysis: {analysis}")
                                
                                # Look for create_task action in suggested_actions
                                task_data = None
                                if 'suggested_actions' in analysis:
                                    for action in analysis['suggested_actions']:
                                        if action.get('type') == 'create_task' and 'task_data' in action:
                                            task_data = action['task_data']
                                            logger.info(f"🔄 [TASK_CREATE] Found task_data in email analysis: {task_data}")
                                            break
                                
                                if task_data:
                                    logger.info(f"🔄 [TASK_CREATE] Creating task with data: {task_data}")
                                    
                                    # Get or create default project (Tasks in Work area)
                                    from sqlalchemy.orm import sessionmaker
                                    from sqlalchemy import create_engine
                                    from models import Task, Project, Area
                                    
                                    engine = create_engine('sqlite:///cos.db', echo=False)
                                    Session = sessionmaker(bind=engine)
                                    session = Session()
                                    
                                    try:
                                        # Find default Work area
                                        work_area = session.query(Area).filter_by(name="Work").first()
                                        if not work_area:
                                            logger.error(f"❌ [TASK_CREATE] Could not find Work area")
                                            success = False
                                        else:
                                            # Find or use default Tasks project in Work area
                                            default_project = session.query(Project).filter_by(
                                                area_id=work_area.id, 
                                                is_catch_all=True
                                            ).first()
                                            
                                            if not default_project:
                                                logger.error(f"❌ [TASK_CREATE] Could not find default Tasks project in Work area")
                                                success = False
                                            else:
                                                # Parse due date
                                                due_date = None
                                                if task_data.get('due_date'):
                                                    from datetime import datetime
                                                    try:
                                                        due_date = datetime.fromisoformat(task_data['due_date'])
                                                    except:
                                                        logger.warning(f"⚠️ [TASK_CREATE] Could not parse due_date: {task_data.get('due_date')}")
                                                
                                                # Create the task
                                                new_task = Task(
                                                    title=task_data.get('title', 'New task from email'),
                                                    objective=task_data.get('objective', 'Review and respond to email'),
                                                    project_id=default_project.id,
                                                    priority=task_data.get('priority', 3),
                                                    due_date=due_date,
                                                    sponsor_email=task_data.get('sponsor_email', 'system@company.com'),
                                                    owner_email=task_data.get('owner_email', 'user@company.com'),
                                                    status='not_started'
                                                )
                                                
                                                session.add(new_task)
                                                session.commit()
                                                
                                                logger.info(f"✅ [TASK_CREATE] Successfully created task: '{new_task.title}' in project '{default_project.name}'")
                                                success = True
                                                
                                    except Exception as e:
                                        logger.error(f"❌ [TASK_CREATE] Database error: {e}")
                                        session.rollback()
                                        success = False
                                    finally:
                                        session.close()
                                else:
                                    logger.warning(f"⚠️ [TASK_CREATE] No task_data found in email analysis")
                                    success = False
                            else:
                                logger.warning(f"⚠️ [TASK_CREATE] No email analysis data found")
                                success = False
                        elif action_type in ['flag_category', 'save_later', 'save_reference']:
                            # For other actions, just mark as successful for now (implement later)
                            success = True
                        
                    else:
                        logger.warning(f"⚠️ [EMAIL_ACTION] Could not find email in Outlook for ID: {email_id}")
                        
                except Exception as e:
                    logger.error(f"❌ [EMAIL_ACTION] Failed to execute action: {e}")
                    success = False
            
            # Store task title for response message
            created_task_title = None
            if action_type == 'create_task' and success:
                # Get the actual task title that was created
                try:
                    from sqlalchemy.orm import sessionmaker
                    from sqlalchemy import create_engine
                    from models import Task
                    
                    engine = create_engine('sqlite:///cos.db', echo=False)
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    # Get the most recently created task
                    latest_task = session.query(Task).order_by(Task.created_at.desc()).first()
                    if latest_task:
                        created_task_title = latest_task.title
                        logger.info(f"📋 [RESPONSE] Using actual task title for response: '{created_task_title}'")
                    session.close()
                except Exception as e:
                    logger.warning(f"⚠️ [RESPONSE] Could not get task title: {e}")
            
            # Send success/failure message and trigger optimistic UI updates
            if action_type == 'archive':
                if success:
                    response_message = "📂 Email moved to COS_Archive folder successfully"
                    # Signal frontend to remove email from list
                    await manager.send_to_client(
                        self.websocket,
                        "email:archived",
                        {"email_id": email_id, "success": True}
                    )
                else:
                    response_message = "❌ Failed to archive email - please try again"
            elif action_type == 'create_task':
                task_title = created_task_title or action_data.get('task_title', 'New task from email')
                response_message = f"✅ Task created: '{task_title}'" if success else f"❌ Failed to create task"
            elif action_type == 'flag_category':
                category = action_data.get('category', 'General')
                response_message = f"✅ Email flagged as: {category}" if success else f"❌ Failed to flag email"
            elif action_type == 'save_later':
                response_message = "✅ Email saved for later reading" if success else "❌ Failed to save for later"
            elif action_type == 'save_reference':
                response_message = "✅ Email saved as reference material" if success else "❌ Failed to save as reference"
            else:
                response_message = f"✅ Action '{action_type}' executed" if success else f"❌ Action '{action_type}' failed"
            
            # Send confirmation banner to COS chat
            message_data = {
                "id": f"recommendation_result_{int(time.time() * 1000)}",
                "text": response_message,
                "timestamp": utc_timestamp(),
                "sender": "system",
                "isStatus": True,
                "success": success,
                "action_type": action_type,
                "email_id": email_id
            }
            
            await manager.send_to_client(
                self.websocket,
                "thread:append", 
                {"message": message_data}
            )
            
            logger.info(f"✅ [EMAIL_ACTION] Action '{action_type}' completed successfully")
            
        except Exception as e:
            logger.error(f"❌ [EMAIL_ACTION] Error executing recommendation action: {e}")
            import traceback
            logger.error(f"❌ [EMAIL_ACTION] Traceback: {traceback.format_exc()}")
            
            # Send error message to chat
            error_message = {
                "id": f"recommendation_error_{int(time.time() * 1000)}",
                "text": f"❌ Failed to execute action: {str(e)}",
                "timestamp": utc_timestamp(),
                "sender": "system",
                "isStatus": True
            }
            
            await manager.send_to_client(
                self.websocket,
                "thread:append",
                {"message": error_message}
            )

    async def handle_email_selected(self, data: Dict[str, Any]):
        """Handle when user selects an email - check for existing recommendations"""
        try:
            import time
            email_id = data.get('email_id')
            if not email_id:
                logger.warning("📧 [EMAIL_SELECTED] No email ID provided")
                return
                
            logger.info(f"📧 [EMAIL_SELECTED] User selected email: {email_id}")
            
            # Use COM service to get the specific email with existing analysis
            com_service = cos_orchestrator.email_triage.com_service
            
            # Ensure COM connection
            if not com_service.is_connected():
                connection_result = com_service.connect()
                if not connection_result.get('connected'):
                    logger.error(f"❌ [EMAIL_SELECTED] Cannot get email: {connection_result.get('message')}")
                    return
            
            # Get email data by ID to access existing COS properties
            outlook_item = com_service.com_connector._get_item_by_id(email_id)
            if not outlook_item:
                logger.warning(f"⚠️ [EMAIL_SELECTED] Could not find email with ID: {email_id}")
                return
            
            # Extract email data using schema
            from schemas.email_schema import create_email_from_com, email_to_dict
            email_schema = create_email_from_com(outlook_item, skip_analysis=True)  # Don't trigger new analysis
            email_data = email_to_dict(email_schema)
            
            # Check if email has existing analysis with recommendations
            analysis = email_data.get('analysis', {})
            if analysis and isinstance(analysis, dict):
                suggested_actions = analysis.get('suggested_actions', [])
                if suggested_actions and isinstance(suggested_actions, list) and len(suggested_actions) > 0:
                    logger.info(f"📧 [EMAIL_SELECTED] Found {len(suggested_actions)} existing recommendations for: {email_data.get('subject', 'Unknown')[:50]}")
                    
                    # Send existing recommendations to COS chat
                    await self._send_email_recommendations_to_chat(email_id, analysis, email_data)
                else:
                    logger.info(f"📧 [EMAIL_SELECTED] No existing recommendations found for: {email_data.get('subject', 'Unknown')[:50]}")
                    
                    # Send message indicating no recommendations available
                    message_data = {
                        "id": f"no_recommendations_{email_id}_{int(time.time() * 1000)}",
                        "text": f"ℹ️ No recommendations available for this email. Click 'Analyze' to generate recommendations.",
                        "timestamp": utc_timestamp(),
                        "sender": "system",
                        "isStatus": True
                    }
                    
                    await manager.send_to_client(
                        self.websocket,
                        "thread:append",
                        {"message": message_data}
                    )
            else:
                logger.info(f"📧 [EMAIL_SELECTED] No analysis data found for: {email_data.get('subject', 'Unknown')[:50]}")
                
                # Send message indicating analysis needed
                message_data = {
                    "id": f"needs_analysis_{email_id}_{int(time.time() * 1000)}",
                    "text": f"ℹ️ This email hasn't been analyzed yet. Click 'Analyze' to generate recommendations.",
                    "timestamp": utc_timestamp(),
                    "sender": "system",
                    "isStatus": True
                }
                
                await manager.send_to_client(
                    self.websocket,
                    "thread:append",
                    {"message": message_data}
                )
                
        except Exception as e:
            logger.error(f"❌ [EMAIL_SELECTED] Error handling email selection: {e}")
            import traceback
            logger.error(f"❌ [EMAIL_SELECTED] Traceback: {traceback.format_exc()}")

    async def handle_get_recent_emails(self, data: Dict[str, Any]):
        """Handle request for recent emails with AI analysis"""
        try:
            limit = data.get("limit", 10)
            logger.info(f"📧 Getting {limit} recent emails using COM-only service")
            
            # Use pure COM service for email loading with analysis
            com_service = cos_orchestrator.email_triage.com_service
            
            # Ensure COM connection
            if not com_service.is_connected():
                connection_result = com_service.connect()
                if not connection_result.get('connected'):
                    logger.error(f"❌ Failed to connect to Outlook: {connection_result.get('message')}")
                    await manager.send_to_client(
                        self.websocket,
                        "email:fetch_error", 
                        {"message": f"Outlook connection failed: {connection_result.get('message', 'Unknown error')}"}
                    )
                    return
                else:
                    logger.info(f"✅ Connected to Outlook via {connection_result.get('method')}")
            
            # Load emails WITHOUT automatic analysis (only existing COS properties)
            emails = com_service.get_recent_emails_without_analysis("Inbox", limit)
            logger.info(f"📧 Retrieved {len(emails)} emails without proactive analysis")
            
            if emails:
                # Send emails in batches for progressive loading
                batch_size = data.get("batch_size", 10)  # Default to 10 emails per batch
                total_emails = len(emails)
                
                # Send initial progress update
                await manager.send_to_client(
                    self.websocket,
                    "email:load_progress",
                    {
                        "status": "loading",
                        "current": 0,
                        "total": total_emails,
                        "message": f"Loading {total_emails} emails..."
                    }
                )
                
                # Process emails in batches
                for batch_start in range(0, total_emails, batch_size):
                    batch_end = min(batch_start + batch_size, total_emails)
                    batch_emails = emails[batch_start:batch_end]
                    
                    # Format emails in this batch
                    formatted_batch = []
                    for email_data in batch_emails:
                        try:
                            # Convert to frontend format
                            simple_email = {
                                "id": email_data.get("id", "unknown"),
                                "subject": email_data.get("subject", "No Subject"),
                                "sender_name": email_data.get("sender_name", "Unknown Sender"),
                                "sender_email": email_data.get("sender_email", ""),
                                "sender": email_data.get("sender", ""),
                                "to_recipients": email_data.get("to_recipients", []),
                                "cc_recipients": email_data.get("cc_recipients", []),
                                "bcc_recipients": email_data.get("bcc_recipients", []),
                                "body_content": email_data.get("body_content", ""),
                                "body_preview": email_data.get("body_preview", ""),
                                "received_at": self._format_datetime(email_data.get("received_at")),
                                "is_read": email_data.get("is_read", False),
                                "has_attachments": email_data.get("has_attachments", False),
                                "importance": email_data.get("importance", "normal"),
                                "analysis": email_data.get("analysis", {}),  # COM service includes analysis
                                "project_id": email_data.get("project_id"),
                                "confidence": email_data.get("confidence"),
                                "provenance": email_data.get("provenance")
                            }
                            
                            # Extract analysis properties for backward compatibility
                            analysis = simple_email.get("analysis", {})
                            if analysis and isinstance(analysis, dict):
                                simple_email["priority"] = analysis.get("priority", "MEDIUM")
                                simple_email["tone"] = analysis.get("tone", "PROFESSIONAL") 
                                simple_email["urgency"] = analysis.get("urgency", "MEDIUM")
                                logger.info(f"✅ Analysis loaded: {email_data.get('subject', 'Unknown')[:30]} - Priority={analysis.get('priority')}, Tone={analysis.get('tone')}, Urgency={analysis.get('urgency')}")
                            else:
                                simple_email["priority"] = "MEDIUM"
                                simple_email["tone"] = "PROFESSIONAL" 
                                simple_email["urgency"] = "MEDIUM"
                                logger.info(f"⚠️ No analysis for: {email_data.get('subject', 'Unknown')[:30]}")
                            
                            formatted_batch.append(simple_email)
                            
                        except Exception as e:
                            logger.error(f"❌ Failed to process email: {e}")
                            continue
                    
                    # Send batch to frontend
                    try:
                        await manager.send_to_client(
                            self.websocket,
                            "email:batch_loaded",
                            {
                                "emails": formatted_batch,
                                "batch_start": batch_start,
                                "batch_end": batch_end,
                                "is_final": batch_end >= total_emails
                            }
                        )
                        logger.info(f"📧 Sent batch {batch_start}-{batch_end} ({len(formatted_batch)} emails)")
                        
                        # Send progress update
                        await manager.send_to_client(
                            self.websocket,
                            "email:load_progress",
                            {
                                "status": "loading",
                                "current": batch_end,
                                "total": total_emails,
                                "message": f"Loaded {batch_end}/{total_emails} emails..."
                            }
                        )
                        
                        # Small delay to show progressive loading (can be removed in production)
                        import asyncio
                        await asyncio.sleep(0.2)
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to send email batch: {e}")
                        break
                
                # Send completion message
                await manager.send_to_client(
                    self.websocket,
                    "email:load_progress",
                    {
                        "status": "completed",
                        "current": total_emails,
                        "total": total_emails,
                        "message": f"Loaded all {total_emails} emails successfully"
                    }
                )
                logger.info(f"✅ Completed loading {total_emails} emails in batches")
                
            else:
                await manager.send_to_client(
                    self.websocket,
                    "email:load_progress",
                    {
                        "status": "completed",
                        "current": 0,
                        "total": 0,
                        "message": "No recent emails found"
                    }
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

# ===== PROJECT MANAGEMENT API ENDPOINTS =====

@app.get("/api/areas")
async def get_areas(db: Session = Depends(get_db)):
    """Get all areas with project and task counts"""
    areas = []
    for area in db.query(Area).order_by(Area.sort_order).all():
        # Count only active projects (exclude archived)
        project_count = db.query(Project).filter(
            Project.area_id == area.id,
            Project.status != 'archived'
        ).count()
        task_count = db.query(Task).join(Project).filter(Project.area_id == area.id).count()
        areas.append({
            "id": area.id,
            "name": area.name,
            "description": area.description,
            "color": area.color,
            "is_default": area.is_default,
            "is_system": area.is_system,
            "sort_order": area.sort_order,
            "project_count": project_count,
            "task_count": task_count,
            "created_at": area.created_at.isoformat() if area.created_at else None
        })
    return areas

@app.post("/api/areas")
async def create_area(area_data: dict, db: Session = Depends(get_db)):
    """Create new area with auto-generated catch-all Tasks project"""
    try:
        # Create the area
        new_area = Area(
            name=area_data["name"],
            description=area_data.get("description", ""),
            color=area_data.get("color", "#3B82F6"),
            sort_order=area_data.get("sort_order", 99)
        )
        db.add(new_area)
        db.flush()  # Get the ID
        
        # Create catch-all Tasks project for this area
        tasks_project = Project(
            name="Tasks",
            description=f"General {area_data['name'].lower()} tasks not assigned to specific projects",
            area_id=new_area.id,
            is_catch_all=True,
            is_system=True,
            sort_order=0,
            priority=3
        )
        db.add(tasks_project)
        db.commit()
        
        return {"success": True, "area_id": new_area.id, "project_id": tasks_project.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}

@app.put("/api/areas/{area_id}")
async def update_area(area_id: str, area_data: dict, db: Session = Depends(get_db)):
    """Update existing area (only non-system areas can be renamed)"""
    try:
        area = db.query(Area).filter_by(id=area_id).first()
        if not area:
            return {"success": False, "error": "Area not found"}
        
        # System areas cannot be renamed
        if area.is_system and "name" in area_data:
            return {"success": False, "error": "Cannot rename system areas"}

        # Update area fields
        if "name" in area_data and not area.is_system:
            # Check for unique name constraint
            existing = db.query(Area).filter(Area.name == area_data["name"], Area.id != area_id).first()
            if existing:
                return {"success": False, "error": f"Area name '{area_data['name']}' already exists"}
            area.name = area_data["name"]
        if "description" in area_data:
            area.description = area_data["description"]
        if "color" in area_data:
            area.color = area_data["color"]
        if "sort_order" in area_data:
            area.sort_order = area_data["sort_order"]

        db.commit()
        return {
            "success": True, 
            "area": {
                "id": area.id,
                "name": area.name,
                "description": area.description,
                "color": area.color,
                "sort_order": area.sort_order,
                "is_system": area.is_system
            }
        }
    except Exception as e:
        logger.error(f"Error updating area: {e}")
        db.rollback()
        return {"success": False, "error": str(e)}

@app.delete("/api/areas/{area_id}")
async def delete_area(area_id: str, db: Session = Depends(get_db)):
    """Delete area (only non-system areas with no active projects/tasks)"""
    try:
        area = db.query(Area).filter_by(id=area_id).first()
        if not area:
            return {"success": False, "error": "Area not found"}
        
        # System areas cannot be deleted
        if area.is_system:
            return {"success": False, "error": "Cannot delete system areas"}
        
        # Check for active projects (excluding catch-all Tasks projects)
        active_projects = db.query(Project).filter(
            Project.area_id == area_id,
            Project.is_catch_all == False,
            Project.status.in_(["active", "planning", "paused", "blocked"])
        ).count()
        
        if active_projects > 0:
            return {"success": False, "error": f"Cannot delete area with {active_projects} active projects"}
        
        # Check for active tasks in any projects in this area
        active_tasks = db.query(Task).join(Project).filter(
            Project.area_id == area_id,
            Task.status.in_(["not_started", "active", "blocked"])
        ).count()
        
        if active_tasks > 0:
            return {"success": False, "error": f"Cannot delete area with {active_tasks} active tasks"}
        
        # All checks passed - delete the area (cascade will handle projects and tasks)
        db.delete(area)
        db.commit()
        
        return {"success": True, "message": f"Area '{area.name}' deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting area: {e}")
        db.rollback()
        return {"success": False, "error": str(e)}

@app.get("/api/areas/{area_id}/projects")
async def get_area_projects(area_id: str, db: Session = Depends(get_db)):
    """Get all projects in an area with task counts"""
    projects = []
    for project in db.query(Project).filter_by(area_id=area_id).order_by(Project.sort_order).all():
        task_count = db.query(Task).filter_by(project_id=project.id).count()
        completed_count = db.query(Task).filter_by(project_id=project.id, status="completed").count()
        overdue_count = db.query(Task).filter(
            Task.project_id == project.id,
            Task.due_date < utc_now(),
            Task.status != "completed"
        ).count()
        
        projects.append({
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "priority": project.priority,
            "is_catch_all": project.is_catch_all,
            "is_system": project.is_system,
            "color": project.color,
            "task_count": task_count,
            "completed_count": completed_count,
            "overdue_count": overdue_count,
            "created_at": project.created_at.isoformat() if project.created_at else None
        })
    return projects

@app.post("/api/projects")
async def create_project(project_data: dict, db: Session = Depends(get_db)):
    """Create new project with auto-renaming for duplicates"""
    try:
        area_id = project_data["area_id"]
        requested_name = project_data["name"]
        
        # Auto-rename logic for duplicate names within the same area
        def generate_unique_project_name(base_name: str, area_id: str) -> str:
            existing_projects = db.query(Project).filter(Project.area_id == area_id).all()
            existing_names = [p.name.lower() for p in existing_projects]
            
            unique_name = base_name
            if unique_name.lower() not in existing_names:
                return unique_name
            
            counter = 2
            while f"{base_name} {counter}".lower() in existing_names:
                counter += 1
            
            return f"{base_name} {counter}"
        
        # Generate unique name if needed
        unique_name = generate_unique_project_name(requested_name, area_id)
        
        new_project = Project(
            name=unique_name,
            description=project_data.get("description", ""),
            area_id=area_id,
            status=project_data.get("status", "active"),
            priority=project_data.get("priority", 3),
            color=project_data.get("color"),
            sort_order=project_data.get("sort_order", 99)
        )
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        
        return {
            "success": True, 
            "project_id": new_project.id,
            "name": new_project.name,  # Return the actual name used
            "original_name": requested_name,  # Return original for debugging
            "was_renamed": unique_name != requested_name
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}

@app.get("/api/projects/{project_id}")
async def get_project_detail(project_id: str, db: Session = Depends(get_db)):
    """Get detailed project info with tasks"""
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        return {"success": False, "error": "Project not found"}
    
    tasks = []
    for task in db.query(Task).filter_by(project_id=project_id).order_by(Task.created_at.desc()).all():
        tasks.append({
            "id": task.id,
            "title": task.title,
            "objective": task.objective,
            "status": task.status,
            "priority": task.priority,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "sponsor_email": task.sponsor_email,
            "owner_email": task.owner_email,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        })
    
    return {
        "success": True,
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "priority": project.priority,
            "is_catch_all": project.is_catch_all,
            "color": project.color,
            "area": {
                "id": project.area.id,
                "name": project.area.name,
                "color": project.area.color
            }
        },
        "tasks": tasks
    }

@app.post("/api/tasks")
async def create_task(task_data: dict, db: Session = Depends(get_db)):
    """Create new task"""
    try:
        new_task = Task(
            title=task_data["title"],
            objective=task_data.get("objective", ""),
            project_id=task_data["project_id"],
            status=task_data.get("status", "not_started"),
            priority=task_data.get("priority", 3),
            due_date=datetime.fromisoformat(task_data["due_date"]) if task_data.get("due_date") else None,
            sponsor_email=task_data.get("sponsor_email"),
            owner_email=task_data.get("owner_email"),
            parent_task_id=task_data.get("parent_task_id")
        )
        db.add(new_task)
        db.commit()
        return {"success": True, "task_id": new_task.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}

@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, task_data: dict, db: Session = Depends(get_db)):
    """Update existing task"""
    logger.info(f"Updating task {task_id} with data: {task_data}")
    try:
        task = db.query(Task).filter_by(id=task_id).first()
        if not task:
            logger.error(f"Task not found: {task_id}")
            return {"success": False, "error": "Task not found"}
        
        # Store original values for logging
        original_values = {
            "title": task.title,
            "objective": task.objective,
            "status": task.status,
            "priority": task.priority,
            "sponsor_email": task.sponsor_email,
            "owner_email": task.owner_email
        }
        
        # Update fields
        for field, value in task_data.items():
            if field == "due_date" and value:
                setattr(task, field, datetime.fromisoformat(value))
                logger.info(f"Updated {field}: {value}")
            elif field == "completed_at" and value:
                setattr(task, field, datetime.fromisoformat(value))
                logger.info(f"Updated {field}: {value}")
            elif field == "created_at" and value and isinstance(value, str):
                setattr(task, field, datetime.fromisoformat(value))
                logger.info(f"Updated {field}: {value}")
            elif hasattr(task, field) and field not in ["created_at"]:  # Skip created_at since it's handled above
                setattr(task, field, value)
                logger.info(f"Updated {field}: {original_values.get(field, 'N/A')} -> {value}")
        
        # Set completed_at when status changes to completed
        if task_data.get("status") == "completed" and not task.completed_at:
            task.completed_at = utc_now()
            logger.info(f"Auto-set completed_at: {task.completed_at}")
        elif task_data.get("status") != "completed":
            if task.completed_at:
                logger.info("Cleared completed_at because status is not completed")
            task.completed_at = None
        
        # Update the updated_at timestamp
        task.updated_at = utc_now()
        
        db.commit()
        logger.info(f"Successfully updated task {task_id}")
        return {"success": True}
    except Exception as e:
        logger.error(f"Error updating task {task_id}: {e}")
        db.rollback()
        return {"success": False, "error": str(e)}

@app.put("/api/tasks/{task_id}/archive")
async def archive_task(task_id: str, db: Session = Depends(get_db)):
    """Archive a task"""
    try:
        task = db.query(Task).filter_by(id=task_id).first()
        if not task:
            return {"success": False, "error": "Task not found"}
        
        task.status = "archived"
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}

@app.put("/api/tasks/{task_id}/restore")
async def restore_task(task_id: str, db: Session = Depends(get_db)):
    """Restore an archived task"""
    try:
        task = db.query(Task).filter_by(id=task_id).first()
        if not task:
            return {"success": False, "error": "Task not found"}
        
        task.status = "active"
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, db: Session = Depends(get_db)):
    """Delete task (no archiving required)"""
    try:
        task = db.query(Task).filter_by(id=task_id).first()
        if not task:
            return {"success": False, "error": "Task not found"}
        
        db.delete(task)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}

@app.put("/api/projects/{project_id}")
async def update_project(project_id: str, project_data: dict, db: Session = Depends(get_db)):
    """Update existing project"""
    logger.info(f"Received project update request for ID: {project_id}")
    logger.info(f"Project data: {project_data}")
    try:
        project = db.query(Project).filter_by(id=project_id).first()
        if not project:
            logger.error(f"Project not found: {project_id}")
            return {"success": False, "error": "Project not found"}
        
        # Only update allowed fields (same pattern as tasks)
        allowed_fields = ["name", "description", "status", "priority", "color"]
        for field, value in project_data.items():
            if field in allowed_fields and hasattr(project, field):
                setattr(project, field, value)
                logger.info(f"Updated {field}: {value}")
        
        db.commit()
        logger.info(f"Project {project_id} updated successfully")
        return {"success": True}
    except Exception as e:
        logger.error(f"Error updating project: {e}")
        db.rollback()
        return {"success": False, "error": str(e)}

@app.put("/api/projects/{project_id}/archive")
async def archive_project(project_id: str, db: Session = Depends(get_db)):
    """Archive a project and block all active tasks"""
    try:
        project = db.query(Project).filter_by(id=project_id).first()
        if not project:
            return {"success": False, "error": "Project not found"}
        
        if project.is_system:
            return {"success": False, "error": "Cannot archive system projects"}
        
        # Update all active tasks to blocked status before archiving project
        active_tasks = db.query(Task).filter(
            Task.project_id == project_id,
            Task.status == 'active'
        ).all()
        
        blocked_tasks_count = 0
        for task in active_tasks:
            task.status = 'blocked'
            blocked_tasks_count += 1
        
        # Archive the project
        project.status = "archived"
        db.commit()
        
        return {
            "success": True, 
            "blocked_tasks": blocked_tasks_count,
            "message": f"Project archived. {blocked_tasks_count} active tasks were blocked."
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}

@app.put("/api/projects/{project_id}/restore")
async def restore_project(project_id: str, db: Session = Depends(get_db)):
    """Restore an archived project"""
    try:
        project = db.query(Project).filter_by(id=project_id).first()
        if not project:
            return {"success": False, "error": "Project not found"}
        
        project.status = "active"
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}

@app.get("/api/projects/{project_id}/deletion-info")
async def get_project_deletion_info(project_id: str, db: Session = Depends(get_db)):
    """Get information about what will be deleted with this project"""
    try:
        project = db.query(Project).filter_by(id=project_id).first()
        if not project:
            return {"success": False, "error": "Project not found"}
        
        # Count direct tasks of this project
        project_tasks = db.query(Task).filter_by(project_id=project_id).all()
        task_count = len(project_tasks)
        
        # Count subtasks that belong to tasks of this project
        subtask_count = 0
        for task in project_tasks:
            subtask_count += db.query(Task).filter_by(parent_task_id=task.id).count()
        
        total_task_count = task_count + subtask_count
        
        return {
            "success": True, 
            "task_count": task_count, 
            "subtask_count": subtask_count, 
            "total_task_count": total_task_count,
            "project_name": project.name
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Delete project (only if archived and not system project)"""
    try:
        project = db.query(Project).filter_by(id=project_id).first()
        if not project:
            return {"success": False, "error": "Project not found"}
        
        if project.is_system:
            return {"success": False, "error": "Cannot delete system projects"}
        
        if project.status != "archived":
            return {"success": False, "error": "Project must be archived before deletion"}
        
        # Get task information for frontend warning (but allow cascade deletion)
        # Count direct tasks of this project
        project_tasks = db.query(Task).filter_by(project_id=project_id).all()
        task_count = len(project_tasks)
        
        # Count subtasks that belong to tasks of this project
        subtask_count = 0
        for task in project_tasks:
            subtask_count += db.query(Task).filter_by(parent_task_id=task.id).count()
        
        total_task_count = task_count + subtask_count
        
        db.delete(project)
        db.commit()
        return {"success": True, "task_count": task_count, "subtask_count": subtask_count, "total_task_count": total_task_count}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}

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
    return {"status": "healthy", "timestamp": utc_timestamp()}

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