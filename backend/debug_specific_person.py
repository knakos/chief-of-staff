#!/usr/bin/env python3
"""
Debug to find the specific email with GEORGITZIKI ELPIDA
and understand if they appear as sender or recipient
"""
import asyncio
import websockets
import json
import sys

async def debug_specific_person():
    """Find the specific person and see their role in emails"""
    
    try:
        uri = "ws://127.0.0.1:8787/ws"
        async with websockets.connect(uri) as websocket:
            
            # Request more emails to find the specific one
            request = {
                "event": "email:get_recent",
                "data": {"limit": 20}
            }
            
            await websocket.send(json.dumps(request))
            response = await websocket.recv()
            response_data = json.loads(response)
            
            if response_data.get('event') == 'email:recent_list':
                emails = response_data.get('data', {}).get('emails', [])
                print(f'Searching through {len(emails)} emails for GEORGITZIKI ELPIDA...')
                
                found = False
                
                for i, email in enumerate(emails, 1):
                    # Check sender fields
                    sender = email.get('sender', '')
                    sender_name = email.get('sender_name', '')
                    sender_email = email.get('sender_email', '')
                    
                    # Check recipient fields
                    to_recipients = email.get('to_recipients', [])
                    cc_recipients = email.get('cc_recipients', [])
                    bcc_recipients = email.get('bcc_recipients', [])
                    
                    # Search for the target person
                    target_in_sender = (
                        'ΓΕΩΡΓΙΤΖΙΚΗ' in sender_name or 'ΕΛΠΙΔΑ' in sender_name or
                        'GEORGITZIKI' in sender_name or 'ELPIDA' in sender_name
                    )
                    
                    target_in_recipients = False
                    target_recipient_info = ""
                    
                    # Check all recipients
                    for recip_list, recip_type in [(to_recipients, 'TO'), (cc_recipients, 'CC'), (bcc_recipients, 'BCC')]:
                        for recip in recip_list:
                            if isinstance(recip, dict):
                                recip_name = recip.get('name', '')
                                if ('ΓΕΩΡΓΙΤΖΙΚΗ' in recip_name or 'ΕΛΠΙΔΑ' in recip_name or
                                    'GEORGITZIKI' in recip_name or 'ELPIDA' in recip_name):
                                    target_in_recipients = True
                                    target_recipient_info = f"{recip_type}: {recip_name}"
                    
                    if target_in_sender or target_in_recipients:
                        found = True
                        subject = email.get('subject', 'No subject')
                        
                        print(f'\\n*** FOUND TARGET PERSON in Email {i} ***')
                        print(f'Subject: {subject}')
                        
                        if target_in_sender:
                            print(f'APPEARS AS SENDER: {sender_name}')
                            print(f'  Sender Email: {sender_email}')
                        
                        if target_in_recipients:
                            print(f'APPEARS AS RECIPIENT: {target_recipient_info}')
                        
                        print(f'\\nFULL EMAIL DATA STRUCTURE:')
                        print(f'  sender: {sender}')
                        print(f'  sender_name: {sender_name}')
                        print(f'  sender_email: {sender_email}')
                        print(f'  to_recipients: {to_recipients}')
                        print(f'  cc_recipients: {cc_recipients}')
                        print(f'  bcc_recipients: {bcc_recipients}')
                        
                        print(f'\\nWHAT FRONTEND WILL DISPLAY:')
                        print(f'  From: {sender_name or sender_email or sender or "Unknown"}')
                        if to_recipients:
                            print(f'  To: {[r.get("name", r.get("address", "Unknown")) for r in to_recipients]}')
                        if cc_recipients:
                            print(f'  CC: {[r.get("name", r.get("address", "Unknown")) for r in cc_recipients]}')
                        if bcc_recipients:
                            print(f'  BCC: {[r.get("name", r.get("address", "Unknown")) for r in bcc_recipients]}')
                        
                        break
                
                if not found:
                    print('GEORGITZIKI ELPIDA not found in recent emails')
                    print('Showing sample email structure from first email:')
                    if emails:
                        sample = emails[0]
                        print(f'Sample email structure:')
                        print(f'  sender_name: {sample.get("sender_name", "missing")}')
                        print(f'  to_recipients: {sample.get("to_recipients", [])}')
                        
            else:
                print(f'Unexpected response: {response_data}')
                
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_specific_person())