"""
Extended Properties handler for COS custom properties in Outlook.
Manages COS.ProjectId, COS.TaskIds, COS.LinkedAt, COS.Confidence, COS.Provenance
"""
import logging
from typing import Dict, List, Optional, Any, Union
import json
from datetime import datetime

from .connector import GraphAPIConnector
from .auth import OutlookAuthManager

logger = logging.getLogger(__name__)

class COSExtendedPropsManager:
    """Manages COS-specific extended properties in Outlook emails"""
    
    # COS Extended Property definitions
    COS_PROPERTIES = {
        "COS.ProjectId": {
            "type": "String",
            "description": "Associated project ID",
            "guid": "{00020329-0000-0000-C000-000000000046}",
            "name": "COSProjectId"
        },
        "COS.TaskIds": {
            "type": "StringArray", 
            "description": "Associated task IDs (JSON array)",
            "guid": "{00020329-0000-0000-C000-000000000046}",
            "name": "COSTaskIds"
        },
        "COS.LinkedAt": {
            "type": "SystemTime",
            "description": "Timestamp when COS processed this email",
            "guid": "{00020329-0000-0000-C000-000000000046}",
            "name": "COSLinkedAt"
        },
        "COS.Confidence": {
            "type": "Double",
            "description": "AI confidence score for associations (0.0-1.0)",
            "guid": "{00020329-0000-0000-C000-000000000046}",
            "name": "COSConfidence"
        },
        "COS.Provenance": {
            "type": "String",
            "description": "How the associations were determined (AI/Manual/Import)",
            "guid": "{00020329-0000-0000-C000-000000000046}",
            "name": "COSProvenance"
        }
    }
    
    def __init__(self, connector: GraphAPIConnector, auth_manager: OutlookAuthManager):
        self.connector = connector
        self.auth_manager = auth_manager
    
    async def set_cos_properties(self, message_id: str, properties: Dict[str, Any], 
                                user_id: str = "default") -> bool:
        """Set COS extended properties on an email"""
        try:
            access_token = await self.auth_manager.get_valid_access_token(user_id)
            
            # Build single value extended properties update
            single_value_props = []
            
            for prop_name, value in properties.items():
                if prop_name not in self.COS_PROPERTIES:
                    logger.warning(f"Unknown COS property: {prop_name}")
                    continue
                
                prop_config = self.COS_PROPERTIES[prop_name]
                formatted_value = self._format_property_value(prop_name, value)
                
                if formatted_value is not None:
                    single_value_props.append({
                        "id": f"{prop_config['type']} {prop_config['guid']} Name {prop_config['name']}",
                        "value": formatted_value
                    })
            
            if not single_value_props:
                logger.warning("No valid properties to set")
                return False
            
            # Update message with extended properties
            update_data = {
                "singleValueExtendedProperties": single_value_props
            }
            
            await self.connector.update_message(access_token, message_id, update_data)
            logger.info(f"Set COS properties on message {message_id}: {list(properties.keys())}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set COS properties: {e}")
            return False
    
    async def get_cos_properties(self, message_id: str, 
                                user_id: str = "default") -> Dict[str, Any]:
        """Get COS extended properties from an email"""
        try:
            access_token = await self.auth_manager.get_valid_access_token(user_id)
            
            # Build expand query for extended properties
            expand_queries = []
            for prop_name, prop_config in self.COS_PROPERTIES.items():
                prop_id = f"{prop_config['type']} {prop_config['guid']} Name {prop_config['name']}"
                expand_queries.append(f"singleValueExtendedProperties($filter=id eq '{prop_id}')")
            
            expand_query = ",".join(expand_queries)
            endpoint = f"/me/messages/{message_id}?$expand={expand_query}"
            
            message = await self.connector.make_graph_request(endpoint, access_token)
            
            # Parse extended properties
            cos_props = {}
            extended_props = message.get("singleValueExtendedProperties", [])
            
            for ext_prop in extended_props:
                prop_id = ext_prop.get("id", "")
                value = ext_prop.get("value")
                
                # Find matching COS property
                for prop_name, prop_config in self.COS_PROPERTIES.items():
                    expected_id = f"{prop_config['type']} {prop_config['guid']} Name {prop_config['name']}"
                    if prop_id == expected_id:
                        cos_props[prop_name] = self._parse_property_value(prop_name, value)
                        break
            
            return cos_props
            
        except Exception as e:
            logger.error(f"Failed to get COS properties: {e}")
            return {}
    
    async def link_to_project(self, message_id: str, project_id: str, 
                             confidence: float = 1.0, provenance: str = "AI",
                             user_id: str = "default") -> bool:
        """Link an email to a project with metadata"""
        properties = {
            "COS.ProjectId": project_id,
            "COS.LinkedAt": datetime.utcnow().isoformat(),
            "COS.Confidence": confidence,
            "COS.Provenance": provenance
        }
        
        return await self.set_cos_properties(message_id, properties, user_id)
    
    async def link_to_tasks(self, message_id: str, task_ids: List[str], 
                           confidence: float = 1.0, provenance: str = "AI",
                           user_id: str = "default") -> bool:
        """Link an email to one or more tasks"""
        properties = {
            "COS.TaskIds": task_ids,
            "COS.LinkedAt": datetime.utcnow().isoformat(),
            "COS.Confidence": confidence,
            "COS.Provenance": provenance
        }
        
        return await self.set_cos_properties(message_id, properties, user_id)
    
    async def update_confidence(self, message_id: str, new_confidence: float,
                               user_id: str = "default") -> bool:
        """Update the confidence score for existing links"""
        properties = {
            "COS.Confidence": new_confidence,
            "COS.LinkedAt": datetime.utcnow().isoformat()
        }
        
        return await self.set_cos_properties(message_id, properties, user_id)
    
    async def search_by_project(self, project_id: str, user_id: str = "default") -> List[Dict]:
        """Search for emails linked to a specific project"""
        try:
            access_token = await self.auth_manager.get_valid_access_token(user_id)
            
            # Build filter query for project ID
            prop_config = self.COS_PROPERTIES["COS.ProjectId"]
            prop_id = f"{prop_config['type']} {prop_config['guid']} Name {prop_config['name']}"
            
            filter_query = f"singleValueExtendedProperties/Any(ep: ep/id eq '{prop_id}' and ep/value eq '{project_id}')"
            
            messages = await self.connector.get_messages(
                access_token=access_token,
                filter_query=filter_query,
                top=100
            )
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to search by project {project_id}: {e}")
            return []
    
    async def search_by_task(self, task_id: str, user_id: str = "default") -> List[Dict]:
        """Search for emails linked to a specific task"""
        try:
            access_token = await self.auth_manager.get_valid_access_token(user_id)
            
            # Build filter query for task ID (JSON array search)
            prop_config = self.COS_PROPERTIES["COS.TaskIds"]
            prop_id = f"{prop_config['type']} {prop_config['guid']} Name {prop_config['name']}"
            
            # Note: This is a simplified search - Graph API has limitations with JSON array searches
            filter_query = f"singleValueExtendedProperties/Any(ep: ep/id eq '{prop_id}' and contains(ep/value, '{task_id}'))"
            
            messages = await self.connector.get_messages(
                access_token=access_token,
                filter_query=filter_query,
                top=100
            )
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to search by task {task_id}: {e}")
            return []
    
    async def get_unprocessed_emails(self, user_id: str = "default") -> List[Dict]:
        """Get emails that haven't been processed by COS yet"""
        try:
            access_token = await self.auth_manager.get_valid_access_token(user_id)
            
            # Get recent emails that don't have COS.LinkedAt property
            prop_config = self.COS_PROPERTIES["COS.LinkedAt"]
            prop_id = f"{prop_config['type']} {prop_config['guid']} Name {prop_config['name']}"
            
            # Filter for emails without the LinkedAt property
            filter_query = f"not singleValueExtendedProperties/Any(ep: ep/id eq '{prop_id}')"
            
            messages = await self.connector.get_messages(
                access_token=access_token,
                filter_query=filter_query,
                top=50
            )
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get unprocessed emails: {e}")
            return []
    
    def _format_property_value(self, prop_name: str, value: Any) -> Optional[str]:
        """Format property value for Graph API"""
        prop_type = self.COS_PROPERTIES[prop_name]["type"]
        
        if value is None:
            return None
        
        try:
            if prop_type == "String":
                return str(value)
            elif prop_type == "StringArray":
                if isinstance(value, list):
                    return json.dumps(value)
                else:
                    return json.dumps([str(value)])
            elif prop_type == "Double":
                return str(float(value))
            elif prop_type == "SystemTime":
                if isinstance(value, datetime):
                    return value.isoformat() + "Z"
                else:
                    return str(value)
            else:
                return str(value)
                
        except Exception as e:
            logger.error(f"Failed to format property {prop_name}: {e}")
            return None
    
    def _parse_property_value(self, prop_name: str, value: str) -> Any:
        """Parse property value from Graph API"""
        prop_type = self.COS_PROPERTIES[prop_name]["type"]
        
        if value is None:
            return None
        
        try:
            if prop_type == "String":
                return value
            elif prop_type == "StringArray":
                return json.loads(value)
            elif prop_type == "Double":
                return float(value)
            elif prop_type == "SystemTime":
                return datetime.fromisoformat(value.replace("Z", ""))
            else:
                return value
                
        except Exception as e:
            logger.error(f"Failed to parse property {prop_name}: {e}")
            return value