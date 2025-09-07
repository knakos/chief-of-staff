"""
Email Intelligence Service for analyzing and processing emails with AI.
Includes context-aware task creation from emails.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class EmailIntelligenceService:
    """Service for AI-powered email analysis and intelligence"""
    
    def __init__(self, claude_client):
        """Initialize with Claude client for AI processing"""
        self.claude_client = claude_client
        
    async def analyze_email(self, email_data, db=None, force_reanalysis: bool = False) -> Dict[str, Any]:
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
            
            # Create analysis prompt with cache-busting for force reanalysis
            cache_buster = ""
            if force_reanalysis:
                import time
                cache_buster = f"\n\n[FORCE_REANALYSIS_REQUEST_{int(time.time() * 1000)}]"
            
            # Get context-aware task suggestions if database is available
            context_info = ""
            task_suggestion = None
            if db:
                try:
                    global task_suggester
                    suggestion = await task_suggester.suggest_task_from_email(email_data, self.claude_client, db)
                    if suggestion.get('should_create_task', False):
                        task_suggestion = suggestion['task_suggestion']
                        area_name = task_suggestion.get('area_name', 'Unknown Area')
                        project_name = task_suggestion.get('project_name', 'Unknown Project')
                        context_info = f"""

TASK CONTEXT AVAILABLE:
- Suggested Area: {area_name}
- Suggested Project: {project_name}
- Suggested Title: {task_suggestion.get('title', 'N/A')}
- Suggested Due Date: {task_suggestion.get('due_date', 'N/A')}
- AI Rationale: {task_suggestion.get('rationale', 'N/A')}

Use this context to provide more specific task recommendations."""
                except Exception as e:
                    logger.warning(f"Context-aware task suggestion failed: {e}")
            
            analysis_prompt = f"""
Analyze this email for priority, tone, urgency, and provide structured action recommendations:

SUBJECT: {subject}
SENDER: {sender}
CONTENT: {body[:1500]}...{cache_buster}{context_info}

Please provide analysis in this exact JSON format:
{{
    "priority": "HIGH|MEDIUM|LOW",
    "tone": "PROFESSIONAL|CASUAL|URGENT|FRIENDLY|FORMAL|CONCERNED|POSITIVE|NEGATIVE",
    "urgency": "IMMEDIATE|HIGH|MEDIUM|LOW",
    "summary": "Brief 2-3 sentence summary of key points and context",
    "action_required": true/false,
    "suggested_actions": [
        {{
            "type": "archive",
            "action": "I can archive this email for you",
            "description": "This will help keep your inbox organized and clutter-free.",
            "confidence": 0.85
        }},
        {{
            "type": "create_task",
            "action": "I can create a task: '[specific task name]' for this",
            "description": "I'd recommend assigning this to [person/role] in your [project name] project. Would you like me to set this up?",
            "task_title": "specific task name",
            "project": "suggested project name", 
            "area": "suggested area name",
            "assignee": "suggested person or role",
            "due_date": "YYYY-MM-DD or null",
            "task_data": {{}},
            "confidence": 0.90
        }},
        {{
            "type": "flag_category",
            "action": "I can categorize this as [CATEGORY] for easy retrieval",
            "description": "This will help you find similar emails quickly when needed.",
            "category": "NEWS|PERSONAL_FINANCE|MEETINGS|PROJECTS|REPORTS|TRAVEL|LEGAL|CONTRACTS|TEAM_UPDATES|ADMINISTRATIVE",
            "confidence": 0.75
        }},
        {{
            "type": "save_later",
            "action": "I can add this to your reading list",
            "description": "This looks valuable but not urgent - perfect for when you have more time to review it properly.",
            "confidence": 0.80
        }},
        {{
            "type": "save_reference",
            "action": "I can save this to your reference folder",
            "description": "This contains useful information worth keeping for future access.",
            "confidence": 0.70
        }}
    ],
    "key_topics": ["topic1", "topic2"],
    "confidence": 0.85,
    "reasoning": "Brief explanation of assessment rationale"
}}

