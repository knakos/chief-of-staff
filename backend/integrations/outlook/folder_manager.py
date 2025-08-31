"""
GTD (Getting Things Done) folder management for Outlook.
Implements the folder scheme: Inbox with COS_Actions, COS_Assigned, COS_ReadLater, COS_Reference, COS_Archive
"""
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from .connector import GraphAPIConnector
from .auth import OutlookAuthManager

logger = logging.getLogger(__name__)

class GTDFolderManager:
    """Manages GTD-style folder structure in Outlook"""
    
    # Standard GTD folder structure with COS prefix
    GTD_FOLDERS = {
        "COS_Actions": "Emails requiring immediate action",
        "COS_Assigned": "Emails assigned to others or waiting for response", 
        "COS_ReadLater": "Emails to read when you have more time",
        "COS_Reference": "Emails to keep for reference",
        "COS_Archive": "Archived emails (catch-all bucket)"
    }
    
    # COS-specific folders for categorization (removed - using extended properties for linking instead)
    COS_FOLDERS = {}
    
    def __init__(self, connector: GraphAPIConnector, auth_manager: OutlookAuthManager):
        self.connector = connector
        self.auth_manager = auth_manager
        
        # Cache folder IDs to avoid repeated API calls
        self._folder_cache: Dict[str, str] = {}
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl = 300  # 5 minutes
    
    async def setup_gtd_folders(self, user_id: str = "default") -> Dict[str, str]:
        """Set up the complete GTD folder structure under Inbox with COS_ prefix"""
        logger.info("Setting up GTD folder structure with COS_ prefix under Inbox")
        
        try:
            access_token = await self.auth_manager.get_valid_access_token(user_id)
            
            # Get existing folders
            existing_folders = await self._get_folder_mapping(access_token)
            folder_ids = {}
            
            # Get Inbox folder ID first
            inbox_id = await self._get_inbox_folder_id(access_token)
            if not inbox_id:
                logger.error("Could not find Inbox folder")
                raise Exception("Inbox folder not found")
            
            # Create GTD folders under Inbox with COS_ prefix
            for folder_name, description in self.GTD_FOLDERS.items():
                if folder_name in existing_folders:
                    folder_ids[folder_name] = existing_folders[folder_name]
                    logger.info(f"Found existing folder: {folder_name}")
                else:
                    # Create folder under Inbox
                    folder_data = await self.connector.create_folder(
                        access_token, folder_name, inbox_id
                    )
                    folder_ids[folder_name] = folder_data["id"]
                    logger.info(f"Created folder under Inbox: {folder_name}")
            
            # COS folders removed - using extended properties for project/task linking instead
            
            # Update cache
            self._folder_cache.update(folder_ids)
            import time
            self._cache_timestamp = time.time()
            
            return folder_ids
            
        except Exception as e:
            logger.error(f"Failed to setup GTD folders: {e}")
            raise
    
    async def get_folder_id(self, folder_name: str, user_id: str = "default") -> Optional[str]:
        """Get folder ID by name, with caching"""
        import time
        
        # Check cache
        if (self._cache_timestamp and 
            time.time() - self._cache_timestamp < self._cache_ttl and
            folder_name in self._folder_cache):
            return self._folder_cache[folder_name]
        
        # Refresh cache
        try:
            access_token = await self.auth_manager.get_valid_access_token(user_id)
            folder_mapping = await self._get_folder_mapping(access_token)
            
            self._folder_cache.update(folder_mapping)
            self._cache_timestamp = time.time()
            
            return folder_mapping.get(folder_name)
            
        except Exception as e:
            logger.error(f"Failed to get folder ID for {folder_name}: {e}")
            return None
    
    async def _get_folder_mapping(self, access_token: str) -> Dict[str, str]:
        """Get mapping of folder names to IDs"""
        folders = await self.connector.get_folders(access_token)
        folder_mapping = {}
        
        # Process top-level folders
        for folder in folders:
            folder_mapping[folder["displayName"]] = folder["id"]
            
            # Check for COS subfolders
            if folder["displayName"] == "COS" and folder.get("childFolderCount", 0) > 0:
                await self._process_subfolders(access_token, folder["id"], "COS", folder_mapping)
        
        return folder_mapping
    
    async def _process_subfolders(self, access_token: str, parent_id: str, 
                                 parent_name: str, folder_mapping: Dict[str, str]):
        """Process subfolders recursively"""
        try:
            endpoint = f"/me/mailFolders/{parent_id}/childFolders"
            response = await self.connector.make_graph_request(endpoint, access_token)
            subfolders = response.get("value", [])
            
            for subfolder in subfolders:
                full_name = f"{parent_name}/{subfolder['displayName']}"
                folder_mapping[full_name] = subfolder["id"]
                
        except Exception as e:
            logger.error(f"Failed to process subfolders for {parent_name}: {e}")
    
    async def _get_inbox_folder_id(self, access_token: str) -> Optional[str]:
        """Get the Inbox folder ID"""
        try:
            # Get well-known folder for Inbox
            endpoint = "/me/mailFolders/inbox"
            response = await self.connector.make_graph_request(endpoint, access_token)
            return response.get("id")
        except Exception as e:
            logger.error(f"Failed to get Inbox folder ID: {e}")
            return None
    
    async def move_email_to_gtd_folder(self, message_id: str, gtd_category: str, 
                                      user_id: str = "default") -> bool:
        """Move email to appropriate GTD folder based on category"""
        try:
            # Map categories to folders (projects/tasks linked via extended properties instead)
            category_folder_map = {
                "action": "COS_Actions",
                "actions": "COS_Actions",
                "assigned": "COS_Assigned",
                "waiting": "COS_Assigned", 
                "read_later": "COS_ReadLater",
                "reference": "COS_Reference",
                "archive": "COS_Archive"
            }
            
            folder_name = category_folder_map.get(gtd_category)
            if not folder_name:
                logger.warning(f"Unknown GTD category: {gtd_category}")
                return False
            
            folder_id = await self.get_folder_id(folder_name, user_id)
            if not folder_id:
                logger.error(f"Folder not found: {folder_name}")
                return False
            
            access_token = await self.auth_manager.get_valid_access_token(user_id)
            await self.connector.move_message(access_token, message_id, folder_id)
            
            logger.info(f"Moved email {message_id} to {folder_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to move email to GTD folder: {e}")
            return False
    
    async def get_folder_contents(self, folder_name: str, user_id: str = "default", 
                                 limit: int = 50) -> List[Dict]:
        """Get emails from a specific GTD folder"""
        try:
            folder_id = await self.get_folder_id(folder_name, user_id)
            if not folder_id:
                return []
            
            access_token = await self.auth_manager.get_valid_access_token(user_id)
            messages = await self.connector.get_messages(
                access_token, folder_id=folder_id, top=limit
            )
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get folder contents for {folder_name}: {e}")
            return []
    
    async def get_folder_statistics(self, user_id: str = "default") -> Dict[str, int]:
        """Get count of emails in each GTD folder"""
        stats = {}
        
        all_folders = {**self.GTD_FOLDERS, **self.COS_FOLDERS}
        
        for folder_name in all_folders.keys():
            try:
                folder_id = await self.get_folder_id(folder_name, user_id)
                if folder_id:
                    access_token = await self.auth_manager.get_valid_access_token(user_id)
                    
                    # Get folder info which includes message count
                    endpoint = f"/me/mailFolders/{folder_id}"
                    folder_info = await self.connector.make_graph_request(endpoint, access_token)
                    stats[folder_name] = folder_info.get("totalItemCount", 0)
                else:
                    stats[folder_name] = 0
                    
            except Exception as e:
                logger.error(f"Failed to get stats for {folder_name}: {e}")
                stats[folder_name] = 0
        
        return stats
    
    def get_gtd_recommendation(self, email_analysis: Dict[str, Any]) -> str:
        """Get GTD folder recommendation based on email analysis"""
        # This would integrate with the AI analysis from EmailTriageAgent
        
        # Check for action items
        if email_analysis.get("requires_action", False):
            if email_analysis.get("waiting_for_response", False):
                return "assigned"
            else:
                return "actions"
        
        # Project/task associations handled via extended properties, not folders
        # Emails will be categorized into GTD folders and linked via metadata
        
        # Check for reference material
        if email_analysis.get("is_reference", False):
            return "reference"
        
        # Default for emails that just need to be read
        return "read_later"