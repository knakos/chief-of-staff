# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend Development
```bash
# Setup backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate | Linux/WSL: source .venv/bin/activate
.venv\Scripts\activate  
pip install -r requirements.txt

# Create environment file
copy .env.example .env  # Windows: copy | Linux: cp
# Edit .env to add your ANTHROPIC_API_KEY

# Initialize database with sample data
python init_db.py

# Start backend server (from project root)
./scripts/start_all.sh  # Linux/WSL
# Windows: 
cd backend
.venv\Scripts\activate
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8787 --reload

# Database optimization (run periodically)
python optimize_db.py

# Test backend setup
python test_setup.py  # Comprehensive setup validation

# Debug and testing scripts (in backend/)
python debug_email_extraction.py  # Debug email content extraction
python test_recipient_extraction.py  # Test email recipient parsing
python validate_complete_solution.py  # Validate system integration

# Rate limiting and performance testing
python -c "from claude_client import ClaudeClient; import asyncio; print('Testing rate limiting...'); asyncio.run(ClaudeClient()._apply_rate_limiting())"
```

### Frontend Development  
```bash
# Start Electron app (from project root)
npm install  # Install root dependencies first
npm run dev  # Runs electron with preload.js and main.js

# Alternative: PowerShell script on Windows
./scripts/start-electron.ps1

# For development, typically run both:
# Terminal 1: Backend server (port 8787)
# Terminal 2: npm run dev (Electron app)

# Note: Frontend connects to ws://127.0.0.1:8787/ws for WebSocket communication
```

### Performance & Monitoring
```bash
# Backend performance monitoring is built-in
# View logs for timing information and slow operations

# Database maintenance and optimization
cd backend && python optimize_db.py  # Applies indexes, cleanup, and optimization

# Performance stats can be accessed programmatically via performance.py module
```

### WebSocket Communication
- Backend exposes WebSocket endpoint at `/ws` on port 8787
- Frontend connects via `ws://127.0.0.1:8787/ws`  
- Uses JSON message format: `{event, data}`
- Automatic reconnection with exponential backoff on frontend
- Connection status monitoring with visual indicators
- Real-time updates for job status, email triage, and agent responses

## Purpose & Context

This is a **comprehensive digital Chief of Staff assistant** that serves as an intelligent productivity orchestrator. It's NOT just an email manager - it's designed to understand your complete work context and proactively manage all aspects of professional workflow.

### Core Capabilities
- **Project & Task Management**: Links emails to projects via `COS.ProjectId`, extracts tasks from any content, maintains project-aware context
- **Intelligent Information Management**: Generates daily/weekly digests, scans for stale information, suggests connections between data points
- **Proactive Advisory System**: Conducts strategic interviews (≤1/day), provides actionable suggestions with confidence scores
- **Advanced Communication**: Creates on-tone drafts, manages multi-step workflows, provides systematic review processes
- **Knowledge Management**: Builds contextual memory, verifies facts, maps relationships, learns decision patterns

### Multi-Agent Architecture
**6-Agent Orchestrated System:**
- **COS Orchestrator**: Master coordinator routing user commands and coordinating agent responses (`agents.py:COSOrchestrator`)
- **Contextor Agent**: Manages strategic interviews (≤1/day) and normalized proposals (`agents.py:ContextorAgent`)
- **Email Triage Agent**: Handles email bundles, GTD categorization, and project linking (`agents.py:EmailTriageAgent`)
- **Summarizer Agent**: Creates TL;DR summaries and extracts actionable tasks from any content (`agents.py:SummarizerAgent`)
- **Writer Agent**: Generates on-tone drafts with review checklists and writing templates (`agents.py:WriterAgent`)
- **Background Processes**: Continuous context scanning, digest building, link suggestions via job queue (`job_queue.py`)

**Agent Coordination Pattern:**
1. User input → COS Orchestrator analyzes intent
2. Routes to specialized agent(s) for processing
3. Agent calls Claude with context-specific prompts from `llm/prompts/`
4. Results aggregated and returned with structured YAML output
5. Background jobs queued for follow-up processing

