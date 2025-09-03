#!/usr/bin/env python3
"""
Debug recipient extraction issues - simpler version
"""
import json
from integrations.outlook.com_connector import OutlookCOMConnector

def debug_recipients():
    """Debug recipient extraction"""
    
    connector = OutlookCOMConnector()
    
    if not connector.connect():
        print("Failed to connect")
        return
    
    print("Connected to Outlook")
    
    # Get a few messages
    messages = connector._get_messages_legacy("Inbox", 2)
    
    if not messages:
        print("No messages found")
        return
    
    print(f"Found {len(messages)} messages")
    
    for i, email in enumerate(messages):
        print(f"\nEMAIL {i+1}:")
        try:
            print(f"Subject: {email.get('subject', 'No subject')[:30]}...")
        except UnicodeEncodeError:
            print("Subject: [Unicode subject]")
        
        # Get recipient data
        to_recipients = email.get('to_recipients', [])
        print(f"TO recipients count: {len(to_recipients)}")
        
        for j, recipient in enumerate(to_recipients):
            try:
                name = recipient.get('name', 'No name')
                address = recipient.get('address', 'No address')
                
                # Check for the generic address issue
                if address == 'recipients@nbg.gr':
                    print(f"  Recipient {j+1}: GENERIC ADDRESS DETECTED")
                    print(f"    Name length: {len(name)}")
                    print(f"    Address: {address}")
                else:
                    print(f"  Recipient {j+1}: Valid address")
                    print(f"    Address: {address}")
                    
            except Exception as e:
                print(f"  Recipient {j+1}: Error processing - {e}")

if __name__ == "__main__":
    debug_recipients()