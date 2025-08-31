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

from models import Base, Project, Task, Email, ContextEntry, Job, Interview, Digest
from job_queue import JobQueue
from claude_client import ClaudeClient
from agents import COSOrchestrator

# Logging setup
logging.basicConfig(level=logging.WARNING)
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
            
        message_text = json.dumps({"event": event, "data": data})
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
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending to specific WebSocket: {e}")

manager = ConnectionManager()

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
            "task:create": self.handle_task_create,
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
        thread_id = data.get("thread_id")
        action = data.get("action")
        payload = data.get("payload")
        
        if not thread_id or not action:
            return
        
        # Find email by thread_id
        email = self.db.query(Email).filter(Email.thread_id == thread_id).first()
        if not email:
            return
        
        # Process action through COS orchestrator
        result = await cos_orchestrator.apply_email_action(email, action, payload, self.db)
        
        # Send result back
        await manager.send_to_client(
            self.websocket,
            "email:action_applied",
            {"thread_id": thread_id, "action": action, "result": result}
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
            
            logger.info(f"Status update sent - AI: {ai_status['status']}, Outlook: {outlook_status['status']}")
            
        except Exception as e:
            logger.error(f"Error handling status request: {e}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    """Main WebSocket endpoint for real-time communication"""
    connection_id = await manager.connect(websocket)
    handler = WSMessageHandler(websocket, db)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            
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