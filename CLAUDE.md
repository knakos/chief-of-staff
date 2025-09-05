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

# Test system (comprehensive validation)
python test_system.py  # New consolidated test suite
python test_setup.py   # Wrapper for comprehensive test

# Database migration (if schema changes)
python migrate_email_removal.py  # Recent migration removing email tables

# Rate limiting test
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
**Simplified Agent System:**
- **COS Orchestrator**: Master coordinator routing user commands and coordinating agent responses (`agents.py:COSOrchestrator`)
- **EmailTriageAgent**: Simplified COM-only email processing with direct Outlook integration (`agents.py:EmailTriageAgent`)
- **Contextor Agent**: Manages strategic interviews (≤1/day) and normalized proposals (`agents.py:ContextorAgent`)
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

Simplified three-tier system with direct COM email integration, real-time WebSocket communication, and modern UI:

### Backend (FastAPI + WebSocket)
- **Location**: `backend/` directory
- **Tech Stack**: FastAPI, WebSockets, SQLAlchemy (SQLite with WAL mode), Pydantic
- **Key Files**:
  - `app.py` - Main FastAPI application with WebSocket broadcasting and REST endpoints
  - `models.py` - Database models: Project, Task, ContextEntry, Job, Interview, Digest (NO Email model)
  - `agents.py` - Simplified multi-agent system with COS orchestrator
  - `claude_client.py` - AI client with response caching (5-min TTL) and prompt management
  - `job_queue.py` - Background job processing with async operations and status tracking
  - `performance.py` - Performance monitoring decorators and timing metrics
  - `integrations/outlook/` - COM-only Outlook integration for direct email access
  - `test_system.py` - Consolidated comprehensive test suite
- **WebSocket Protocol**: JSON messages `{event, data}`, handles user input, job updates, agent responses
- **AI Integration**: Claude-only provider, prompts loaded from `llm/prompts/`, hard-fail if missing
- **Job Processing**: Flat job queue for background tasks (context_scan, digest_build)
- **Database**: SQLite with WAL mode, indexes, connection pooling (emails NOT stored in database)

**Email Architecture - COM-Only Integration:**
- **Direct COM Access**: Emails accessed directly from Outlook via `pywin32`, not stored in database
- **COM Service**: `OutlookCOMService` provides email loading, analysis, and folder operations
- **Required Methods**: Uses `_get_messages_legacy()` and standard property sync methods - these are the ONLY allowed methods
- **COS Properties**: Email analysis persisted as Outlook extended properties (`COS.Priority`, `COS.Tone`, etc.)
- **GTD Folders**: Automated creation of COS_Actions, COS_Assigned, COS_ReadLater, COS_Reference, COS_Archive
- **On-Demand Analysis**: Emails analyzed only when explicitly requested via UI

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
1. User types command (e.g., `/outlook connect`, `/outlook status`)
2. WebSocket message sent to backend
3. COS Orchestrator analyzes intent and selects appropriate agent
4. Agent loads relevant prompt from `llm/prompts/`
5. Context gathered from database (projects, tasks, previous conversations)
6. Claude API called with prompt + context
7. Response processed and sent back via WebSocket
8. Background jobs queued for follow-up actions

### Database Schema & Performance
- **Core Entities**: Projects, Tasks, ContextEntries, Jobs, Interviews, Digests
- **Email Storage**: **REMOVED** - Emails accessed directly from Outlook, not stored in database
- **Optimization Features**:
  - Comprehensive indexing on frequently queried columns (status, foreign keys, dates)
  - WAL mode for better concurrency
  - Connection pooling with StaticPool
  - Automatic cleanup of old data (completed jobs, dismissed interviews, expired context)
  - Performance pragmas (cache_size, temp_store, mmap_size)
- **Key Indexes**: Composite indexes for complex queries, covering indexes for performance
- **Foreign Key Updates**: Uses `related_email_outlook_id` (string) instead of database foreign keys

