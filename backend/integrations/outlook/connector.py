"""
Microsoft Graph API Connector for Outlook integration.
Handles all direct API communication with Microsoft Graph.
"""
import os
import logging
from typing import Dict, List, Optional, Any
import aiohttp
import asyncio
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class GraphAPIConnector:
    """Pure Microsoft Graph API client - no business logic"""
    
    def __init__(self):
        self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET") 
        self.tenant_id = os.getenv("MICROSOFT_TENANT_ID", "common")
        
        self.graph_base_url = "https://graph.microsoft.com/v1.0"
        self.auth_base_url = f"https://login.microsoftonline.com/{self.tenant_id}"
        
        # Session for connection pooling
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with connection pooling"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def make_graph_request(self, endpoint: str, access_token: str, 
                                method: str = "GET", data: Dict = None) -> Dict[str, Any]:
        """Make authenticated request to Microsoft Graph API"""
        session = await self._get_session()
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.graph_base_url}{endpoint}"
        
        try:
            if method == "GET":
                async with session.get(url, headers=headers) as response:
                    return await self._handle_response(response)
            elif method == "POST":
                async with session.post(url, headers=headers, json=data) as response:
                    return await self._handle_response(response)
            elif method == "PATCH":
                async with session.patch(url, headers=headers, json=data) as response:
                    return await self._handle_response(response)
            elif method == "DELETE":
                async with session.delete(url, headers=headers) as response:
                    return await self._handle_response(response)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
        except aiohttp.ClientError as e:
            logger.error(f"Graph API request failed: {e}")
            raise Exception(f"Graph API request failed: {str(e)}")
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Handle Graph API response with error checking"""
        try:
            response_data = await response.json()
        except:
            response_data = {"text": await response.text()}
        
        if response.status >= 400:
            error_msg = response_data.get("error", {}).get("message", "Unknown error")
            logger.error(f"Graph API error {response.status}: {error_msg}")
            raise Exception(f"Graph API error {response.status}: {error_msg}")
        
        return response_data
    
    # Email-specific API methods
    async def get_messages(self, access_token: str, folder_id: str = None, 
                          filter_query: str = None, select: str = None, 
                          top: int = 50) -> List[Dict]:
        """Get messages from a specific folder or inbox"""
        endpoint = "/me/messages"
        if folder_id:
            endpoint = f"/me/mailFolders/{folder_id}/messages"
        
        params = []
        if filter_query:
            params.append(f"$filter={filter_query}")
        if select:
            params.append(f"$select={select}")
        if top:
            params.append(f"$top={top}")
        
        if params:
            endpoint += "?" + "&".join(params)
        
        response = await self.make_graph_request(endpoint, access_token)
        return response.get("value", [])
    
    async def get_message(self, access_token: str, message_id: str) -> Dict:
        """Get a specific message by ID"""
        endpoint = f"/me/messages/{message_id}"
        return await self.make_graph_request(endpoint, access_token)
    
    async def get_folders(self, access_token: str) -> List[Dict]:
        """Get all mail folders"""
        endpoint = "/me/mailFolders"
        response = await self.make_graph_request(endpoint, access_token)
        return response.get("value", [])
    
    async def create_folder(self, access_token: str, display_name: str, 
                           parent_folder_id: str = None) -> Dict:
        """Create a new mail folder"""
        endpoint = "/me/mailFolders"
        if parent_folder_id:
            endpoint = f"/me/mailFolders/{parent_folder_id}/childFolders"
        
        data = {"displayName": display_name}
        return await self.make_graph_request(endpoint, access_token, "POST", data)
    
    async def move_message(self, access_token: str, message_id: str, 
                          destination_folder_id: str) -> Dict:
        """Move a message to a different folder"""
        endpoint = f"/me/messages/{message_id}/move"
        data = {"destinationId": destination_folder_id}
        return await self.make_graph_request(endpoint, access_token, "POST", data)
    
    async def update_message(self, access_token: str, message_id: str, 
                           updates: Dict) -> Dict:
        """Update message properties"""
        endpoint = f"/me/messages/{message_id}"
        return await self.make_graph_request(endpoint, access_token, "PATCH", updates)
    
    async def get_delta_messages(self, access_token: str, delta_link: str = None) -> Dict:
        """Get message changes using delta query"""
        if delta_link:
            # Use existing delta link
            url = delta_link
            session = await self._get_session()
            headers = {"Authorization": f"Bearer {access_token}"}
            async with session.get(url, headers=headers) as response:
                return await self._handle_response(response)
        else:
            # Initial delta query
            endpoint = "/me/messages/delta"
            return await self.make_graph_request(endpoint, access_token)
    
    async def send_message(self, access_token: str, message_data: Dict) -> Dict:
        """Send an email message"""
        endpoint = "/me/sendMail"
        return await self.make_graph_request(endpoint, access_token, "POST", message_data)
    
    async def create_reply(self, access_token: str, message_id: str, 
                          reply_data: Dict) -> Dict:
        """Create a reply to a message"""
        endpoint = f"/me/messages/{message_id}/reply"
        return await self.make_graph_request(endpoint, access_token, "POST", reply_data)