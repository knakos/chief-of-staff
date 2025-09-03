"""
Check what email data is actually being sent over WebSocket.
"""
import asyncio
import websockets
import json

async def test_websocket_data():
    print("🔍 Testing WebSocket Email Data\n")
    
    try:
        # Connect to WebSocket
        uri = "ws://127.0.0.1:8787/ws"
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to WebSocket")
            
            # Send email request
            request = {
                "event": "email:get_recent",
                "data": {"limit": 3}
            }
            
            await websocket.send(json.dumps(request))
            print("📤 Sent email request")
            
            # Wait for response
            response = await websocket.recv()
            response_data = json.loads(response)
            
            if response_data.get('event') == 'email:recent_list':
                emails = response_data.get('data', {}).get('emails', [])
                print(f"📧 Received {len(emails)} emails\n")
                
                if emails:
                    # Show first email properties
                    first_email = emails[0]
                    print("📋 First Email Properties:")
                    print(f"   Keys: {list(first_email.keys())}")
                    print(f"   Subject: {first_email.get('subject', 'NO SUBJECT')}")
                    print(f"   Sender: {first_email.get('sender', 'NO SENDER')}")
                    print(f"   Sender Name: {first_email.get('sender_name', 'NO SENDER NAME')}")
                    print(f"   Body Preview: {bool(first_email.get('body_preview'))}")
                    print(f"   Recipients TO: {len(first_email.get('to_recipients', []))}")
                    print(f"   Recipients CC: {len(first_email.get('cc_recipients', []))}")
                    print(f"   Is Read: {first_email.get('is_read')}")
                    print(f"   Size: {first_email.get('size')}")
                    print(f"   Has Attachments: {first_email.get('has_attachments')}")
                    
                    # Check COS properties
                    print(f"\n🤖 COS Properties:")
                    print(f"   Project ID: {first_email.get('project_id')}")
                    print(f"   Confidence: {first_email.get('confidence')}")
                    print(f"   Analysis: {first_email.get('analysis')}")
                    
                    # Show full JSON for debugging
                    print(f"\n📄 Full Email JSON:")
                    print(json.dumps(first_email, indent=2, default=str))
                else:
                    print("❌ No emails in response")
            else:
                print(f"❌ Unexpected response: {response_data}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_data())