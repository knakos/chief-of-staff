"""
GTD (Getting Things Done) folder management for Outlook.
Implements the folder scheme: Inbox, @Action, @Waiting, @ReadLater, @Reference, COS/Processed
"""
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from .connector import GraphAPIConnector
from .auth import OutlookAuthManager

logger = logging.getLogger(__name__)

class GTDFolderManager:
    """Manages GTD-style folder structure in Outlook"""
    
    # Standard GTD folder structure
    GTD_FOLDERS = {
        "@Action": "Emails requiring immediate action",
        "@Waiting": "Emails waiting for response from others", 
        "@ReadLater": "Emails to read when you have more time",
        "@Reference": "Emails to keep for reference",
        "COS/Processed": "Emails processed by Chief of Staff"
    }
    
    # COS-specific folders for categorization
    COS_FOLDERS = {
        "COS/Projects": "Project-related emails",
        "COS/Tasks": "Task-related emails",
        "COS/Meetings": "Meeting-related emails",
        "COS/Archive": "Archived processed emails"
    }
    
    def __init__(self, connector: GraphAPIConnector, auth_manager: OutlookAuthManager):
        self.connector = connector
        self.auth_manager = auth_manager
        
        # Cache folder IDs to avoid repeated API calls
        self._folder_cache: Dict[str, str] = {}
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl = 300  # 5 minutes
    
    async def setup_gtd_folders(self, user_id: str = "default") -> Dict[str, str]:
        """Set up the complete GTD folder structure"""
        logger.info("Setting up GTD folder structure")
        
        try:
            access_token = await self.auth_manager.get_valid_access_token(user_id)
            
            # Get existing folders
            existing_folders = await self._get_folder_mapping(access_token)
            folder_ids = {}
            
            # Create GTD folders
            for folder_name, description in self.GTD_FOLDERS.items():
                if folder_name in existing_folders:
                    folder_ids[folder_name] = existing_folders[folder_name]
                    logger.info(f"Found existing folder: {folder_name}")
                else:
                    folder_data = await self.connector.create_folder(access_token, folder_name)
                    folder_ids[folder_name] = folder_data["id"]
                    logger.info(f"Created folder: {folder_name}")
            
            # Create COS folders (with parent COS folder if needed)
            cos_parent_id = None
            if "COS" not in existing_folders:
                cos_parent = await self.connector.create_folder(access_token, "COS")
                cos_parent_id = cos_parent["id"]
                logger.info("Created parent COS folder")
            else:
                cos_parent_id = existing_folders["COS"]
            
            for folder_name, description in self.COS_FOLDERS.items():
                if folder_name in existing_folders:
                    folder_ids[folder_name] = existing_folders[folder_name]
                else:
                    # Extract subfolder name (e.g., "Projects" from "COS/Projects")
                    subfolder_name = folder_name.split("/")[1]
                    folder_data = await self.connector.create_folder(
                        access_token, subfolder_name, cos_parent_id
                    )
                    folder_ids[folder_name] = folder_data["id"]
                    logger.info(f"Created folder: {folder_name}")
            
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
    
    async def move_email_to_gtd_folder(self, message_id: str, gtd_category: str, 
                                      user_id: str = "default") -> bool:
        """Move email to appropriate GTD folder based on category"""
        try:
            # Map categories to folders
            category_folder_map = {
                "action": "@Action",
                "waiting": "@Waiting", 
                "read_later": "@ReadLater",
                "reference": "@Reference",
                "processed": "COS/Processed",
                "project": "COS/Projects",
                "task": "COS/Tasks",
                "meeting": "COS/Meetings",
                "archive": "COS/Archive"
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
                return "waiting"
            else:
                return "action"
        
        # Check for meeting-related content
        if email_analysis.get("is_meeting_related", False):
            return "meeting"
        
        # Check for project association
        if email_analysis.get("project_id"):
            return "project"
        
        # Check for task content
        if email_analysis.get("contains_tasks", False):
            return "task"
        
        # Check for reference material
        if email_analysis.get("is_reference", False):
            return "reference"
        
        # Default for emails that just need to be read
        return "read_later"