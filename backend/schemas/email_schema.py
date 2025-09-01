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
    recipients: Optional[str] = None
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
    
    # Get recipients
    recipients = []
    try:
        if hasattr(outlook_item, 'Recipients'):
            for recipient in outlook_item.Recipients:
                recipients.append({
                    "name": recipient.Name,
                    "address": recipient.Address
                })
    except:
        pass
    
    # Get body content
    body_content = ""
    body_preview = ""
    try:
        if hasattr(outlook_item, 'Body'):
            body_content = outlook_item.Body or ""
            body_preview = body_content[:200] + "..." if len(body_content) > 200 else body_content
    except:
        pass
    
    return EmailSchema(
        id=outlook_item.EntryID,
        subject=getattr(outlook_item, 'Subject', ''),
        sender=sender_address,
        sender_name=sender_name,
        recipients=json.dumps(recipients) if recipients else None,
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