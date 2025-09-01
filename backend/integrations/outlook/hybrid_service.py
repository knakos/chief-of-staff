"""
Hybrid Outlook service that tries COM first, then falls back to Graph API
"""
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from .com_connector import OutlookCOMConnector, COM_AVAILABLE
from .auth import OutlookAuthManager
# EmailSyncService removed - no longer needed without database email storage
from .folder_manager import GTDFolderManager
from .connector import GraphAPIConnector
from .property_sync import OutlookPropertySync

logger = logging.getLogger(__name__)

class HybridOutlookService:
    """Unified Outlook service with COM and Graph API support"""
    
    def __init__(self):
        # COM components
        self.com_connector = OutlookCOMConnector() if COM_AVAILABLE else None
        
        # Graph API components  
        self.graph_connector = GraphAPIConnector()
        self.auth_manager = OutlookAuthManager()
        # sync_service removed - no longer needed without database email storage
        self.folder_manager = GTDFolderManager(self.graph_connector, self.auth_manager)
        self.property_sync = OutlookPropertySync()
        
        self._connection_method = None  # "com" or "graph"
    
    async def connect(self) -> Dict[str, Any]:
        """Try to connect via COM first, then Graph API, and ensure COS folders exist"""
        connection_result = None
        
        # Try COM first (if available and Outlook is running)
        if COM_AVAILABLE and self.com_connector:
            if self.com_connector.connect():
                self._connection_method = "com"
                account_info = self.com_connector.get_account_info()
                logger.info("Connected via COM to local Outlook")
                connection_result = {
                    "method": "com",
                    "connected": True,
                    "account_info": account_info,
                    "message": "Connected to local Outlook application"
                }
        
        # Fall back to Graph API
        if not connection_result and self.auth_manager.is_authenticated():
            self._connection_method = "graph"
            try:
                access_token = await self.auth_manager.get_valid_access_token()
                logger.info("Connected via Graph API")
                connection_result = {
                    "method": "graph", 
                    "connected": True,
                    "account_info": {"method": "Microsoft Graph API"},
                    "message": "Connected via Microsoft Graph API"
                }
            except Exception as e:
                logger.error(f"Graph API connection failed: {e}")
        
        # If connected, ensure COS folders exist
        if connection_result and connection_result["connected"]:
            await self._ensure_cos_folders_exist()
            connection_result["folders_checked"] = True
        
        # No connection available
        if not connection_result:
            connection_result = {
                "method": None,
                "connected": False,
                "account_info": {},
                "message": self._get_connection_help()
            }
        
        return connection_result
    
    def _get_connection_help(self) -> str:
        """Get help message for connection options"""
        if not COM_AVAILABLE:
            return "Install pywin32 for COM support: pip install pywin32. For Graph API, use /outlook status to authenticate."
        elif not self.com_connector.is_connected():
            return "Start Outlook application for COM support, or use /outlook status for Graph API authentication."
        else:
            return "Use /outlook status to authenticate with Microsoft Graph API."
    
    async def _ensure_cos_folders_exist(self) -> None:
        """Check if COS folders exist and create them if missing"""
        try:
            if self._connection_method == "graph":
                # Use Graph API folder manager
                logger.info("Checking COS folder structure via Graph API...")
                folder_ids = await self.folder_manager.setup_gtd_folders()
                logger.info(f"COS folders verified/created: {list(folder_ids.keys())}")
            elif self._connection_method == "com" and self.com_connector:
                # Use COM connector
                logger.info("Checking COS folder structure via COM...")
                results = self.com_connector.setup_gtd_folders()
                created_folders = [name for name, success in results.items() if success]
                logger.info(f"COS folders verified/created: {created_folders}")
            else:
                logger.warning("No valid connection method for folder setup")
        except Exception as e:
            logger.error(f"Failed to ensure COS folders exist: {e}")
            # Don't fail the connection if folder setup fails
    
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
    
    # sync_emails method removed - emails are accessed directly from Outlook, not stored in database
    
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
    
    async def sync_email_analysis_to_outlook(self, email_schema) -> bool:
        """
        Sync COS email analysis data back to Outlook as custom properties
        
        Args:
            email_schema: EmailSchema with analysis data to sync
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            from schemas.email_schema import EmailSchema
            
            if not isinstance(email_schema, EmailSchema):
                logger.error("Invalid email schema provided for Outlook sync")
                return False
                
            if self._connection_method == "com" and self.com_connector:
                # Get the Outlook item
                outlook_item = self.com_connector.namespace.GetItemFromID(email_schema.id)
                if not outlook_item:
                    logger.warning(f"Could not find Outlook item for email {email_schema.id}")
                    return False
                
                # Sync COS data to Outlook properties
                self.property_sync.com_connector = self.com_connector
                success = self.property_sync.write_cos_data_to_outlook(email_schema, outlook_item)
                
                if success:
                    logger.info(f"Successfully synced COS analysis to Outlook for email: {email_schema.subject[:50]}")
                return success
                
            else:
                logger.warning("COM connection not available for property sync")
                return False
                
        except Exception as e:
            logger.error(f"Failed to sync email analysis to Outlook: {e}")
            return False
    
    async def load_email_with_cos_data(self, email_id: str):
        """
        Load an email from Outlook including any existing COS data from properties
        
        Args:
            email_id: Outlook EntryID of the email
            
        Returns:
            EmailSchema with COS data populated from Outlook properties
        """
        try:
            if self._connection_method == "com" and self.com_connector:
                # Get the Outlook item
                outlook_item = self.com_connector.namespace.GetItemFromID(email_id)
                if not outlook_item:
                    logger.warning(f"Could not find Outlook item for email {email_id}")
                    return None
                
                # Load with COS data enhancement
                from .property_sync import load_email_from_outlook_with_cos_data
                email_schema = load_email_from_outlook_with_cos_data(outlook_item, self.com_connector)
                
                logger.debug(f"Loaded email with COS data: {email_schema.subject[:50]}")
                return email_schema
                
            else:
                logger.warning("COM connection not available for loading COS data")
                return None
                
        except Exception as e:
            logger.error(f"Failed to load email with COS data: {e}")
            return None