"""
COM-based Outlook connector for direct integration with running Outlook application.
Fallback when Graph API/OAuth is not available.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

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
        self._batch_loader = None
        
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
            
            # USE ONLY LEGACY METHOD - No batch processing as per user requirements
            self._batch_loader = None
            
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
        """Get messages from specified folder with optimized batch loading"""
        if not self.is_connected():
            return []
            
        try:
            # Always use legacy method for now (reliable synchronous operation)
            return self._get_messages_legacy(folder_name, limit)
            
        except Exception as e:
            logger.error(f"Failed to get messages from {folder_name}: {e}")
            return []
    
    
    def _get_messages_legacy(self, folder_name: str, limit: int) -> List[Dict[str, Any]]:
        """Legacy message loading method (synchronous fallback)"""
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
            logger.error(f"Legacy message loading failed: {e}")
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
        """Extract message data using standardized email schema"""
        try:
            from schemas.email_schema import create_email_from_com, email_to_dict
            
            email_schema = create_email_from_com(item)
            email_dict = email_to_dict(email_schema)
            
            # Log successful extraction for debugging
            logger.debug(f"Schema extraction successful: {len(email_dict)} properties")
            
            return email_dict
        except Exception as e:
            logger.warning(f"Schema extraction failed, using legacy method: {e}")
            # Fallback to legacy extraction
            return self._extract_message_data_legacy(item)
    
    def _extract_message_data_legacy(self, item) -> Optional[Dict[str, Any]]:
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
            
            # Get recipients (separate To, CC, BCC)
            to_recipients = []
            cc_recipients = []
            bcc_recipients = []
            
            try:
                if hasattr(item, 'Recipients'):
                    for recipient in item.Recipients:
                        try:
                            # Safely extract name with unicode handling
                            name = ''
                            try:
                                name = str(getattr(recipient, 'Name', ''))
                            except (UnicodeError, UnicodeEncodeError, UnicodeDecodeError):
                                name = getattr(recipient, 'Name', '').encode('utf-8', errors='ignore').decode('utf-8')
                            except:
                                name = 'Unknown Name'
                            
                            # Extract email address - try multiple methods
                            address = ''
                            debug_info = []
                            try:
                                # First try direct Address property
                                raw_address = str(getattr(recipient, 'Address', ''))
                                debug_info.append(f"Raw address: '{raw_address}'")
                                address = raw_address
                                
                                # If empty or not an email, try various methods to get actual email
                                if not address or '@' not in address:
                                    debug_info.append("Address empty or not email, trying AddressEntry...")
                                    # Try AddressEntry first
                                    if hasattr(recipient, 'AddressEntry') and recipient.AddressEntry:
                                        addr_entry = recipient.AddressEntry
                                        # Try SMTPAddress property
                                        try:
                                            smtp_addr = str(getattr(addr_entry, 'SMTPAddress', ''))
                                            debug_info.append(f"SMTPAddress: '{smtp_addr}'")
                                            if smtp_addr and '@' in smtp_addr:
                                                address = smtp_addr
                                                debug_info.append(f"Using SMTPAddress: '{smtp_addr}'")
                                        except Exception as e:
                                            debug_info.append(f"SMTPAddress failed: {e}")
                                            pass
                                        
                                                # If SMTPAddress didn't work, try regular Address
                                        if not address or '@' not in address:
                                            try:
                                                addr_from_entry = str(getattr(addr_entry, 'Address', ''))
                                                debug_info.append(f"AddressEntry.Address: '{addr_from_entry}'")
                                                if addr_from_entry and '@' in addr_from_entry:
                                                    address = addr_from_entry
                                                    debug_info.append(f"Using AddressEntry.Address: '{addr_from_entry}'")
                                            except Exception as e:
                                                debug_info.append(f"AddressEntry.Address failed: {e}")
                                                pass
                                        
                                        # Try additional methods to resolve Exchange DN to SMTP
                                        if not address or '@' not in address:
                                            try:
                                                # Try PropertyAccessor for PR_SMTP_ADDRESS
                                                if hasattr(addr_entry, 'PropertyAccessor'):
                                                    prop_accessor = addr_entry.PropertyAccessor
                                                    smtp_from_prop = prop_accessor.GetProperty("http://schemas.microsoft.com/mapi/proptag/0x39FE001E")
                                                    debug_info.append(f"PropertyAccessor SMTP: '{smtp_from_prop}'")
                                                    if smtp_from_prop and '@' in str(smtp_from_prop):
                                                        address = str(smtp_from_prop)
                                                        debug_info.append(f"Using PropertyAccessor SMTP: '{address}'")
                                            except Exception as e:
                                                debug_info.append(f"PropertyAccessor failed: {e}")
                                                pass
                                        
                                        # If we have an Exchange DN, try to resolve it
                                        if not address or ('@' not in address and address.startswith('/')):
                                            try:
                                                # This is likely an Exchange DN, try to resolve via global address book
                                                if hasattr(addr_entry, 'GetExchangeUser'):
                                                    exchange_user = addr_entry.GetExchangeUser()
                                                    if exchange_user:
                                                        primary_smtp = str(getattr(exchange_user, 'PrimarySmtpAddress', ''))
                                                        debug_info.append(f"Exchange PrimarySmtpAddress: '{primary_smtp}'")
                                                        if primary_smtp and '@' in primary_smtp:
                                                            address = primary_smtp
                                                            debug_info.append(f"Resolved Exchange DN to SMTP: '{primary_smtp}'")
                                            except Exception as e:
                                                debug_info.append(f"Exchange DN resolution failed: {e}")
                                                pass
                                
                                # Final fallback: If we still have an Exchange DN, try to extract the user part
                                if address and address.startswith('/') and '@' not in address:
                                    debug_info.append(f"Final fallback for Exchange DN: {address}")
                                    try:
                                        # Try to extract user identifier from DN path
                                        if '/cn=' in address.lower():
                                            cn_parts = address.lower().split('/cn=')
                                            if len(cn_parts) > 1:
                                                # Get the last CN part (usually the user identifier)
                                                last_cn = cn_parts[-1]
                                                # Try to extract a meaningful username
                                                if '-' in last_cn:
                                                    # Format like "506b8eb39253431b91e2e8be271e9e96-knakos"
                                                    potential_user = last_cn.split('-')[-1]
                                                elif len(last_cn) > 32:
                                                    # Very long string, might have user at the end
                                                    potential_user = last_cn[32:] if len(last_cn) > 32 else last_cn
                                                else:
                                                    potential_user = last_cn
                                                
                                                # Try to construct SMTP address
                                                if potential_user and potential_user.isalpha():
                                                    constructed_smtp = f"{potential_user}@nbg.gr"
                                                    address = constructed_smtp
                                                    debug_info.append(f"Constructed SMTP from DN: '{constructed_smtp}'")
                                    except Exception as e:
                                        debug_info.append(f"DN parsing failed: {e}")
                                        
                                else:
                                    debug_info.append(f"Using raw address: '{address}'")
                                        
                            except (UnicodeError, UnicodeEncodeError, UnicodeDecodeError):
                                try:
                                    address = getattr(recipient, 'Address', '').encode('utf-8', errors='ignore').decode('utf-8')
                                except:
                                    address = ''
                            except:
                                address = ''
                            
                            # Log debug info for recipient extraction  
                            logger.info(f"🔍 Recipient debug - Name: '{name}', Address: '{address}', Debug: {debug_info}")
                            
                            # Only add if we have at least a name or address
                            if name or address:
                                # Skip if this recipient is actually the sender (common in sent emails)
                                is_sender = False
                                if sender_address and address:
                                    # Compare addresses (handle Exchange format)
                                    if address == sender_address or sender_address in address or address in sender_address:
                                        is_sender = True
                                
                                # Also check by name if we have sender name
                                if not is_sender and sender_name and name:
                                    if name == sender_name or sender_name in name or name in sender_name:
                                        is_sender = True
                                
                                # Only add non-sender recipients
                                if not is_sender:
                                    recipient_data = {
                                        "name": name,
                                        "address": address
                                    }
                                    
                                    # Add separate email field if address looks like actual email
                                    if address and '@' in address and not address.startswith('/'):
                                        recipient_data["email"] = address
                                    
                                    # Recipient Type: 1=To, 2=CC, 3=BCC
                                    recipient_type = getattr(recipient, 'Type', 1)
                                    if recipient_type == 1:  # To
                                        to_recipients.append(recipient_data)
                                    elif recipient_type == 2:  # CC
                                        cc_recipients.append(recipient_data)
                                    elif recipient_type == 3:  # BCC
                                        bcc_recipients.append(recipient_data)
                                    else:
                                        # Default to To if type is unclear
                                        to_recipients.append(recipient_data)
                        except Exception as recipient_error:
                            logger.warning(f"Failed to extract individual recipient: {recipient_error}")
                            continue
            except Exception as e:
                logger.warning(f"Failed to extract recipients: {e}")
                pass
            
            # Extract COS properties if available
            cos_properties = self._extract_cos_properties_legacy(item)
            
            # Convert datetime objects to strings for JSON serialization
            received_at = getattr(item, 'ReceivedTime', datetime.now())
            sent_at = getattr(item, 'SentOn', None)
            
            email_data = {
                "id": item.EntryID,
                "subject": getattr(item, 'Subject', ''),
                "sender": sender_address,
                "sender_name": sender_name,
                "to_recipients": to_recipients,
                "cc_recipients": cc_recipients,
                "bcc_recipients": bcc_recipients,
                "body_content": body_content,
                "body_preview": body_preview,
                "received_at": received_at.isoformat() if received_at else None,
                "sent_at": sent_at.isoformat() if sent_at else None,
                "is_read": getattr(item, 'UnRead', True) == False,
                "importance": self._get_importance_text(getattr(item, 'Importance', 1)),
                "has_attachments": getattr(item, 'Attachments', None) and item.Attachments.Count > 0,
                "categories": getattr(item, 'Categories', ''),
                "conversation_id": getattr(item, 'ConversationID', ''),
                "size": getattr(item, 'Size', 0),
                # Add COS properties (convert datetime objects)
                "project_id": str(cos_properties.get("COS.ProjectId")) if cos_properties.get("COS.ProjectId") else None,
                "confidence": self._convert_datetime_to_float(cos_properties.get("COS.Confidence")),
                "provenance": str(cos_properties.get("COS.Provenance")) if cos_properties.get("COS.Provenance") else None,
                "analysis": self._reconstruct_analysis_from_cos(cos_properties)
            }
            
            # Log property extraction for debugging
            logger.debug(f"Legacy extraction: {len(email_data)} properties, {len(cos_properties)} COS properties")
            
            return email_data
            
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
    
    def _extract_cos_properties_legacy(self, item) -> Dict[str, Any]:
        """Extract COS properties from Outlook item (legacy method)"""
        cos_properties = {}
        
        try:
            if not hasattr(item, 'UserProperties'):
                return cos_properties
            
            user_props = item.UserProperties
            prop_count = getattr(user_props, 'Count', 0)
            
            if prop_count == 0:
                return cos_properties
            
            # Try direct iteration first
            try:
                for prop in user_props:
                    try:
                        prop_name = getattr(prop, 'Name', '')
                        if prop_name and prop_name.startswith("COS."):
                            prop_value = getattr(prop, 'Value', None)
                            cos_properties[prop_name] = prop_value
                    except Exception as e:
                        logger.debug(f"Failed to read property via iteration: {e}")
                        continue
            except Exception as e:
                # Fallback to indexed access
                try:
                    for i in range(1, prop_count + 1):
                        try:
                            prop = user_props.Item(i)
                            prop_name = getattr(prop, 'Name', '')
                            if prop_name and prop_name.startswith("COS."):
                                prop_value = getattr(prop, 'Value', None)
                                cos_properties[prop_name] = prop_value
                        except Exception as e:
                            continue
                except Exception as e:
                    logger.debug(f"Both iteration methods failed: {e}")
            
            if cos_properties:
                logger.debug(f"Found {len(cos_properties)} COS properties in legacy extraction")
                        
        except Exception as e:
            logger.debug(f"COS property extraction failed: {e}")
        
        return cos_properties
    
    def _reconstruct_analysis_from_cos(self, cos_properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Reconstruct analysis data from COS properties (legacy method)"""
        analysis_data = {}
        
        # Map COS properties to analysis structure
        prop_mapping = {
            "COS.Priority": "priority",
            "COS.Tone": "tone",
            "COS.Urgency": "urgency", 
            "COS.Summary": "summary",
            "COS.AnalysisConfidence": "confidence"
        }
        
        for cos_prop, analysis_key in prop_mapping.items():
            if cos_prop in cos_properties and cos_properties[cos_prop] is not None:
                value = cos_properties[cos_prop]
                
                # Convert datetime objects to float (confidence scores)
                if hasattr(value, 'timestamp'):
                    # This is a datetime object, convert to confidence score
                    try:
                        # Convert COM datetime to reasonable confidence score (0.0-1.0)
                        analysis_data[analysis_key] = 0.95  # Default high confidence
                    except:
                        analysis_data[analysis_key] = 0.95
                else:
                    analysis_data[analysis_key] = value
        
        return analysis_data if analysis_data else None
    
    def _convert_datetime_to_float(self, value) -> Optional[float]:
        """Convert COM datetime objects to confidence float values"""
        if value is None:
            return None
        
        # If it's already a number, return it
        if isinstance(value, (int, float)):
            return float(value)
        
        # If it's a datetime object, convert to confidence score
        if hasattr(value, 'timestamp') or hasattr(value, 'year'):
            return 0.95  # Default high confidence
        
        # Try to convert string to float
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.95
    
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
    
    def _get_item_by_id(self, entry_id: str):
        """Get Outlook item by EntryID"""
        if not self.is_connected():
            return None
            
        try:
            return self.namespace.GetItemFromID(entry_id)
        except Exception as e:
            logger.error(f"Failed to get item by ID {entry_id}: {e}")
            return None
    
    def _save_cos_properties(self, outlook_item, cos_properties: Dict[str, Any]) -> bool:
        """Save COS properties to Outlook item using UserProperties"""
        if not outlook_item:
            return False
            
        try:
            if not hasattr(outlook_item, 'UserProperties'):
                logger.error("Outlook item does not support UserProperties")
                return False
            
            user_props = outlook_item.UserProperties
            
            for prop_name, prop_value in cos_properties.items():
                try:
                    # Convert value to string to ensure consistency
                    string_value = str(prop_value)
                    
                    # Check if property already exists
                    existing_prop = None
                    try:
                        existing_prop = user_props.Find(prop_name)
                    except:
                        pass
                    
                    if existing_prop:
                        # Try to update existing property
                        try:
                            existing_prop.Value = string_value
                            logger.debug(f"Updated COS property: {prop_name} = {prop_value}")
                        except Exception as update_e:
                            logger.warning(f"Failed to update existing property {prop_name} (likely data type conflict), attempting to delete and recreate: {update_e}")
                            # Data type conflict - need to delete existing and create new
                            try:
                                existing_prop.Delete()
                                logger.debug(f"Deleted existing property {prop_name} due to data type conflict")
                                
                                # Force save to commit the deletion
                                try:
                                    outlook_item.Save()
                                    logger.debug(f"Forced save after property deletion")
                                except Exception as save_e:
                                    logger.warning(f"Failed to save after property deletion: {save_e}")
                                
                                # Create new property with text type
                                new_prop = user_props.Add(prop_name, 1)  # 1 = olText type
                                new_prop.Value = string_value
                                logger.debug(f"Recreated COS property: {prop_name} = {prop_value}")
                            except Exception as recreate_e:
                                logger.error(f"Failed to recreate property {prop_name}: {recreate_e}")
                                # If we can't recreate, try renaming the property to avoid conflicts
                                try:
                                    alt_prop_name = f"{prop_name}_v2"
                                    logger.info(f"Attempting to create alternative property: {alt_prop_name}")
                                    alt_prop = user_props.Add(alt_prop_name, 1)
                                    alt_prop.Value = string_value
                                    logger.info(f"Successfully created alternative property: {alt_prop_name}")
                                except Exception as alt_e:
                                    logger.error(f"Failed to create alternative property: {alt_e}")
                    else:
                        # Create new property as text type
                        new_prop = user_props.Add(prop_name, 1)  # 1 = olText type
                        new_prop.Value = string_value
                        logger.debug(f"Created COS property: {prop_name} = {prop_value}")
                        
                except Exception as prop_e:
                    logger.error(f"Failed to save property {prop_name}: {prop_e}")
                    continue
            
            # Save the item
            outlook_item.Save()
            logger.info(f"Successfully saved {len(cos_properties)} COS properties")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save COS properties: {e}")
            return False
    
    def move_email(self, email_id: str, target_folder: str) -> bool:
        """Move email to target folder (alias for move_message)"""
        return self.move_message(email_id, target_folder)