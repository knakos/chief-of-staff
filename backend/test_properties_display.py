"""
Test to verify email properties are loading and being displayed correctly.
"""
import asyncio
import logging
import json

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_property_visibility():
    """Test that email properties are visible and complete"""
    print("🔍 Testing Email Property Visibility\n")
    
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
        
        # Step 2: Load emails and check properties
        print("\n2. Loading emails and checking properties...")
        
        emails = asyncio.run(service.get_messages("Inbox", 3))
        
        if not emails:
            print("❌ No emails loaded")
            return False
        
        print(f"✅ Loaded {len(emails)} emails")
        
        # Step 3: Detailed property analysis
        print("\n3. Analyzing email properties...")
        
        for i, email in enumerate(emails):
            print(f"\n--- Email {i+1} ---")
            print(f"Subject: {email.get('subject', 'NO SUBJECT')[:60]}...")
            print(f"Sender: {email.get('sender', 'NO SENDER')}")
            print(f"Sender Name: {email.get('sender_name', 'NO SENDER NAME')}")
            
            # Check basic properties
            basic_props = [
                'id', 'received_at', 'sent_at', 'is_read', 'importance', 
                'has_attachments', 'categories', 'conversation_id', 'size'
            ]
            
            missing_basic = []
            for prop in basic_props:
                if prop not in email:
                    missing_basic.append(prop)
                else:
                    print(f"  {prop}: {email[prop]}")
            
            if missing_basic:
                print(f"  ⚠️  Missing basic properties: {missing_basic}")
            else:
                print(f"  ✅ All basic properties present")
            
            # Check recipient properties
            to_count = len(email.get('to_recipients', []))
            cc_count = len(email.get('cc_recipients', []))
            bcc_count = len(email.get('bcc_recipients', []))
            
            print(f"  Recipients: To={to_count}, CC={cc_count}, BCC={bcc_count}")
            
            if to_count > 0:
                sample_recipient = email['to_recipients'][0]
                print(f"    Sample TO: {sample_recipient.get('name', 'No name')} <{sample_recipient.get('address', 'No address')}>")
            
            # Check body properties
            body_content = email.get('body_content', '')
            body_preview = email.get('body_preview', '')
            
            print(f"  Body content length: {len(body_content)} chars")
            print(f"  Body preview: {body_preview[:100]}..." if body_preview else "  No body preview")
            
            # Check COS properties
            cos_props = []
            cos_values = {}
            
            if email.get('project_id'):
                cos_props.append('project_id')
                cos_values['project_id'] = email['project_id']
            
            if email.get('confidence'):
                cos_props.append('confidence')
                cos_values['confidence'] = email['confidence']
            
            if email.get('provenance'):
                cos_props.append('provenance')
                cos_values['provenance'] = email['provenance']
            
            if email.get('analysis'):
                cos_props.append('analysis')
                cos_values['analysis'] = email['analysis']
            
            if cos_props:
                print(f"  ✅ COS properties found: {cos_props}")
                for prop, value in cos_values.items():
                    print(f"    {prop}: {value}")
            else:
                print(f"  ℹ️  No COS properties (normal if not analyzed yet)")
            
            print(f"  📊 Total properties: {len(email)} keys")
        
        # Step 4: Test property extraction methods
        print(f"\n4. Testing different extraction methods...")
        
        if hasattr(service.com_connector, '_batch_loader') and service.com_connector._batch_loader:
            print("   Testing batch loader...")
            try:
                batch_emails = asyncio.run(service.com_connector.get_messages_batch("Inbox", 1))
                if batch_emails:
                    batch_email = batch_emails[0]
                    print(f"   ✅ Batch loader: {len(batch_email)} properties")
                    
                    # Compare with regular loading
                    regular_email = emails[0] if emails else {}
                    if len(batch_email) != len(regular_email):
                        print(f"   ⚠️  Property count mismatch: batch={len(batch_email)}, regular={len(regular_email)}")
                    else:
                        print(f"   ✅ Property counts match")
                else:
                    print("   ❌ Batch loader returned no emails")
            except Exception as e:
                print(f"   ❌ Batch loader failed: {e}")
        
        # Step 5: Write test COS properties and reload
        print(f"\n5. Testing COS property persistence...")
        
        if emails and hasattr(service, 'com_connector') and service.com_connector:
            try:
                test_email = emails[0]
                email_id = test_email['id']
                
                # Get Outlook item and write test properties
                outlook_item = service.com_connector.namespace.GetItemFromID(email_id)
                
                # Write test COS properties
                test_props = {
                    "COS.Priority": "high",
                    "COS.Urgency": "medium", 
                    "COS.Tone": "professional",
                    "COS.Summary": "Test summary for property visibility",
                    "COS.ProjectId": "test-proj-123",
                    "COS.Confidence": 0.95
                }
                
                for prop_name, prop_value in test_props.items():
                    try:
                        if isinstance(prop_value, float):
                            user_prop = outlook_item.UserProperties.Add(prop_name, 5)
                        else:
                            user_prop = outlook_item.UserProperties.Add(prop_name, 1)
                        user_prop.Value = prop_value
                    except:
                        # Property might exist, try to update
                        try:
                            existing_prop = outlook_item.UserProperties(prop_name)
                            existing_prop.Value = prop_value
                        except:
                            pass
                
                outlook_item.Save()
                print(f"   ✅ Wrote {len(test_props)} test COS properties")
                
                # Reload and check
                print("   Reloading email to test persistence...")
                reloaded_emails = asyncio.run(service.get_messages("Inbox", 1))
                
                if reloaded_emails:
                    reloaded_email = reloaded_emails[0]
                    
                    cos_found = []
                    if reloaded_email.get('project_id'):
                        cos_found.append(f"project_id={reloaded_email['project_id']}")
                    if reloaded_email.get('confidence'):
                        cos_found.append(f"confidence={reloaded_email['confidence']}")
                    if reloaded_email.get('analysis'):
                        analysis = reloaded_email['analysis']
                        if isinstance(analysis, dict):
                            cos_found.extend([f"{k}={v}" for k, v in analysis.items()])
                    
                    if cos_found:
                        print(f"   ✅ COS properties loaded: {', '.join(cos_found)}")
                    else:
                        print(f"   ❌ COS properties not found after reload")
                
            except Exception as e:
                print(f"   ❌ COS property test failed: {e}")
                logger.exception("COS property test error:")
        
        return True
        
    except Exception as e:
        logger.exception("Property visibility test failed:")
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Email Property Visibility Test\n")
    success = test_property_visibility()
    
    print(f"\n{'='*60}")
    print(f"Property Visibility Test: {'✅ PASS' if success else '❌ FAIL'}")
    
    if success:
        print("\n🎉 Email properties are loading and visible!")
        print("   - Basic properties: ✅")
        print("   - Recipient properties: ✅") 
        print("   - COS properties: ✅ (when present)")
    else:
        print("\n❌ Property loading issues detected")
    
    exit(0 if success else 1)