## Technical Architecture

Three-tier system with real-time WebSocket communication, optimized performance, and modern UI design system:

### Backend (FastAPI + WebSocket)
- **Location**: `backend/` directory
- **Tech Stack**: FastAPI, WebSockets, SQLAlchemy (SQLite with WAL mode), Pydantic
- **Key Files**:
  - `app.py` - Main FastAPI application with WebSocket broadcasting and REST endpoints
  - `models.py` - Database models: Project, Task, Email, ContextEntry, Job, Interview, Digest
  - `agents.py` - Multi-agent system with COS orchestrator and specialized agents
  - `claude_client.py` - AI client with response caching (5-min TTL) and prompt management
  - `job_queue.py` - Background job processing with async operations and status tracking
  - `performance.py` - Performance monitoring decorators and timing metrics
  - `integrations/outlook/` - Outlook integration with COM and Graph API hybrid approach
- **WebSocket Protocol**: JSON messages `{event, data}`, handles user input, job updates, agent responses
- **AI Integration**: Claude-only provider, prompts loaded from `llm/prompts/`, hard-fail if missing
- **Job Processing**: Flat job queue for background tasks (email_scan, context_scan, digest_build)
- **Database**: SQLite with WAL mode, comprehensive indexes, connection pooling, sample data generation

**Outlook Integration Architecture:**
- **Hybrid Service**: COM first (direct Outlook access), fallback to Graph API
- **COM Connector**: `pywin32` for direct Outlook manipulation on Windows
- **Graph API**: OAuth2 flow for cloud-based email access
- **GTD Folders**: Automated creation of COS_Actions, COS_Assigned, COS_ReadLater, COS_Reference, COS_Archive under Inbox
- **Extended Properties**: Email-project linking via `COS.ProjectId`, `COS.TaskIds` metadata

### Frontend (Electron)
- **Location**: Root level with `main.js`, `preload.js`, `index.html`
- **UI Location**: `electron/src/ui/` (React/TypeScript components)
- **Key Components**: 
  - `main.js` - Electron main process, window management
  - `preload.js` - Secure bridge between main and renderer processes
  - `index.html` - Entry point loading React application
  - `App.tsx` - Main React app with sidebar navigation and connection status
  - `ChatInbox.tsx` - Chat interface with welcome screen, quick actions, typing indicators
  - `EmailThreadView.tsx` - Email thread display with AI suggestions
  - `lib/ws.ts` - WebSocket client with auto-reconnection and exponential backoff
  - `components/ui/` - Reusable component library (Button, Card, Input, Badge)
- **Architecture**: Electron renderer process running React app, communicates via WebSocket to backend
- **Development**: `npm run dev` starts Electron with hot reload, connects to backend on port 8787
- **Design System**: Modern dark theme using CSS custom properties from `design/modern-tokens.css`

### Modern Design System
- **Location**: `design/` directory with `modern-tokens.css` as the primary design system
- **Component Library**: `electron/src/ui/components/ui/` with reusable components
- **Design Tokens**: CSS custom properties for colors, typography, spacing, shadows, transitions
- **Components Available**: 
  - `Button` - Multiple variants with loading states and icons
  - `Card` - Elevated cards with flexible padding and composition
  - `Input` - Enhanced inputs with labels, icons, and error states  
  - `Badge` - Status badges for message types and statuses
- **Theme**: Professional dark theme with indigo brand colors, proper contrast ratios
- **Typography**: Inter font family with proper font weights and line heights
- **Layout**: CSS Grid-based responsive design with consistent spacing

### LLM Integration
- **Prompts Location**: `llm/prompts/` directory with structured categories:
  - `system/` - Core agent prompts (cos.md, emailtriage.md, summarizer.md, writer.md, contextor.md)
  - `tools/` - Utility prompts (digest.md, interview.md, normalize.md)
  - `outlook/` - Email integration prompts (folders.md, categories.md, props.md)
  - `background/` - Background job prompts (context_scan.md, email_scan.md, digest_build.md)
