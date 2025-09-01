"""
Email Intelligence Service for analyzing and processing emails with AI.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class EmailIntelligenceService:
    """Service for AI-powered email analysis and intelligence"""
    
    def __init__(self, claude_client):
        """Initialize with Claude client for AI processing"""
        self.claude_client = claude_client
        
    async def analyze_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single email for insights, sentiment, and actions"""
        try:
            analysis = {
                'priority': 'medium',
                'sentiment': 'neutral',
                'action_required': False,
                'suggested_actions': [],
                'key_topics': [],
                'urgency_score': 0.5,
                'confidence': 0.8
            }
            
            # Basic priority assessment based on subject and sender
            subject = email_data.get('subject', '').lower()
            if any(word in subject for word in ['urgent', 'asap', 'immediate']):
                analysis['priority'] = 'high'
                analysis['urgency_score'] = 0.9
            elif any(word in subject for word in ['fyi', 'info', 'update']):
                analysis['priority'] = 'low'
                analysis['urgency_score'] = 0.2
                
            # Basic action detection
            if any(word in subject for word in ['action', 'request', 'please', 'need']):
                analysis['action_required'] = True
                analysis['suggested_actions'] = ['review_and_respond']
                
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze email: {e}")
            return {
                'priority': 'medium',
                'sentiment': 'neutral', 
                'action_required': False,
                'suggested_actions': [],
                'key_topics': [],
                'urgency_score': 0.5,
                'confidence': 0.5,
                'error': str(e)
            }
    
    async def analyze_email_batch(self, emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze multiple emails in batch"""
        results = []
        for email in emails:
            analysis = await self.analyze_email(email)
            results.append({
                'email_id': email.get('id'),
                'analysis': analysis
            })
        return results
    
    async def suggest_email_actions(self, email_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Suggest actions for an email based on content and context"""
        try:
            actions = []
            subject = email_data.get('subject', '').lower()
            sender = email_data.get('sender_name', '').lower()
            
            # Basic action suggestions
            if 'meeting' in subject or 'calendar' in subject:
                actions.append({
                    'type': 'schedule',
                    'description': 'Schedule meeting or add to calendar',
                    'confidence': 0.8
                })
                
            if any(word in subject for word in ['task', 'todo', 'action']):
                actions.append({
                    'type': 'create_task',
                    'description': 'Create task from email content',
                    'confidence': 0.7
                })
                
            if any(word in subject for word in ['reply', 'response', 'answer']):
                actions.append({
                    'type': 'reply',
                    'description': 'Reply required',
                    'confidence': 0.9
                })
            else:
                actions.append({
                    'type': 'archive',
                    'description': 'Archive for reference',
                    'confidence': 0.6
                })
                
            return actions
            
        except Exception as e:
            logger.error(f"Failed to suggest email actions: {e}")
            return [{'type': 'review', 'description': 'Review manually', 'confidence': 0.5}]
    
    async def extract_tasks_from_email(self, email_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract actionable tasks from email content"""
        try:
            tasks = []
            body = email_data.get('body_content', '') or email_data.get('body_preview', '')
            
            # Simple task detection patterns
            task_indicators = ['please', 'could you', 'can you', 'need to', 'should', 'must']
            
            if any(indicator in body.lower() for indicator in task_indicators):
                tasks.append({
                    'title': f"Follow up on: {email_data.get('subject', 'Email')}",
                    'description': email_data.get('body_preview', ''),
                    'priority': 'medium',
                    'due_date': None,
                    'source': 'email',
                    'source_id': email_data.get('id')
                })
                
            return tasks
            
        except Exception as e:
            logger.error(f"Failed to extract tasks from email: {e}")
            return []
    
    def categorize_email(self, email_data: Dict[str, Any]) -> str:
        """Categorize email into GTD-style categories"""
        try:
            subject = email_data.get('subject', '').lower()
            sender = email_data.get('sender_name', '').lower()
            
            # Action required
            if any(word in subject for word in ['action', 'request', 'please', 'urgent', 'asap']):
                return 'COS_Actions'
                
            # Delegated/Assigned
            if any(word in subject for word in ['assigned', 'delegated', 'cc:', 'fyi']):
                return 'COS_Assigned'
                
            # Read later
            if any(word in subject for word in ['newsletter', 'update', 'digest', 'report']):
                return 'COS_ReadLater'
                
            # Reference
            if any(word in subject for word in ['reference', 'info', 'documentation']):
                return 'COS_Reference'
                
            # Default to actions for now
            return 'COS_Actions'
            
        except Exception as e:
            logger.error(f"Failed to categorize email: {e}")
            return 'COS_Actions'