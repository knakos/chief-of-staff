"""
Email schema for standardized email data handling.
"""
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel


class EmailSchema(BaseModel):
    """Standardized email schema"""
    id: str
    subject: str
    sender: str
    sender_name: Optional[str] = None
    recipients: Optional[str] = None  # Legacy field for backwards compatibility
    to_recipients: Optional[List[Dict[str, str]]] = None
    cc_recipients: Optional[List[Dict[str, str]]] = None
    bcc_recipients: Optional[List[Dict[str, str]]] = None
    body_content: Optional[str] = None
    body_preview: Optional[str] = None
    received_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    is_read: bool = False
    importance: str = "normal"
    has_attachments: bool = False
    categories: Optional[str] = None
    conversation_id: Optional[str] = None
    size: int = 0
    
    # COS metadata
    project_id: Optional[str] = None
    confidence: Optional[float] = None
    provenance: Optional[str] = None
    linked_at: Optional[datetime] = None
    analysis: Optional[Dict[str, Any]] = None  # COS AI analysis data
    
    class Config:
        arbitrary_types_allowed = True


def create_email_from_com(outlook_item, skip_analysis: bool = False) -> EmailSchema:
    """Create EmailSchema from COM Outlook item"""
    
    # Get sender info
    sender_address = ""
    sender_name = ""
    
    try:
        if hasattr(outlook_item, 'SenderEmailAddress'):
            sender_address = outlook_item.SenderEmailAddress or ""
        if hasattr(outlook_item, 'SenderName'):
            sender_name = outlook_item.SenderName or ""
    except:
        pass
    
    # Get recipients (separate To, CC, BCC)
    to_recipients = []
    cc_recipients = []
    bcc_recipients = []
    
    try:
        if hasattr(outlook_item, 'Recipients'):
            for recipient in outlook_item.Recipients:
                try:
                    # Safely extract name with unicode handling
                    name = ''
                    try:
                        name = str(getattr(recipient, 'Name', ''))
                    except (UnicodeError, UnicodeEncodeError, UnicodeDecodeError):
                        name = getattr(recipient, 'Name', '').encode('utf-8', errors='ignore').decode('utf-8')
                    except:
                        name = 'Unknown Name'
                    
                    # Extract email address - try multiple methods with Exchange DN resolution
                    address = ''
                    try:
                        # First try direct Address property
                        raw_address = str(getattr(recipient, 'Address', ''))
                        address = raw_address
                        
                        # If empty or not an email, try various methods to get actual email
                        if not address or '@' not in address:
                            # Try AddressEntry first
                            if hasattr(recipient, 'AddressEntry') and recipient.AddressEntry:
                                addr_entry = recipient.AddressEntry
                                
                                # Try SMTPAddress property
                                try:
                                    smtp_addr = str(getattr(addr_entry, 'SMTPAddress', ''))
                                    if smtp_addr and '@' in smtp_addr:
                                        address = smtp_addr
                                except:
                                    pass
                                
                                # If SMTPAddress didn't work, try regular Address
                                if not address or '@' not in address:
                                    try:
                                        addr_from_entry = str(getattr(addr_entry, 'Address', ''))
                                        if addr_from_entry and '@' in addr_from_entry:
                                            address = addr_from_entry
                                    except:
                                        pass
                                
                                # Try Exchange DN resolution
                                if not address or '@' not in address:
                                    try:
                                        # Try to resolve Exchange DN via GetExchangeUser
                                        if hasattr(addr_entry, 'GetExchangeUser'):
                                            exchange_user = addr_entry.GetExchangeUser()
                                            if exchange_user:
                                                primary_smtp = str(getattr(exchange_user, 'PrimarySmtpAddress', ''))
                                                if primary_smtp and '@' in primary_smtp:
                                                    address = primary_smtp
                                    except:
                                        pass
                        
                        # Final fallback: If we still have an Exchange DN, try to parse it
                        if address and address.startswith('/') and '@' not in address:
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
                            except:
                                pass
                                    
                    except (UnicodeError, UnicodeEncodeError, UnicodeDecodeError):
                        try:
                            address = getattr(recipient, 'Address', '').encode('utf-8', errors='ignore').decode('utf-8')
                        except:
                            address = ''
                    except:
                        address = ''
                    
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
                        
                        # Always include recipients - sender may legitimately send to themselves
                        # (e.g., BCC scenarios, confirmation emails, etc.)
                        recipient_data = {
                            "name": name,
                            "address": address
                        }
                        
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
                except Exception:
                    # Skip problematic individual recipients
                    continue
    except:
        pass
    
    # Legacy recipients field for backwards compatibility
    all_recipients = to_recipients + cc_recipients + bcc_recipients
    
    # Get body content
    body_content = ""
    body_preview = ""
    try:
        if hasattr(outlook_item, 'Body'):
            raw_body = outlook_item.Body
            body_content = raw_body or ""
            body_preview = body_content[:200] + "..." if len(body_content) > 200 else body_content
            # Removed logger call - not always available in schema context
        else:
            # No Body attribute available
            pass
    except Exception as e:
        # Body extraction failed - continue without body content
        pass
    
    # Extract COS properties and analysis data
    project_id = None
    confidence = None
    provenance = None
    linked_at = None
    analysis = None
    
    # Always load existing COS properties regardless of skip_analysis flag
    # skip_analysis only controls generation of NEW analysis, not loading of existing analysis
    try:
        # Load COS properties using existing COM connector methods
        cos_properties = _extract_cos_properties_from_item(outlook_item)
        if cos_properties:
            project_id = cos_properties.get("COS.ProjectId")
            confidence = cos_properties.get("COS.Confidence") 
            provenance = cos_properties.get("COS.Provenance")
            linked_at = cos_properties.get("COS.LinkedAt")
            
            # Reconstruct analysis from COS properties
            analysis = _reconstruct_analysis_from_cos_properties(cos_properties)
                
    except Exception as e:
        # COS property loading failed - continue without COS data
        # Note: logger not always available in schema context
        pass
    
    return EmailSchema(
        id=outlook_item.EntryID,
        subject=getattr(outlook_item, 'Subject', ''),
        sender=sender_address,
        sender_name=sender_name,
        recipients=json.dumps(all_recipients) if all_recipients else None,
        to_recipients=to_recipients,
        cc_recipients=cc_recipients,
        bcc_recipients=bcc_recipients,
        body_content=body_content,
        body_preview=body_preview,
        received_at=getattr(outlook_item, 'ReceivedTime', datetime.utcnow()),
        sent_at=getattr(outlook_item, 'SentOn', None),
        is_read=getattr(outlook_item, 'UnRead', True) == False,
        importance=_get_importance_text(getattr(outlook_item, 'Importance', 1)),
        has_attachments=getattr(outlook_item, 'Attachments', None) and outlook_item.Attachments.Count > 0,
        categories=getattr(outlook_item, 'Categories', ''),
        conversation_id=getattr(outlook_item, 'ConversationID', ''),
        size=getattr(outlook_item, 'Size', 0),
        # COS metadata
        project_id=project_id,
        confidence=confidence,
        provenance=provenance,
        linked_at=linked_at,
        analysis=analysis
    )


