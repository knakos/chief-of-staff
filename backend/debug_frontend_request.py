"""
Test to simulate exact frontend WebSocket request and see raw response.
"""
import asyncio
import websockets
import json

async def test_frontend_request():
    print("Testing EXACT Frontend WebSocket Request\n")
    
    try:
        uri = "ws://127.0.0.1:8787/ws"
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket")
            
            # Send the EXACT request that frontend sends
            request = {"event": "email:get_recent", "data": {"limit": 1}}
            await websocket.send(json.dumps(request))
            print(f"Sent request: {json.dumps(request)}")
            
            # Get response
            response = await websocket.recv()
            response_data = json.loads(response)
            
            print(f"\nResponse event: {response_data.get('event')}")
            print(f"Response keys: {list(response_data.keys())}")
            
            if response_data.get('event') == 'email:recent_list':
                data = response_data.get('data', {})
                print(f"Data keys: {list(data.keys())}")
                
                emails = data.get('emails', [])
                print(f"Number of emails: {len(emails)}")
                
                if emails:
                    first_email = emails[0]
                    print(f"\nFirst email keys: {list(first_email.keys())}")
                    print(f"Subject: {first_email.get('subject', 'No Subject')}")
                    
                    # Check ALL body-related fields
                    body_content = first_email.get('body_content', '')
                    body_preview = first_email.get('body_preview', '') 
                    body = first_email.get('body', '')
                    content = first_email.get('content', '')
                    text_content = first_email.get('text_content', '')
                    preview = first_email.get('preview', '')
                    
                    print(f"\nBODY FIELD ANALYSIS:")
                    print(f"  body_content: {len(body_content)} chars - Type: {type(body_content)}")
                    print(f"  body_preview: {len(body_preview)} chars - Type: {type(body_preview)}")
                    print(f"  body: {len(body)} chars - Type: {type(body)}")
                    print(f"  content: {len(content)} chars - Type: {type(content)}")
                    print(f"  text_content: {len(text_content)} chars - Type: {type(text_content)}")
                    print(f"  preview: {len(preview)} chars - Type: {type(preview)}")
                    
                    # Show actual content of non-empty fields
                    if body_content:
                        print(f"\nbody_content (first 200 chars):")
                        print(f"'{body_content[:200]}'")
                    if body_preview:
                        print(f"\nbody_preview (first 200 chars):")
                        print(f"'{body_preview[:200]}'")
                    if body:
                        print(f"\nbody (first 200 chars):")
                        print(f"'{body[:200]}'")
                    if preview:
                        print(f"\npreview (first 200 chars):")
                        print(f"'{preview[:200]}'")
                        
                    # Show which field would be used by frontend logic
                    final_content = body_content or body or content or text_content or preview or ""
                    print(f"\nFINAL CONTENT SELECTION:")
                    print(f"Selected field: {'body_content' if body_content else 'body' if body else 'content' if content else 'text_content' if text_content else 'preview' if preview else 'NONE'}")
                    print(f"Final content length: {len(final_content)} chars")
                    print(f"Final content (first 200 chars): '{final_content[:200]}'")
                    
            else:
                print(f"Unexpected response: {response_data}")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_frontend_request())