### Email Integration Features
- **Direct COM Integration**: All email access via Outlook COM interface, no database storage
- **Smart Outlook Organization**: GTD-style folders (COS_Actions, COS_Assigned, COS_ReadLater, COS_Reference, COS_Archive under Inbox)
- **Extended Properties**: Email metadata via `COS.ProjectId`, `COS.Priority`, `COS.Tone`, `COS.Urgency`, etc.
- **Intelligent Analysis**: On-demand AI analysis with results persisted as Outlook properties
- **Required Methods Only**: Must use `_get_messages_legacy()` and standard property sync - batch processing methods are forbidden
- **Progressive Loading**: Emails loaded in batches to frontend for smooth UX
- **Analysis Persistence**: All AI analysis stored in Outlook, survives application restarts

**Available Commands:**
- `/outlook connect` - Establish COM connection to Outlook
- `/outlook info` - Show connection details and account information
- `/outlook setup` - Create GTD folder structure in Outlook
- `/outlook status` - Check COM connection status
- `/outlook triage` - Simplified triage message (functionality moved to UI)

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
- **🚨 EMAIL ARCHITECTURE RULE**: Emails are **NEVER** stored in database - all email access is direct COM integration with Outlook
- **🚨 OUTLOOK INTEGRATION RULE**: **ONLY USE STANDARD METHODS** - Always use `_get_messages_legacy()` and standard property sync methods - these are the ONLY allowed methods. Batch loaders and optimized methods are forbidden and break COS property loading
- **Prompt Management**: All prompts stored as `.md` files in `llm/prompts/` - these define the core AI intelligence behavior
- **Simplified Agent System**: EmailTriageAgent streamlined to only essential methods, deprecated methods removed
- **Testing**: Consolidated into `test_system.py` - comprehensive test covering all functionality
- **Database Migration**: `migrate_email_removal.py` handles schema updates for removing email tables
- **Development vs Production**: Mock responses when no `ANTHROPIC_API_KEY`, real Claude calls in production
- **Environment Setup**: `.env` file in `backend/` with `ANTHROPIC_API_KEY`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`
- **Windows COM Requirements**: `pywin32` installed, Outlook running with target account logged in
- **Database Initialization**: Run `python init_db.py` to create tables with sample data
- **Testing**: `python test_system.py` validates entire backend setup without API keys
- **Design System**: Use `design/modern-tokens.css` for styling, reusable components in `electron/src/ui/components/ui/`

**Key Architecture Decisions:**
- SQLite with WAL mode for concurrent access and performance
- WebSocket for real-time communication (not REST for chat-like interactions)
- Electron for cross-platform desktop app with native OS integration
- COM-only Outlook integration for maximum reliability and performance
- Job queue pattern for background processing without blocking user interactions
- Agent-based AI architecture for specialized, context-aware responses
- Direct email access eliminates database overhead and complexity

### Performance & Architecture Patterns
- **Database**: WAL mode + comprehensive indexing + connection pooling = high performance
- **Email Access**: Direct COM integration eliminates database bottleneck
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
- **Backend must be started before frontend** for WebSocket connection
- **Missing `.env` file** will cause backend startup failure - copy from `.env.example`
- **Database optimization** should be run periodically for best performance
- **Rate Limit Errors**: System prevents 429 errors with 30-minute idle timeout and 1-second API spacing
- **COM Requirements**: Windows Outlook must be running with target account logged in for COM integration
- **Port Conflicts**: Backend runs on port 8787 - ensure no other services use this port
- **Node/Electron Issues**: Run `npm install` in root directory before `npm run dev`
- **Schema Migration**: If database schema errors occur, run migration script first

## Key Implementation Priorities

When building this system, remember:
1. **Simplicity First**: The architecture has been streamlined - avoid adding complexity back
2. **Direct Email Access**: Never store emails in database - always use COM integration
3. **Performance Optimization**: The system is optimized for responsiveness and efficiency
4. **Context is King**: Every feature should contribute to building and maintaining user context
5. **Proactive not Reactive**: The system should anticipate needs, not just respond to requests  
6. **Project-Centric**: Everything (emails, tasks, information) should link back to projects and goals
7. **Intelligence Over Automation**: Use AI to provide insights and suggestions, not just automate tasks
8. **Respectful Interruption**: Interviews and suggestions should be valuable and well-timed
9. **Design Consistency**: Use the modern design system and component library for all UI development
10. **User Experience**: Prioritize connection awareness, loading states, and error feedback