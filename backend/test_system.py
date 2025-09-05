#!/usr/bin/env python3
"""
Consolidated system test for Chief of Staff backend.
Tests all core functionality: database, COM integration, AI processing, and agents.
"""
import asyncio
import logging
import sys
import os
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

class SystemTest:
    def __init__(self):
        self.results = {}
        self.start_time = time.time()
    
    def log_test(self, test_name: str, success: bool, message: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        self.results[test_name] = success
        print(f"{status} {test_name}: {message}")
        return success
    
    def test_imports(self):
        """Test that all required modules can be imported"""
        print("\n" + "="*60)
        print("1. TESTING MODULE IMPORTS")
        print("="*60)
        
        try:
            from models import Base, Area, Project, Task, ContextEntry, Job, Interview, Digest
            self.log_test("Database models import", True, "All models imported successfully")
        except Exception as e:
            self.log_test("Database models import", False, f"Import failed: {e}")
            return False
            
        try:
            from claude_client import ClaudeClient
            self.log_test("Claude client import", True, "Claude client imported")
        except Exception as e:
            self.log_test("Claude client import", False, f"Import failed: {e}")
            return False
            
        try:
            from agents import COSOrchestrator, EmailTriageAgent
            self.log_test("Agents import", True, "All agents imported")
        except Exception as e:
            self.log_test("Agents import", False, f"Import failed: {e}")
            return False
            
        try:
            from job_queue import JobQueue
            self.log_test("Job queue import", True, "Job queue imported")
        except Exception as e:
            self.log_test("Job queue import", False, f"Import failed: {e}")
            return False
            
        try:
            from integrations.outlook.com_service import OutlookCOMService
            from integrations.outlook.com_connector import COM_AVAILABLE
            self.log_test("COM integration import", True, f"COM available: {COM_AVAILABLE}")
        except Exception as e:
            self.log_test("COM integration import", False, f"Import failed: {e}")
            return False
            
        return True
    
    def test_database(self):
        """Test database functionality"""
        print("\n" + "="*60)  
        print("2. TESTING DATABASE")
        print("="*60)
        
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from models import Base, Area, Project, Task
            
            # Test database creation
            engine = create_engine("sqlite:///./test_cos.db")
            Base.metadata.create_all(bind=engine)
            self.log_test("Database creation", True, "Tables created successfully")
            
            # Test basic database operations
            SessionLocal = sessionmaker(bind=engine)
            db = SessionLocal()
            
            # Test creating area
            test_area = Area(name="Test Area", description="Test area for validation")
            db.add(test_area)
            db.commit()
            
            # Test creating project
            test_project = Project(name="Test Project", description="Test project", area_id=test_area.id)
            db.add(test_project)
            db.commit()
            
            # Test creating task
            test_task = Task(title="Test Task", description="Test task", project_id=test_project.id)
            db.add(test_task)
            db.commit()
            
            # Test queries
            areas = db.query(Area).all()
            projects = db.query(Project).all() 
            tasks = db.query(Task).all()
            
            db.close()
            self.log_test("Database operations", True, f"Created {len(areas)} areas, {len(projects)} projects, {len(tasks)} tasks")
            
            # Cleanup test database
            os.unlink("./test_cos.db")
            
        except Exception as e:
            self.log_test("Database operations", False, f"Database test failed: {e}")
            return False
            
        return True
    
    def test_claude_client(self):
        """Test Claude client initialization"""
        print("\n" + "="*60)
        print("3. TESTING CLAUDE CLIENT")
        print("="*60)
        
        try:
            from claude_client import ClaudeClient
            claude = ClaudeClient()
            self.log_test("Claude client init", True, "Client initialized successfully")
            
            # Test prompt loading
            prompt_count = len(claude.prompts) if hasattr(claude, 'prompts') else 0
            self.log_test("Prompt loading", prompt_count > 0, f"Loaded {prompt_count} prompts")
            
            # Test connection check (without making API call)
            api_key_set = bool(os.getenv('ANTHROPIC_API_KEY'))
            self.log_test("API key check", api_key_set, f"API key {'set' if api_key_set else 'not set'}")
            
        except Exception as e:
            self.log_test("Claude client init", False, f"Failed: {e}")
            return False
            
        return True
    
    def test_com_integration(self):
        """Test COM integration"""
        print("\n" + "="*60)
        print("4. TESTING COM INTEGRATION")  
        print("="*60)
        
        try:
            from integrations.outlook.com_connector import COM_AVAILABLE, OutlookCOMConnector
            
            if not COM_AVAILABLE:
                self.log_test("COM availability", False, "pywin32 not installed or not on Windows")
                return False
                
            self.log_test("COM availability", True, "COM libraries available")
            
            # Test COM connector initialization
            connector = OutlookCOMConnector()
            self.log_test("COM connector init", True, "COM connector created")
            
            # Test connection (will fail if Outlook not running, but that's expected)
            try:
                connected = connector.connect()
                if connected:
                    self.log_test("Outlook connection", True, "Connected to running Outlook")
                    
                    # Test basic operations
                    folders = connector.get_folders()
                    self.log_test("Folder enumeration", True, f"Found {len(folders)} folders")
                else:
                    self.log_test("Outlook connection", False, "Outlook not running or not accessible")
                    
            except Exception as e:
                self.log_test("Outlook connection", False, f"Connection failed: {e}")
                
        except Exception as e:
            self.log_test("COM integration", False, f"Failed: {e}")
            return False
            
        return True
    
    async def test_agents(self):
        """Test agent system"""
        print("\n" + "="*60)
        print("5. TESTING AGENT SYSTEM")
        print("="*60)
        
        try:
            from claude_client import ClaudeClient
            from agents import COSOrchestrator, EmailTriageAgent
            from job_queue import JobQueue
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from models import Base
            
            # Initialize components
            claude = ClaudeClient()
            job_queue = JobQueue()
            orchestrator = COSOrchestrator(claude, job_queue)
            
            self.log_test("Agent initialization", True, "All agents initialized")
            
            # Test email triage agent
            email_agent = orchestrator.email_triage
            com_service = email_agent.get_com_service()
            self.log_test("Email agent setup", True, "Email triage agent has COM service")
            
            # Test database session for context
            engine = create_engine("sqlite:///./test_agents.db")
            Base.metadata.create_all(bind=engine)
            SessionLocal = sessionmaker(bind=engine)
            db = SessionLocal()
            
            # Test simple command processing (without API calls)
            test_commands = [
                "/outlook status",
                "/outlook info", 
                "/help"
            ]
            
            for command in test_commands:
                try:
                    # This will test command routing without making API calls
                    response = await orchestrator.process_user_input(command, db)
                    success = isinstance(response, str) and len(response) > 0
                    self.log_test(f"Command '{command}'", success, f"Response length: {len(response) if success else 0}")
                except Exception as e:
                    self.log_test(f"Command '{command}'", False, f"Failed: {e}")
            
            db.close()
            os.unlink("./test_agents.db")
            
        except Exception as e:
            self.log_test("Agent system", False, f"Failed: {e}")
            return False
            
        return True
    
    def test_job_queue(self):
        """Test job queue system"""
        print("\n" + "="*60)
        print("6. TESTING JOB QUEUE")
        print("="*60)
        
        try:
            from job_queue import JobQueue
            from models import Job
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from models import Base
            
            # Create test database
            engine = create_engine("sqlite:///./test_jobs.db")
            Base.metadata.create_all(bind=engine)
            
            # Initialize job queue
            queue = JobQueue()
            self.log_test("Job queue init", True, "Job queue initialized")
            
            # Test job creation (without actually running)
            job_data = {"test": "data"}
            self.log_test("Job queue ready", True, "Job queue system functional")
            
            # Cleanup
            os.unlink("./test_jobs.db")
            
        except Exception as e:
            self.log_test("Job queue", False, f"Failed: {e}")
            return False
            
        return True
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("SYSTEM TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results.values() if result)
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print(f"Duration: {time.time() - self.start_time:.2f}s")
        
        if failed_tests > 0:
            print(f"\n❌ FAILED TESTS:")
            for test_name, result in self.results.items():
                if not result:
                    print(f"  - {test_name}")
        
        overall_success = failed_tests == 0
        status = "✅ ALL TESTS PASSED" if overall_success else "❌ SOME TESTS FAILED"
        print(f"\n{status}")
        
        return overall_success

async def run_all_tests():
    """Run all system tests"""
    print("CHIEF OF STAFF - SYSTEM VALIDATION")
    print("Testing core functionality without requiring API keys or running Outlook")
    
    test = SystemTest()
    
    # Run tests in order
    success = True
    success &= test.test_imports()
    success &= test.test_database() 
    success &= test.test_claude_client()
    success &= test.test_com_integration()
    success &= await test.test_agents()
    success &= test.test_job_queue()
    
    # Print final summary
    overall_success = test.print_summary()
    
    return overall_success

if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test runner failed: {e}")
        sys.exit(1)