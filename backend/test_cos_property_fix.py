"""
Simple test to verify COS properties are now loading correctly.
"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_cos_property_loading():
    """Test that COS properties are now loaded correctly"""
    print("🧪 Testing COS Property Loading Fix\n")
    
    try:
        from integrations.outlook.hybrid_service import HybridOutlookService
        from integrations.outlook.com_connector import COM_AVAILABLE
        from schemas.email_schema import EmailSchema
        
        if not COM_AVAILABLE:
            print("❌ COM not available")
            return False
        
        # Step 1: Connect
        service = HybridOutlookService()
        connection = asyncio.run(service.connect())
        
        if not connection.get("connected"):
            print(f"❌ Connection failed: {connection.get('message')}")
            return False
        
        print(f"✅ Connected via {connection['method']}")
        
        # Step 2: Get a test email and add COS properties to it
        print("\n📧 Preparing test email with COS properties...")
        
        emails = asyncio.run(service.get_messages("Inbox", 1))
        if not emails:
            print("❌ No emails found for testing")
            return False
        
        test_email = emails[0]
        email_id = test_email['id']
        print(f"   Using email: {test_email['subject'][:40]}...")
        
        # Step 3: Write test COS properties directly
        print("\n✍️  Writing test COS properties...")
        
        if service.com_connector and service.com_connector.is_connected():
            try:
                # Get Outlook item
                outlook_item = service.com_connector.namespace.GetItemFromID(email_id)
                
                # Write test properties directly
                test_data = {
                    "COS.Priority": "high",
                    "COS.Urgency": "medium",
                    "COS.Tone": "professional", 
                    "COS.Summary": "Test AI summary for COS property loading",
                    "COS.ProjectId": "test-project-123",
                    "COS.Confidence": 0.85,
                    "COS.ProcessedAt": "2024-01-15T10:30:00Z"
                }
                
                for prop_name, prop_value in test_data.items():
                    try:
                        if isinstance(prop_value, float):
                            user_prop = outlook_item.UserProperties.Add(prop_name, 5)  # Float type
                        else:
                            user_prop = outlook_item.UserProperties.Add(prop_name, 1)  # String type
                        user_prop.Value = prop_value
                    except:
                        # Property might already exist, try to update
                        try:
                            existing_prop = outlook_item.UserProperties(prop_name)
                            existing_prop.Value = prop_value
                        except:
                            logger.warning(f"Could not set property {prop_name}")
                
                outlook_item.Save()
                print(f"   ✅ Wrote {len(test_data)} test COS properties")
                
            except Exception as e:
                print(f"   ❌ Failed to write COS properties: {e}")
                return False
        
        # Step 4: Test batch loading with COS properties
        print("\n🔄 Testing batch loading with COS properties...")
        
        # Force clear any cache
        if hasattr(service.com_connector, '_batch_loader') and service.com_connector._batch_loader:
            service.com_connector._batch_loader.clear_cache()
        
        # Load emails with batch loader
        batch_emails = asyncio.run(service.get_messages("Inbox", 5))
        
        print(f"   Loaded {len(batch_emails)} emails via batch loader")
        
        # Step 5: Check for COS properties in the test email
        print("\n🔍 Checking for COS properties...")
        
        test_email_loaded = None
        for email in batch_emails:
            if email['id'] == email_id:
                test_email_loaded = email
                break
        
        if not test_email_loaded:
            print("   ❌ Test email not found in batch results")
            return False
        
        # Check COS properties
        cos_props_found = []
        expected_props = ['project_id', 'confidence', 'analysis']
        
        for prop in expected_props:
            if test_email_loaded.get(prop) is not None:
                cos_props_found.append(prop)
        
        print(f"   Found COS properties: {cos_props_found}")
        
        # Check specific values
        if test_email_loaded.get('project_id'):
            print(f"   ✅ Project ID: {test_email_loaded['project_id']}")
        
        if test_email_loaded.get('confidence'):
            print(f"   ✅ Confidence: {test_email_loaded['confidence']}")
        
        if test_email_loaded.get('analysis'):
            analysis = test_email_loaded['analysis']
            print(f"   ✅ Analysis data:")
            if isinstance(analysis, dict):
                for key, value in analysis.items():
                    print(f"      {key}: {value}")
            else:
                print(f"      {analysis}")
        
        # Final validation
        if cos_props_found:
            print(f"\n🎉 SUCCESS: Found {len(cos_props_found)} COS properties in batch-loaded email!")
            print("   COS properties are now loading correctly with batch property loader")
            return True
        else:
            print(f"\n⚠️  No COS properties found in batch-loaded email")
            print("   This could indicate an issue with property extraction")
            return False
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"\n❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_cos_property_loading()
    print(f"\n{'='*50}")
    print(f"COS Property Loading Test: {'✅ PASS' if success else '❌ FAIL'}")
    exit(0 if success else 1)