IMPORTANT RULES:
- The "action" field should contain the direct actionable phrase ("I can archive this email for you", "I can add this to your reading list") - NOT explanatory text
- Each suggested action must include a confidence score (0.0-1.0) indicating how relevant/appropriate the action is
- Write all actions in first person as an executive assistant would speak ("I can...", "I'll...", "Let me...")
- Prioritize the most valuable actions first based on email content and urgency
- ALWAYS include archiving as the final option in every recommendation set
- Include 2-4 other meaningful actions from: create_task, flag_category, save_later, save_reference
- Archive should always be the last action listed
- Use natural, conversational executive assistant language - be helpful and professional
- Be specific with task names, project suggestions, and assignee recommendations
- For categories, use: NEWS, PERSONAL_FINANCE, MEETINGS, PROJECTS, REPORTS, TRAVEL, LEGAL, CONTRACTS, TEAM_UPDATES, ADMINISTRATIVE (or create new ones as appropriate)
- For save_reference actions: NEVER suggest specific folder names - reference material always goes to the default reference folder automatically
- Consider sender relationship, content urgency, and action requirements
- Sound like a competent, proactive executive assistant who anticipates needs
- Confidence scores should reflect: sender importance (0.1), content relevance (0.3), urgency (0.2), action appropriateness (0.4)
"""
            
            # Call Claude for analysis
            try:
                logger.info(f"🤖 [EMAIL_INTELLIGENCE] About to call Claude API for email: {subject[:30]}")
                logger.info(f"🔄 [EMAIL_INTELLIGENCE] Calling claude_client.generate_response with prompt length: {len(analysis_prompt)} chars")
                
                claude_response = await self.claude_client.generate_response("system/emailtriage", {}, analysis_prompt)
                
                logger.info(f"✅ [EMAIL_INTELLIGENCE] Claude API responded with {len(str(claude_response))} characters")
                logger.info(f"🔍 [EMAIL_INTELLIGENCE] Claude response preview: {str(claude_response)[:200]}...")
                
                # Parse Claude's JSON response
                import json
                # Extract JSON from response if wrapped in text
                response_text = claude_response.strip()
                
                logger.info(f"🔄 [EMAIL_INTELLIGENCE] Raw Claude response: {response_text[:300]}...")
                
                # Try multiple JSON extraction methods
                json_text = None
                
                if '```json' in response_text:
                    json_start = response_text.find('```json') + 7
                    json_end = response_text.find('```', json_start)
                    if json_end > json_start:
                        json_text = response_text[json_start:json_end].strip()
                        logger.info(f"🔍 [EMAIL_INTELLIGENCE] Extracted JSON from ```json block")
                elif response_text.startswith('```') and response_text.endswith('```'):
                    json_text = response_text[3:-3].strip()
                    logger.info(f"🔍 [EMAIL_INTELLIGENCE] Extracted JSON from ``` block")
                else:
                    # Try to find JSON object within the text
                    json_start = response_text.find('{')
                    if json_start >= 0:
                        # Find matching closing brace
                        brace_count = 0
                        json_end = json_start
                        for i in range(json_start, len(response_text)):
                            if response_text[i] == '{':
                                brace_count += 1
                            elif response_text[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    json_end = i + 1
                                    break
                        
                        if json_end > json_start:
                            json_text = response_text[json_start:json_end]
                            logger.info(f"🔍 [EMAIL_INTELLIGENCE] Found JSON object in text at position {json_start}-{json_end}")
                
                if not json_text:
                    logger.error(f"❌ [EMAIL_INTELLIGENCE] Could not find JSON in response: {response_text}")
                    raise Exception("No valid JSON found in Claude response")
                
                logger.info(f"🔄 [EMAIL_INTELLIGENCE] Parsing JSON: {json_text[:200]}...")
                analysis = json.loads(json_text)
                logger.info(f"✅ [EMAIL_INTELLIGENCE] Successfully parsed JSON analysis")
                
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
                
                # Embed context-aware task data into create_task suggestions
                if task_suggestion and 'suggested_actions' in analysis:
                    for action in analysis['suggested_actions']:
                        if action.get('type') == 'create_task':
                            # Embed the full task data from our context-aware suggester
                            action['task_data'] = {
                                'title': task_suggestion.get('title', action.get('task_title', 'Untitled Task')),
                                'objective': task_suggestion.get('objective', ''),
                                'project_id': task_suggestion.get('project_id'),
                                'area_id': task_suggestion.get('area_id'),
                                'priority': task_suggestion.get('priority', 3),
                                'due_date': task_suggestion.get('due_date'),
                                'sponsor_email': task_suggestion.get('sponsor_email', ''),
                                'owner_email': task_suggestion.get('owner_email', ''),
                                'ai_reasoning': task_suggestion.get('rationale', '')
                            }
                            # Update the action text with specific details
                            action['task_title'] = task_suggestion.get('title')
                            action['project'] = task_suggestion.get('project_name')
                            action['area'] = task_suggestion.get('area_name')
                            action['due_date'] = task_suggestion.get('due_date')
                            logger.info(f"[SUCCESS] Embedded context-aware task data into email analysis")
                            break
                
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
    
    async def extract_tasks_from_email(self, email_data: Dict[str, Any], db=None) -> List[Dict[str, Any]]:
        """Extract actionable tasks from email content using context-aware AI"""
        try:
            # Use the global task suggester for intelligent task extraction
            global task_suggester
            
            if not db:
                logger.warning("⚠️ No database session provided, using basic task extraction")
                return await self._basic_task_extraction(email_data)
            
            # Get context-aware task suggestion
            suggestion = await task_suggester.suggest_task_from_email(email_data, self.claude_client, db)
            
            # If AI suggests creating a task, format it for the tasks system
            if suggestion.get('should_create_task', False) and 'task_suggestion' in suggestion:
                task_data = suggestion['task_suggestion']
                return [{
                    'title': task_data['title'],
                    'objective': task_data['objective'],
                    'priority': task_data['priority'],
                    'due_date': task_data['due_date'],
                    'sponsor_email': task_data['sponsor_email'],
                    'owner_email': task_data['owner_email'],
                    'project_id': task_data['project_id'],
                    'area_id': task_data['area_id'],
                    'source': 'email_ai_suggestion',
                    'source_id': email_data.get('id'),
                    'ai_reasoning': suggestion['reasoning'],
                    'ai_rationale': task_data['rationale']
                }]
            else:
                logger.info(f"📧 AI determined no task needed for email: {email_data.get('subject', 'No subject')[:50]} - {suggestion.get('reasoning', 'No reasoning provided')}")
                return []
                
        except Exception as e:
            logger.error(f"[ERROR] Context-aware task extraction failed: {e}")
            return await self._basic_task_extraction(email_data)
    
    async def _basic_task_extraction(self, email_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fallback basic task extraction when AI is unavailable"""
        try:
            tasks = []
            body = email_data.get('body_content', '') or email_data.get('body_preview', '')
            
            # Simple task detection patterns
            task_indicators = ['please', 'could you', 'can you', 'need to', 'should', 'must']
            
            if any(indicator in body.lower() for indicator in task_indicators):
                tasks.append({
                    'title': f"Follow up on: {email_data.get('subject', 'Email')}",
                    'objective': f"Review and respond to email from {email_data.get('sender_name', 'sender')}",
                    'priority': 3,
                    'due_date': None,
                    'sponsor_email': task_suggester.user_email,
                    'owner_email': task_suggester.user_email,
                    'project_id': None,
                    'area_id': None,
                    'source': 'email_basic_extraction',
                    'source_id': email_data.get('id'),
                    'ai_reasoning': 'Basic pattern matching detected action indicators',
                    'ai_rationale': 'Fallback extraction - manual review recommended'
                })
                
            return tasks
            
        except Exception as e:
            logger.error(f"[ERROR] Even basic task extraction failed: {e}")
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


