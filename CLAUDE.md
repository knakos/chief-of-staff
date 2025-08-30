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

# Start backend server
./scripts/start_all.sh  # Runs uvicorn on 127.0.0.1:8787 with reload
```

### Frontend Development  
```bash
# Start Electron app
./scripts/start-electron.ps1  # PowerShell script that runs npm install && npm run dev
```

### WebSocket Communication
- Backend exposes WebSocket endpoint at `/ws` on port 8788
- Frontend connects via `ws://127.0.0.1:8788/ws`
- Uses JSON message format: `{event, data}`

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
- **COS Orchestrator**: Master coordinator with YAML output and guardrails
- **Contextor Agent**: Manages interviews and normalized proposals  
- **Email Triage Agent**: Handles email bundles and suggested actions
- **Summarizer Agent**: Creates TL;DR summaries and extracts tasks from any content
- **Writer Agent**: Generates on-tone drafts with review checklists
- **Background Processes**: Continuous context scanning, digest building, link suggestions

## Technical Architecture

Three-tier system with real-time WebSocket communication:

### Backend (FastAPI + WebSocket)
- **Location**: `backend/` directory
- **Tech Stack**: FastAPI, WebSockets, SQLAlchemy (SQLite), Pydantic
- **WebSocket Protocol**: JSON messages with `{event, data}` structure
- **AI Integration**: Claude-only provider with fail-fast behavior
- **Job Processing**: Flat job queue with background job status tracking

### Frontend (Electron + React/TypeScript)
- **Location**: `electron/src/ui/` 
- **Components**: 
  - `App.tsx` - Main application
  - `ChatInbox.tsx` - Chat interface
  - `EmailThreadView.tsx` - Email thread display
- **State Management**: TypeScript models in `state/models.ts`
- **WebSocket Client**: `lib/ws.ts` handles backend communication

### LLM Integration
- **Prompts Location**: `llm/prompts/` directory with structured categories:
  - `system/` - Core system prompts (cos.md, emailtriage.md, etc.)
  - `tools/` - Tool-specific prompts (digest.md, interview.md)
  - `outlook/` - Outlook integration prompts
  - `background/` - Background processing prompts
- **Claude Integration**: Hard-fail if prompts are missing from expected locations

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
- **Job Queue System**: Flat job queue with background job status tracking

## Development Notes

- **Prompt Management**: All prompts stored as `.md` files with version logging - these define the core intelligence
- **Multi-Agent Coordination**: Each agent has specific responsibilities but works within the COS orchestrator framework
- **UI Design System**: Design tokens defined in `design/tokens.css`
- **Interview Limits**: Context interviews limited to ≤1 per day to avoid user fatigue
- **Mock Replacement**: Replace UI mocks incrementally with actual Claude API calls
- **Environment**: Requires `.env` file in backend directory (see backend/README.md for example)

## Key Implementation Priorities

When building this system, remember:
1. **Context is King**: Every feature should contribute to building and maintaining user context
2. **Proactive not Reactive**: The system should anticipate needs, not just respond to requests  
3. **Project-Centric**: Everything (emails, tasks, information) should link back to projects and goals
4. **Intelligence Over Automation**: Use AI to provide insights and suggestions, not just automate tasks
5. **Respectful Interruption**: Interviews and suggestions should be valuable and well-timed