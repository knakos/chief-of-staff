#!/usr/bin/env python3
"""
Debug email extraction to see if we're getting actual email addresses
"""
import asyncio
import websockets
import json

async def debug_extraction():
    """Debug email extraction"""
    
    try:
        uri = "ws://127.0.0.1:8787/ws"
        async with websockets.connect(uri) as websocket:
            
            # Request just a few emails
            await websocket.send(json.dumps({
                "event": "email:get_recent", 
                "data": {"limit": 3}
            }))
            
            response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            response_data = json.loads(response)
            
            if response_data.get('event') == 'email:recent_list':
                emails = response_data.get('data', {}).get('emails', [])
                print(f"Received {len(emails)} emails")
                
                for i, email in enumerate(emails, 1):
                    print(f"\n=== EMAIL {i} ===")
                    print(f"Subject: {email.get('subject', 'No subject')[:50]}...")
                    
                    to_recipients = email.get('to_recipients', [])
                    print(f"TO Recipients ({len(to_recipients)}):")
                    for j, recip in enumerate(to_recipients[:2]):  # First 2
                        print(f"  {j+1}. Name: {recip.get('name', 'No name')}")
                        print(f"     Address: {recip.get('address', 'No address')}")
                        print(f"     Email: {recip.get('email', 'No email field')}")
                        
                        # Check if address looks like email
                        address = recip.get('address', '')
                        has_at = '@' in address if address else False
                        starts_with_slash = address.startswith('/') if address else False
                        print(f"     Has @: {has_at}, Starts with /: {starts_with_slash}")
                
                return True
            else:
                print(f"Unexpected response: {response_data}")
                return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(debug_extraction())
    if success:
        print("\nExtraction debug completed")
    else:
        print("\nExtraction debug failed")