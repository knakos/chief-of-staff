"""
OAuth2 authentication handler for Microsoft Graph API.
Manages token acquisition, refresh, and storage.
"""
import os
import logging
from typing import Dict, Optional
import aiohttp
import asyncio
from datetime import datetime, timedelta
import json
import secrets
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

class OutlookAuthManager:
    """Handles OAuth2 authentication flow for Microsoft Graph"""
    
    def __init__(self):
        # Always load fresh environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET") 
        self.tenant_id = os.getenv("MICROSOFT_TENANT_ID", "common")
        self.redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8787/auth/callback")
        
        # Log environment variable status (without exposing secrets)
        logger.info(f"OutlookAuthManager initialized:")
        logger.info(f"  CLIENT_ID: {'SET' if self.client_id else 'NOT SET'} (value: {self.client_id[:10] if self.client_id else 'None'}...)")
        logger.info(f"  CLIENT_SECRET: {'SET' if self.client_secret else 'NOT SET'} (length: {len(self.client_secret) if self.client_secret else 0})")
        logger.info(f"  TENANT_ID: {self.tenant_id}")
        logger.info(f"  REDIRECT_URI: {self.redirect_uri}")
        
        # Check if all required variables are set
        if not self.client_id:
            logger.error("MICROSOFT_CLIENT_ID environment variable is not set!")
        if not self.client_secret:
            logger.error("MICROSOFT_CLIENT_SECRET environment variable is not set!")
        
        # Required scopes for email operations
        self.scopes = [
            "https://graph.microsoft.com/Mail.ReadWrite",
            "https://graph.microsoft.com/Mail.Send", 
            "https://graph.microsoft.com/MailboxSettings.ReadWrite",
            "offline_access"  # For refresh tokens
        ]
        
        self.auth_base_url = f"https://login.microsoftonline.com/{self.tenant_id}"
        
        # In-memory token storage (replace with database in production)
        # Use class-level storage to persist across instances
        if not hasattr(OutlookAuthManager, '_shared_tokens'):
            OutlookAuthManager._shared_tokens = {}
        self._tokens = OutlookAuthManager._shared_tokens
        
    def get_authorization_url(self, user_id: str = "default") -> tuple[str, str]:
        """Generate OAuth2 authorization URL and state"""
        # Force reload environment variables if missing
        if not self.client_id:
            logger.warning("client_id is None, force reloading environment variables")
            from dotenv import load_dotenv
            load_dotenv(override=True)  # Force reload
            self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
            self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
            logger.info(f"Force re-read CLIENT_ID: {'SET' if self.client_id else 'STILL NOT SET'} (value: {self.client_id[:10] if self.client_id else 'None'}...)")
            
            # If still None, raise an error with clear message
            if not self.client_id:
                raise ValueError("MICROSOFT_CLIENT_ID environment variable is not set. Please check your .env file.")
        
        state = secrets.token_urlsafe(32)
        
        # Store state for verification
        self._tokens[user_id] = {"state": state}
        
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
            "response_mode": "query",
            "prompt": "login"  # Force fresh login
        }
        
        auth_url = f"{self.auth_base_url}/oauth2/v2.0/authorize?" + urlencode(params)
        logger.info(f"Generated authorization URL with client_id: {self.client_id}")
        return auth_url, state
    
    async def exchange_code_for_token(self, authorization_code: str, state: str, 
                                     user_id: str = "default") -> Dict:
        """Exchange authorization code for access token"""
        # Verify state
        stored_state = self._tokens.get(user_id, {}).get("state")
        if not stored_state or stored_state != state:
            raise Exception("Invalid state parameter - possible CSRF attack")
        
        token_url = f"{self.auth_base_url}/oauth2/v2.0/token"
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Token exchange failed: {error_text}")
                    raise Exception(f"Token exchange failed: {response.status}")
                
                token_data = await response.json()
        
        # Store tokens with expiry
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        self._tokens[user_id] = {
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": expires_at,
            "token_type": token_data.get("token_type", "Bearer")
        }
        
        logger.info(f"Successfully acquired tokens for user {user_id}")
        return token_data
    
    async def get_valid_access_token(self, user_id: str = "default") -> str:
        """Get a valid access token, refreshing if necessary"""
        token_info = self._tokens.get(user_id)
        
        if not token_info:
            raise Exception("No tokens found - user needs to authenticate")
        
        # Check if token is expired (with 5 minute buffer)
        if "expires_at" in token_info and datetime.utcnow() + timedelta(minutes=5) > token_info["expires_at"]:
            logger.info("Access token expired, refreshing...")
            await self._refresh_access_token(user_id)
        
        return self._tokens[user_id]["access_token"]
    
    async def _refresh_access_token(self, user_id: str) -> Dict:
        """Refresh an expired access token"""
        token_info = self._tokens.get(user_id)
        
        if not token_info or not token_info.get("refresh_token"):
            raise Exception("No refresh token available - user needs to re-authenticate")
        
        token_url = f"{self.auth_base_url}/oauth2/v2.0/token"
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": token_info["refresh_token"],
            "grant_type": "refresh_token"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Token refresh failed: {error_text}")
                    # Clear invalid tokens
                    self._tokens.pop(user_id, None)
                    raise Exception(f"Token refresh failed: {response.status}")
                
                token_data = await response.json()
        
        # Update stored tokens
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        self._tokens[user_id].update({
            "access_token": token_data["access_token"],
            "expires_at": expires_at
        })
        
        # Update refresh token if provided
        if "refresh_token" in token_data:
            self._tokens[user_id]["refresh_token"] = token_data["refresh_token"]
        
        logger.info(f"Successfully refreshed tokens for user {user_id}")
        return token_data
    
    def is_authenticated(self, user_id: str = "default") -> bool:
        """Check if user has valid authentication"""
        token_info = self._tokens.get(user_id)
        return token_info is not None and "access_token" in token_info
    
    def revoke_tokens(self, user_id: str = "default"):
        """Revoke stored tokens for a user"""
        self._tokens.pop(user_id, None)
        logger.info(f"Revoked tokens for user {user_id}")
    
    def get_token_info(self, user_id: str = "default") -> Optional[Dict]:
        """Get token information (excluding sensitive data)"""
        token_info = self._tokens.get(user_id)
        if not token_info:
            return None
        
        return {
            "expires_at": token_info.get("expires_at"),
            "token_type": token_info.get("token_type", "Bearer"),
            "has_refresh_token": "refresh_token" in token_info
        }