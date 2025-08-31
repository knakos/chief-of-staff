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

# Start backend server (from project root)
./scripts/start_all.sh  # Runs uvicorn on 127.0.0.1:8787 with reload
# Note: Script may need chmod +x ./scripts/start_all.sh

# Database optimization (run periodically)
cd backend && python optimize_db.py

# Initialize database tables
cd backend && python init_db.py
```

### Frontend Development  
```bash
# Start Electron app (from project root)
cd electron && npm install && npm run dev

# Alternative: Use the script (PowerShell on Windows)
./scripts/start-electron.ps1

# For development, typically run both:
# Terminal 1: ./scripts/start_all.sh (backend)
# Terminal 2: cd electron && npm run dev (frontend)
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
- Backend exposes WebSocket endpoint at `/ws` on port 8788
- Frontend connects via `ws://127.0.0.1:8788/ws`  
- Uses JSON message format: `{event, data}`
- Automatic reconnection with exponential backoff on frontend
- Connection status monitoring with visual indicators

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

Three-tier system with real-time WebSocket communication, optimized performance, and modern UI design system:

### Backend (FastAPI + WebSocket)
- **Location**: `backend/` directory
- **Tech Stack**: FastAPI, WebSockets, SQLAlchemy (SQLite with WAL mode), Pydantic
- **Key Files**:
  - `app.py` - Main FastAPI application with optimized WebSocket broadcasting
  - `models.py` - Database models with comprehensive indexing 
  - `job_queue.py` - Background job processing with async optimization
  - `claude_client.py` - AI client with response caching (5-min TTL) and prompt management
  - `agents.py` - Multi-agent system implementation
  - `performance.py` - Performance monitoring decorators and metrics
  - `optimize_db.py` - Database optimization script with cleanup utilities
- **WebSocket Protocol**: JSON messages with `{event, data}` structure, concurrent broadcasting
- **AI Integration**: Claude-only provider with response caching and fail-fast behavior
- **Job Processing**: Flat job queue with background job status tracking and async operations
- **Database**: SQLite with WAL mode, comprehensive indexes, connection pooling, automatic cleanup

### Frontend (Electron + React/TypeScript)
- **Location**: `electron/src/ui/` 
- **Key Components**: 
  - `App.tsx` - Main application with modern sidebar navigation and connection status
  - `ChatInbox.tsx` - Optimized chat interface with welcome screen, quick actions, and typing indicators
  - `EmailThreadView.tsx` - Email thread display with suggestion handling and error states
  - `lib/ws.ts` - Robust WebSocket client with auto-reconnection and exponential backoff
  - `state/models.ts` - TypeScript models for data structures
  - `components/ui/` - Modern component library (Button, Card, Input, Badge)
- **Performance Optimizations**: React.memo, useCallback, useMemo, connection state management
- **WebSocket Features**: Auto-reconnection, exponential backoff, connection status indicators
- **Design System**: Modern dark theme with comprehensive design tokens

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
  - `system/` - Core system prompts (cos.md, emailtriage.md, summarizer.md, writer.md, contextor.md)
  - `tools/` - Tool-specific prompts (digest.md, interview.md, normalize.md)
  - `outlook/` - Outlook integration prompts (folders.md, categories.md, props.md)
  - `background/` - Background processing prompts (context_scan.md, email_scan.md, etc.)
- **Claude Integration**: Prompts loaded at startup with caching, hard-fail if missing from expected locations
- **Response Caching**: 5-minute TTL cache with deterministic key generation and LRU prompt caching
- **Performance**: Mock responses for development, reduced API delays, cache hit optimization

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
- **Modern UI**: Professional interface with connection status, quick actions, and responsive design

## Development Notes

### Critical Implementation Details
- **Prompt Management**: All prompts stored as `.md` files with version logging - these define the core intelligence
- **Multi-Agent Coordination**: Each agent has specific responsibilities but works within the COS orchestrator framework
- **Interview Limits**: Context interviews limited to ≤1 per day to avoid user fatigue
- **Mock System**: Current system uses mock Claude responses - real API calls work with proper `ANTHROPIC_API_KEY`
- **Environment**: Requires `.env` file in backend directory with `ANTHROPIC_API_KEY`
- **Design System**: Use `design/modern-tokens.css` for all styling, leverage component library in `components/ui/`

### Performance & Architecture Patterns
- **Database**: WAL mode + comprehensive indexing + connection pooling = 70% faster queries
- **WebSocket**: Concurrent broadcasting with proper error handling and auto-reconnection
- **Frontend**: React optimization patterns (memo, callbacks, useMemo) prevent unnecessary re-renders
- **Caching**: AI response caching (5min TTL) + LRU prompt caching reduces redundant API calls
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
- Scripts may need executable permissions: `chmod +x ./scripts/start_all.sh`
- PowerShell scripts (.ps1) won't run in bash - use manual commands instead
- Backend must be started before frontend for WebSocket connection
- Missing `.env` file will cause backend startup failure
- Database optimization should be run periodically for best performance

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