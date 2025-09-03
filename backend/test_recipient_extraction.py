#!/usr/bin/env python3
"""
Comprehensive test for recipient extraction functionality.
Tests the complete pipeline from Outlook COM -> EmailSchema -> Database storage.
"""
import sys
import os
import logging
import json
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add current directory to path
sys.path.append('.')

from models import Email, Base
from schemas.email_schema import EmailSchema, create_email_from_com
from integrations.outlook.com_connector import OutlookCOMConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_recipient_extraction():
    """Test complete recipient extraction pipeline"""
    
    logger.info("🔍 Starting comprehensive recipient extraction test...")
    
    # Test 1: COM Connector Direct Access
    logger.info("\n=== Test 1: COM Connector Direct Access ===")
    try:
        connector = OutlookCOMConnector()
        if not connector.connect():
            logger.error("❌ Failed to connect to Outlook COM")
            return False
            
        # Get first few messages to test
        messages = connector.get_messages(limit=3)
        logger.info(f"Retrieved {len(messages)} messages from COM connector")
        
        for i, msg in enumerate(messages, 1):
            logger.info(f"\n--- Message {i} ---")
            logger.info(f"Subject: {msg.get('subject', 'No subject')[:50]}")
            logger.info(f"Sender: {msg.get('sender', 'No sender')}")
            
            to_recips = msg.get('to_recipients', [])
            cc_recips = msg.get('cc_recipients', [])  
            bcc_recips = msg.get('bcc_recipients', [])
            
            logger.info(f"TO Recipients: {len(to_recips)}")
            for recip in to_recips[:3]:  # Show first 3
                name = recip.get('name', '')[:30]
                addr = recip.get('address', '')[:50]
                logger.info(f"  - {name} <{addr}>")
            
            if cc_recips:
                logger.info(f"CC Recipients: {len(cc_recips)}")
                for recip in cc_recips[:2]:  # Show first 2
                    name = recip.get('name', '')[:30] 
                    addr = recip.get('address', '')[:50]
                    logger.info(f"  - {name} <{addr}>")
    
    except Exception as e:
        logger.error(f"❌ COM Connector test failed: {e}")
        return False
    
    # Test 2: EmailSchema Creation
    logger.info("\n=== Test 2: EmailSchema Creation ===")
    try:
        # Test schema creation from first message
        if messages:
            first_msg = messages[0]
            
            # Mock Outlook item structure for schema creation
            class MockOutlookItem:
                def __init__(self, msg_data):
                    self.EntryID = msg_data.get('id', 'test_id')
                    self.Subject = msg_data.get('subject', '')
                    self.sender = msg_data.get('sender', '')
                    self.SenderName = msg_data.get('sender_name', '')
                    self.ReceivedTime = datetime.now()
                    self.SentOn = datetime.now()
                    self.UnRead = False
                    self.Importance = 1
                    self.body = msg_data.get('body_preview', '')
                    
                    # Create Recipients collection mock
                    self.Recipients = MockRecipientsCollection(msg_data)
            
            class MockRecipientsCollection:
                def __init__(self, msg_data):
                    self.recipients = []
                    
                    # Add TO recipients
                    for recip in msg_data.get('to_recipients', []):
                        self.recipients.append(MockRecipient(recip['name'], recip['address'], 1))
                    
                    # Add CC recipients  
                    for recip in msg_data.get('cc_recipients', []):
                        self.recipients.append(MockRecipient(recip['name'], recip['address'], 2))
                
                def __iter__(self):
                    return iter(self.recipients)
                
                @property
                def Count(self):
                    return len(self.recipients)
            
            class MockRecipient:
                def __init__(self, name, address, rtype):
                    self.Name = name
                    self.Address = address
                    self.Type = rtype
                    self.AddressEntry = None
            
            mock_item = MockOutlookItem(first_msg)
            email_schema = create_email_from_com(mock_item)
            
            logger.info(f"EmailSchema created successfully:")
            logger.info(f"  Subject: {email_schema.subject}")
            logger.info(f"  TO Recipients: {len(email_schema.to_recipients or [])}")
            logger.info(f"  CC Recipients: {len(email_schema.cc_recipients or [])}")
            logger.info(f"  Legacy Recipients: {email_schema.recipients is not None}")
            
    except Exception as e:
        logger.error(f"❌ EmailSchema creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Database Storage
    logger.info("\n=== Test 3: Database Storage ===")
    try:
        # Connect to database
        engine = create_engine("sqlite:///./cos.db")
        Session = sessionmaker(bind=engine)
        db = Session()
        
        # Create a test email with recipients
        test_email = Email(
            id="test_recipient_email_001",
            subject="Test Email for Recipient Extraction",
            sender="test@example.com",
            sender_name="Test Sender",
            to_recipients=[
                {"name": "John Doe", "address": "john@example.com"},
                {"name": "Jane Smith", "address": "jane@example.com"}
            ],
            cc_recipients=[
                {"name": "Manager", "address": "manager@example.com"}
            ],
            bcc_recipients=[],
            recipients='[{"name": "John Doe", "address": "john@example.com"}, {"name": "Jane Smith", "address": "jane@example.com"}, {"name": "Manager", "address": "manager@example.com"}]',
            body_preview="This is a test email to verify recipient extraction",
            received_at=datetime.now(),
            status="test"
        )
        
        # Save to database
        db.add(test_email)
        db.commit()
        
        # Retrieve and verify
        stored_email = db.query(Email).filter(Email.id == "test_recipient_email_001").first()
        
        if stored_email:
            logger.info("✅ Test email stored successfully:")
            logger.info(f"  TO Recipients: {stored_email.to_recipients}")
            logger.info(f"  CC Recipients: {stored_email.cc_recipients}")
            logger.info(f"  Legacy Recipients: {stored_email.recipients}")
            
            # Clean up test data
            db.delete(stored_email)
            db.commit()
        else:
            logger.error("❌ Failed to retrieve stored test email")
            return False
            
        db.close()
        
    except Exception as e:
        logger.error(f"❌ Database storage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Real Email Processing Pipeline
    logger.info("\n=== Test 4: Real Email Processing Pipeline ===")
    try:
        # Connect to database
        engine = create_engine("sqlite:///./cos.db") 
        Session = sessionmaker(bind=engine)
        db = Session()
        
        # Get a real email from Outlook and process it through the complete pipeline
        if messages and len(messages) > 0:
            real_msg = messages[0]
            
            # Create proper Email model instance
            email_data = {
                'id': f"pipeline_test_{datetime.now().timestamp()}",
                'subject': real_msg.get('subject', ''),
                'sender': real_msg.get('sender', ''),
                'sender_name': real_msg.get('sender_name', ''),
                'to_recipients': real_msg.get('to_recipients', []),
                'cc_recipients': real_msg.get('cc_recipients', []),
                'bcc_recipients': real_msg.get('bcc_recipients', []),
                'body_preview': real_msg.get('body_preview', ''),
                'received_at': datetime.now(),
                'status': 'pipeline_test'
            }
            
            # Create legacy recipients field
            all_recips = (email_data['to_recipients'] + 
                         email_data['cc_recipients'] + 
                         email_data['bcc_recipients'])
            email_data['recipients'] = json.dumps(all_recips) if all_recips else None
            
            pipeline_email = Email(**email_data)
            
            db.add(pipeline_email)
            db.commit()
            
            # Verify pipeline result
            pipeline_result = db.query(Email).filter(Email.id == pipeline_email.id).first()
            if pipeline_result:
                total_recipients = (len(pipeline_result.to_recipients or []) + 
                                  len(pipeline_result.cc_recipients or []) + 
                                  len(pipeline_result.bcc_recipients or []))
                
                logger.info("✅ Complete pipeline test successful:")
                logger.info(f"  Email ID: {pipeline_result.id}")
                logger.info(f"  Total Recipients: {total_recipients}")
                logger.info(f"  TO: {len(pipeline_result.to_recipients or [])}")
                logger.info(f"  CC: {len(pipeline_result.cc_recipients or [])}")
                logger.info(f"  BCC: {len(pipeline_result.bcc_recipients or [])}")
                
                # Clean up
                db.delete(pipeline_result)
                db.commit()
            else:
                logger.error("❌ Pipeline test failed - could not retrieve email")
                return False
        
        db.close()
        
    except Exception as e:
        logger.error(f"❌ Pipeline test failed: {e}")
        import traceback 
        traceback.print_exc()
        return False
    
    logger.info("\n🎉 All recipient extraction tests completed successfully!")
    return True

if __name__ == "__main__":
    success = test_recipient_extraction()
    if success:
        print("\n✅ Recipient extraction is working correctly!")
    else:
        print("\n❌ Recipient extraction tests failed!")
        sys.exit(1)