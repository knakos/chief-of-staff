#!/usr/bin/env python3
"""
Dump the exact JSON data for Email 3 to see what the frontend receives
"""
import asyncio
import websockets
import json

async def dump_email_3():
    """Get the exact JSON for Email 3"""
    
    uri = "ws://127.0.0.1:8787/ws"
    async with websockets.connect(uri) as websocket:
        request = {"event": "email:get_recent", "data": {"limit": 5}}
        await websocket.send(json.dumps(request))
        response = await websocket.recv()
        response_data = json.loads(response)
        
        if response_data.get('event') == 'email:recent_list':
            emails = response_data.get('data', {}).get('emails', [])
            
            if len(emails) >= 3:
                email3 = emails[2]  # Third email
                
                # Save to file to avoid Unicode issues
                with open('email3_data.json', 'w', encoding='utf-8') as f:
                    json.dump(email3, f, indent=2, ensure_ascii=False)
                
                print("Email 3 data saved to email3_data.json")
                
                # Also print key field info safely
                print("EMAIL 3 KEY FIELD ANALYSIS:")
                print("==========================")
                
                # Check field types and presence
                fields_to_check = ['sender', 'sender_name', 'sender_email', 'to_recipients', 'cc_recipients', 'bcc_recipients']
                
                for field in fields_to_check:
                    value = email3.get(field)
                    if isinstance(value, list):
                        print(f"{field}: LIST with {len(value)} items")
                        for i, item in enumerate(value[:2]):  # First 2 items
                            if isinstance(item, dict):
                                print(f"  [{i}] DICT with keys: {list(item.keys())}")
                            else:
                                print(f"  [{i}] {type(item).__name__}: {str(item)[:30]}...")
                    elif isinstance(value, str):
                        print(f"{field}: STRING (length {len(value)})")
                    elif value is None:
                        print(f"{field}: NULL")
                    else:
                        print(f"{field}: {type(value).__name__}")
                
                # Critical check: Is sender_name somehow in to_recipients?
                to_recipients = email3.get('to_recipients', [])
                sender_name = email3.get('sender_name', '')
                
                if isinstance(to_recipients, list):
                    print(f"\nCRITICAL CHECK:")
                    print(f"Sender name contains ΓΕΩΡΓΙΤΖΙΚΗ or ΕΛΠΙΔΑ: {bool(sender_name and ('ΓΕΩΡΓΙΤΖΙΚΗ' in sender_name or 'ΕΛΠΙΔΑ' in sender_name))}")
                    
                    sender_in_recipients = False
                    for i, recip in enumerate(to_recipients):
                        if isinstance(recip, dict):
                            recip_name = recip.get('name', '')
                            if recip_name and sender_name and (sender_name in recip_name or recip_name in sender_name):
                                print(f"FOUND ISSUE: Sender name appears in TO recipient #{i}")
                                sender_in_recipients = True
                    
                    if not sender_in_recipients:
                        print("GOOD: Sender name does not appear in TO recipients")
                else:
                    print(f"ERROR: to_recipients is not a list: {type(to_recipients)}")

if __name__ == "__main__":
    asyncio.run(dump_email_3())