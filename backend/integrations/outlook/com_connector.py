"""
COM-based Outlook connector for direct integration with running Outlook application.
Fallback when Graph API/OAuth is not available.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

try:
    import win32com.client
    import pythoncom
    COM_AVAILABLE = True
except ImportError:
    COM_AVAILABLE = False
    logger.warning("win32com not available - COM integration disabled")

class OutlookCOMConnector:
    """Direct COM interface to running Outlook application"""
    
    def __init__(self):
        self.outlook_app = None
        self.namespace = None
        self._connected = False
        
    def connect(self) -> bool:
        """Connect to running Outlook application"""
        if not COM_AVAILABLE:
            logger.error("COM not available - install pywin32: pip install pywin32")
            return False
            
        try:
            # Connect to existing Outlook application
            self.outlook_app = win32com.client.GetActiveObject("Outlook.Application")
            self.namespace = self.outlook_app.GetNamespace("MAPI")
            self._connected = True
            logger.info("Successfully connected to Outlook via COM")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Outlook via COM: {e}")
            logger.info("Make sure Outlook is running and try again")
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to Outlook"""
        return self._connected and self.outlook_app is not None
    
    def get_folders(self) -> List[Dict[str, Any]]:
        """Get all mail folders"""
        if not self.is_connected():
            return []
            
        try:
            folders = []
            
            # Get default folders
            inbox = self.namespace.GetDefaultFolder(6)  # olFolderInbox
            sent = self.namespace.GetDefaultFolder(5)   # olFolderSentMail
            drafts = self.namespace.GetDefaultFolder(16) # olFolderDrafts
            
            folders.append({
                "name": "Inbox",
                "path": "Inbox", 
                "item_count": inbox.Items.Count,
                "folder_object": inbox
            })
            
            folders.append({
                "name": "Sent Items",
                "path": "Sent Items",
                "item_count": sent.Items.Count,
                "folder_object": sent
            })
            
            # Get custom folders (recursive)
            self._get_subfolders(inbox.Parent, folders, "")
            
            return folders
            
        except Exception as e:
            logger.error(f"Failed to get folders: {e}")
            return []
    
    def _get_subfolders(self, parent_folder, folders_list, parent_path):
        """Recursively get subfolders"""
        try:
            for folder in parent_folder.Folders:
                folder_path = f"{parent_path}/{folder.Name}" if parent_path else folder.Name
                
                folders_list.append({
                    "name": folder.Name,
                    "path": folder_path,
                    "item_count": folder.Items.Count,
                    "folder_object": folder
                })
                
                # Recursively get subfolders
                if folder.Folders.Count > 0:
                    self._get_subfolders(folder, folders_list, folder_path)
                    
        except Exception as e:
            logger.error(f"Error getting subfolders: {e}")
    
    def get_messages(self, folder_name: str = "Inbox", limit: int = 50) -> List[Dict[str, Any]]:
        """Get messages from specified folder"""
        if not self.is_connected():
            return []
            
        try:
            # Get folder
            if folder_name.lower() == "inbox":
                folder = self.namespace.GetDefaultFolder(6)
            else:
                # Find folder by name
                folder = self._find_folder_by_name(folder_name)
                if not folder:
                    logger.error(f"Folder '{folder_name}' not found")
                    return []
            
            # Get messages (sorted by received time, newest first)
            items = folder.Items
            logger.info(f"Total items in {folder_name}: {items.Count}")
            
            items.Sort("[ReceivedTime]", True)  # True = descending
            
            messages = []
            count = 0
            processed = 0
            
            for item in items:
                processed += 1
                if count >= limit:
                    break
                    
                # Only process mail items
                if hasattr(item, 'Subject'):
                    logger.info(f"Processing item {processed}: {getattr(item, 'Subject', 'No Subject')[:50]}")
                    message_data = self._extract_message_data(item)
                    if message_data:
                        messages.append(message_data)
                        count += 1
                    else:
                        logger.warning(f"Failed to extract data from item {processed}")
                else:
                    logger.info(f"Skipping item {processed} - no Subject attribute")
            
            logger.info(f"Retrieved {len(messages)} messages from {folder_name} (processed {processed} items)")
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get messages from {folder_name}: {e}")
            return []
    
    def _find_folder_by_name(self, folder_name: str):
        """Find folder by name (supports path notation like 'COS/Projects')"""
        try:
            if '/' in folder_name:
                # Handle nested folders
                parts = folder_name.split('/')
                current_folder = None
                
                # Start from root folders
                for root_folder in self.namespace.Folders:
                    if root_folder.Name == parts[0]:
                        current_folder = root_folder
                        break
                
                if not current_folder:
                    return None
                
                # Navigate through subfolders
                for part in parts[1:]:
                    found = False
                    for subfolder in current_folder.Folders:
                        if subfolder.Name == part:
                            current_folder = subfolder
                            found = True
                            break
                    if not found:
                        return None
                
                return current_folder
            else:
                # Search all folders for simple name
                for root_folder in self.namespace.Folders:
                    if root_folder.Name == folder_name:
                        return root_folder
                    
                    # Search subfolders
                    result = self._search_subfolders(root_folder, folder_name)
                    if result:
                        return result
                
                return None
                
        except Exception as e:
            logger.error(f"Error finding folder {folder_name}: {e}")
            return None
    
    def _check_folder_exists(self, folder_name: str, parent_folder):
        """Check if a folder exists within a specific parent folder"""
        try:
            for folder in parent_folder.Folders:
                if folder.Name == folder_name:
                    return folder
            return None
        except Exception as e:
            logger.error(f"Failed to check folder existence '{folder_name}': {e}")
            return None
    
    def _search_subfolders(self, parent_folder, target_name):
        """Recursively search subfolders"""
        try:
            for folder in parent_folder.Folders:
                if folder.Name == target_name:
                    return folder
                
                result = self._search_subfolders(folder, target_name)
                if result:
                    return result
            
            return None
            
        except Exception as e:
            return None
    
    def _extract_message_data(self, item) -> Optional[Dict[str, Any]]:
        """Extract message data from COM item"""
        try:
            # Get sender info
            sender_address = ""
            sender_name = ""
            
            try:
                if hasattr(item, 'SenderEmailAddress'):
                    sender_address = item.SenderEmailAddress or ""
                if hasattr(item, 'SenderName'):
                    sender_name = item.SenderName or ""
            except:
                pass
            
            # Get body content
            body_content = ""
            body_preview = ""
            try:
                if hasattr(item, 'Body'):
                    body_content = item.Body or ""
                    body_preview = body_content[:200] + "..." if len(body_content) > 200 else body_content
            except:
                pass
            
            # Get recipients
            recipients = []
            try:
                if hasattr(item, 'Recipients'):
                    for recipient in item.Recipients:
                        recipients.append({
                            "name": recipient.Name,
                            "address": recipient.Address
                        })
            except:
                pass
            
            return {
                "id": item.EntryID,
                "subject": getattr(item, 'Subject', ''),
                "sender": sender_address,
                "sender_name": sender_name,
                "recipients": json.dumps(recipients),
                "body_content": body_content,
                "body_preview": body_preview,
                "received_at": getattr(item, 'ReceivedTime', datetime.now()),
                "sent_at": getattr(item, 'SentOn', None),
                "is_read": getattr(item, 'UnRead', True) == False,
                "importance": self._get_importance_text(getattr(item, 'Importance', 1)),
                "has_attachments": getattr(item, 'Attachments', None) and item.Attachments.Count > 0,
                "categories": getattr(item, 'Categories', ''),
                "conversation_id": getattr(item, 'ConversationID', ''),
                "size": getattr(item, 'Size', 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to extract message data: {e}")
            return None
    
    def _get_importance_text(self, importance_value: int) -> str:
        """Convert importance value to text"""
        importance_map = {
            0: "low",
            1: "normal", 
            2: "high"
        }
        return importance_map.get(importance_value, "normal")
    
    def create_folder(self, folder_name: str, parent_folder: str = None) -> bool:
        """Create a new folder if it doesn't exist"""
        if not self.is_connected():
            return False
            
        try:
            if parent_folder:
                parent = self._find_folder_by_name(parent_folder)
                if not parent:
                    logger.error(f"Parent folder '{parent_folder}' not found")
                    return False
            else:
                # Create under Inbox
                parent = self.namespace.GetDefaultFolder(6)  # Inbox
            
            # Check if folder already exists in parent
            existing_folder = self._check_folder_exists(folder_name, parent)
            if existing_folder:
                logger.info(f"Folder already exists: {folder_name}")
                return True
            
            # Create the folder
            new_folder = parent.Folders.Add(folder_name)
            logger.info(f"Created folder: {folder_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create folder {folder_name}: {e}")
            return False
    
    def move_message(self, message_id: str, destination_folder: str) -> bool:
        """Move message to different folder"""
        if not self.is_connected():
            return False
            
        try:
            # Find the message by EntryID
            item = self.namespace.GetItemFromID(message_id)
            
            # Find destination folder
            dest_folder = self._find_folder_by_name(destination_folder)
            if not dest_folder:
                logger.error(f"Destination folder '{destination_folder}' not found")
                return False
            
            # Move the item
            item.Move(dest_folder)
            logger.info(f"Moved message to {destination_folder}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to move message: {e}")
            return False
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get current account information"""
        if not self.is_connected():
            return {}
            
        try:
            accounts = []
            for account in self.namespace.Accounts:
                accounts.append({
                    "name": account.DisplayName,
                    "email": account.SmtpAddress,
                    "type": account.AccountType
                })
            
            return {
                "accounts": accounts,
                "primary_account": accounts[0] if accounts else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return {}
    
    def setup_gtd_folders(self) -> Dict[str, bool]:
        """Setup GTD folder structure under Inbox"""
        gtd_folders = [
            "COS_Actions",
            "COS_Assigned", 
            "COS_ReadLater",
            "COS_Reference",
            "COS_Archive"
        ]
        
        # COS folders removed - using extended properties for project/task linking instead
        
        results = {}
        
        # Create GTD folders under Inbox (default behavior of create_folder)
        for folder in gtd_folders:
            results[folder] = self.create_folder(folder)
        
        return results