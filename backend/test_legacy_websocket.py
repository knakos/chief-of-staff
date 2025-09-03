"""
Test WebSocket email data with legacy-only integration.
"""
import asyncio
import websockets
import json

async def test_websocket_data():
    print("Testing WebSocket Email Data with Legacy Integration\n")
    
    try:
        # Connect to WebSocket
        uri = "ws://127.0.0.1:8787/ws"
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket")
            
            # Send email request
            request = {
                "event": "email:get_recent",
                "data": {"limit": 2}
            }
            
            await websocket.send(json.dumps(request))
            print("Sent email request")
            
            # Wait for response
            response = await websocket.recv()
            response_data = json.loads(response)
            
            if response_data.get('event') == 'email:recent_list':
                emails = response_data.get('data', {}).get('emails', [])
                print(f"Received {len(emails)} emails\n")
                
                if emails:
                    # Show first email properties
                    first_email = emails[0]
                    print("First Email Properties:")
                    print(f"   Subject: {first_email.get('subject', 'NO SUBJECT')}")
                    print(f"   Sender: {first_email.get('sender', 'NO SENDER')}")
                    print(f"   Analysis: {first_email.get('analysis')}")
                    
                    # Check analysis data specifically
                    analysis = first_email.get('analysis')
                    if analysis:
                        print(f"\nCOS Analysis Properties:")
                        print(f"   Priority: {analysis.get('priority')}")
                        print(f"   Tone: {analysis.get('tone')}")
                        print(f"   Urgency: {analysis.get('urgency')}")
                        print(f"   Summary: {analysis.get('summary', '')[:50] if analysis.get('summary') else 'None'}")
                        print(f"   Confidence: {analysis.get('confidence')}")
                        print("\nSUCCESS: Legacy method correctly loaded COS analysis!")
                    else:
                        print("\nWARNING: Analysis is None - legacy method may not be working")
                        
                else:
                    print("No emails in response")
            else:
                print(f"Unexpected response: {response_data}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_data())