class ContextAwareTaskSuggester:
    """Generate intelligent task suggestions from emails using full context."""
    
    def __init__(self):
        self.user_email = None
        
    def set_user_context(self, primary_email: str):
        """Set the primary user email from Outlook connection."""
        self.user_email = primary_email
        logger.info(f"🔧 Set user context: {primary_email}")
    
    async def get_task_creation_context(self, db: Session) -> Dict[str, Any]:
        """Gather comprehensive context for task creation suggestions."""
        try:
            from models import Area, Project, Task
            
            # Get available areas and projects
            areas_query = db.query(Area).filter(Area.status == 'active').all()
            projects_query = db.query(Project).filter(Project.status == 'active').all()
            
            # Build project context with workload info
            areas_context = []
            for area in areas_query:
                area_projects = []
                for project in projects_query:
                    if project.area_id == area.id:
                        # Get task counts for workload analysis
                        active_tasks = db.query(Task).filter(
                            Task.project_id == project.id,
                            Task.status.in_(['not_started', 'active'])
                        ).count()
                        
                        overdue_tasks = db.query(Task).filter(
                            Task.project_id == project.id,
                            Task.status.in_(['not_started', 'active']),
                            Task.due_date < datetime.utcnow()
                        ).count()
                        
                        area_projects.append({
                            'id': project.id,
                            'name': project.name,
                            'description': project.description,
                            'is_catch_all': project.is_catch_all,
                            'active_tasks': active_tasks,
                            'overdue_tasks': overdue_tasks,
                            'priority': project.priority
                        })
                
                areas_context.append({
                    'id': area.id,
                    'name': area.name,
                    'description': area.description,
                    'projects': area_projects
                })
            
            # Get recent task patterns for context
            recent_tasks = db.query(Task).filter(
                Task.created_at > datetime.utcnow() - timedelta(days=30)
            ).limit(20).all()
            
            task_patterns = []
            for task in recent_tasks:
                if task.project and task.project.area:
                    task_patterns.append({
                        'title': task.title,
                        'area': task.project.area.name,
                        'project': task.project.name,
                        'priority': task.priority,
                        'sponsor_email': task.sponsor_email,
                        'days_to_due': (task.due_date - task.created_at).days if task.due_date else None
                    })
            
            context = {
                'user_email': self.user_email,
                'areas_and_projects': areas_context,
                'recent_task_patterns': task_patterns,
                'current_date': datetime.utcnow().isoformat()
            }
            
            logger.info(f"📊 Generated task context: {len(areas_context)} areas, {len(task_patterns)} recent patterns")
            return context
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to get task creation context: {e}")
            return {
                'user_email': self.user_email,
                'areas_and_projects': [],
                'recent_task_patterns': [],
                'current_date': datetime.utcnow().isoformat()
            }
    
    async def suggest_task_from_email(self, email_data: Dict[str, Any], claude_client, db: Session) -> Dict[str, Any]:
        """Generate intelligent task suggestion from email using full context."""
        try:
            # Get comprehensive context
            context = await self.get_task_creation_context(db)
            
            # Prepare email information
            email_info = {
                'subject': email_data.get('subject', ''),
                'sender': email_data.get('sender', ''),
                'content': email_data.get('preview', '') or email_data.get('body', ''),
                'received_date': email_data.get('date', ''),
                'analysis': email_data.get('analysis', {})
            }
            
            # Create context-aware prompt
            prompt = f"""You are a Chief of Staff AI helping to create intelligent task suggestions from emails.

USER CONTEXT:
- Primary email: {context['user_email']}
- Current date: {context['current_date']}

EMAIL TO ANALYZE:
Subject: {email_info['subject']}
Sender: {email_info['sender']}
Content: {email_info['content'][:500]}...
Received: {email_info['received_date']}
AI Analysis: Priority={email_info['analysis'].get('priority', 'UNKNOWN')}, Tone={email_info['analysis'].get('tone', 'UNKNOWN')}, Urgency={email_info['analysis'].get('urgency', 'UNKNOWN')}

AVAILABLE AREAS & PROJECTS:
{self._format_projects_for_prompt(context['areas_and_projects'])}

RECENT TASK PATTERNS (for context):
{self._format_patterns_for_prompt(context['recent_task_patterns'])}

TASK: Analyze this email and suggest a comprehensive task creation if appropriate. Consider:
1. **Should this become a task?** (some emails are just informational)
2. **Best Area/Project fit** based on content, sender, and subject
3. **Smart due date** based on urgency, content keywords, and email analysis
4. **Appropriate priority** (1=highest, 5=lowest) based on sender relationship and urgency
5. **Task owner** (usually the user, but consider if delegation is appropriate)

Return your analysis as a JSON object:
{{
    "should_create_task": boolean,
    "reasoning": "Why this should/shouldn't become a task",
    "task_suggestion": {{
        "title": "Clear, actionable task title",
        "objective": "Specific outcome or goal to achieve",
        "area_id": "recommended area ID",
        "area_name": "area name for confirmation", 
        "project_id": "recommended project ID",
        "project_name": "project name for confirmation",
        "priority": number (1-5),
        "due_date": "YYYY-MM-DD or null",
        "sponsor_email": "{context['user_email']}",
        "owner_email": "who should do this work",
        "rationale": "Why this area/project/priority/date was chosen"
    }}
}}

Only suggest task creation for emails that require action. Informational emails, newsletters, automated reports, etc. should have should_create_task: false."""

            # Get AI suggestion
            response = await claude_client.generate_response("system/emailtriage", {}, prompt)
            
            # Parse response (assuming it returns JSON)
            import json
            try:
                # Extract JSON from response if needed
                response_text = response.strip()
                
                if '```json' in response_text:
                    json_start = response_text.find('```json') + 7
                    json_end = response_text.find('```', json_start)
                    if json_end > json_start:
                        json_text = response_text[json_start:json_end].strip()
                elif response_text.startswith('{'):
                    json_text = response_text
                else:
                    # Find JSON object within the text
                    json_start = response_text.find('{')
                    if json_start >= 0:
                        # Find matching closing brace
                        brace_count = 0
                        json_end = json_start
                        for i in range(json_start, len(response_text)):
                            if response_text[i] == '{':
                                brace_count += 1
                            elif response_text[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    json_end = i + 1
                                    break
                        json_text = response_text[json_start:json_end]
                    else:
                        raise Exception("No JSON found in response")
                
                suggestion = json.loads(json_text)
                logger.info(f"✅ Generated intelligent task suggestion for email: {email_info['subject'][:50]}")
                return suggestion
            except json.JSONDecodeError:
                logger.warning(f"⚠️ AI response was not valid JSON, using fallback")
                return self._fallback_suggestion(email_info, context)
                
        except Exception as e:
            logger.error(f"[ERROR] Failed to generate task suggestion: {e}")
            return self._fallback_suggestion(email_info, context)
    
    def _format_projects_for_prompt(self, areas_context: List[Dict]) -> str:
        """Format areas and projects for AI prompt."""
        formatted = []
        for area in areas_context:
            formatted.append(f"\n**{area['name']}** ({area['description']})")
            for project in area['projects']:
                catch_all = " [CATCH-ALL]" if project['is_catch_all'] else ""
                workload = f" (Active: {project['active_tasks']}, Overdue: {project['overdue_tasks']})"
                formatted.append(f"  - {project['name']}{catch_all}{workload}")
        return '\n'.join(formatted)
    
    def _format_patterns_for_prompt(self, patterns: List[Dict]) -> str:
        """Format recent task patterns for AI context."""
        if not patterns:
            return "No recent patterns available."
        
        formatted = []
        for pattern in patterns[:10]:  # Show last 10 patterns
            due_info = f", Due: {pattern['days_to_due']} days" if pattern['days_to_due'] else ""
            formatted.append(f"- '{pattern['title']}' → {pattern['area']}/{pattern['project']} (P{pattern['priority']}{due_info})")
        return '\n'.join(formatted)
    
    def _fallback_suggestion(self, email_info: Dict, context: Dict) -> Dict[str, Any]:
        """Generate basic fallback suggestion when AI fails."""
        # Find first available catch-all project
        catch_all_project = None
        for area in context['areas_and_projects']:
            for project in area['projects']:
                if project['is_catch_all']:
                    catch_all_project = {'area_id': area['id'], 'area_name': area['name'], 
                                       'project_id': project['id'], 'project_name': project['name']}
                    break
            if catch_all_project:
                break
        
        return {
            "should_create_task": True,
            "reasoning": "Fallback suggestion - manual review recommended",
            "task_suggestion": {
                "title": f"Review: {email_info['subject'][:50]}",
                "objective": "Review email and determine appropriate action",
                "area_id": catch_all_project['area_id'] if catch_all_project else None,
                "area_name": catch_all_project['area_name'] if catch_all_project else "Unknown",
                "project_id": catch_all_project['project_id'] if catch_all_project else None,
                "project_name": catch_all_project['project_name'] if catch_all_project else "Tasks",
                "priority": 3,
                "due_date": (datetime.utcnow() + timedelta(days=7)).strftime('%Y-%m-%d'),
                "sponsor_email": context['user_email'],
                "owner_email": context['user_email'],
                "rationale": "Fallback to catch-all project with 1-week due date"
            }
        }


# Global instances
task_suggester = ContextAwareTaskSuggester()