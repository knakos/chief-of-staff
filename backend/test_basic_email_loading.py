"""
Emergency test to verify basic email loading is working again.
"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_basic_email_loading():
    """Test that emails are loading again"""
    print("🚨 EMERGENCY TEST: Basic Email Loading\n")
    
    try:
        from integrations.outlook.hybrid_service import HybridOutlookService
        from integrations.outlook.com_connector import COM_AVAILABLE
        
        if not COM_AVAILABLE:
            print("❌ COM not available")
            return False
        
        # Step 1: Connect
        print("1. Connecting to Outlook...")
        service = HybridOutlookService()
        connection = asyncio.run(service.connect())
        
        if not connection.get("connected"):
            print(f"❌ Connection failed: {connection.get('message')}")
            return False
        
        print(f"✅ Connected via {connection['method']}")
        
        # Step 2: Test basic email loading
        print("\n2. Testing basic email loading...")
        try:
            emails = asyncio.run(service.get_messages("Inbox", 5))
            
            if emails:
                print(f"✅ SUCCESS: Loaded {len(emails)} emails")
                
                # Show sample email
                sample = emails[0]
                print(f"   Sample email:")
                print(f"   - Subject: {sample.get('subject', 'No subject')[:50]}...")
                print(f"   - Sender: {sample.get('sender', 'No sender')}")
                print(f"   - ID: {sample.get('id', 'No ID')[:20]}...")
                print(f"   - Keys: {len(sample.keys())} properties")
                
                return True
            else:
                print("❌ No emails returned")
                return False
                
        except Exception as e:
            print(f"❌ Email loading failed: {e}")
            logger.exception("Email loading error:")
            return False
        
    except Exception as e:
        logger.exception("Test failed:")
        print(f"❌ Test failed: {e}")
        return False

def test_com_connector_directly():
    """Test COM connector directly"""
    print("\n🔧 Direct COM Connector Test\n")
    
    try:
        from integrations.outlook.com_connector import OutlookCOMConnector, COM_AVAILABLE
        
        if not COM_AVAILABLE:
            print("❌ COM not available")
            return False
        
        # Test direct connection
        print("1. Testing direct COM connection...")
        connector = OutlookCOMConnector()
        
        if not connector.connect():
            print("❌ COM connection failed")
            return False
        
        print("✅ COM connected")
        
        # Test direct email loading
        print("\n2. Testing direct COM email loading...")
        try:
            emails = connector.get_messages("Inbox", 3)
            
            if emails:
                print(f"✅ SUCCESS: Direct COM loaded {len(emails)} emails")
                
                sample = emails[0]
                print(f"   Sample email:")
                print(f"   - Subject: {sample.get('subject', 'No subject')[:50]}...")
                print(f"   - Sender: {sample.get('sender', 'No sender')}")
                
                return True
            else:
                print("❌ Direct COM returned no emails")
                return False
                
        except Exception as e:
            print(f"❌ Direct COM loading failed: {e}")
            logger.exception("Direct COM error:")
            return False
        
    except Exception as e:
        logger.exception("Direct COM test failed:")
        print(f"❌ Direct COM test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚨 EMERGENCY EMAIL LOADING TEST\n")
    
    # Test 1: Basic service loading
    success1 = test_basic_email_loading()
    
    # Test 2: Direct COM loading  
    success2 = test_com_connector_directly()
    
    print(f"\n{'='*50}")
    print("EMERGENCY TEST RESULTS:")
    print(f"✅ Service Loading: {'PASS' if success1 else 'FAIL'}")
    print(f"✅ Direct COM Loading: {'PASS' if success2 else 'FAIL'}")
    
    if success1 or success2:
        print(f"\n✅ EMAILS ARE LOADING AGAIN!")
        if success1:
            print("   -> Use service.get_messages() for normal operation")
        if success2:
            print("   -> Direct COM connector is working")
    else:
        print(f"\n❌ EMAILS STILL NOT LOADING - CHECK ERRORS ABOVE")
    
    exit(0 if (success1 or success2) else 1)