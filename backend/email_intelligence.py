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
        
    async def analyze_email(self, email_data, db=None) -> Dict[str, Any]:
        """Analyze a single email for insights, priority, tone, urgency, and actions using Claude AI
        
        Args:
            email_data: Either a dict with email data or an email schema object
            db: Database session (optional, for compatibility)
        """
        try:
            # Handle both dict and schema object inputs
            if hasattr(email_data, 'subject'):
                # Schema object
                subject = email_data.subject or ''
                sender = email_data.sender_name or email_data.sender or ''
                body = email_data.body_content or email_data.body_preview or ''
            else:
                # Dict object
                subject = email_data.get('subject', '')
                sender = email_data.get('sender_name', '') or email_data.get('sender', '')
                body = email_data.get('body_content', '') or email_data.get('body_preview', '') or email_data.get('preview', '')
            
            # Create analysis prompt
            analysis_prompt = f"""
Analyze this email for priority, tone, urgency, and provide a thoughtful summary with action recommendations:

SUBJECT: {subject}
SENDER: {sender}
CONTENT: {body[:1500]}...

Please provide analysis in this exact JSON format:
{{
    "priority": "HIGH|MEDIUM|LOW",
    "tone": "PROFESSIONAL|CASUAL|URGENT|FRIENDLY|FORMAL|CONCERNED|POSITIVE|NEGATIVE",
    "urgency": "IMMEDIATE|HIGH|MEDIUM|LOW",
    "summary": "Brief 2-3 sentence summary of key points and context",
    "action_required": true/false,
    "suggested_actions": ["action1", "action2", "action3"],
    "key_topics": ["topic1", "topic2"],
    "confidence": 0.85,
    "reasoning": "Brief explanation of assessment rationale"
}}

Consider:
- Sender relationship and context
- Content urgency indicators
- Action requirements
- Professional tone assessment
- Time sensitivity
"""
            
            # Call Claude for analysis
            try:
                claude_response = await self.claude_client.generate_response("system/emailtriage", {}, analysis_prompt)
                
                # Parse Claude's JSON response
                import json
                # Extract JSON from response if wrapped in text
                response_text = claude_response.strip()
                if '```json' in response_text:
                    json_start = response_text.find('```json') + 7
                    json_end = response_text.find('```', json_start)
                    response_text = response_text[json_start:json_end].strip()
                elif response_text.startswith('```') and response_text.endswith('```'):
                    response_text = response_text[3:-3].strip()
                
                analysis = json.loads(response_text)
                
                # Ensure required fields and format
                analysis.setdefault('priority', 'MEDIUM')
                analysis.setdefault('tone', 'PROFESSIONAL')
                analysis.setdefault('urgency', 'MEDIUM')
                analysis.setdefault('summary', 'Email analysis completed')
                analysis.setdefault('action_required', False)
                analysis.setdefault('suggested_actions', [])
                analysis.setdefault('key_topics', [])
                analysis.setdefault('confidence', 0.8)
                analysis.setdefault('reasoning', 'AI analysis completed')
                
                # Normalize to uppercase for consistency
                analysis['priority'] = str(analysis['priority']).upper()
                analysis['tone'] = str(analysis['tone']).upper()
                analysis['urgency'] = str(analysis['urgency']).upper()
                
                logger.info(f"Email analysis completed for: {subject[:50]}")
                return analysis
                
            except Exception as claude_error:
                logger.error(f"Claude analysis failed: {claude_error}")
                # Fallback to basic analysis
                return await self._basic_email_analysis(email_data)
            
        except Exception as e:
            logger.error(f"Failed to analyze email: {e}")
            return {
                'priority': 'MEDIUM',
                'tone': 'PROFESSIONAL',
                'urgency': 'MEDIUM',
                'summary': 'Email analysis failed',
                'action_required': False,
                'suggested_actions': [],
                'key_topics': [],
                'confidence': 0.5,
                'reasoning': f'Analysis error: {str(e)}',
                'error': str(e)
            }
    
    async def _basic_email_analysis(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback basic analysis when Claude is unavailable"""
        subject = email_data.get('subject', '').lower()
        
        # Basic priority assessment
        priority = 'MEDIUM'
        urgency = 'MEDIUM'
        tone = 'PROFESSIONAL'
        
        if any(word in subject for word in ['urgent', 'asap', 'immediate', 'critical', 'emergency']):
            priority = 'HIGH'
            urgency = 'IMMEDIATE'
            tone = 'URGENT'
        elif any(word in subject for word in ['fyi', 'info', 'update', 'newsletter']):
            priority = 'LOW'
            urgency = 'LOW'
            
        # Basic action detection
        action_required = any(word in subject for word in ['action', 'request', 'please', 'need', 'review', 'approve'])
        suggested_actions = ['review_and_respond'] if action_required else ['archive']
        
        return {
            'priority': priority,
            'tone': tone,
            'urgency': urgency,
            'summary': f'Basic analysis of email: {email_data.get("subject", "No subject")}',
            'action_required': action_required,
            'suggested_actions': suggested_actions,
            'key_topics': [],
            'confidence': 0.6,
            'reasoning': 'Fallback basic analysis used'
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