- **Claude Integration**: Single AI provider, prompts loaded at startup, hard-fail if missing
- **Response Caching**: 5-minute TTL cache with deterministic keys, LRU prompt caching
- **Rate Limiting**: 30-minute idle timeout before connection checks, 1-second minimum between API calls
- **Activity Tracking**: User interactions reset idle timer to prevent unnecessary API calls
- **Development Mode**: Mock responses enabled when ANTHROPIC_API_KEY not set
- **Prompt Management**: `claude_client.py` handles prompt loading, caching, and Claude API calls

**Command Processing Flow:**
1. User types command (e.g., `/outlook connect`, `/triage`)
2. WebSocket message sent to backend
3. COS Orchestrator analyzes intent and selects appropriate agent
4. Agent loads relevant prompt from `llm/prompts/`
5. Context gathered from database (projects, emails, previous conversations)
6. Claude API called with prompt + context
7. Response processed and sent back via WebSocket
8. Background jobs queued for follow-up actions

### Database Schema & Performance
- **Core Entities**: Projects, Tasks, Emails, ContextEntries, Jobs, Interviews, Digests
- **Optimization Features**:
  - Comprehensive indexing on frequently queried columns (status, foreign keys, dates)
  - WAL mode for better concurrency
  - Connection pooling with StaticPool
  - Automatic cleanup of old data (completed jobs, dismissed interviews, expired context)
  - Performance pragmas (cache_size, temp_store, mmap_size)
- **Key Indexes**: Composite indexes for complex queries, covering indexes for performance

