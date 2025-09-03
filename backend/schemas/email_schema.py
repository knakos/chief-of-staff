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


def create_email_from_com(outlook_item) -> EmailSchema:
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
                    
                    # Extract email address - try multiple methods
                    address = ''
                    try:
                        # First try direct Address property
                        address = str(getattr(recipient, 'Address', ''))
                        
                        # If empty or not an email, try AddressEntry
                        if not address or '@' not in address:
                            if hasattr(recipient, 'AddressEntry') and recipient.AddressEntry:
                                addr_entry = recipient.AddressEntry
                                addr_from_entry = str(getattr(addr_entry, 'Address', ''))
                                if addr_from_entry and '@' in addr_from_entry:
                                    address = addr_from_entry
                                    
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
                        
                        # Only add non-sender recipients
                        if not is_sender:
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
            logger.info(f"📧 BODY DEBUG - Subject: {getattr(outlook_item, 'Subject', 'No Subject')[:30]} | Raw body length: {len(raw_body) if raw_body else 0} | Final body_content length: {len(body_content)}")
        else:
            logger.warning(f"📧 BODY DEBUG - No Body attribute for email: {getattr(outlook_item, 'Subject', 'No Subject')[:30]}")
    except Exception as e:
        logger.error(f"📧 BODY DEBUG - Error getting body for email {getattr(outlook_item, 'Subject', 'No Subject')[:30]}: {e}")
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
        received_at=getattr(outlook_item, 'ReceivedTime', datetime.now()),
        sent_at=getattr(outlook_item, 'SentOn', None),
        is_read=getattr(outlook_item, 'UnRead', True) == False,
        importance=_get_importance_text(getattr(outlook_item, 'Importance', 1)),
        has_attachments=getattr(outlook_item, 'Attachments', None) and outlook_item.Attachments.Count > 0,
        categories=getattr(outlook_item, 'Categories', ''),
        conversation_id=getattr(outlook_item, 'ConversationID', ''),
        size=getattr(outlook_item, 'Size', 0)
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
        "size": email_schema.size
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