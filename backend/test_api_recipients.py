#!/usr/bin/env python3
"""
Test that the API is properly returning recipient data.
"""
import sys
import asyncio
import json
from datetime import datetime

sys.path.append('.')

from integrations.outlook.hybrid_service import HybridOutlookService

async def test_api_recipients():
    """Test API recipient data extraction"""
    print("Testing API recipient data extraction...")
    
    try:
        # Create hybrid service 
        hybrid_service = HybridOutlookService()
        
        # Get messages like the API does
        emails = await hybrid_service.get_messages("Inbox", limit=3)
        print(f"Retrieved {len(emails)} emails")
        
        for i, email_data in enumerate(emails, 1):
            print(f"\n=== Email {i} ===")
            print(f"Subject: {email_data.get('subject', 'No subject')[:50]}")
            print(f"Sender: {email_data.get('sender', 'No sender')}")
            
            to_recipients = email_data.get('to_recipients', [])
            cc_recipients = email_data.get('cc_recipients', [])
            bcc_recipients = email_data.get('bcc_recipients', [])
            
            print(f"TO Recipients ({len(to_recipients)}):")
            for j, recip in enumerate(to_recipients[:3]):  # Show first 3
                name = str(recip.get('name', ''))[:30]
                address = str(recip.get('address', ''))[:50]
                print(f"  {j+1}. {name} <{address}>")
            
            if cc_recipients:
                print(f"CC Recipients ({len(cc_recipients)}):")
                for j, recip in enumerate(cc_recipients[:2]):  # Show first 2
                    name = str(recip.get('name', ''))[:30]
                    address = str(recip.get('address', ''))[:50]
                    print(f"  {j+1}. {name} <{address}>")
            
            # Test what would be sent to frontend
            simple_email = {
                "id": email_data.get("id", "unknown"),
                "subject": email_data.get("subject", "No Subject"),
                "sender_name": email_data.get("sender_name", "Unknown Sender"),
                "sender_email": email_data.get("sender_email", ""),
                "sender": email_data.get("sender", ""),
                "to_recipients": to_recipients,
                "cc_recipients": cc_recipients,
                "bcc_recipients": bcc_recipients,
                "body_preview": email_data.get("body_preview", ""),
                "received_at": str(email_data.get("received_at", "")),
                "is_read": email_data.get("is_read", False),
                "has_attachments": email_data.get("has_attachments", False),
                "importance": email_data.get("importance", "normal"),
            }
            
            # Check if recipients would be included
            if simple_email["to_recipients"]:
                print(f"✅ API will include {len(simple_email['to_recipients'])} TO recipients")
            else:
                print("❌ API will NOT include TO recipients")
                
            if simple_email["cc_recipients"]:
                print(f"✅ API will include {len(simple_email['cc_recipients'])} CC recipients")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ API recipient test completed")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_api_recipients())
    if not success:
        sys.exit(1)