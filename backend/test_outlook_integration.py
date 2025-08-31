#!/usr/bin/env python3
"""
Comprehensive test script for Outlook integration
Tests all components thoroughly to identify the exact issue
"""
import os
import asyncio
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from integrations.outlook.auth import OutlookAuthManager
from integrations.outlook.connector import GraphAPIConnector
from agents import COSOrchestrator
from claude_client import ClaudeClient
from job_queue import JobQueue
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

async def test_environment_variables():
    """Test 1: Environment Variables Loading"""
    print("\n" + "="*60)
    print("TEST 1: ENVIRONMENT VARIABLES")
    print("="*60)
    
    # Load .env file
    env_loaded = load_dotenv()
    print(f"✓ .env file loading: {'SUCCESS' if env_loaded else 'FAILED'}")
    
    # Check individual variables
    client_id = os.getenv("MICROSOFT_CLIENT_ID")
    client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
    tenant_id = os.getenv("MICROSOFT_TENANT_ID", "common")
    redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8787/auth/callback")
    
    print(f"✓ MICROSOFT_CLIENT_ID: {'SET' if client_id else 'NOT SET'}")
    if client_id:
        print(f"   Value: {client_id}")
    
    print(f"✓ MICROSOFT_CLIENT_SECRET: {'SET' if client_secret else 'NOT SET'}")
    if client_secret:
        print(f"   Length: {len(client_secret)} characters")
    
    print(f"✓ MICROSOFT_TENANT_ID: {tenant_id}")
    print(f"✓ MICROSOFT_REDIRECT_URI: {redirect_uri}")
    
    return bool(client_id and client_secret)

def test_auth_manager_creation():
    """Test 2: Auth Manager Creation"""
    print("\n" + "="*60)
    print("TEST 2: AUTH MANAGER CREATION")
    print("="*60)
    
    try:
        auth_manager = OutlookAuthManager()
        print(f"✓ OutlookAuthManager created successfully")
        print(f"✓ client_id: {'SET' if auth_manager.client_id else 'NOT SET'}")
        if auth_manager.client_id:
            print(f"   Value: {auth_manager.client_id}")
        print(f"✓ client_secret: {'SET' if auth_manager.client_secret else 'NOT SET'}")
        print(f"✓ tenant_id: {auth_manager.tenant_id}")
        print(f"✓ redirect_uri: {auth_manager.redirect_uri}")
        return auth_manager
    except Exception as e:
        print(f"✗ Failed to create OutlookAuthManager: {e}")
        return None

def test_authorization_url_generation(auth_manager):
    """Test 3: Authorization URL Generation"""
    print("\n" + "="*60)
    print("TEST 3: AUTHORIZATION URL GENERATION")
    print("="*60)
    
    if not auth_manager:
        print("✗ Cannot test - auth_manager is None")
        return None, None
    
    try:
        auth_url, state = auth_manager.get_authorization_url()
        print(f"✓ Authorization URL generated successfully")
        print(f"✓ URL length: {len(auth_url)} characters")
        print(f"✓ State length: {len(state)} characters")
        print(f"✓ URL preview: {auth_url[:100]}...")
        
        # Check for client_id in URL
        if "client_id=None" in auth_url:
            print("✗ ERROR: URL contains client_id=None")
        elif auth_manager.client_id and auth_manager.client_id in auth_url:
            print(f"✓ URL contains correct client_id: {auth_manager.client_id}")
        else:
            print(f"✗ WARNING: client_id not found in URL")
        
        return auth_url, state
    except Exception as e:
        print(f"✗ Failed to generate authorization URL: {e}")
        return None, None

