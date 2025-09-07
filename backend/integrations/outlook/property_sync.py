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
                outlook_item.UserProperties.Add("COS.ProjectId", 1).Value = str(email_schema.project_id)
            
            if hasattr(email_schema, 'confidence') and email_schema.confidence:
                outlook_item.UserProperties.Add("COS.Confidence", 5).Value = float(email_schema.confidence)
            
            if hasattr(email_schema, 'provenance') and email_schema.provenance:
                outlook_item.UserProperties.Add("COS.Provenance", 1).Value = str(email_schema.provenance)
            
            # Store AI analysis results if available
            if hasattr(email_schema, 'analysis') and email_schema.analysis:
                analysis = email_schema.analysis
                
                # Store priority, tone, urgency as separate properties
                if hasattr(analysis, 'priority') and analysis.priority:
                    outlook_item.UserProperties.Add("COS.Priority", 1).Value = str(analysis.priority)
                elif isinstance(analysis, dict) and 'priority' in analysis:
                    outlook_item.UserProperties.Add("COS.Priority", 1).Value = str(analysis['priority'])
                    
                if hasattr(analysis, 'tone') and analysis.tone:
                    outlook_item.UserProperties.Add("COS.Tone", 1).Value = str(analysis.tone)
                elif isinstance(analysis, dict) and 'tone' in analysis:
                    outlook_item.UserProperties.Add("COS.Tone", 1).Value = str(analysis['tone'])
                    
                if hasattr(analysis, 'urgency') and analysis.urgency:
                    outlook_item.UserProperties.Add("COS.Urgency", 1).Value = str(analysis.urgency)
                elif isinstance(analysis, dict) and 'urgency' in analysis:
                    outlook_item.UserProperties.Add("COS.Urgency", 1).Value = str(analysis['urgency'])
                    
                # Store summary as text property
                if hasattr(analysis, 'summary') and analysis.summary:
                    outlook_item.UserProperties.Add("COS.Summary", 1).Value = str(analysis.summary)
                elif isinstance(analysis, dict) and 'summary' in analysis:
                    outlook_item.UserProperties.Add("COS.Summary", 1).Value = str(analysis['summary'])
                    
                # Store analysis confidence
                if hasattr(analysis, 'confidence') and analysis.confidence:
                    outlook_item.UserProperties.Add("COS.AnalysisConfidence", 5).Value = float(analysis.confidence)
                elif isinstance(analysis, dict) and 'confidence' in analysis:
                    outlook_item.UserProperties.Add("COS.AnalysisConfidence", 5).Value = float(analysis['confidence'])
                    
                # Store suggested actions as JSON for future retrieval and tracking
                if hasattr(analysis, 'suggested_actions') and analysis.suggested_actions:
                    import json
                    outlook_item.UserProperties.Add("COS.SuggestedActions", 1).Value = json.dumps(analysis.suggested_actions)
                elif isinstance(analysis, dict) and 'suggested_actions' in analysis:
                    import json
                    outlook_item.UserProperties.Add("COS.SuggestedActions", 1).Value = json.dumps(analysis['suggested_actions'])
            
            # Set processing timestamp
            outlook_item.UserProperties.Add("COS.ProcessedAt", 7).Value = datetime.utcnow()
            
            outlook_item.Save()
            logger.info("Successfully saved COS properties to Outlook item")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write COS properties to Outlook: {e}")
            return False
    
    def read_cos_data_from_outlook(self, outlook_item) -> Dict[str, Any]:
        """Read COS data from Outlook item custom properties"""
        cos_data = {}
        try:
            if not hasattr(outlook_item, 'UserProperties'):
                logger.debug("Outlook item has no UserProperties")
                return cos_data
            
            user_props = outlook_item.UserProperties
            prop_count = getattr(user_props, 'Count', 0)
            logger.debug(f"Reading COS properties from {prop_count} user properties")
            
            if prop_count == 0:
                return cos_data
            
            # Try direct iteration first
            try:
                for prop in user_props:
                    try:
                        prop_name = getattr(prop, 'Name', '')
                        if prop_name and prop_name.startswith("COS."):
                            prop_value = getattr(prop, 'Value', None)
                            cos_data[prop_name] = prop_value
                            logger.debug(f"Read COS property: {prop_name} = {prop_value}")
                    except Exception as e:
                        logger.debug(f"Failed to read individual property: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Direct iteration failed, trying indexed access: {e}")
                
                # Fallback to indexed access
                try:
                    for i in range(1, prop_count + 1):
                        try:
                            prop = user_props.Item(i)
                            prop_name = getattr(prop, 'Name', '')
                            if prop_name and prop_name.startswith("COS."):
                                prop_value = getattr(prop, 'Value', None)
                                cos_data[prop_name] = prop_value
                                logger.debug(f"Read COS property (indexed): {prop_name} = {prop_value}")
                        except Exception as e:
                            logger.debug(f"Failed to read property {i}: {e}")
                            continue
                except Exception as e:
                    logger.error(f"Indexed access also failed: {e}")
                    
            logger.info(f"Successfully read {len(cos_data)} COS properties from Outlook")
                    
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
            
        # Reconstruct analysis data if available
        analysis_data = {}
        if "COS.Priority" in cos_data:
            analysis_data["priority"] = cos_data["COS.Priority"]
        if "COS.Tone" in cos_data:
            analysis_data["tone"] = cos_data["COS.Tone"]
        if "COS.Urgency" in cos_data:
            analysis_data["urgency"] = cos_data["COS.Urgency"]
        if "COS.Summary" in cos_data:
            analysis_data["summary"] = cos_data["COS.Summary"]
        if "COS.AnalysisConfidence" in cos_data:
            analysis_data["confidence"] = cos_data["COS.AnalysisConfidence"]
            
        # Set analysis if we found any analysis data
        if analysis_data:
            email_schema.analysis = analysis_data
            logger.info(f"Loaded analysis from Outlook: Priority={analysis_data.get('priority', 'N/A')}, Tone={analysis_data.get('tone', 'N/A')}, Urgency={analysis_data.get('urgency', 'N/A')}")
            
        return email_schema
        
    except Exception as e:
        logger.error(f"Failed to load email with COS data: {e}")
        return None

def save_selected_action_to_outlook(outlook_item, action_type: str, action_data: dict = None) -> bool:
    """Save a user-selected action to Outlook for future training"""
    try:
        import json
        from datetime import datetime
        
        # Get existing selected actions or create new list
        selected_actions = []
        try:
            existing_prop = outlook_item.UserProperties.Find("COS.SelectedActions")
            if existing_prop and existing_prop.Value:
                selected_actions = json.loads(existing_prop.Value)
        except:
            selected_actions = []
        
        # Add new selected action with timestamp
        new_action = {
            "action_type": action_type,
            "selected_at": datetime.utcnow().isoformat(),
            "action_data": action_data or {}
        }
        
        selected_actions.append(new_action)
        
        # Keep only last 10 selections to avoid bloat
        selected_actions = selected_actions[-10:]
        
        # Save updated list to Outlook
        outlook_item.UserProperties.Add("COS.SelectedActions", 1).Value = json.dumps(selected_actions)
        outlook_item.Save()
        
        logger.info(f"✅ Saved user action selection: {action_type} to email COS properties")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to save selected action to Outlook: {e}")
        return False