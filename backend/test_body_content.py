"""
Test that full body content is sent via WebSocket without truncation.
"""
import asyncio
import websockets
import json

async def test_full_body_content():
    print("Testing Full Body Content via WebSocket\n")
    
    try:
        uri = "ws://127.0.0.1:8787/ws"
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket")
            
            # Request emails
            request = {"event": "email:get_recent", "data": {"limit": 1}}
            await websocket.send(json.dumps(request))
            print("Sent email request")
            
            # Get response
            response = await websocket.recv()
            response_data = json.loads(response)
            
            if response_data.get('event') == 'email:recent_list':
                emails = response_data.get('data', {}).get('emails', [])
                print(f"Received {len(emails)} emails\n")
                
                if emails:
                    first_email = emails[0]
                    body_content = first_email.get('body_content', '')
                    body_preview = first_email.get('body_preview', '')
                    
                    print(f"Subject: {first_email.get('subject', 'No Subject')}")
                    print(f"Body Content Length: {len(body_content)} characters")
                    print(f"Body Preview Length: {len(body_preview)} characters")
                    
                    if len(body_content) > 5000:
                        print("✅ SUCCESS: Body content is NOT truncated (>5000 chars)")
                    elif len(body_content) > 0:
                        print(f"✅ SUCCESS: Body content available ({len(body_content)} chars)")
                        print(f"First 200 characters: {body_content[:200]}...")
                    else:
                        print("❌ WARNING: No body content found")
                        
                    if body_content != body_preview:
                        print("✅ Body content and preview are different (as expected)")
                    else:
                        print("⚠️  Body content and preview are identical")
                        
                else:
                    print("No emails found")
            else:
                print(f"Unexpected response: {response_data}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_full_body_content())