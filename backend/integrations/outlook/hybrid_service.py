"""
Hybrid Outlook service that tries COM first, then falls back to Graph API
"""
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from .com_connector import OutlookCOMConnector, COM_AVAILABLE
from .auth import OutlookAuthManager
from .sync_service import EmailSyncService
from .folder_manager import GTDFolderManager
from .connector import GraphAPIConnector

logger = logging.getLogger(__name__)

class HybridOutlookService:
    """Unified Outlook service with COM and Graph API support"""
    
    def __init__(self):
        # COM components
        self.com_connector = OutlookCOMConnector() if COM_AVAILABLE else None
        
        # Graph API components  
        self.graph_connector = GraphAPIConnector()
        self.auth_manager = OutlookAuthManager()
        self.sync_service = EmailSyncService(self.graph_connector, self.auth_manager)
        self.folder_manager = GTDFolderManager(self.graph_connector, self.auth_manager)
        
        self._connection_method = None  # "com" or "graph"
    
    async def connect(self) -> Dict[str, Any]:
        """Try to connect via COM first, then Graph API"""
        # Try COM first (if available and Outlook is running)
        if COM_AVAILABLE and self.com_connector:
            if self.com_connector.connect():
                self._connection_method = "com"
                account_info = self.com_connector.get_account_info()
                logger.info("Connected via COM to local Outlook")
                return {
                    "method": "com",
                    "connected": True,
                    "account_info": account_info,
                    "message": "Connected to local Outlook application"
                }
        
        # Fall back to Graph API
        if self.auth_manager.is_authenticated():
            self._connection_method = "graph"
            try:
                access_token = await self.auth_manager.get_valid_access_token()
                logger.info("Connected via Graph API")
                return {
                    "method": "graph", 
                    "connected": True,
                    "account_info": {"method": "Microsoft Graph API"},
                    "message": "Connected via Microsoft Graph API"
                }
            except Exception as e:
                logger.error(f"Graph API connection failed: {e}")
        
        # No connection available
        return {
            "method": None,
            "connected": False,
            "account_info": {},
            "message": self._get_connection_help()
        }
    
    def _get_connection_help(self) -> str:
        """Get help message for connection options"""
        if not COM_AVAILABLE:
            return "Install pywin32 for COM support: pip install pywin32. For Graph API, use /outlook status to authenticate."
        elif not self.com_connector.is_connected():
            return "Start Outlook application for COM support, or use /outlook status for Graph API authentication."
        else:
            return "Use /outlook status to authenticate with Microsoft Graph API."
    
    def is_connected(self) -> bool:
        """Check if any connection method is available"""
        if self._connection_method == "com":
            return self.com_connector and self.com_connector.is_connected()
        elif self._connection_method == "graph":
            return self.auth_manager.is_authenticated()
        return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get current connection information"""
        if self._connection_method == "com" and self.com_connector:
            account_info = self.com_connector.get_account_info()
            return {
                "method": "COM",
                "status": "Connected to local Outlook",
                "accounts": account_info.get("accounts", [])
            }
        elif self._connection_method == "graph":
            token_info = self.auth_manager.get_token_info()
            return {
                "method": "Graph API",
                "status": "Connected via Microsoft Graph",
                "expires_at": token_info.get("expires_at") if token_info else None
            }
        else:
            return {
                "method": None,
                "status": "Not connected",
                "help": self._get_connection_help()
            }
    
    async def get_folders(self) -> List[Dict[str, Any]]:
        """Get folders using available connection method"""
        if self._connection_method == "com" and self.com_connector:
            return self.com_connector.get_folders()
        elif self._connection_method == "graph":
            try:
                access_token = await self.auth_manager.get_valid_access_token()
                return await self.graph_connector.get_folders(access_token)
            except Exception as e:
                logger.error(f"Graph API get_folders failed: {e}")
                return []
        else:
            return []
    
    async def get_messages(self, folder_name: str = "Inbox", limit: int = 50) -> List[Dict[str, Any]]:
        """Get messages using available connection method"""
        if self._connection_method == "com" and self.com_connector:
            return self.com_connector.get_messages(folder_name, limit)
        elif self._connection_method == "graph":
            try:
                access_token = await self.auth_manager.get_valid_access_token()
                return await self.graph_connector.get_messages(access_token, top=limit)
            except Exception as e:
                logger.error(f"Graph API get_messages failed: {e}")
                return []
        else:
            return []
    
    async def setup_gtd_folders(self) -> Dict[str, Any]:
        """Setup GTD folders using available method"""
        if self._connection_method == "com" and self.com_connector:
            results = self.com_connector.setup_gtd_folders()
            return {
                "success": any(results.values()),
                "method": "COM",
                "folders_created": results
            }
        elif self._connection_method == "graph":
            try:
                folder_ids = await self.folder_manager.setup_gtd_folders()
                return {
                    "success": True,
                    "method": "Graph API", 
                    "folders_created": folder_ids
                }
            except Exception as e:
                logger.error(f"Graph API folder setup failed: {e}")
                return {
                    "success": False,
                    "method": "Graph API",
                    "error": str(e)
                }
        else:
            return {
                "success": False,
                "method": None,
                "error": "No connection available"
            }
    
    async def sync_emails(self, db: Session) -> Dict[str, Any]:
        """Sync emails using available method"""
        if self._connection_method == "com" and self.com_connector:
            # Get messages via COM and store in database
            messages = self.com_connector.get_messages(limit=100)
            
            synced_count = 0
            for msg_data in messages:
                try:
                    # Check if email already exists
                    from models import Email
                    existing = db.query(Email).filter(
                        Email.outlook_id == msg_data["id"]
                    ).first()
                    
                    if not existing:
                        # Create new email record
                        new_email = Email(
                            outlook_id=msg_data["id"],
                            subject=msg_data["subject"],
                            sender=msg_data["sender"],
                            sender_name=msg_data["sender_name"],
                            body_content=msg_data["body_content"],
                            body_preview=msg_data["body_preview"], 
                            received_at=msg_data["received_at"],
                            sent_at=msg_data["sent_at"],
                            is_read=msg_data["is_read"],
                            importance=msg_data["importance"],
                            has_attachments=msg_data["has_attachments"]
                        )
                        db.add(new_email)
                        synced_count += 1
                
                except Exception as e:
                    logger.error(f"Failed to sync COM message: {e}")
                    continue
            
            db.commit()
            return {
                "success": True,
                "method": "COM",
                "synced_count": synced_count,
                "total_messages": len(messages)
            }
            
        elif self._connection_method == "graph":
            try:
                # Use existing Graph API sync
                result = await self.sync_service.delta_sync(db)
                return {
                    "success": True,
                    "method": "Graph API",
                    "synced_count": len(result),
                    "emails": result
                }
            except Exception as e:
                logger.error(f"Graph API sync failed: {e}")
                return {
                    "success": False,
                    "method": "Graph API",
                    "error": str(e)
                }
        else:
            return {
                "success": False,
                "method": None,
                "error": "No connection available"
            }
    
    async def move_email(self, email_id: str, folder_name: str) -> bool:
        """Move email using available method"""
        if self._connection_method == "com" and self.com_connector:
            return self.com_connector.move_message(email_id, folder_name)
        elif self._connection_method == "graph":
            # Would need folder ID for Graph API
            # This is more complex and would require folder lookup
            logger.warning("Graph API move_email not yet implemented")
            return False
        else:
            return False