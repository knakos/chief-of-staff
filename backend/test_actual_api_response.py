#!/usr/bin/env python3
"""
Test what the actual API is returning to the frontend right now.
This will show us what the user is actually seeing.
"""
import asyncio
import websockets
import json
import sys

async def test_actual_api():
    """Test the actual API response that the frontend receives"""
    
    print("=== TESTING ACTUAL API RESPONSE ===")
    print("Connecting to WebSocket...")
    
    try:
        uri = "ws://127.0.0.1:8787/ws"
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to WebSocket")
            
            # Send the same request that the frontend sends
            request = {
                "event": "email:get_recent",
                "data": {"limit": 3}
            }
            
            print("Sending email request...")
            await websocket.send(json.dumps(request))
            
            # Wait for response
            print("Waiting for response...")
            response = await websocket.recv()
            response_data = json.loads(response)
            
            print(f"Response event: {response_data.get('event')}")
            
            if response_data.get('event') == 'email:recent_list':
                emails = response_data.get('data', {}).get('emails', [])
                print(f"Received {len(emails)} emails")
                
                # Examine the actual data structure
                for i, email in enumerate(emails, 1):
                    print(f"\\n=== EMAIL {i} (API Response) ===")
                    print(f"ID: {email.get('id', 'missing')}")
                    print(f"Subject: {email.get('subject', 'missing')[:50]}")
                    print(f"Sender: {email.get('sender', 'missing')}")
                    print(f"Sender Name: {email.get('sender_name', 'missing')}")
                    print(f"Sender Email: {email.get('sender_email', 'missing')}")
                    
                    # Check recipient fields
                    to_recipients = email.get('to_recipients', [])
                    cc_recipients = email.get('cc_recipients', [])
                    bcc_recipients = email.get('bcc_recipients', [])
                    
                    print(f"TO Recipients ({len(to_recipients)}):")
                    for j, recip in enumerate(to_recipients[:3]):
                        if isinstance(recip, dict):
                            name = recip.get('name', 'No name')
                            address = recip.get('address', 'No address')
                            print(f"  {j+1}. '{name}' <{address}>")
                        else:
                            print(f"  {j+1}. {recip} (not dict)")
                    
                    if cc_recipients:
                        print(f"CC Recipients ({len(cc_recipients)}):")
                        for j, recip in enumerate(cc_recipients[:2]):
                            if isinstance(recip, dict):
                                name = recip.get('name', 'No name')
                                address = recip.get('address', 'No address')
                                print(f"  {j+1}. '{name}' <{address}>")
                            else:
                                print(f"  {j+1}. {recip} (not dict)")
                    
                    # Check if any recipient matches sender
                    sender_name = email.get('sender_name', '')
                    for recip in to_recipients + cc_recipients:
                        if isinstance(recip, dict):
                            recip_name = recip.get('name', '')
                            if sender_name and recip_name and sender_name in recip_name:
                                print(f"🚨 PROBLEM: Sender '{sender_name}' appears in recipients as '{recip_name}'")
                    
                    print("-" * 60)
                    
                    if i >= 3:  # Limit output
                        break
                        
            else:
                print(f"Unexpected response: {response_data}")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_actual_api())