def _get_importance_text(importance_value: int) -> str:
    """Convert importance value to text"""
    importance_map = {
        0: "low",
        1: "normal", 
        2: "high"
    }
    return importance_map.get(importance_value, "normal")


def email_to_dict(email_schema: EmailSchema) -> Dict[str, Any]:
    """Convert EmailSchema to dictionary"""
    return {
        "id": email_schema.id,
        "subject": email_schema.subject,
        "sender": email_schema.sender,
        "sender_name": email_schema.sender_name,
        "recipients": email_schema.recipients,
        "to_recipients": email_schema.to_recipients,
        "cc_recipients": email_schema.cc_recipients,
        "bcc_recipients": email_schema.bcc_recipients,
        "body_content": email_schema.body_content,
        "body_preview": email_schema.body_preview,
        "received_at": email_schema.received_at,
        "sent_at": email_schema.sent_at,
        "is_read": email_schema.is_read,
        "importance": email_schema.importance,
        "has_attachments": email_schema.has_attachments,
        "categories": email_schema.categories,
        "conversation_id": email_schema.conversation_id,
        "size": email_schema.size,
        # COS metadata
        "project_id": email_schema.project_id,
        "confidence": email_schema.confidence,
        "provenance": email_schema.provenance,
        "linked_at": email_schema.linked_at,
        "analysis": email_schema.analysis
    }


def validate_email_schema(email_data: Dict[str, Any]) -> bool:
    """Validate email data against schema requirements"""
    try:
        # Check required fields
        required_fields = ["id", "subject", "sender"]
        for field in required_fields:
            if field not in email_data:
                return False
        
        # Basic type validation
        if not isinstance(email_data.get("id"), str):
            return False
        if not isinstance(email_data.get("subject"), str):
            return False
        if not isinstance(email_data.get("sender"), str):
            return False
            
        return True
    except Exception:
        return False


