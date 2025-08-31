"""
Claude AI client with prompt loading from llm/prompts directory.
Handles all AI interactions for the Chief of Staff system.
"""
import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import asyncio
import time
from functools import lru_cache
import hashlib
from datetime import datetime
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

class ClaudeClient:
    """Claude AI client with prompt management"""
    
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.prompts_cache: Dict[str, str] = {}
        self.prompts_dir = Path(__file__).parent.parent / "llm" / "prompts"
        
        # Response cache with TTL
        self.response_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 300  # 5 minutes cache TTL
        
        # Initialize Anthropic client
        self.client = AsyncAnthropic(api_key=self.api_key) if self.api_key else None
        
        # Load all prompts on initialization
        self._load_all_prompts()
        logger.info(f"Loaded {len(self.prompts_cache)} prompts")
    
    def _load_all_prompts(self):
        """Load all prompt files into memory"""
        if not self.prompts_dir.exists():
            logger.error(f"Prompts directory not found: {self.prompts_dir}")
            raise FileNotFoundError(f"Prompts directory not found: {self.prompts_dir}")
        
        prompt_files = list(self.prompts_dir.glob("**/*.md"))
        
        for prompt_file in prompt_files:
            # Create key from relative path (e.g., "system/cos.md" -> "system/cos")
            relative_path = prompt_file.relative_to(self.prompts_dir)
            prompt_key = str(relative_path).replace(".md", "").replace("\\", "/")
            
            try:
                # Get file modification time
                mod_time = prompt_file.stat().st_mtime
                mod_datetime = datetime.fromtimestamp(mod_time)
                
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    # Add timestamp header to content
                    timestamp_str = mod_datetime.strftime('%Y-%m-%d %H:%M:%S')
                    timestamped_content = f"<!-- Last saved: {timestamp_str} -->\n{content}"
                    self.prompts_cache[prompt_key] = timestamped_content
                    
                    logger.info(f"Loaded prompt '{prompt_key}' (saved: {timestamp_str})")
                    
            except Exception as e:
                logger.error(f"Failed to load prompt {prompt_file}: {e}")
        
        logger.info(f"Loaded {len(self.prompts_cache)} prompts")
    
    # @lru_cache(maxsize=128)  # Temporarily disabled for debugging
    def get_prompt(self, prompt_key: str) -> str:
        """Get a prompt by key (e.g., 'system/cos' or 'tools/digest')"""
        # Force reload prompts to pick up changes during debugging
        self._load_all_prompts()
        
        if prompt_key not in self.prompts_cache:
            raise ValueError(f"Prompt not found: {prompt_key}. Available prompts: {list(self.prompts_cache.keys())}")
        
        return self.prompts_cache[prompt_key]
    
    async def generate_response(self, prompt_key: str, context: Dict[str, Any] = None, user_input: str = "") -> str:
        """Generate AI response using specified prompt with caching"""
        try:
            # Create cache key from inputs
            cache_key = self._create_cache_key(prompt_key, context, user_input)
            
            # Check cache first (temporarily disabled for debugging)
            # cached_response = self._get_cached_response(cache_key)
            # if cached_response:
            #     logger.info(f"Cache hit for prompt {prompt_key}")
            #     return cached_response
            
            system_prompt = self.get_prompt(prompt_key)
            logger.info(f"Using prompt for {prompt_key}: {system_prompt[:100]}...")
            
            # Use real Claude API if key available, otherwise fallback to mock
            if self.api_key and not os.getenv("USE_MOCK_RESPONSES", "").lower() == "true":
                logger.info(f"Calling Claude API with user input: {user_input}")
                response = await self._call_claude_api(system_prompt, context, user_input)
                logger.info(f"Claude API response: {response[:100]}...")
            else:
                logger.warning("Using mock response - no API key or USE_MOCK_RESPONSES=true")
                response = await self._mock_claude_response(prompt_key, context, user_input)
            
            # Cache the response
            self._cache_response(cache_key, response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating response with prompt {prompt_key}: {e}")
            return f"Error: Could not generate response. {str(e)}"
    
    def _create_cache_key(self, prompt_key: str, context: Dict[str, Any], user_input: str) -> str:
        """Create a cache key from the inputs"""
        # Create deterministic hash from inputs
        content = f"{prompt_key}:{context or ''}:{user_input}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_cached_response(self, cache_key: str) -> Optional[str]:
        """Get cached response if still valid"""
        if cache_key not in self.response_cache:
            return None
            
        cached = self.response_cache[cache_key]
        if time.time() - cached['timestamp'] > self.cache_ttl:
            # Cache expired
            del self.response_cache[cache_key]
            return None
            
        return cached['response']
    
    def _cache_response(self, cache_key: str, response: str):
        """Cache a response with timestamp"""
        self.response_cache[cache_key] = {
            'response': response,
            'timestamp': time.time()
        }
        
        # Clean up old cache entries (simple cleanup)
        if len(self.response_cache) > 1000:
            # Remove oldest 100 entries
            sorted_items = sorted(self.response_cache.items(), key=lambda x: x[1]['timestamp'])
            for key, _ in sorted_items[:100]:
                del self.response_cache[key]
    
    async def _call_claude_api(self, system_prompt: str, context: Dict[str, Any], user_input: str) -> str:
        """Make actual API call to Claude"""
        if not self.client:
            raise Exception("Claude client not initialized - missing API key")
        
        try:
            # Build the user message with context
            user_message = user_input
            if context:
                context_str = self._format_context_for_prompt(context)
                user_message = f"Context: {context_str}\n\nUser input: {user_input}"
            
            # Call Claude API
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0.7,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            raise Exception(f"Claude API call failed: {str(e)}")
    
    def _format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """Format context dictionary for inclusion in prompt"""
        if not context:
            return ""
        
        formatted_parts = []
        for key, value in context.items():
            if value is not None:
                formatted_parts.append(f"{key}: {value}")
        
        return "\n".join(formatted_parts)
    
    async def _mock_claude_response(self, prompt_key: str, context: Dict[str, Any], user_input: str) -> str:
        """Mock Claude responses for development with reduced delay"""
        # Simulate API delay (reduced for better performance)
        await asyncio.sleep(0.2)
        
        mock_responses = {
            "system/cos": self._mock_cos_response(user_input, context),
            "system/emailtriage": self._mock_email_triage_response(context),
            "system/summarizer": self._mock_summarizer_response(context),
            "system/writer": self._mock_writer_response(context),
            "tools/interview": self._mock_interview_response(context),
            "tools/digest": self._mock_digest_response(context),
        }
        
        return mock_responses.get(prompt_key, f"Mock response for {prompt_key}: {user_input}")
    
    def _mock_cos_response(self, user_input: str, context: Dict[str, Any]) -> str:
        """Mock Chief of Staff orchestrator response"""
        if "/plan" in user_input.lower():
            return """I'll help you plan your work. Based on your current context, here are some key areas to focus on:

1. **Email Processing** - You have 3 unread emails that may need action
2. **Project Updates** - 2 projects need status updates  
3. **Context Interview** - I have a brief question about your priorities

Would you like me to start with email triage or conduct the context interview?"""

        elif "/summarize" in user_input.lower():
            return """Here's a summary of your current work status:

**Active Projects**: 3 projects in progress
**Pending Tasks**: 7 tasks across all projects
**Recent Email Activity**: 12 emails processed today
**Priority Items**: 2 high-priority tasks due this week

**Key Focus Areas**:
- Project Alpha: Waiting for client feedback
- Task Management: 3 tasks overdue
- Email: 1 urgent response needed

Would you like me to dive deeper into any specific area?"""

        elif "/triage" in user_input.lower():
            return """Starting inbox triage...

**Processed 8 emails:**
- 3 moved to COS_Actions (require response)
- 2 moved to COS_Assigned (pending others)  
- 2 moved to COS_ReadLater (informational)
- 1 moved to COS_Archive (completed)

**Action Required:**
1. Email from John Smith - Project proposal review (Due: Tomorrow)
2. Meeting request from Sarah - Weekly sync confirmation needed
3. Budget approval request - Finance team needs response by Friday

Would you like me to draft responses for any of these?"""

        else:
            return f"""I understand you want help with: "{user_input}"

As your Chief of Staff, I can assist with:
- Planning and prioritizing your work
- Processing and organizing emails  
- Tracking projects and tasks
- Conducting brief context interviews to better understand your needs

What would you like to focus on first?"""
    
    def _mock_email_triage_response(self, context: Dict[str, Any]) -> str:
        """Mock email triage response"""
        return """Email triage completed. Recommended actions:
- Move to COS_Actions folder
- Tag with COS/Project-Alpha  
- Priority: High
- Suggested response: Schedule follow-up meeting"""
    
    def _mock_summarizer_response(self, context: Dict[str, Any]) -> str:
        """Mock summarizer response"""
        return """**Summary**: Client meeting recap with key decisions and next steps identified.

**Key Points**:
- Budget approved for Q2
- Timeline extended by 2 weeks
- New stakeholder added to project

**Extracted Tasks**:
1. Update project timeline
2. Notify team of budget approval
3. Schedule stakeholder onboarding"""
    
    def _mock_writer_response(self, context: Dict[str, Any]) -> str:
        """Mock writer response"""
        return """Subject: Project Alpha Update - Next Steps

Hi [Name],

Thank you for the productive discussion yesterday. I wanted to follow up on the key decisions and outline our next steps.

**Decisions Made:**
- Approved revised timeline with 2-week extension
- Budget increase approved for additional resources

**Next Steps:**
1. I'll update the project plan by Friday
2. Team notification meeting scheduled for Monday  
3. Resource allocation review next week

Please let me know if you have any questions or concerns.

Best regards,
[Your name]"""
    
    def _mock_interview_response(self, context: Dict[str, Any]) -> str:
        """Mock interview question generation"""
        questions = [
            "What's your biggest priority for this week?",
            "Which project would benefit most from additional focus?",
            "Are there any decisions you're waiting on from others?",
            "What information would help you work more effectively?"
        ]
        
        import random
        return random.choice(questions)
    
    def _mock_digest_response(self, context: Dict[str, Any]) -> str:
        """Mock digest generation"""
        return """# Daily Digest - Today's Focus

## Priority Items
- **Project Alpha**: Review client feedback (Due today)
- **Budget Planning**: Prepare Q2 forecast (Due Friday)

## Recent Activity  
- 8 emails processed and triaged
- 3 tasks completed yesterday
- 2 new project inquiries received

## Upcoming This Week
- Client presentation on Wednesday
- Team standup meetings (Tue, Thu)
- Quarterly planning session Friday

## Suggestions
Consider scheduling focused time for Project Alpha client feedback review - it's been pending for 3 days and is blocking next steps.

---
*Generated by your Chief of Staff assistant*"""

    async def extract_tasks_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract actionable tasks from text content with caching"""
        # Check cache first
        cache_key = f"extract_tasks:{hashlib.md5(text.encode()).hexdigest()}"
        cached = self._get_cached_response(cache_key)
        if cached:
            import json
            return json.loads(cached)
        
        # Mock task extraction (reduced delay)
        await asyncio.sleep(0.1)
        
        tasks = []
        action_words = ["review", "schedule", "update", "prepare", "send", "call", "meet", "analyze"]
        
        sentences = text.split('.')
        for sentence in sentences:
            sentence = sentence.strip().lower()
            if any(word in sentence for word in action_words) and len(sentence.split()) > 3:
                # Extract potential task
                task_title = sentence.capitalize()
                if len(task_title) > 100:
                    task_title = task_title[:97] + "..."
                
                tasks.append({
                    "title": task_title,
                    "confidence": 0.7,
                    "source": "text_extraction"
                })
        
        result = tasks[:5]  # Limit to 5 tasks
        
        # Cache the result
        import json
        self._cache_response(cache_key, json.dumps(result))
        
        return result
    
    async def suggest_project_links(self, content: str, existing_projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Suggest which projects this content might relate to"""
        # Mock project linking
        await asyncio.sleep(0.2)
        
        suggestions = []
        if existing_projects:
            # Simple mock - suggest first project with medium confidence
            suggestions.append({
                "project_id": existing_projects[0]["id"],
                "project_name": existing_projects[0]["name"],
                "confidence": 0.65,
                "rationale": "Keywords match project focus area"
            })
        
        return suggestions
    
    async def generate_email_summary(self, email_content: str, subject: str) -> Dict[str, Any]:
        """Generate summary and highlights for an email"""
        # Mock email summarization
        await asyncio.sleep(0.4)
        
        return {
            "summary": f"Email regarding {subject.lower()} with key updates and action items.",
            "highlights": [
                "Meeting scheduled for next week",
                "Budget approval required",
                "Timeline updated with new deadline"
            ],
            "sentiment": "neutral",
            "urgency": "medium"
        }
    
    async def generate_suggestions(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate actionable suggestions based on context"""
        # Mock suggestion generation
        await asyncio.sleep(0.3)
        
        suggestions = [
            {
                "action": "Schedule follow-up meeting",
                "confidence": 0.8,
                "rationale": "Email thread indicates next steps need coordination",
                "payload": {"duration": "30min", "type": "follow-up"}
            },
            {
                "action": "Move to COS_Actions folder", 
                "confidence": 0.9,
                "rationale": "Email contains clear action items requiring response",
                "payload": {"folder": "COS_Actions"}
            }
        ]
        
        return suggestions