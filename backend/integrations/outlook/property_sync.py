"""
Property sync module for COS-Outlook integration.
Handles reading and writing COS metadata to Outlook items.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class OutlookPropertySync:
    """Handles syncing COS data to/from Outlook custom properties"""
    
    def __init__(self):
        self.com_connector = None
    
    def write_cos_data_to_outlook(self, email_schema, outlook_item) -> bool:
        """Write COS analysis data to Outlook item as custom properties"""
        try:
            # Set basic COS properties
            if hasattr(email_schema, 'project_id') and email_schema.project_id:
                outlook_item.UserProperties.Add("COS.ProjectId", 1).Value = email_schema.project_id
            
            if hasattr(email_schema, 'confidence') and email_schema.confidence:
                outlook_item.UserProperties.Add("COS.Confidence", 5).Value = email_schema.confidence
            
            if hasattr(email_schema, 'provenance') and email_schema.provenance:
                outlook_item.UserProperties.Add("COS.Provenance", 1).Value = email_schema.provenance
            
            # Set processing timestamp
            outlook_item.UserProperties.Add("COS.ProcessedAt", 7).Value = datetime.now()
            
            outlook_item.Save()
            return True
            
        except Exception as e:
            logger.error(f"Failed to write COS properties to Outlook: {e}")
            return False
    
    def read_cos_data_from_outlook(self, outlook_item) -> Dict[str, Any]:
        """Read COS data from Outlook item custom properties"""
        cos_data = {}
        try:
            user_props = outlook_item.UserProperties
            
            # Read COS properties
            for prop in user_props:
                if prop.Name.startswith("COS."):
                    cos_data[prop.Name] = prop.Value
                    
        except Exception as e:
            logger.error(f"Failed to read COS properties from Outlook: {e}")
            
        return cos_data


def load_email_from_outlook_with_cos_data(outlook_item, com_connector):
    """Load an email from Outlook item with COS data enhancement"""
    from schemas.email_schema import create_email_from_com
    
    try:
        # Create basic email schema
        email_schema = create_email_from_com(outlook_item)
        
        # Enhance with COS data
        property_sync = OutlookPropertySync()
        property_sync.com_connector = com_connector
        cos_data = property_sync.read_cos_data_from_outlook(outlook_item)
        
        # Apply COS data to schema
        if "COS.ProjectId" in cos_data:
            email_schema.project_id = cos_data["COS.ProjectId"]
        if "COS.Confidence" in cos_data:
            email_schema.confidence = cos_data["COS.Confidence"]
        if "COS.Provenance" in cos_data:
            email_schema.provenance = cos_data["COS.Provenance"]
            
        return email_schema
        
    except Exception as e:
        logger.error(f"Failed to load email with COS data: {e}")
        return None