def _extract_cos_properties_from_item(outlook_item) -> Dict[str, Any]:
    """Extract COS properties from Outlook COM item"""
    import logging
    logger = logging.getLogger(__name__)
    
    cos_properties = {}
    
    try:
        if not hasattr(outlook_item, 'UserProperties'):
            return cos_properties
        
        user_props = outlook_item.UserProperties
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
                        if prop_value is not None:
                            cos_properties[prop_name] = prop_value
                            logger.debug(f"Found COS property: {prop_name} = {prop_value}")
                except Exception as prop_e:
                    logger.debug(f"Error reading property: {prop_e}")
                    continue
                    
        except Exception as iter_e:
            # Fallback to indexed access
            logger.debug(f"Direct iteration failed, trying indexed access: {iter_e}")
            try:
                for i in range(1, prop_count + 1):
                    try:
                        prop = user_props.Item(i)
                        prop_name = getattr(prop, 'Name', '')
                        if prop_name and prop_name.startswith("COS."):
                            prop_value = getattr(prop, 'Value', None)
                            if prop_value is not None:
                                cos_properties[prop_name] = prop_value
                                logger.debug(f"Found COS property (indexed): {prop_name} = {prop_value}")
                    except Exception as idx_prop_e:
                        logger.debug(f"Error reading indexed property {i}: {idx_prop_e}")
                        continue
                        
            except Exception as idx_e:
                logger.warning(f"Indexed access also failed: {idx_e}")
        
        logger.info(f"Extracted {len(cos_properties)} COS properties")
        
    except Exception as e:
        logger.error(f"Failed to extract COS properties: {e}")
    
    return cos_properties


def _reconstruct_analysis_from_cos_properties(cos_properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Reconstruct analysis data from COS properties"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not cos_properties:
        return None
        
    analysis_data = {}
    
    # Map COS properties to analysis structure
    prop_mapping = {
        "COS.Priority": "priority",
        "COS.Tone": "tone", 
        "COS.Urgency": "urgency",
        "COS.Summary": "summary",
        "COS.AnalysisConfidence": "confidence",
        "COS.SuggestedActions": "suggested_actions"
    }
    
    # Add alternative property names for conflict resolution
    alt_prop_mapping = {
        "COS.AnalysisConfidence_v2": "confidence"
    }
    
    # Process main properties first
    for cos_prop, analysis_key in prop_mapping.items():
        if cos_prop in cos_properties and cos_properties[cos_prop] is not None:
            value = cos_properties[cos_prop]
            
            # Special handling for confidence field
            if analysis_key == "confidence":
                if hasattr(value, 'timestamp'):
                    try:
                        # Convert datetime to confidence score (0.0 to 1.0) - legacy support
                        timestamp = value.timestamp()
                        confidence_score = min(1.0, max(0.0, (timestamp % 1000000) / 1000000))
                        analysis_data[analysis_key] = confidence_score
                        logger.debug(f"Converted datetime to confidence: {confidence_score}")
                    except Exception as e:
                        logger.warning(f"Failed to convert datetime to confidence: {e}")
                        analysis_data[analysis_key] = 0.8  # Default
                else:
                    # Try to convert string to float
                    try:
                        confidence_value = float(str(value))
                        # Ensure value is between 0.0 and 1.0
                        analysis_data[analysis_key] = max(0.0, min(1.0, confidence_value))
                        logger.debug(f"Converted string to confidence: {confidence_value}")
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to parse confidence value '{value}', using default")
                        analysis_data[analysis_key] = 0.8  # Default
            elif analysis_key == "suggested_actions":
                # Handle JSON-encoded suggested actions
                if value and str(value).strip():
                    try:
                        import json
                        suggested_actions = json.loads(str(value))
                        if isinstance(suggested_actions, list):
                            analysis_data[analysis_key] = suggested_actions
                        else:
                            logger.warning(f"Invalid suggested_actions format: {type(suggested_actions)}")
                    except Exception as e:
                        logger.warning(f"Failed to parse suggested_actions JSON: {e}")
            else:
                # Store other fields as strings
                analysis_data[analysis_key] = str(value)
    
    # Process alternative properties if main ones are missing
    for alt_cos_prop, analysis_key in alt_prop_mapping.items():
        if analysis_key not in analysis_data and alt_cos_prop in cos_properties and cos_properties[alt_cos_prop] is not None:
            value = cos_properties[alt_cos_prop]
            logger.info(f"Using alternative property {alt_cos_prop} for {analysis_key}")
            
            # Handle confidence field from alternative property
            if analysis_key == "confidence":
                try:
                    confidence_value = float(str(value))
                    analysis_data[analysis_key] = max(0.0, min(1.0, confidence_value))
                    logger.debug(f"Converted alternative confidence: {confidence_value}")
                except (ValueError, TypeError):
                    logger.warning(f"Failed to parse alternative confidence '{value}', using default")
                    analysis_data[analysis_key] = 0.8
    
    # Only return analysis if we found actual data
    if analysis_data:
        # Set defaults for missing values
        analysis_data.setdefault('priority', 'MEDIUM')
        analysis_data.setdefault('tone', 'PROFESSIONAL') 
        analysis_data.setdefault('urgency', 'MEDIUM')
        analysis_data.setdefault('confidence', 0.8)
        
        logger.info(f"Reconstructed analysis: {analysis_data}")
        return analysis_data
    
    return None