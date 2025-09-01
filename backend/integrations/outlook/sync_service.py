"""
Email synchronization service using Microsoft Graph delta queries.
Efficiently syncs email changes and maintains local state.
"""
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime, timedelta
import asyncio
from sqlalchemy.orm import Session

from .connector import GraphAPIConnector
from .auth import OutlookAuthManager
from models import Email

logger = logging.getLogger(__name__)

class EmailSyncService:
    """Handles efficient email synchronization using delta queries"""
    
    def __init__(self, connector: GraphAPIConnector, auth_manager: OutlookAuthManager):
        self.connector = connector
        self.auth_manager = auth_manager
        
        # Store delta links for incremental sync
        self._delta_links: Dict[str, str] = {}
        
        # Email field selection for efficiency
        self.email_select_fields = [
            "id", "subject", "bodyPreview", "body", "from", "toRecipients", 
            "ccRecipients", "receivedDateTime", "sentDateTime", "importance",
            "isRead", "hasAttachments", "parentFolderId", "conversationId",
            "internetMessageId", "webLink", "flag", "categories"
        ]
    
    async def initial_sync(self, db: Session, user_id: str = "default", 
                          days_back: int = 30) -> List[Dict]:
        """Perform initial email sync for the last N days"""
        logger.info(f"Starting initial email sync for {days_back} days")
        
        try:
            access_token = await self.auth_manager.get_valid_access_token(user_id)
            
            # Calculate date filter
            since_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"
            filter_query = f"receivedDateTime ge {since_date}"
            select_fields = ",".join(self.email_select_fields)
            
            # Get initial batch of messages
            messages = await self.connector.get_messages(
                access_token=access_token,
                filter_query=filter_query,
                select=select_fields,
                top=100
            )
            
            # Process and store emails
            synced_emails = []
            for message in messages:
                email_data = await self._process_message(message, db)
                if email_data:
                    synced_emails.append(email_data)
            
            # Initialize delta tracking
            await self._initialize_delta_tracking(access_token, user_id)
            
            logger.info(f"Initial sync completed: {len(synced_emails)} emails")
            return synced_emails
            
        except Exception as e:
            logger.error(f"Initial sync failed: {e}")
            raise
    
    async def delta_sync(self, db: Session, user_id: str = "default") -> List[Dict]:
        """Perform incremental sync using delta queries"""
        logger.info("Starting delta email sync")
        
        try:
            access_token = await self.auth_manager.get_valid_access_token(user_id)
            delta_link = self._delta_links.get(user_id)
            
            if not delta_link:
                logger.warning("No delta link found, performing initial sync")
                return await self.initial_sync(db, user_id)
            
            # Get changes since last sync
            delta_response = await self.connector.get_delta_messages(access_token, delta_link)
            
            changes = delta_response.get("value", [])
            synced_emails = []
            
            for change in changes:
                email_data = await self._process_message(change, db, is_delta=True)
                if email_data:
                    synced_emails.append(email_data)
            
            # Update delta link for next sync
            next_link = delta_response.get("@odata.nextLink")
            delta_link = delta_response.get("@odata.deltaLink")
            
            if delta_link:
                self._delta_links[user_id] = delta_link
            elif next_link:
                # More pages available, continue syncing
                await self._process_additional_pages(access_token, next_link, db, synced_emails)
            
            logger.info(f"Delta sync completed: {len(synced_emails)} changes")
            return synced_emails
            
        except Exception as e:
            logger.error(f"Delta sync failed: {e}")
            # Clear delta link to force full sync next time
            self._delta_links.pop(user_id, None)
            raise
    
    async def _process_additional_pages(self, access_token: str, next_link: str, 
                                       db: Session, synced_emails: List[Dict]):
        """Process additional pages of delta results"""
        while next_link:
            session = await self.connector._get_session()
            headers = {"Authorization": f"Bearer {access_token}"}
            
            async with session.get(next_link, headers=headers) as response:
                page_data = await self.connector._handle_response(response)
            
            changes = page_data.get("value", [])
            for change in changes:
                email_data = await self._process_message(change, db, is_delta=True)
                if email_data:
                    synced_emails.append(email_data)
            
            next_link = page_data.get("@odata.nextLink")
            delta_link = page_data.get("@odata.deltaLink")
            
            if delta_link:
                # Store final delta link
                self._delta_links["default"] = delta_link
                break
    
    async def _initialize_delta_tracking(self, access_token: str, user_id: str):
        """Initialize delta tracking by getting the delta link"""
        try:
            delta_response = await self.connector.get_delta_messages(access_token)
            
            # Process all pages to get to the final delta link
            next_link = delta_response.get("@odata.nextLink")
            delta_link = delta_response.get("@odata.deltaLink")
            
            while next_link and not delta_link:
                session = await self.connector._get_session()
                headers = {"Authorization": f"Bearer {access_token}"}
                
                async with session.get(next_link, headers=headers) as response:
                    page_data = await self.connector._handle_response(response)
                
                next_link = page_data.get("@odata.nextLink")
                delta_link = page_data.get("@odata.deltaLink")
            
            if delta_link:
                self._delta_links[user_id] = delta_link
                logger.info("Delta tracking initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize delta tracking: {e}")
    
    async def _process_message(self, message: Dict, db: Session, is_delta: bool = False) -> Optional[Dict]:
        """Process a single message and update database"""
        try:
            message_id = message.get("id")
            if not message_id:
                return None
            
            # Check if this is a deletion (delta sync)
            if is_delta and "@removed" in message:
                await self._handle_message_deletion(message_id, db)
                return {"action": "deleted", "id": message_id}
            
            # Check if email already exists
            existing_email = db.query(Email).filter(Email.outlook_id == message_id).first()
            
            # Extract email data
            email_data = self._extract_email_data(message)
            
            if existing_email:
                # Update existing email
                for key, value in email_data.items():
                    setattr(existing_email, key, value)
                existing_email.last_synced_at = datetime.utcnow()
                action = "updated"
            else:
                # Create new email
                email_data.update({
                    "outlook_id": message_id,
                    "created_at": datetime.utcnow(),
                    "last_synced_at": datetime.utcnow()
                })
                new_email = Email(**email_data)
                db.add(new_email)
                action = "created"
            
            db.commit()
            
            return {
                "action": action,
                "id": message_id,
                "subject": email_data.get("subject"),
                "from": email_data.get("sender")
            }
            
        except Exception as e:
            logger.error(f"Failed to process message {message.get('id')}: {e}")
            db.rollback()
            return None
    
    def _extract_email_data(self, message: Dict) -> Dict[str, Any]:
        """Extract email data from Graph API message"""
        from_field = message.get("from", {}).get("emailAddress", {})
        
        return {
            "subject": message.get("subject", ""),
            "sender": from_field.get("address", ""),
            "sender_name": from_field.get("name", ""),
            "body_preview": message.get("bodyPreview", ""),
            "body_content": message.get("body", {}).get("content", ""),
            "body_content_type": message.get("body", {}).get("contentType", "text"),
            "received_at": self._parse_datetime(message.get("receivedDateTime")),
            "sent_at": self._parse_datetime(message.get("sentDateTime")),
            "is_read": message.get("isRead", False),
            "importance": message.get("importance", "normal"),
            "has_attachments": message.get("hasAttachments", False),
            "conversation_id": message.get("conversationId"),
            "internet_message_id": message.get("internetMessageId"),
            "web_link": message.get("webLink"),
            "categories": message.get("categories", []),
            "folder_id": message.get("parentFolderId")
        }
    
    def _parse_datetime(self, dt_string: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string"""
        if not dt_string:
            return None
        try:
            # Remove 'Z' and parse
            if dt_string.endswith('Z'):
                dt_string = dt_string[:-1]
            return datetime.fromisoformat(dt_string)
        except:
            return None
    
    async def _handle_message_deletion(self, message_id: str, db: Session):
        """Handle message deletion from delta sync"""
        try:
            email = db.query(Email).filter(Email.outlook_id == message_id).first()
            if email:
                db.delete(email)
                db.commit()
                logger.info(f"Deleted email {message_id}")
        except Exception as e:
            logger.error(f"Failed to delete email {message_id}: {e}")
            db.rollback()
    
    async def sync_specific_message(self, db: Session, message_id: str, 
                                   user_id: str = "default") -> Optional[Dict]:
        """Sync a specific message by ID"""
        try:
            access_token = await self.auth_manager.get_valid_access_token(user_id)
            message = await self.connector.get_message(access_token, message_id)
            return await self._process_message(message, db)
        except Exception as e:
            logger.error(f"Failed to sync specific message {message_id}: {e}")
            return None