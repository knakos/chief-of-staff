"""
Test script to verify the Chief of Staff backend setup.
Tests basic functionality without requiring full API keys.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.append(str(Path(__file__).parent))

from models import Base, Project, Task, Email
from claude_client import ClaudeClient
from job_queue import JobQueue
from agents import COSOrchestrator
from init_db import init_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_setup():
    """Test the basic setup of all components"""
    
    print("\n" + "="*60)
    print("TESTING CHIEF OF STAFF BACKEND SETUP")
    print("="*60)
    
    # Test 1: Database initialization
    print("\n1. Testing database initialization...")
    try:
        init_database(add_sample_data=True)
        print("✅ Database initialization: SUCCESS")
    except Exception as e:
        print(f"❌ Database initialization: FAILED - {e}")
        return False
    
    # Test 2: Claude client (mock mode)
    print("\n2. Testing Claude client...")
    try:
        claude_client = ClaudeClient()
        prompts_loaded = len(claude_client.prompts_cache)
        print(f"✅ Claude client: SUCCESS - {prompts_loaded} prompts loaded")
        
        # Test mock response generation
        response = await claude_client.generate_response("system/cos", user_input="test")
        print(f"✅ Mock response generation: SUCCESS - {len(response)} chars")
        
    except Exception as e:
        print(f"❌ Claude client: FAILED - {e}")
        return False
    
    # Test 3: Job queue
    print("\n3. Testing job queue...")
    try:
        job_queue = JobQueue()
        await job_queue.start()
        
        # Add a test job
        job = await job_queue.add_job("email_scan", {"test": "data"})
        print(f"✅ Job queue: SUCCESS - Job {job.id} added")
        
        # Wait a bit for job processing
        await asyncio.sleep(2)
        
        status = await job_queue.get_job_status(job.id)
        print(f"✅ Job processing: SUCCESS - Status: {status['status']}")
        
        await job_queue.stop()
        
    except Exception as e:
        print(f"❌ Job queue: FAILED - {e}")
        return False
    
    # Test 4: Agent system
    print("\n4. Testing agent system...")
    try:
        job_queue = JobQueue()
        await job_queue.start()
        
        cos_orchestrator = COSOrchestrator(claude_client, job_queue)
        
        # Create a mock database session
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        engine = create_engine("sqlite:///./cos.db")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Test user input processing
        response = await cos_orchestrator.process_user_input("/plan", db)
        print(f"✅ Agent system: SUCCESS - Response generated")
        print(f"   Sample response: {response[:100]}...")
        
        db.close()
        await job_queue.stop()
        
    except Exception as e:
        print(f"❌ Agent system: FAILED - {e}")
        return False
    
    # Test 5: Prompt loading
    print("\n5. Testing prompt system...")
    try:
        available_prompts = list(claude_client.prompts_cache.keys())
        print(f"✅ Prompt system: SUCCESS")
        print(f"   Available prompts: {', '.join(available_prompts[:5])}{'...' if len(available_prompts) > 5 else ''}")
        
        # Test specific prompt loading
        cos_prompt = claude_client.get_prompt("system/cos")
        print(f"✅ Specific prompt loading: SUCCESS - {len(cos_prompt)} chars")
        
    except Exception as e:
        print(f"❌ Prompt system: FAILED - {e}")
        return False
    
    print("\n" + "="*60)
    print("🎉 ALL TESTS PASSED! Backend setup is ready.")
    print("="*60)
    print("\nNext steps:")
    print("1. Copy .env.example to .env and add your ANTHROPIC_API_KEY")
    print("2. Run: python app.py to start the backend server")
    print("3. Run the frontend: scripts/start-electron.ps1")
    print("4. Visit the Electron app to test the full system")
    print("\nDatabase file: cos.db (contains sample data)")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_setup())
    if not success:
        sys.exit(1)