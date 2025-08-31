# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend Development
```bash
# Setup backend (in WSL)
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv/Scripts/activate on Windows
pip install -r requirements.txt

# Create environment file
cp .env.example .env
# Edit .env to add your ANTHROPIC_API_KEY

# Start backend server
./scripts/start_all.sh  # Runs uvicorn on 127.0.0.1:8787 with reload

# Database optimization (run periodically)
python optimize_db.py

# Initialize database tables
python init_db.py
```

### Frontend Development  
```bash
# Start Electron app
./scripts/start-electron.ps1  # PowerShell script that runs npm install && npm run dev

# Alternative manual startup
cd electron
npm install
npm run dev
```

### Performance & Monitoring
```bash
# Backend performance monitoring is built-in
# View logs for timing information and slow operations
# Access performance stats at GET /api/performance (if implemented)

# Database maintenance
cd backend
python optimize_db.py  # Applies indexes, cleanup, and optimization
```

### WebSocket Communication
- Backend exposes WebSocket endpoint at `/ws` on port 8788
- Frontend connects via `ws://127.0.0.1:8788/ws`
- Uses JSON message format: `{event, data}`
- Automatic reconnection with exponential backoff on frontend

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
- **COS Orchestrator**: Master coordinator with YAML output and guardrails (`agents.py:COSOrchestrator`)
- **Contextor Agent**: Manages interviews and normalized proposals (`agents.py:ContextorAgent`)
- **Email Triage Agent**: Handles email bundles and suggested actions (`agents.py:EmailTriageAgent`)
- **Summarizer Agent**: Creates TL;DR summaries and extracts tasks from any content (`agents.py:SummarizerAgent`)
- **Writer Agent**: Generates on-tone drafts with review checklists (`agents.py:WriterAgent`)
- **Background Processes**: Continuous context scanning, digest building, link suggestions (`job_queue.py`)

## Technical Architecture

Three-tier system with real-time WebSocket communication and optimized performance:

### Backend (FastAPI + WebSocket)
- **Location**: `backend/` directory
- **Tech Stack**: FastAPI, WebSockets, SQLAlchemy (SQLite with WAL mode), Pydantic
- **Key Files**:
  - `app.py` - Main FastAPI application with optimized WebSocket broadcasting
  - `models.py` - Database models with comprehensive indexing 
  - `job_queue.py` - Background job processing with async optimization
  - `claude_client.py` - AI client with response caching and prompt management
  - `agents.py` - Multi-agent system implementation
  - `performance.py` - Performance monitoring decorators and metrics
- **WebSocket Protocol**: JSON messages with `{event, data}` structure
- **AI Integration**: Claude-only provider with response caching and fail-fast behavior
- **Job Processing**: Flat job queue with background job status tracking and async operations
- **Database**: SQLite with WAL mode, comprehensive indexes, connection pooling

### Frontend (Electron + React/TypeScript)
- **Location**: `electron/src/ui/` 
- **Key Components**: 
  - `App.tsx` - Main application with routing
  - `ChatInbox.tsx` - Optimized chat interface with React.memo and message virtualization
  - `EmailThreadView.tsx` - Email thread display with suggestion handling
  - `lib/ws.ts` - Robust WebSocket client with auto-reconnection and error recovery
  - `state/models.ts` - TypeScript models for data structures
- **Performance Optimizations**: React.memo, useCallback, useMemo, connection state management
- **WebSocket Features**: Auto-reconnection, exponential backoff, connection status indicators

### LLM Integration
- **Prompts Location**: `llm/prompts/` directory with structured categories:
  - `system/` - Core system prompts (cos.md, emailtriage.md, summarizer.md, writer.md, contextor.md)
  - `tools/` - Tool-specific prompts (digest.md, interview.md, normalize.md)
  - `outlook/` - Outlook integration prompts (folders.md, categories.md, props.md)
  - `background/` - Background processing prompts (context_scan.md, email_scan.md, etc.)
- **Claude Integration**: Prompts loaded at startup with caching, hard-fail if missing from expected locations
- **Response Caching**: 5-minute TTL cache with deterministic key generation

### Database Schema & Performance
- **Core Entities**: Projects, Tasks, Emails, ContextEntries, Jobs, Interviews, Digests
- **Optimization Features**:
  - Comprehensive indexing on frequently queried columns
  - WAL mode for better concurrency
  - Connection pooling with StaticPool
  - Automatic cleanup of old data
  - Performance pragmas (cache_size, temp_store, mmap_size)
- **Key Indexes**: Status fields, foreign keys, date ranges, composite indexes for complex queries

### Email Integration Features
- **Smart Outlook Organization**: GTD-style folders (@Action, @Waiting, @ReadLater, @Reference, COS/Processed)
- **Extended Properties**: `COS.ProjectId`, `COS.TaskIds`, `COS.LinkedAt`, `COS.Confidence`, `COS.Provenance`
- **Intelligent Categorization**: COS/* namespace for systematic email categorization
- **Email-Project Linking**: Automatic association of emails with ongoing projects and tasks

### Core System Features  
- **Context Interviews**: Strategic questioning system with `interview:start/answer/dismiss` events
- **Background Processing**: Continuous context scanning, digest building, and link suggestion
- **Suggestion Engine**: Actionable recommendations with confidence scores and rationale
- **Data Normalization**: Standardizes dates, emails, titles, and contact information
- **Job Queue System**: Flat job queue with background job status tracking and async processing
- **Performance Monitoring**: Built-in timing decorators and performance statistics

## Development Notes

### Critical Implementation Details
- **Prompt Management**: All prompts stored as `.md` files with version logging - these define the core intelligence
- **Multi-Agent Coordination**: Each agent has specific responsibilities but works within the COS orchestrator framework
- **Interview Limits**: Context interviews limited to ≤1 per day to avoid user fatigue
- **Mock Replacement**: Current system uses mock Claude responses (`claude_client.py`) - replace incrementally with actual API calls
- **Environment**: Requires `.env` file in backend directory with `ANTHROPIC_API_KEY`

### Performance Considerations
- Database operations are heavily optimized with indexes and WAL mode
- WebSocket broadcasting uses concurrent sending with proper error handling
- Frontend uses React optimization patterns to prevent unnecessary re-renders
- Response caching reduces redundant AI API calls
- Background jobs run asynchronously without blocking main application

### Error Handling Architecture
- WebSocket client automatically reconnects with exponential backoff
- Database operations use connection pooling and proper transaction management
- AI operations have caching fallbacks and graceful degradation
- Frontend components show connection status and error states

## Key Implementation Priorities

When building this system, remember:
1. **Context is King**: Every feature should contribute to building and maintaining user context
2. **Proactive not Reactive**: The system should anticipate needs, not just respond to requests  
3. **Project-Centric**: Everything (emails, tasks, information) should link back to projects and goals
4. **Intelligence Over Automation**: Use AI to provide insights and suggestions, not just automate tasks
5. **Respectful Interruption**: Interviews and suggestions should be valuable and well-timed
6. **Performance First**: All operations should be optimized for responsiveness and reliability