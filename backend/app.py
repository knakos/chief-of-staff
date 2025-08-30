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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel

from models import Base, Project, Task, Email, ContextEntry, Job, Interview, Digest
from job_queue import JobQueue
from claude_client import ClaudeClient
from agents import COSOrchestrator

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = "sqlite:///./cos.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
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
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_to_all(self, event: str, data: Any):
        """Send message to all connected clients"""
        message = {"event": event, "data": data}
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.active_connections.remove(conn)

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
        }
        
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

        # Echo user message
        await manager.send_to_client(
            self.websocket,
            "thread:append",
            {
                "message": {
                    "id": str(datetime.utcnow().timestamp()),
                    "role": "user",
                    "content": text
                }
            }
        )

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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    """Main WebSocket endpoint for real-time communication"""
    await manager.connect(websocket)
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
    """Get all projects"""
    projects = db.query(Project).all()
    return [{"id": p.id, "name": p.name, "status": p.status} for p in projects]

@app.get("/api/projects/{project_id}/tasks")
async def get_project_tasks(project_id: str, db: Session = Depends(get_db)):
    """Get tasks for a project"""
    tasks = db.query(Task).filter(Task.project_id == project_id).all()
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

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8787, reload=True)