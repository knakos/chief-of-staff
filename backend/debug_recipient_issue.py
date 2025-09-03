#!/usr/bin/env python3
"""
Debug the specific recipient display issue where sender appears as recipient.
"""
import sys
import json
sys.path.append('.')

from integrations.outlook.com_connector import OutlookCOMConnector

def debug_recipient_issue():
    """Debug recipient vs sender display issue"""
    
    print("=== DEBUGGING RECIPIENT DISPLAY ISSUE ===\n")
    
    connector = OutlookCOMConnector()
    if not connector.connect():
        print("Failed to connect to Outlook")
        return
    
    # Get messages and analyze the data structure
    messages = connector.get_messages(limit=10)
    print(f"Retrieved {len(messages)} messages for analysis\n")
    
    for i, msg in enumerate(messages, 1):
        print(f"=== EMAIL {i} ===")
        
        subject = msg.get('subject', 'No subject')
        sender = msg.get('sender', 'No sender')
        sender_name = msg.get('sender_name', 'No sender name')
        
        # Safely display subject (avoiding Unicode)
        try:
            print(f"Subject: {subject[:40]}")
        except:
            print("Subject: [Unicode subject]")
        
        print(f"Sender Address: {sender[:50] if sender else 'None'}")
        
        # Safely display sender name  
        try:
            print(f"Sender Name: {sender_name[:30] if sender_name else 'None'}")
        except:
            print("Sender Name: [Unicode name]")
        
        # Check recipients
        to_recipients = msg.get('to_recipients', [])
        cc_recipients = msg.get('cc_recipients', [])
        
        print(f"TO Recipients: {len(to_recipients)}")
        for j, recip in enumerate(to_recipients[:3]):  # Show first 3
            try:
                name = recip.get('name', 'No name')
                addr = recip.get('address', 'No address')
                # Check if recipient name is actually the sender name
                if name == sender_name:
                    print(f"  ⚠️  TO{j+1}: SENDER NAME IN RECIPIENT! {name[:20]}")
                else:
                    print(f"  ✓ TO{j+1}: {name[:20]} | {addr[:30]}")
            except:
                print(f"  TO{j+1}: [Unicode recipient]")
        
        print(f"CC Recipients: {len(cc_recipients)}")
        for j, recip in enumerate(cc_recipients[:2]):  # Show first 2
            try:
                name = recip.get('name', 'No name')
                addr = recip.get('address', 'No address')
                # Check if recipient name is actually the sender name
                if name == sender_name:
                    print(f"  ⚠️  CC{j+1}: SENDER NAME IN RECIPIENT! {name[:20]}")
                else:
                    print(f"  ✓ CC{j+1}: {name[:20]} | {addr[:30]}")
            except:
                print(f"  CC{j+1}: [Unicode recipient]")
        
        # Check for the specific issue pattern
        if to_recipients:
            first_recip_name = to_recipients[0].get('name', '')
            if sender_name and sender_name in first_recip_name:
                print("🔥 ISSUE FOUND: Sender name appears in recipient field!")
                print(f"   Sender name: '{sender_name[:30]}'")
                print(f"   Recipient name: '{first_recip_name[:30]}'")
        
        print("-" * 50)
        
        if i >= 5:  # Limit output
            break
    
    print("\n=== ANALYSIS COMPLETE ===")
    print("Look for '⚠️' markers indicating sender names in recipient fields")

if __name__ == "__main__":
    debug_recipient_issue()