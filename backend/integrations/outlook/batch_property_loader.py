"""
Batch property loader for Outlook emails with concurrent processing.
Optimizes email loading by batching property access and using concurrent execution.
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logger = logging.getLogger(__name__)

class BatchOutlookPropertyLoader:
    """
    Efficient batch loader for Outlook email properties with concurrent processing.
    
    Key optimizations:
    1. Batch property access to minimize COM calls
    2. Concurrent processing of multiple emails
    3. Property caching to avoid redundant lookups
    4. Optimized COS data extraction
    """
    
    def __init__(self, com_connector):
        self.com_connector = com_connector
        self.thread_pool = ThreadPoolExecutor(max_workers=4)  # Limit concurrent COM operations
        self._property_cache = {}
        self._cache_lock = threading.Lock()
        
        # Pre-defined property lists for batch access
        self.standard_properties = [
            'Subject', 'SenderEmailAddress', 'SenderName', 'Body', 'ReceivedTime',
            'SentOn', 'UnRead', 'Importance', 'Size', 'ConversationID', 'Categories'
        ]
        
        self.cos_property_prefixes = ['COS.']
    
    async def load_emails_batch(self, folder_name: str = "Inbox", limit: int = 50) -> List[Dict[str, Any]]:
        """
        Load multiple emails concurrently with optimized property access.
        
        Args:
            folder_name: Folder to load emails from
            limit: Maximum number of emails to load
            
        Returns:
            List of email dictionaries with all properties loaded
        """
        if not self.com_connector.is_connected():
            return []
        
        try:
            # Step 1: Get raw Outlook items (lightweight operation)
            outlook_items = self._get_outlook_items(folder_name, limit)
            if not outlook_items:
                logger.warning(f"No items found in folder {folder_name}")
                return []
            
            logger.info(f"Processing {len(outlook_items)} emails with batch loader from folder '{folder_name}'")
            
            # Step 2: Process items concurrently in batches
            batch_size = 10  # Process 10 emails at a time to avoid overwhelming COM
            all_emails = []
            
            for i in range(0, len(outlook_items), batch_size):
                batch = outlook_items[i:i + batch_size]
                batch_results = await self._process_batch_concurrent(batch)
                all_emails.extend(batch_results)
                
                # Small delay between batches to prevent COM overload
                if i + batch_size < len(outlook_items):
                    await asyncio.sleep(0.1)
            
            # Log performance statistics
            if all_emails:
                logger.info(f"Successfully loaded {len(all_emails)} emails with properties")
                logger.debug(f"Sample email keys: {list(all_emails[0].keys())}")
                
                # Log COS property statistics
                cos_count = sum(1 for email in all_emails if any(
                    email.get(prop) is not None for prop in ['project_id', 'confidence', 'provenance', 'analysis']
                ))
                if cos_count > 0:
                    logger.info(f"Found COS properties in {cos_count}/{len(all_emails)} emails")
            
            return all_emails
            
        except Exception as e:
            logger.error(f"Batch email loading failed: {e}")
            return []
    
    def _get_outlook_items(self, folder_name: str, limit: int) -> List[Any]:
        """Get raw Outlook items without extracting properties (fast operation)"""
        try:
            # Get folder
            if folder_name.lower() == "inbox":
                folder = self.com_connector.namespace.GetDefaultFolder(6)
            else:
                folder = self.com_connector._find_folder_by_name(folder_name)
                if not folder:
                    logger.error(f"Folder '{folder_name}' not found")
                    return []
            
            # Get items and sort (but don't extract properties yet)
            items = folder.Items
            items.Sort("[ReceivedTime]", True)  # Descending
            
            # Collect items up to limit
            outlook_items = []
            count = 0
            
            for item in items:
                if count >= limit:
                    break
                if hasattr(item, 'Subject'):  # Only mail items
                    outlook_items.append(item)
                    count += 1
            
            return outlook_items
            
        except Exception as e:
            logger.error(f"Failed to get Outlook items: {e}")
            return []
    
    async def _process_batch_concurrent(self, outlook_items: List[Any]) -> List[Dict[str, Any]]:
        """Process a batch of Outlook items concurrently"""
        loop = asyncio.get_event_loop()
        
        # Create concurrent tasks for property extraction
        tasks = []
        for item in outlook_items:
            task = loop.run_in_executor(
                self.thread_pool,
                self._extract_all_properties_optimized,
                item
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = []
        completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(completed_tasks):
            if isinstance(result, Exception):
                logger.error(f"Failed to process item {i}: {result}")
            elif result:
                results.append(result)
        
        return results
    
    def _extract_all_properties_optimized(self, outlook_item) -> Optional[Dict[str, Any]]:
        """
        Optimized property extraction that batches all property access.
        
        This method minimizes COM calls by:
        1. Extracting all standard properties in one pass
        2. Batch-loading COS properties
        3. Efficient recipient processing
        4. Caching frequently accessed data
        """
        try:
            item_id = outlook_item.EntryID
            
            # Check cache first
            with self._cache_lock:
                if item_id in self._property_cache:
                    return self._property_cache[item_id]
            
            # Batch extract standard properties
            properties = self._extract_standard_properties_batch(outlook_item)
            
            # Batch extract COS properties
            cos_properties = self._extract_cos_properties_batch(outlook_item)
            properties.update(cos_properties)
            
            # Extract recipients (optimized)
            recipient_data = self._extract_recipients_optimized(outlook_item)
            properties.update(recipient_data)
            
            # Create final email data structure
            email_data = {
                "id": item_id,
                "subject": properties.get("Subject", ""),
                "sender": properties.get("SenderEmailAddress", ""),
                "sender_name": properties.get("SenderName", ""),
                "to_recipients": properties.get("to_recipients", []),
                "cc_recipients": properties.get("cc_recipients", []),
                "bcc_recipients": properties.get("bcc_recipients", []),
                "body_content": properties.get("Body", ""),
                "body_preview": self._create_preview(properties.get("Body", "")),
                "received_at": properties.get("ReceivedTime", datetime.now()),
                "sent_at": properties.get("SentOn"),
                "is_read": not properties.get("UnRead", True),
                "importance": self._get_importance_text(properties.get("Importance", 1)),
                "has_attachments": properties.get("has_attachments", False),
                "categories": properties.get("Categories", ""),
                "conversation_id": properties.get("ConversationID", ""),
                "size": properties.get("Size", 0),
                # COS properties
                "project_id": cos_properties.get("COS.ProjectId"),
                "confidence": cos_properties.get("COS.Confidence"),
                "provenance": cos_properties.get("COS.Provenance"),
                "analysis": self._reconstruct_analysis_data(cos_properties)
            }
            
            # Cache the result
            with self._cache_lock:
                self._property_cache[item_id] = email_data
            
            return email_data
            
        except Exception as e:
            logger.error(f"Optimized property extraction failed: {e}")
            return None
    
    def _extract_standard_properties_batch(self, outlook_item) -> Dict[str, Any]:
        """Extract all standard Outlook properties in one optimized pass"""
        properties = {}
        
        # Batch extract standard properties with error handling
        for prop_name in self.standard_properties:
            try:
                if hasattr(outlook_item, prop_name):
                    properties[prop_name] = getattr(outlook_item, prop_name)
            except Exception as e:
                logger.debug(f"Failed to get property {prop_name}: {e}")
                properties[prop_name] = None
        
        # Handle attachments (requires special handling)
        try:
            properties["has_attachments"] = (
                hasattr(outlook_item, 'Attachments') and 
                outlook_item.Attachments and 
                outlook_item.Attachments.Count > 0
            )
        except:
            properties["has_attachments"] = False
        
        return properties
    
    def _extract_cos_properties_batch(self, outlook_item) -> Dict[str, Any]:
        """Batch extract all COS properties at once"""
        cos_properties = {}
        
        try:
            if not hasattr(outlook_item, 'UserProperties'):
                logger.debug("Outlook item has no UserProperties attribute")
                return cos_properties
            
            user_props = outlook_item.UserProperties
            prop_count = getattr(user_props, 'Count', 0)
            logger.debug(f"Found {prop_count} user properties to scan")
            
            if prop_count == 0:
                return cos_properties
            
            # Try different iteration methods for COM compatibility
            cos_found = 0
            
            # Method 1: Direct iteration (Python-style)
            try:
                for prop in user_props:
                    try:
                        prop_name = getattr(prop, 'Name', '')
                        if prop_name and any(prop_name.startswith(prefix) for prefix in self.cos_property_prefixes):
                            prop_value = getattr(prop, 'Value', None)
                            cos_properties[prop_name] = prop_value
                            cos_found += 1
                            logger.debug(f"Found COS property: {prop_name} = {prop_value}")
                    except Exception as e:
                        logger.debug(f"Failed to read property via iteration: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Direct iteration failed, trying indexed access: {e}")
                
                # Method 2: Indexed access (COM-style)
                try:
                    for i in range(1, prop_count + 1):  # COM collections are 1-indexed
                        try:
                            prop = user_props.Item(i)
                            prop_name = getattr(prop, 'Name', '')
                            if prop_name and any(prop_name.startswith(prefix) for prefix in self.cos_property_prefixes):
                                prop_value = getattr(prop, 'Value', None)
                                cos_properties[prop_name] = prop_value
                                cos_found += 1
                                logger.debug(f"Found COS property (indexed): {prop_name} = {prop_value}")
                        except Exception as e:
                            logger.debug(f"Failed to read property {i} via index: {e}")
                            continue
                except Exception as e:
                    logger.debug(f"Indexed access also failed: {e}")
            
            if cos_found > 0:
                logger.debug(f"Successfully extracted {cos_found} COS properties")
            else:
                logger.debug("No COS properties found (this is normal if email hasn't been analyzed)")
                        
        except Exception as e:
            logger.error(f"Failed to extract COS properties: {e}")
        
        return cos_properties
    
    def _extract_recipients_optimized(self, outlook_item) -> Dict[str, Any]:
        """Optimized recipient extraction with minimal COM calls"""
        recipient_data = {
            "to_recipients": [],
            "cc_recipients": [],
            "bcc_recipients": []
        }
        
        try:
            if not hasattr(outlook_item, 'Recipients'):
                return recipient_data
            
            # Get sender info for filtering
            sender_address = getattr(outlook_item, 'SenderEmailAddress', '') or ''
            sender_name = getattr(outlook_item, 'SenderName', '') or ''
            
            # Single pass through recipients
            for recipient in outlook_item.Recipients:
                try:
                    # Batch extract recipient properties
                    recipient_props = self._extract_recipient_properties(recipient)
                    
                    # Skip if this recipient is actually the sender
                    if self._is_sender(recipient_props, sender_address, sender_name):
                        continue
                    
                    # Add to appropriate list based on type
                    recipient_type = recipient_props.get("Type", 1)
                    recipient_dict = {
                        "name": recipient_props.get("name", ""),
                        "address": recipient_props.get("address", "")
                    }
                    
                    if recipient_props.get("email"):
                        recipient_dict["email"] = recipient_props["email"]
                    
                    if recipient_type == 1:  # To
                        recipient_data["to_recipients"].append(recipient_dict)
                    elif recipient_type == 2:  # CC
                        recipient_data["cc_recipients"].append(recipient_dict)
                    elif recipient_type == 3:  # BCC
                        recipient_data["bcc_recipients"].append(recipient_dict)
                    else:
                        recipient_data["to_recipients"].append(recipient_dict)  # Default to To
                        
                except Exception as e:
                    logger.debug(f"Failed to process individual recipient: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"Failed to extract recipients: {e}")
        
        return recipient_data
    
    def _extract_recipient_properties(self, recipient) -> Dict[str, Any]:
        """Extract all recipient properties in one batch operation"""
        props = {}
        
        # Get basic properties
        try:
            props["name"] = str(getattr(recipient, 'Name', ''))
        except (UnicodeError, UnicodeEncodeError, UnicodeDecodeError):
            props["name"] = getattr(recipient, 'Name', '').encode('utf-8', errors='ignore').decode('utf-8')
        except:
            props["name"] = 'Unknown Name'
        
        # Get address with fallback methods
        address = ''
        try:
            address = str(getattr(recipient, 'Address', ''))
            
            # Try to get actual email address if we got Exchange format
            if not address or '@' not in address:
                if hasattr(recipient, 'AddressEntry') and recipient.AddressEntry:
                    addr_entry = recipient.AddressEntry
                    
                    # Try SMTPAddress first
                    try:
                        smtp_addr = str(getattr(addr_entry, 'SMTPAddress', ''))
                        if smtp_addr and '@' in smtp_addr:
                            address = smtp_addr
                    except:
                        pass
                    
                    # Try regular Address if SMTPAddress didn't work
                    if not address or '@' not in address:
                        try:
                            addr_from_entry = str(getattr(addr_entry, 'Address', ''))
                            if addr_from_entry and '@' in addr_from_entry:
                                address = addr_from_entry
                        except:
                            pass
                            
        except (UnicodeError, UnicodeEncodeError, UnicodeDecodeError):
            try:
                address = getattr(recipient, 'Address', '').encode('utf-8', errors='ignore').decode('utf-8')
            except:
                address = ''
        except:
            address = ''
        
        props["address"] = address
        
        # Add separate email field if address looks like actual email
        if address and '@' in address and not address.startswith('/'):
            props["email"] = address
        
        # Get recipient type
        try:
            props["Type"] = getattr(recipient, 'Type', 1)
        except:
            props["Type"] = 1
        
        return props
    
    def _is_sender(self, recipient_props: Dict[str, Any], sender_address: str, sender_name: str) -> bool:
        """Check if recipient is actually the sender"""
        address = recipient_props.get("address", "")
        name = recipient_props.get("name", "")
        
        # Compare addresses
        if sender_address and address:
            if (address == sender_address or 
                sender_address in address or 
                address in sender_address):
                return True
        
        # Compare names
        if sender_name and name:
            if (name == sender_name or 
                sender_name in name or 
                name in sender_name):
                return True
        
        return False
    
    def _reconstruct_analysis_data(self, cos_properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Reconstruct analysis data from COS properties"""
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
            if cos_prop in cos_properties:
                value = cos_properties[cos_prop]
                
                # Handle COM datetime objects for confidence values
                if analysis_key == "confidence":
                    analysis_data[analysis_key] = self._convert_datetime_to_float(value)
                else:
                    # Convert other datetime objects to strings for JSON serialization
                    if hasattr(value, 'strftime') or hasattr(value, 'year'):
                        # This is a datetime object - convert to string
                        try:
                            analysis_data[analysis_key] = str(value)
                        except:
                            analysis_data[analysis_key] = value
                    else:
                        analysis_data[analysis_key] = value
        
        return analysis_data if analysis_data else None
    
    def _convert_datetime_to_float(self, value) -> Optional[float]:
        """Convert COM datetime objects to confidence float values"""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if hasattr(value, 'timestamp') or hasattr(value, 'year'):
            return 0.95  # Default high confidence for datetime placeholders
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.95
    
    def _create_preview(self, body_content: str) -> str:
        """Create body preview from content"""
        if not body_content:
            return ""
        return body_content[:200] + "..." if len(body_content) > 200 else body_content
    
    def _get_importance_text(self, importance_value: int) -> str:
        """Convert importance value to text"""
        importance_map = {
            0: "low",
            1: "normal",
            2: "high"
        }
        return importance_map.get(importance_value, "normal")
    
    def clear_cache(self):
        """Clear the property cache"""
        with self._cache_lock:
            self._property_cache.clear()
        logger.info("Property cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        with self._cache_lock:
            return {
                "cached_emails": len(self._property_cache),
                "cache_size_mb": len(str(self._property_cache)) / (1024 * 1024)
            }
    
    def __del__(self):
        """Cleanup thread pool on destruction"""
        if hasattr(self, 'thread_pool'):
            self.thread_pool.shutdown(wait=False)