async def test_cos_orchestrator():
    """Test 4: COS Orchestrator Integration"""
    print("\n" + "="*60)
    print("TEST 4: COS ORCHESTRATOR INTEGRATION")
    print("="*60)
    
    try:
        # Create minimal components
        claude_client = ClaudeClient()
        job_queue = JobQueue()
        cos_orchestrator = COSOrchestrator(claude_client, job_queue)
        print("✓ COSOrchestrator created successfully")
        
        # Test auth manager within orchestrator
        auth_manager = cos_orchestrator.email_triage.auth_manager
        print(f"✓ Auth manager accessible: {'YES' if auth_manager else 'NO'}")
        
        if auth_manager:
            print(f"✓ client_id in orchestrator: {'SET' if auth_manager.client_id else 'NOT SET'}")
            if auth_manager.client_id:
                print(f"   Value: {auth_manager.client_id}")
        
        return cos_orchestrator
    except Exception as e:
        print(f"✗ Failed to create COSOrchestrator: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_outlook_status_command(cos_orchestrator):
    """Test 5: /outlook status Command Simulation"""
    print("\n" + "="*60)
    print("TEST 5: /OUTLOOK STATUS COMMAND SIMULATION")
    print("="*60)
    
    if not cos_orchestrator:
        print("✗ Cannot test - cos_orchestrator is None")
        return None
    
    try:
        # Simulate the exact command path
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from models import Base
        
        # Create temporary database
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        # Execute the command
        print("✓ Simulating '/outlook status' command...")
        result = await cos_orchestrator._handle_outlook_command("/outlook status", db)
        
        print(f"✓ Command executed successfully")
        print(f"✓ Result length: {len(result)} characters")
        print(f"✓ Result preview: {result[:200]}...")
        
        # Check for client_id=None in result
        if "client_id=None" in result:
            print("✗ ERROR: Result contains client_id=None")
        else:
            print("✓ Result does not contain client_id=None")
        
        db.close()
        return result
    except Exception as e:
        print(f"✗ Failed to execute /outlook status command: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_direct_api_call():
    """Test 6: Direct API Endpoint Test"""
    print("\n" + "="*60)
    print("TEST 6: DIRECT API ENDPOINT TEST")
    print("="*60)
    
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8787/auth/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✓ Direct API call successful")
                    print(f"✓ Response: {data}")
                    
                    if data.get("authenticated"):
                        print("✓ User is authenticated")
                    else:
                        auth_url = data.get("auth_url", "")
                        if "client_id=None" in auth_url:
                            print("✗ ERROR: Direct API returns client_id=None")
                        else:
                            print("✓ Direct API returns correct client_id")
                        print(f"✓ Auth URL: {auth_url[:100]}...")
                else:
                    print(f"✗ Direct API call failed: {response.status}")
    except Exception as e:
        print(f"✗ Direct API test failed: {e}")

async def main():
    """Run all tests"""
    print("OUTLOOK INTEGRATION COMPREHENSIVE TEST")
    print("="*60)
    print(f"Working directory: {os.getcwd()}")
    print(f"Python path: {sys.path[0]}")
    
    # Run all tests
    env_ok = await test_environment_variables()
    auth_manager = test_auth_manager_creation()
    auth_url, state = test_authorization_url_generation(auth_manager)
    cos_orchestrator = await test_cos_orchestrator()
    command_result = await test_outlook_status_command(cos_orchestrator)
    await test_direct_api_call()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✓ Environment Variables: {'PASS' if env_ok else 'FAIL'}")
    print(f"✓ Auth Manager Creation: {'PASS' if auth_manager else 'FAIL'}")
    print(f"✓ URL Generation: {'PASS' if auth_url and 'client_id=None' not in auth_url else 'FAIL'}")
    print(f"✓ COS Orchestrator: {'PASS' if cos_orchestrator else 'FAIL'}")
    print(f"✓ Command Simulation: {'PASS' if command_result and 'client_id=None' not in command_result else 'FAIL'}")
    
    if command_result:
        print(f"\nFINAL COMMAND RESULT:")
        print(f"'{command_result}'")
        
        if "client_id=None" in command_result:
            print("\n🚨 ISSUE IDENTIFIED: Command result contains client_id=None")
            print("   This means the issue is in the backend logic, not frontend caching")
        else:
            print("\n✅ BACKEND IS WORKING CORRECTLY")
            print("   The issue is likely in the frontend/WebSocket communication")

if __name__ == "__main__":
    asyncio.run(main())