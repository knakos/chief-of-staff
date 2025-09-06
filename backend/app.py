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
            
            elif action == "extract_tasks":
                # Extract tasks would require analyzing the email first
                result = {"success": False, "message": "Task extraction not implemented yet"}
            
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
                    com_service.analyze_single_email(email_id), 
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
        project_count = db.query(Project).filter_by(area_id=area.id).count()
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

@app.get("/api/areas/{area_id}/projects")
async def get_area_projects(area_id: str, db: Session = Depends(get_db)):
    """Get all projects in an area with task counts"""
    projects = []
    for project in db.query(Project).filter_by(area_id=area_id).order_by(Project.sort_order).all():
        task_count = db.query(Task).filter_by(project_id=project.id).count()
        completed_count = db.query(Task).filter_by(project_id=project.id, status="completed").count()
        overdue_count = db.query(Task).filter(
            Task.project_id == project.id,
            Task.due_date < datetime.utcnow(),
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
    """Create new project"""
    try:
        new_project = Project(
            name=project_data["name"],
            description=project_data.get("description", ""),
            area_id=project_data["area_id"],
            status=project_data.get("status", "active"),
            priority=project_data.get("priority", 3),
            color=project_data.get("color"),
            sort_order=project_data.get("sort_order", 99)
        )
        db.add(new_project)
        db.commit()
        return {"success": True, "project_id": new_project.id}
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
            "description": task.description,
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
            description=task_data.get("description", ""),
            objective=task_data.get("objective", ""),
            project_id=task_data["project_id"],
            status=task_data.get("status", "pending"),
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
    try:
        task = db.query(Task).filter_by(id=task_id).first()
        if not task:
            return {"success": False, "error": "Task not found"}
        
        # Update fields
        for field, value in task_data.items():
            if field == "due_date" and value:
                setattr(task, field, datetime.fromisoformat(value))
            elif field == "completed_at" and value:
                setattr(task, field, datetime.fromisoformat(value))
            elif hasattr(task, field):
                setattr(task, field, value)
        
        # Set completed_at when status changes to completed
        if task_data.get("status") == "completed" and not task.completed_at:
            task.completed_at = datetime.utcnow()
        elif task_data.get("status") != "completed":
            task.completed_at = None
        
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
    try:
        project = db.query(Project).filter_by(id=project_id).first()
        if not project:
            return {"success": False, "error": "Project not found"}
        
        # Update fields
        for field, value in project_data.items():
            if hasattr(project, field):
                setattr(project, field, value)
        
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
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
        
        # Check if there are any tasks
        task_count = db.query(Task).filter_by(project_id=project_id).count()
        if task_count > 0:
            return {"success": False, "error": f"Cannot delete project with {task_count} tasks"}
        
        db.delete(project)
        db.commit()
        return {"success": True}
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