#!/usr/bin/env python3
"""
Test the sender exclusion fix to ensure senders don't appear in recipient lists.
"""
import sys
sys.path.append('.')

from integrations.outlook.com_connector import OutlookCOMConnector

def test_sender_exclusion_fix():
    """Test that senders are properly excluded from recipient lists"""
    
    print("=== TESTING SENDER EXCLUSION FIX ===")
    
    connector = OutlookCOMConnector()
    if not connector.connect():
        print("Failed to connect to Outlook")
        return False
    
    # Get messages and check for sender in recipients
    messages = connector.get_messages(limit=10)
    print(f"Retrieved {len(messages)} messages for testing")
    
    issues_found = 0
    emails_processed = 0
    
    for i, msg in enumerate(messages, 1):
        sender = msg.get('sender', '')
        sender_name = msg.get('sender_name', '')
        to_recipients = msg.get('to_recipients', [])
        cc_recipients = msg.get('cc_recipients', [])
        
        emails_processed += 1
        
        try:
            # Check if sender appears in TO recipients
            for recip in to_recipients:
                recip_name = recip.get('name', '')
                recip_addr = recip.get('address', '')
                
                # Check for sender in recipients
                if sender and recip_addr and (sender in recip_addr or recip_addr in sender):
                    print(f"ISSUE Email {i}: Sender address found in TO recipients")
                    print(f"  Sender: {sender[:50]}")
                    print(f"  Recipient: {recip_addr[:50]}")
                    issues_found += 1
                
                if sender_name and recip_name and (sender_name in recip_name or recip_name in sender_name):
                    print(f"ISSUE Email {i}: Sender name found in TO recipients")
                    print(f"  Sender Name: {sender_name[:30]}")
                    print(f"  Recipient Name: {recip_name[:30]}")
                    issues_found += 1
            
            # Check if sender appears in CC recipients
            for recip in cc_recipients:
                recip_name = recip.get('name', '')
                recip_addr = recip.get('address', '')
                
                if sender and recip_addr and (sender in recip_addr or recip_addr in sender):
                    print(f"ISSUE Email {i}: Sender address found in CC recipients")
                    issues_found += 1
                
                if sender_name and recip_name and (sender_name in recip_name or recip_name in sender_name):
                    print(f"ISSUE Email {i}: Sender name found in CC recipients")
                    issues_found += 1
        
        except Exception as e:
            print(f"Error processing email {i}: {e}")
            continue
    
    print(f"\n=== TEST RESULTS ===")
    print(f"Emails processed: {emails_processed}")
    print(f"Issues found: {issues_found}")
    
    if issues_found == 0:
        print("SUCCESS: No senders found in recipient lists!")
        print("The sender exclusion fix is working correctly.")
        return True
    else:
        print("FAILURE: Senders still appearing in recipient lists.")
        print("The fix may need refinement.")
        return False

if __name__ == "__main__":
    success = test_sender_exclusion_fix()
    if not success:
        sys.exit(1)