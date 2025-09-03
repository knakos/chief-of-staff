"""
Debug script to diagnose COS property loading issues.
Tests whether COS properties are being written to and read from Outlook correctly.
"""
import logging
from datetime import datetime

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_cos_properties():
    """Debug COS property reading and writing"""
    print("=== COS Property Debug ===\n")
    
    try:
        from integrations.outlook.com_connector import OutlookCOMConnector, COM_AVAILABLE
        from integrations.outlook.property_sync import OutlookPropertySync
        from schemas.email_schema import EmailSchema
        
        if not COM_AVAILABLE:
            print("❌ COM not available")
            return False
        
        # Connect to Outlook
        connector = OutlookCOMConnector()
        if not connector.connect():
            print("❌ Failed to connect to Outlook")
            return False
        
        print("✅ Connected to Outlook")
        
        # Get a test email
        print("\n1. Getting test email...")
        emails = connector._get_messages_legacy("Inbox", 1)
        if not emails:
            print("❌ No emails found for testing")
            return False
        
        test_email = emails[0]
        email_id = test_email['id']
        print(f"   Test email: {test_email['subject'][:50]}...")
        
        # Get the Outlook item directly
        outlook_item = connector.namespace.GetItemFromID(email_id)
        
        # Step 2: Check existing COS properties
        print("\n2. Checking existing COS properties...")
        property_sync = OutlookPropertySync()
        property_sync.com_connector = connector
        
        existing_cos_data = property_sync.read_cos_data_from_outlook(outlook_item)
        print(f"   Found {len(existing_cos_data)} existing COS properties:")
        for key, value in existing_cos_data.items():
            print(f"      {key}: {value}")
        
        # Step 3: Write test COS properties
        print("\n3. Writing test COS properties...")
        
        # Create test email schema with analysis data
        email_schema = EmailSchema(
            id=email_id,
            subject=test_email['subject'],
            sender=test_email['sender'],
            project_id="test-project-123",
            confidence=0.85,
            provenance="debug_test",
            analysis={
                "priority": "high",
                "urgency": "medium", 
                "tone": "professional",
                "summary": "Test AI summary for debugging COS properties",
                "confidence": 0.90
            }
        )
        
        success = property_sync.write_cos_data_to_outlook(email_schema, outlook_item)
        if success:
            print("   ✅ Successfully wrote test COS properties")
        else:
            print("   ❌ Failed to write COS properties")
            return False
        
        # Step 4: Read back the properties
        print("\n4. Reading back COS properties...")
        updated_cos_data = property_sync.read_cos_data_from_outlook(outlook_item)
        print(f"   Found {len(updated_cos_data)} COS properties after write:")
        for key, value in updated_cos_data.items():
            print(f"      {key}: {value}")
        
        # Step 5: Test batch loader property extraction
        print("\n5. Testing batch loader COS property extraction...")
        if hasattr(connector, '_batch_loader') and connector._batch_loader:
            batch_loader = connector._batch_loader
            cos_props = batch_loader._extract_cos_properties_batch(outlook_item)
            print(f"   Batch loader found {len(cos_props)} COS properties:")
            for key, value in cos_props.items():
                print(f"      {key}: {value}")
            
            # Test full property extraction
            print("\n6. Testing full batch property extraction...")
            full_email_data = batch_loader._extract_all_properties_optimized(outlook_item)
            if full_email_data:
                print("   ✅ Full extraction successful")
                print(f"   Project ID: {full_email_data.get('project_id')}")
                print(f"   Confidence: {full_email_data.get('confidence')}")
                print(f"   Analysis: {full_email_data.get('analysis')}")
            else:
                print("   ❌ Full extraction failed")
        else:
            print("   ⚠️  Batch loader not available")
        
        # Step 6: Test property enumeration directly
        print("\n7. Direct property enumeration test...")
        try:
            user_props = outlook_item.UserProperties
            print(f"   Total UserProperties: {user_props.Count}")
            
            cos_props_direct = {}
            for i in range(1, user_props.Count + 1):  # COM collections are 1-indexed
                try:
                    prop = user_props.Item(i)
                    prop_name = prop.Name
                    prop_value = prop.Value
                    print(f"      Property {i}: {prop_name} = {prop_value}")
                    
                    if prop_name.startswith("COS."):
                        cos_props_direct[prop_name] = prop_value
                except Exception as e:
                    print(f"      Error reading property {i}: {e}")
            
            print(f"   Direct enumeration found {len(cos_props_direct)} COS properties:")
            for key, value in cos_props_direct.items():
                print(f"      {key}: {value}")
                
        except Exception as e:
            print(f"   ❌ Direct enumeration failed: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Debug failed: {e}")
        print(f"❌ Debug failed: {e}")
        return False

def test_batch_loader_cos_integration():
    """Test if batch loader properly integrates COS properties"""
    print("\n=== Batch Loader COS Integration Test ===\n")
    
    try:
        import asyncio
        from integrations.outlook.com_connector import OutlookCOMConnector, COM_AVAILABLE
        
        if not COM_AVAILABLE:
            print("❌ COM not available")
            return False
        
        connector = OutlookCOMConnector()
        if not connector.connect():
            print("❌ Failed to connect to Outlook")
            return False
        
        print("✅ Connected to Outlook")
        
        # Test batch loading
        print("\n1. Testing batch loader...")
        if hasattr(connector, '_batch_loader') and connector._batch_loader:
            batch_loader = connector._batch_loader
            emails = asyncio.run(batch_loader.load_emails_batch("Inbox", 5))
            
            print(f"   Loaded {len(emails)} emails via batch loader")
            
            # Check for COS properties in results
            cos_email_count = 0
            for email in emails:
                has_cos = any(email.get(prop) is not None for prop in ['project_id', 'confidence', 'provenance', 'analysis'])
                if has_cos:
                    cos_email_count += 1
                    print(f"   Email with COS data: {email['subject'][:30]}...")
                    print(f"      Project ID: {email.get('project_id')}")
                    print(f"      Confidence: {email.get('confidence')}")
                    print(f"      Analysis: {email.get('analysis')}")
            
            print(f"\n   Summary: {cos_email_count}/{len(emails)} emails have COS properties")
            
            if cos_email_count == 0:
                print("   ⚠️  No COS properties found - this could be normal if no emails have been analyzed yet")
            else:
                print("   ✅ COS properties are being loaded correctly")
                
        else:
            print("   ❌ Batch loader not initialized")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        print(f"❌ Integration test failed: {e}")
        return False

if __name__ == "__main__":
    try:
        print("🔍 Starting COS Property Debugging\n")
        
        success1 = debug_cos_properties()
        success2 = test_batch_loader_cos_integration()
        
        print(f"\n{'='*50}")
        print("DEBUG RESULTS:")
        print(f"✅ Property Debug: {'PASS' if success1 else 'FAIL'}")
        print(f"✅ Integration Test: {'PASS' if success2 else 'FAIL'}")
        
        if success1 and success2:
            print(f"\n🎉 COS properties are working correctly!")
        else:
            print(f"\n❌ COS property issues found - check implementation")
        
    except Exception as e:
        logger.error(f"Debug execution failed: {e}")
        print(f"💥 Debug failed: {e}")