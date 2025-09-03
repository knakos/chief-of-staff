#!/usr/bin/env python3
"""
Test script to diagnose and fix recipient extraction issues
"""
import logging
from integrations.outlook.com_connector import OutlookCOMConnector

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

def test_recipient_extraction():
    """Test recipient extraction with enhanced debugging"""
    
    # Initialize COM connector
    connector = OutlookCOMConnector()
    
    if not connector.connect():
        print("FAILED to connect to Outlook")
        return
    
    print("CONNECTED to Outlook")
    
    # Get a few messages to test
    messages = connector._get_messages_legacy("Inbox", 3)
    
    if not messages:
        print("No messages found")
        return
    
    print(f"Found {len(messages)} messages to analyze")
    
    for i, email in enumerate(messages):
        print(f"\n=== EMAIL {i+1} ===")
        print(f"Subject: {email.get('subject', 'No subject')[:50]}...")
        
        # Show recipient data
        to_recipients = email.get('to_recipients', [])
        cc_recipients = email.get('cc_recipients', [])
        
        print(f"TO recipients ({len(to_recipients)}):")
        for recipient in to_recipients:
            print(f"  Name: '{recipient.get('name', 'No name')}'")
            print(f"  Address: '{recipient.get('address', 'No address')}'")
            if recipient.get('address') == 'recipients@nbg.gr':
                print("  WARNING: GENERIC ADDRESS DETECTED!")
        
        print(f"CC recipients ({len(cc_recipients)}):")
        for recipient in cc_recipients:
            print(f"  Name: '{recipient.get('name', 'No name')}'")
            print(f"  Address: '{recipient.get('address', 'No address')}'")
            if recipient.get('address') == 'recipients@nbg.gr':
                print("  WARNING: GENERIC ADDRESS DETECTED!")

if __name__ == "__main__":
    test_recipient_extraction()