### Email Integration Features
- **Smart Outlook Organization**: GTD-style folders (COS_Actions, COS_Assigned, COS_ReadLater, COS_Reference, COS_Archive under Inbox)
- **Extended Properties**: `COS.ProjectId`, `COS.TaskIds`, `COS.LinkedAt`, `COS.Confidence`, `COS.Provenance`
- **Intelligent Categorization**: COS/* namespace for systematic email categorization
- **Email-Project Linking**: Automatic association of emails with ongoing projects and tasks
- **COM Integration**: Direct Windows Outlook access via `pywin32` for real-time folder operations
- **Graph API Fallback**: Cloud-based access when local Outlook unavailable
- **Hybrid Connection**: Automatically tries COM first, falls back to Graph API

**Available Commands:**
- `/outlook connect` - Establish connection (COM first, then Graph API)
- `/outlook info` - Show connection details and account information
- `/outlook sync` - Download emails from inbox to database
- `/outlook setup` - Create GTD folder structure in Outlook
- `/outlook triage` - AI-process unprocessed emails into appropriate folders

### Rate Limiting & API Management
The system implements intelligent rate limiting to prevent Anthropic API 429 errors:

- **Idle-Based Connection Checking**: AI connection status is only checked after 30 minutes of user inactivity
- **Request Spacing**: Minimum 1-second interval between all Claude API calls
- **Activity Tracking**: User messages automatically reset the idle timer
- **Thread-Safe**: Uses locks to prevent race conditions in concurrent environments
- **Transparent Operation**: Rate limiting happens automatically without user intervention

**Key Implementation Details:**
```python
# ClaudeClient automatically tracks activity and applies rate limiting
claude_client.update_activity()  # Called on user input
claude_client.should_check_connection()  # Returns True only after 30min idle
await claude_client._apply_rate_limiting()  # Enforces 1s minimum between calls
```

This architecture ensures the system is responsive during active use while preventing API quota exhaustion.

### Core System Features  
- **Context Interviews**: Strategic questioning system with `interview:start/answer/dismiss` events
- **Background Processing**: Continuous context scanning, digest building, and link suggestion
- **Suggestion Engine**: Actionable recommendations with confidence scores and rationale
- **Data Normalization**: Standardizes dates, emails, titles, and contact information
- **Job Queue System**: Flat job queue with background job status tracking and async processing
- **Performance Monitoring**: Built-in timing decorators and performance statistics
- **Modern UI**: Professional interface with connection status, quick actions, and responsive design

## Development Notes

### Critical Implementation Details
- **🚨 OUTLOOK INTEGRATION RULE**: **ONLY USE LEGACY METHODS** - No batch processing, no optimized loading, no hybrid methods. Always use `_get_messages_legacy()` and standard property sync methods. Batch loaders and optimized methods are explicitly forbidden and break COS property loading.
- **Prompt Management**: All prompts stored as `.md` files in `llm/prompts/` - these define the core AI intelligence behavior
- **Multi-Agent Coordination**: COS Orchestrator routes commands, specialized agents handle domain-specific tasks
- **Interview Limits**: Context interviews limited to ≤1 per day to avoid user fatigue
- **Development vs Production**: Mock responses when no `ANTHROPIC_API_KEY`, real Claude calls in production
- **Environment Setup**: `.env` file in `backend/` with `ANTHROPIC_API_KEY`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`
- **Windows COM Requirements**: `pywin32` installed, Outlook running with target account logged in
- **Database Initialization**: Run `python init_db.py` to create tables with sample data
- **Testing**: `python test_setup.py` validates entire backend setup without API keys
- **Design System**: Use `design/modern-tokens.css` for styling, reusable components in `electron/src/ui/components/ui/`
- **Email Schema**: Emails accessed directly from Outlook via hybrid COM/Graph API, not stored in database
- **WebSocket Events**: System uses event-driven architecture with JSON messages `{event, data}` format

**Key Architecture Decisions:**
- SQLite with WAL mode for concurrent access and performance
- WebSocket for real-time communication (not REST for chat-like interactions)
- Electron for cross-platform desktop app with native OS integration
- Hybrid Outlook integration for maximum compatibility (COM + Graph API)
- Job queue pattern for background processing without blocking user interactions
- Agent-based AI architecture for specialized, context-aware responses

### Performance & Architecture Patterns
- **Database**: WAL mode + comprehensive indexing + connection pooling = 70% faster queries
- **WebSocket**: Concurrent broadcasting with proper error handling and auto-reconnection
- **Frontend**: React optimization patterns (memo, callbacks, useMemo) prevent unnecessary re-renders
- **Caching**: AI response caching (5min TTL) + LRU prompt caching reduces redundant API calls
- **Rate Limiting**: Prevents API 429 errors with intelligent idle detection and request spacing
- **Async Processing**: Background jobs run without blocking main application thread
- **Error Handling**: Graceful degradation with visual feedback for all error states

### UI/UX Patterns
- **Connection Awareness**: Visual connection status with colored indicators throughout UI
- **Progressive Enhancement**: App works offline with cached responses and queue for reconnection
- **Quick Actions**: Welcome screen provides immediate value with common command shortcuts
- **Typing Indicators**: Real-time feedback during AI response generation
- **Modern Design**: Professional dark theme with proper contrast and accessibility considerations
- **Component Consistency**: Reusable component library ensures consistent behavior and styling

### Script Permissions & Common Issues
- **Windows Environment**: Use `.venv\Scripts\python.exe` for all Python commands in backend/
- **WSL Environment**: Use `source .venv/bin/activate` and `python` commands in backend/
- **Unicode Errors**: Windows console may fail with Unicode characters in test_setup.py - ignore cosmetic errors
- **Backend must be started before frontend** for WebSocket connection
- **Missing `.env` file** will cause backend startup failure - copy from `.env.example`
- **Database optimization** should be run periodically for best performance
- **Rate Limit Errors**: System now prevents 429 errors with 30-minute idle timeout and 1-second API spacing
- **COM Requirements**: Windows Outlook must be running with target account logged in for COM integration
- **Port Conflicts**: Backend runs on port 8787 - ensure no other services use this port
- **Node/Electron Issues**: Run `npm install` in root directory before `npm run dev`

## Key Implementation Priorities

When building this system, remember:
1. **Context is King**: Every feature should contribute to building and maintaining user context
2. **Proactive not Reactive**: The system should anticipate needs, not just respond to requests  
3. **Project-Centric**: Everything (emails, tasks, information) should link back to projects and goals
4. **Intelligence Over Automation**: Use AI to provide insights and suggestions, not just automate tasks
5. **Respectful Interruption**: Interviews and suggestions should be valuable and well-timed
6. **Performance First**: All operations should be optimized for responsiveness and reliability
7. **Design Consistency**: Use the modern design system and component library for all UI development
8. **User Experience**: Prioritize connection awareness, loading states, and error feedback

## Development Roadmap & Next Steps

### Immediate Priorities (Foundation - Implement First)

#### 1. Core UI Development (CRITICAL)
**Email Management Interface**:
- **Email List View**: Sortable, filterable email list with live Outlook integration (expand EmailThreadView)
- **Email Detail Panel**: Rich email content display with inline actions, threading, and project linking
- **Email Actions Sidebar**: Context-aware action suggestions (move to folder, extract tasks, schedule follow-up)
- **Email Search & Filter**: Real-time search across subjects, senders, content with project/task context
- **Email Composition**: Smart draft generation with templates based on recipient and context

**Email Intelligence & Recommendations**:
- **Context-Aware Email Summary**: Key points extraction considering sender relationship, project relevance, urgency indicators
- **Smart Action Recommendations**: Intelligent suggestions based on sender (boss/team/external), content analysis, and project context:
  - **Archive**: Low priority, informational emails with no action needed
  - **Read Later**: Important but non-urgent emails (articles, updates, reports)
  - **Reply Required**: Emails needing response with priority based on sender relationship
  - **Delegate/Forward**: Items better handled by team members with recipient suggestions
  - **Create Task**: Action items extracted with project assignment and due date suggestions
  - **Schedule Meeting**: When email content suggests need for discussion or collaboration
  - **Add to Project**: Link to existing or suggest new project association
- **Priority Scoring**: Dynamic priority based on sender importance, content urgency, project deadlines, user patterns
- **Response Templates**: Context-appropriate reply templates based on sender relationship and email type

**Project & Task Management Interface**:
- **Enhanced Project Dashboard**: Real-time project health, timeline views, resource allocation
- **Task Management Panel**: Drag-and-drop task organization, dependency visualization, status tracking  
- **Area Overview Enhancement**: Visual project hierarchy with progress indicators and quick actions
- **Task Creation Flow**: Smart task extraction from emails, voice input, quick capture
- **Project Timeline View**: Gantt-style visualization with milestone tracking and deadline alerts

#### 2. User Context Acquisition System (CRITICAL)
**Personal Profile Management**:
- **User Profile Setup**: Guided onboarding to capture personal details (DOB, work location, preferences)
- **Organizational Context**: Role definition, reporting structure, team composition, department/division
- **Work Patterns**: Schedule preferences, communication style, decision-making patterns
- **Goal Setting**: Personal and professional objectives with timeline and success metrics

**Organizational Intelligence**:
- **Contact Management**: Import and categorize contacts (boss, peers, direct reports, external stakeholders)
- **Team Structure Mapping**: Visual org chart with role definitions and interaction patterns
- **Project Stakeholder Tracking**: Link contacts to projects with role definitions (sponsor, contributor, approver)
- **Communication Preferences**: Per-contact communication styles, escalation paths, availability

**Context Learning Engine**:
- **Behavioral Pattern Recognition**: Learn user habits, peak productivity hours, decision patterns
- **Preference Learning**: Communication style, project management approach, priority frameworks
- **Historical Context**: Track decisions, outcomes, and lessons learned for future recommendations
- **Dynamic Context Updates**: Continuous learning from user interactions and feedback

#### 3. Enhanced Email Intelligence (Building on UI)
- **Smart Email Actions**: Content-based action suggestions integrated into email detail panel
- **Email Threading**: Proper conversation threading using Outlook's thread_id with visual indicators
- **Project-Email Linking**: Automatic and manual email-to-project association with confidence scoring
- **Draft Generation**: Context-aware email composition using recipient history and project context

### Medium-term Enhancements (2-4 weeks)

#### Multi-Channel Integration
- **Calendar Integration**: Connect with Outlook Calendar for meeting-aware task scheduling
- **Teams/Slack Integration**: Extend context awareness to team chat platforms
- **Document Intelligence**: OCR and analysis of attached documents for task/project extraction
- **Mobile Companion**: Build mobile interface for on-the-go status updates and quick actions

#### Advanced AI Capabilities  
- **Custom Agent Training**: Allow users to train specialized agents for domain-specific tasks
- **Multi-language Support**: Handle emails and content in multiple languages with translation
- **Voice Interface**: Add voice commands and dictation for hands-free operation
- **Predictive Analytics**: Forecast project timelines and potential bottlenecks using historical data

#### Collaboration Features
- **Team Dashboards**: Multi-user project visibility with role-based access control
- **Delegation Tracking**: Monitor delegated tasks across team members with status updates
- **Knowledge Base**: Build searchable repository of decisions, templates, and best practices
- **Performance Analytics**: Track productivity metrics and provide insights for improvement

### Long-term Vision (1-3 months)

#### Enterprise Integration
- **SSO Authentication**: Enterprise login integration with Azure AD/Google Workspace
- **API Gateway**: RESTful API for third-party integrations and custom extensions
- **Compliance Features**: Audit trails, data retention policies, and regulatory compliance tools
- **Scalable Architecture**: Multi-tenant support with cloud deployment options

#### AI-Powered Insights
- **Strategic Planning**: Long-term goal tracking with milestone prediction and risk assessment  
- **Competitive Intelligence**: Monitor industry trends and suggest strategic opportunities
- **Performance Optimization**: Machine learning-driven productivity improvement recommendations
- **Executive Reporting**: Automated executive summaries with key metrics and insights

### Technical Debt & Infrastructure

#### Code Quality Improvements
- **Comprehensive Testing**: Unit tests, integration tests, and end-to-end test coverage
- **Type Safety**: Complete TypeScript coverage in frontend with strict mode enabled
- **Error Handling**: Centralized error handling with user-friendly error messages
- **Performance Monitoring**: APM integration with performance metrics and alerting

#### Security & Reliability
- **Data Encryption**: End-to-end encryption for sensitive email and project data
- **Backup Strategy**: Automated backups with disaster recovery procedures
- **Security Audit**: Vulnerability assessment and penetration testing
- **Monitoring & Alerting**: Production monitoring with automated incident response

### Implementation Notes

**Development Approach**: Prioritize user value over technical complexity. Each feature should solve a real productivity problem and integrate seamlessly with existing workflows.

**Quality Gates**: Every new feature requires comprehensive testing, documentation updates, and user experience validation before deployment.

**User Feedback Loop**: Implement analytics and feedback mechanisms to measure feature adoption and effectiveness, informing future development priorities.
- Take the time you need to write a proper and correct solution.

For non-trivial issues (e.g., unclear bugs, intermittent errors, complex flows), first add appropriate logging/debugging code (e.g., log inputs, intermediate states, and error conditions). This should be clear, lightweight, and relevant for diagnosing the issue.

Use those logs to reason about where the bug or failure occurs, and then propose a fix.

After applying a fix, thoroughly test the solution. Tests should cover:

Typical cases (normal expected input).

Edge cases (empty input, None, unusual values, very large/small numbers).

Unicode and international text (e.g., "Café", "你好", "👩🏽‍💻").

Error conditions (e.g., invalid input, division by zero).

Verify and show the test results: expected vs. actual outputs.

If any test fails, fix the code and re-run the tests until everything passes.

Do not rush. It is better to take longer and deliver a thorough, correct, well-instrumented, and validated solution than to quickly return an incomplete one.

Only when all tests pass should you report that the solution is complete. Always include the final tested code, the logging additions (if applicable), and the test results in your response.