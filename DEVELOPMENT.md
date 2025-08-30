# Chief of Staff - Development Guide

## 🚀 Quick Start

### 1. Backend Setup
```bash
# Setup and test backend
./setup_backend.sh

# Manually start backend (alternative)
cd backend
source .venv/bin/activate
python app.py
```

### 2. Frontend Setup  
```bash
# Start Electron app (PowerShell)
./scripts/start-electron.ps1

# Or manually
cd electron
npm install
npm run dev
```

### 3. Environment Configuration
```bash
# Copy and edit environment file
cd backend
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## 📋 Development Status

✅ **Completed Infrastructure:**
- Database schema with 8 core entities (Projects, Tasks, Emails, Context, Jobs, Interviews, Digests)
- FastAPI backend with WebSocket real-time communication
- Background job queue system with 8 built-in job types
- Multi-agent AI system (COS Orchestrator + 4 specialized agents)
- Claude integration with prompt loading from `llm/prompts/`
- Frontend components with WebSocket client
- Sample data for development testing

🔄 **Working Features:**
- Chat interface with `/plan`, `/summarize`, `/triage`, `/digest` commands
- Email processing and triage simulation
- Context interview system
- Project-task linking
- Background job processing
- Mock AI responses (Claude integration ready)

## 🗄️ Database Schema

### Core Entities
- **Projects**: High-level work initiatives with status tracking
- **Tasks**: Actionable items linked to projects with dependencies
- **Emails**: Email metadata with AI-generated summaries and suggestions
- **ContextEntry**: User context and insights from interviews/analysis
- **Jobs**: Background processing queue with status tracking
- **Interviews**: Context questions with answers (≤1/day limit)
- **Digests**: Generated daily/weekly summaries

### Key Relationships
- Projects → Tasks (one-to-many)
- Projects → Emails (one-to-many via linking)
- Tasks ↔ Emails (many-to-many for extraction)
- Projects → Context (domain-specific insights)

## 🤖 AI Agent System

### COS Orchestrator
- **Role**: Master coordinator and decision maker
- **Capabilities**: User input routing, workflow coordination, high-level responses
- **Prompts**: `system/cos.md`

### Specialized Agents
1. **ContextorAgent**: Interview management and context building
2. **EmailTriageAgent**: Email processing, categorization, and action suggestions  
3. **SummarizerAgent**: Content summarization and task extraction
4. **WriterAgent**: Draft generation and communication assistance

### Job Types
- `email_scan`: Scan for new emails to process
- `context_scan`: Identify stale/uncertain information
- `digest_build`: Generate daily/weekly digests
- `interview_seed`: Create context interview questions
- `link_suggest`: Suggest connections between data
- `email_triage`: Process individual emails
- `task_extract`: Extract tasks from content
- `project_summary`: Generate project summaries

## 🔧 API Endpoints

### WebSocket (`ws://127.0.0.1:8788/ws`)
- `thread:send` - Chat messages from user
- `thread:append` - Chat messages to user
- `email:apply_action` - Apply actions to emails
- `interview:answer/dismiss` - Handle context interviews
- `project:create` - Create new projects
- `task:create` - Create new tasks

### REST API (`http://127.0.0.1:8787/api/`)
- `GET /projects` - List all projects
- `GET /projects/{id}/tasks` - Get project tasks
- `GET /interviews/active` - Get pending interviews
- `POST /jobs/{type}` - Trigger background jobs
- `GET /jobs/{id}/status` - Check job status

## 📁 File Structure

```
backend/
├── app.py              # FastAPI application & WebSocket handlers
├── models.py           # SQLAlchemy database models
├── claude_client.py    # Claude AI integration & prompt loading
├── agents.py           # Multi-agent system (COS + specialists)
├── job_queue.py        # Background job processing
├── init_db.py          # Database initialization & sample data
├── test_setup.py       # Backend testing script
└── .env.example        # Environment configuration template

electron/src/ui/
├── App.tsx             # Main React application
├── components/
│   ├── ChatInbox.tsx   # Chat interface component
│   └── EmailThreadView.tsx # Email thread component
├── lib/ws.ts           # WebSocket client
└── state/models.ts     # TypeScript type definitions

llm/prompts/            # AI prompts organized by category
├── system/             # Core system prompts
├── tools/              # Tool-specific prompts  
├── outlook/            # Email integration prompts
└── background/         # Background job prompts
```

## 🧪 Testing

```bash
# Run full backend test suite
cd backend
./.venv/bin/python test_setup.py

# Test individual components
./.venv/bin/python init_db.py    # Database & sample data
./.venv/bin/python app.py        # Start server manually
```

## 📊 Sample Data

The system includes sample data for development:
- **3 Projects**: Alpha (active), Website Redesign (active), Training (paused)
- **4 Tasks**: Mix of pending, in-progress, and completed
- **3 Emails**: Unprocessed emails with different priorities
- **3 Context Entries**: User behavior observations and insights
- **1 Interview**: Pending context question

## 🔄 Development Workflow

1. **Backend Development**: Modify Python files, restart server to see changes
2. **Frontend Development**: Edit React/TypeScript, hot reload automatically updates
3. **Prompt Engineering**: Edit `.md` files in `llm/prompts/`, restart backend to reload
4. **Database Changes**: Modify `models.py`, delete `cos.db`, restart to recreate

## 🐛 Common Issues

- **Import Errors**: Ensure virtual environment is activated
- **Database Errors**: Delete `cos.db` and restart to recreate
- **WebSocket Connection**: Verify ports 8787 (HTTP) and 8788 (WebSocket) are free
- **Missing Prompts**: Ensure all prompt files exist in `llm/prompts/`

## 📚 Next Steps

1. **Add Real Claude API**: Replace mock responses with actual Claude calls
2. **Outlook Integration**: Implement Microsoft Graph API
3. **Advanced Features**: Digest generation, link suggestions, context learning
4. **UI Polish**: Enhanced frontend components and workflows
5. **Testing**: Comprehensive test suites for all components