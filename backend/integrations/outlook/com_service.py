"""
Pure COM-only Outlook service for Chief of Staff.
This service exclusively uses COM methods to ensure COS properties are properly loaded.
"""
import logging
from typing import Dict, List, Optional, Any
import asyncio
import json
from datetime import datetime

from .com_connector import OutlookCOMConnector, COM_AVAILABLE

logger = logging.getLogger(__name__)


class OutlookCOMService:
    """Pure COM-only Outlook service - no Graph API contamination"""
    
    def __init__(self):
        """Initialize COM service with intelligence integration"""
        self.com_connector = OutlookCOMConnector() if COM_AVAILABLE else None
        self._connected = False
        self._connection_method = None
        
        # Will be injected by email_triage agent
        self.intelligence_service = None
        
    def connect(self) -> Dict[str, Any]:
        """Connect to Outlook via COM only"""
        if not COM_AVAILABLE:
            logger.error("COM not available - install pywin32: pip install pywin32")
            return {
                "connected": False,
                "method": None,
                "message": "COM not available - install pywin32",
                "account_info": None
            }
            
        if not self.com_connector:
            logger.error("COM connector not initialized")
            return {
                "connected": False,
                "method": None, 
                "message": "COM connector initialization failed",
                "account_info": None
            }
        
        # Attempt COM connection
        if self.com_connector.connect():
            self._connected = True
            self._connection_method = "com"
            account_info = self.com_connector.get_account_info()
            
            logger.info("✅ Connected to Outlook via COM")
            return {
                "connected": True,
                "method": "com",
                "message": "Connected to local Outlook application",
                "account_info": account_info
            }
        else:
            logger.error("❌ Failed to connect to Outlook via COM")
            return {
                "connected": False,
                "method": None,
                "message": "Failed to connect - ensure Outlook is running",
                "account_info": None
            }
    
    def is_connected(self) -> bool:
        """Check if connected to Outlook"""
        return self._connected and self.com_connector and self.com_connector.is_connected()
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get current connection information"""
        if not self.is_connected():
            return {"connected": False, "method": None}
            
        return {
            "connected": True,
            "method": self._connection_method,
            "account_info": self.com_connector.get_account_info() if self.com_connector else None
        }
    
    def get_recent_emails(self, folder_name: str = "Inbox", limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent emails using ONLY the legacy COM method.
        This ensures COS properties are properly loaded.
        """
        if not self.is_connected():
            logger.error("Not connected to Outlook - call connect() first")
            return []
        
        try:
            logger.info(f"📧 Loading {limit} emails from {folder_name} using COM legacy method")
            
            # ONLY use legacy method - this is critical for COS property loading
            emails = self.com_connector._get_messages_legacy(folder_name, limit)
            
            if emails:
                logger.info(f"✅ Successfully loaded {len(emails)} emails with COS properties")
                
                # Log sample of COS properties for debugging
                for i, email in enumerate(emails[:3]):
                    analysis = email.get('analysis')
                    if analysis:
                        logger.info(f"Email {i+1} analysis: priority={analysis.get('priority')}, tone={analysis.get('tone')}, urgency={analysis.get('urgency')}")
                    else:
                        logger.info(f"Email {i+1}: No analysis data found")
                
                return emails
            else:
                logger.warning(f"No emails returned from {folder_name}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Failed to load emails: {e}")
            return []
    
    def get_recent_emails_without_analysis(self, folder_name: str = "Inbox", limit: int = 10) -> List[Dict[str, Any]]:
        """
        Load emails WITHOUT automatic AI analysis.
        Only loads existing COS properties from Outlook. Analysis is on-demand only.
        """
        if not self.is_connected():
            logger.error("Not connected to Outlook")
            return []
            
        # Get emails using COM legacy method - this loads existing COS properties only
        emails = self.get_recent_emails(folder_name, limit)
        
        if not emails:
            return []
        
        logger.info(f"✅ Loaded {len(emails)} emails without analysis (existing COS properties only)")
        return emails
    
    async def analyze_single_email(self, email_id: str, force_reanalysis: bool = True, db=None) -> Dict[str, Any]:
        """
        Analyze a single email on-demand by email ID.
        This is called when user explicitly requests analysis.
        
        Args:
            email_id: The Outlook email ID
            force_reanalysis: If True, forces new analysis even if existing analysis exists
        """
        logger.info(f"🔄 [ANALYZE_SINGLE] Starting analysis for email_id: {email_id}")
        
        if not self.is_connected():
            logger.error(f"❌ [ANALYZE_SINGLE] Not connected to Outlook for email_id: {email_id}")
            return {}
            
        try:
            logger.info(f"🔍 [ANALYZE_SINGLE] Getting Outlook item by ID: {email_id}")
            
            # Get the specific email by ID
            outlook_item = self.com_connector._get_item_by_id(email_id)
            if not outlook_item:
                logger.error(f"❌ [ANALYZE_SINGLE] Could not find email with ID: {email_id}")
                return {}
            
            logger.info(f"✅ [ANALYZE_SINGLE] Found Outlook item for: {email_id}")
            
            # Extract email data using schema
            logger.info(f"🔄 [ANALYZE_SINGLE] Extracting email data from COM object... (skip_analysis: {force_reanalysis})")
            from schemas.email_schema import create_email_from_com, email_to_dict
            email_schema = create_email_from_com(outlook_item, skip_analysis=force_reanalysis)
            email_data = email_to_dict(email_schema)
            
            subject = email_data.get('subject', 'Unknown')[:50]
            logger.info(f"✅ [ANALYZE_SINGLE] Email data extracted. Subject: '{subject}', ID: {email_id}")
            
            # Generate analysis if needed
            logger.info(f"🤖 [ANALYZE_SINGLE] Calling _ensure_email_analysis for: {subject} (force_reanalysis: {force_reanalysis})")
            processed_email = await self._ensure_email_analysis(email_data, force_reanalysis=force_reanalysis, db=db)
            
            logger.info(f"✅ [ANALYZE_SINGLE] Analysis completed for: {subject}")
            return processed_email
            
        except Exception as e:
            logger.error(f"❌ [ANALYZE_SINGLE] Failed to analyze single email {email_id}: {e}")
            import traceback
            logger.error(f"❌ [ANALYZE_SINGLE] Traceback: {traceback.format_exc()}")
            return {}
    
    async def _ensure_email_analysis(self, email_data: Dict[str, Any], force_reanalysis: bool = False, db=None) -> Dict[str, Any]:
        """
        Ensure an email has AI analysis data.
        If analysis is missing, generate it and save to Outlook.
        
        Args:
            email_data: Email data dictionary
            force_reanalysis: If True, forces new analysis even if existing analysis exists
        """
        subject = email_data.get('subject', 'Unknown')[:50]
        email_id = email_data.get('id', 'Unknown')
        logger.info(f"🔄 [ENSURE_ANALYSIS] Starting analysis check for '{subject}' (ID: {email_id})")
        
        analysis = email_data.get('analysis')
        logger.info(f"🔍 [ENSURE_ANALYSIS] Current analysis data: {analysis}")
        logger.info(f"🔧 [ENSURE_ANALYSIS] Force reanalysis flag: {force_reanalysis}")
        
        # If analysis exists and is complete, return as-is (unless forced reanalysis)
        if analysis and isinstance(analysis, dict) and analysis.get('priority') and not force_reanalysis:
            logger.info(f"✅ [ENSURE_ANALYSIS] Email already has analysis: '{subject}' - Priority: {analysis.get('priority')}")
            return email_data
        
        if force_reanalysis:
            logger.info(f"🔄 [ENSURE_ANALYSIS] FORCE REANALYSIS requested for '{subject}' - generating new analysis regardless of existing data")
        else:
            logger.info(f"🔄 [ENSURE_ANALYSIS] Analysis missing or incomplete for '{subject}', generating new analysis...")
        
        # Generate analysis if intelligence service is available
        if self.intelligence_service:
            try:
                logger.info(f"🤖 [ENSURE_ANALYSIS] Intelligence service available, calling analyze_email for: '{subject}'")
                
                # Generate AI analysis with timeout protection
                logger.info(f"🔄 [ENSURE_ANALYSIS] About to call intelligence_service.analyze_email() with timeout...")
                try:
                    # Add 45 second timeout for the AI analysis call
                    new_analysis = await asyncio.wait_for(
                        self.intelligence_service.analyze_email(email_data, db=db, force_reanalysis=force_reanalysis), 
                        timeout=45.0
                    )
                    logger.info(f"✅ [ENSURE_ANALYSIS] Intelligence service returned: {new_analysis}")
                    
                except asyncio.TimeoutError:
                    logger.error(f"❌ [ENSURE_ANALYSIS] Intelligence service timed out after 45 seconds for '{subject}'")
                    # Set fallback analysis for timeout
                    email_data['analysis'] = {
                        'priority': 'MEDIUM',
                        'tone': 'PROFESSIONAL', 
                        'urgency': 'MEDIUM',
                        'summary': 'Analysis timed out - manual review recommended',
                        'confidence': 0.3,
                        'error': 'Analysis timeout'
                    }
                    logger.info(f"✅ [ENSURE_ANALYSIS] Using timeout fallback analysis")
                    return email_data
                
                if new_analysis:
                    logger.info(f"🔄 [ENSURE_ANALYSIS] Updating email data with new analysis...")
                    # Update email data with new analysis
                    email_data['analysis'] = new_analysis
                    
                    # Save analysis back to Outlook as COS properties
                    logger.info(f"🔄 [ENSURE_ANALYSIS] Saving analysis to Outlook...")
                    await self._save_analysis_to_outlook(email_data['id'], new_analysis)
                    
                    logger.info(f"✅ [ENSURE_ANALYSIS] Analysis complete: priority={new_analysis.get('priority')}, tone={new_analysis.get('tone')}")
                else:
                    logger.warning(f"⚠️ [ENSURE_ANALYSIS] Analysis service returned empty result for '{subject}'")
                    
            except Exception as e:
                logger.error(f"❌ [ENSURE_ANALYSIS] Failed to generate analysis for '{subject}': {e}")
                import traceback
                logger.error(f"❌ [ENSURE_ANALYSIS] Traceback: {traceback.format_exc()}")
                # Set fallback analysis
                email_data['analysis'] = {
                    'priority': 'MEDIUM',
                    'tone': 'PROFESSIONAL', 
                    'urgency': 'MEDIUM',
                    'summary': 'Analysis unavailable',
                    'confidence': 0.5
                }
        else:
            logger.warning(f"⚠️ [ENSURE_ANALYSIS] Intelligence service not available for '{subject}' - cannot generate analysis")
        
        logger.info(f"✅ [ENSURE_ANALYSIS] Returning processed email for '{subject}'")
        return email_data
    
    async def _save_analysis_to_outlook(self, email_id: str, analysis: Dict[str, Any]) -> bool:
        """
        Save AI analysis back to Outlook as COS properties.
        This ensures persistence across sessions.
        """
        if not self.is_connected():
            return False
            
        try:
            # Get the Outlook item by ID
            outlook_item = self.com_connector._get_item_by_id(email_id)
            if not outlook_item:
                logger.error(f"Could not find Outlook item with ID: {email_id}")
                return False
            
            # Save analysis as COS properties
            import json
            suggested_actions_json = ""
            if analysis.get('suggested_actions'):
                try:
                    suggested_actions_json = json.dumps(analysis.get('suggested_actions'))
                except Exception as e:
                    logger.warning(f"Failed to serialize suggested_actions: {e}")
            
            success = self.com_connector._save_cos_properties(outlook_item, {
                "COS.Priority": analysis.get('priority', 'MEDIUM'),
                "COS.Tone": analysis.get('tone', 'PROFESSIONAL'),
                "COS.Urgency": analysis.get('urgency', 'MEDIUM'),
                "COS.Summary": analysis.get('summary', ''),
                "COS.AnalysisConfidence": analysis.get('confidence', 0.8),
                "COS.SuggestedActions": suggested_actions_json
            })
            
            if success:
                logger.info(f"✅ Saved analysis to Outlook for: {email_id}")
            else:
                logger.warning(f"⚠️ Failed to save analysis to Outlook for: {email_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error saving analysis to Outlook: {e}")
            return False
    
    def get_folders(self) -> List[Dict[str, Any]]:
        """Get list of mail folders"""
        if not self.is_connected():
            return []
        
        try:
            return self.com_connector.get_folders()
        except Exception as e:
            logger.error(f"Failed to get folders: {e}")
            return []
    
    def move_email(self, email_id: str, target_folder: str) -> bool:
        """Move email to target folder"""
        if not self.is_connected():
            return False
        
        try:
            return self.com_connector.move_email(email_id, target_folder)
        except Exception as e:
            logger.error(f"Failed to move email: {e}")
            return False
    
    def create_folder(self, folder_name: str, parent_folder: str = "Inbox") -> bool:
        """Create a new mail folder"""
        if not self.is_connected():
            return False
        
        try:
            return self.com_connector.create_folder(folder_name, parent_folder)
        except Exception as e:
            logger.error(f"Failed to create folder: {e}")
            return False
    
    def setup_gtd_folders(self) -> Dict[str, bool]:
        """Set up GTD-style folders for Chief of Staff"""
        if not self.is_connected():
            return {}
        
        gtd_folders = [
            "COS_Actions",
            "COS_Assigned", 
            "COS_ReadLater",
            "COS_Reference",
            "COS_Archive"
        ]
        
        results = {}
        for folder_name in gtd_folders:
            try:
                success = self.create_folder(folder_name, "Inbox")
                results[folder_name] = success
                logger.info(f"{'✅' if success else '❌'} GTD folder: {folder_name}")
            except Exception as e:
                logger.error(f"Failed to create GTD folder {folder_name}: {e}")
                results[folder_name] = False
        
        return results
    
    def get_email_details(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed email information for task extraction"""
        if not self.is_connected():
            logger.error("Cannot get email details - not connected to Outlook")
            return None
        
        try:
            # Get the Outlook item
            outlook_item = self.com_connector._get_item_by_id(email_id)
            if not outlook_item:
                logger.error(f"Could not find email with ID: {email_id}")
                return None
            
            # Extract email details for task suggestion
            email_data = {
                'id': email_id,
                'subject': getattr(outlook_item, 'Subject', '') or '',
                'sender': getattr(outlook_item, 'SenderName', '') or '',
                'sender_email': getattr(outlook_item, 'SenderEmailAddress', '') or '',
                'sender_name': getattr(outlook_item, 'SenderName', '') or '',
                'body': getattr(outlook_item, 'Body', '') or '',
                'body_content': getattr(outlook_item, 'Body', '') or '',
                'body_preview': getattr(outlook_item, 'Body', '')[:500] if getattr(outlook_item, 'Body', '') else '',
                'received_time': getattr(outlook_item, 'ReceivedTime', None),
                'date': str(getattr(outlook_item, 'ReceivedTime', '')),
                'importance': getattr(outlook_item, 'Importance', 1),  # 0=Low, 1=Normal, 2=High
                'has_attachments': getattr(outlook_item, 'Attachments', []) and len(getattr(outlook_item, 'Attachments', [])) > 0
            }
            
            # Get any existing AI analysis from COS properties
            try:
                cos_props = self.com_connector._load_cos_properties(outlook_item)
                if 'AIAnalysis' in cos_props:
                    import json
                    email_data['analysis'] = json.loads(cos_props['AIAnalysis'])
                else:
                    email_data['analysis'] = {}
            except Exception as e:
                logger.warning(f"Could not load AI analysis from COS properties: {e}")
                email_data['analysis'] = {}
            
            logger.info(f"📧 Retrieved email details for task extraction: {email_data['subject'][:50]}")
            return email_data
            
        except Exception as e:
            logger.error(f"❌ Failed to get email details for {email_id}: {e}")
            return None