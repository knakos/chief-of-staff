# Chief of Staff - AI-Powered Personal Productivity Orchestrator

> **A comprehensive digital Chief of Staff assistant that serves as an intelligent productivity orchestrator, designed to understand your complete work context and proactively manage all aspects of professional workflow.**

## 🎯 Project Vision

Chief of Staff is **NOT** just another email manager or task tracker. It's an intelligent productivity orchestrator that:

- **Understands Context**: Builds deep understanding of your work patterns, priorities, and relationships
- **Proactive Intelligence**: Anticipates needs and provides actionable insights before you ask
- **Project-Centric**: Everything (emails, tasks, information) links back to your strategic goals
- **Contextual Memory**: Learns from your decisions and evolves with your workflow
- **Multi-Channel Integration**: Unifies email, calendar, tasks, and communication across platforms

## 🏗️ Architecture Overview

### **Three-Tier System**
- **Frontend**: Electron desktop app with React-in-HTML architecture and modern design system
- **Backend**: FastAPI with WebSocket real-time communication, multi-agent AI coordination
- **AI Layer**: Claude-powered multi-agent system with specialized domain expertise

### **Multi-Agent AI System**
- **COS Orchestrator**: Master coordinator routing user input and coordinating responses
- **Contextor Agent**: Manages strategic interviews and builds user context (≤1/day limit)
- **Email Triage Agent**: Intelligent email processing with GTD categorization and project linking
- **Summarizer Agent**: Content analysis and actionable task extraction
- **Writer Agent**: Context-aware draft generation and communication assistance
- **Background Jobs**: Continuous scanning, digest building, and intelligent link suggestions

### **Hybrid Outlook Integration**
- **COM Integration**: Direct Windows Outlook access for real-time email manipulation
- **Graph API Fallback**: Cloud-based access when local Outlook unavailable
- **GTD Organization**: Automated folder structure (COS_Actions, COS_Assigned, COS_ReadLater, etc.)
- **Extended Properties**: Email-project linking via custom metadata fields

## 🚀 Quick Start

### Prerequisites
- **Windows Environment**: Required for Outlook COM integration
- **Outlook Desktop**: Must be running with target account logged in
- **Python 3.11+**: For backend development
- **Node.js**: For Electron frontend
- **Anthropic API Key**: For AI functionality (optional for development with mock responses)

### Setup Commands
```bash
# 1. Backend Setup
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
copy .env.example .env  # Add your ANTHROPIC_API_KEY
python init_db.py  # Initialize with sample data

# 2. Start Backend Server
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8787 --reload

# 3. Start Frontend (new terminal)
cd ..
npm install
npm run dev
```

### Verification
- Backend: `http://127.0.0.1:8787/docs` (API documentation)
- WebSocket: `ws://127.0.0.1:8787/ws` (real-time communication)
- Frontend: Electron window opens automatically

## 💡 Key Features

### **Intelligent Project Management**
- **Area → Project → Task Hierarchy**: Strategic organization with Work/Personal system areas
- **Project Areas Carousel**: Clean 2-area navigation with position indicators
- **Inline Task Editing**: Click-to-edit functionality with real-time synchronization
- **Status Flow Logic**: Strategic project statuses (planning→active⟷paused⟷blocked→completed)
- **Cascade Operations**: Archive projects with task pausing, delete with full cascade warnings

### **Advanced Email Intelligence**
- **Smart Triage**: AI-powered categorization with project context awareness
- **Extended Metadata**: Custom properties for project linking and confidence scoring
- **GTD Workflow**: Automated folder organization following Getting Things Done methodology
- **Context-Aware Actions**: Intelligent suggestions based on sender relationship and content analysis

### **Proactive Context Building**
- **Strategic Interviews**: Daily context-gathering questions with intelligent timing
- **Behavioral Learning**: Pattern recognition for work habits and decision-making styles
- **Relationship Mapping**: Contact categorization and communication preference learning
- **Context Expiration**: Time-sensitive information management with automatic cleanup

### **Real-Time Communication**
- **WebSocket Architecture**: Instant updates for job status, agent responses, and system events
- **Connection Awareness**: Visual indicators throughout UI with graceful offline handling
- **Background Processing**: Non-blocking job queue for continuous intelligence gathering

## 🛠️ Technical Stack

### **Backend Technologies**
- **FastAPI**: Modern Python web framework with automatic API documentation
- **SQLAlchemy**: ORM with SQLite database (WAL mode for performance)
- **WebSockets**: Real-time bidirectional communication
- **Pydantic**: Data validation and serialization
- **Claude AI**: Single AI provider with prompt-based agent system
- **pywin32**: Windows COM integration for direct Outlook access

### **Frontend Technologies**
- **Electron**: Cross-platform desktop application framework
- **React**: Component-based UI (embedded in HTML, no separate build process)
- **CSS Custom Properties**: Design token system for consistent theming
- **WebSocket Client**: Real-time backend communication with auto-reconnection

### **Database Schema**
- **Areas**: Top-level organization categories (Work, Personal)
- **Projects**: Strategic initiatives within areas with status tracking
- **Tasks**: Actionable items with sponsor/owner business context
- **Emails**: Metadata and intelligence (actual emails accessed via Outlook)
- **ContextEntries**: User insights and behavioral patterns
- **Jobs**: Background processing queue with status tracking
- **Interviews**: Strategic context-gathering questions with scheduling limits

## 📊 Development Status

### ✅ **Completed Core Infrastructure**
- Multi-agent AI system with specialized domain agents
- Real-time WebSocket communication with connection awareness
- Comprehensive project/task management with business logic
- Outlook integration (COM + Graph API hybrid approach)
- Modern design system with CSS custom properties
- Background job processing with status tracking
- Database optimization with WAL mode and comprehensive indexing
- Rate limiting system preventing API quota exhaustion
- Archived project deletion with cascade warnings

### 🔄 **Active Development Areas**
- Email management interface with live Outlook integration
- Enhanced context interview system with intelligent scheduling
- Advanced email intelligence and recommendation engine
- User profile and organizational context acquisition
- Performance monitoring and optimization

### 📋 **Upcoming Priorities**
- Calendar integration for meeting-aware task scheduling
- Document intelligence with OCR and content extraction
- Advanced analytics and productivity insights
- Mobile companion application
- Enterprise features (SSO, compliance, multi-tenant)

## 📁 Project Structure

```
├── backend/                 # FastAPI backend application
│   ├── app.py              # Main application and WebSocket handlers
│   ├── models.py           # SQLAlchemy database models
│   ├── agents.py           # Multi-agent AI coordination system
│   ├── claude_client.py    # AI client with prompt management
│   ├── job_queue.py        # Background processing system
│   ├── integrations/       # External service connectors
│   └── llm/prompts/        # AI agent prompts organized by category
├── design/                 # Design system and UI tokens
│   └── modern-tokens.css   # CSS custom properties for theming
├── scripts/                # Development and deployment scripts
├── main.js                 # Electron main process
├── preload.js             # Secure bridge for renderer process
├── index.html             # Complete React application (~5000 lines)
└── package.json           # Node.js dependencies and scripts
```

## 🔧 Development Workflow

### **Local Development**
1. **Backend Changes**: Modify Python files → uvicorn auto-reloads
2. **Frontend Changes**: Edit index.html → Electron hot reloads
3. **AI Prompts**: Edit `.md` files in `llm/prompts/` → restart backend
4. **Database Schema**: Modify `models.py` → delete `cos.db` → restart

### **Testing & Validation**
```bash
# Comprehensive backend validation
cd backend && python test_setup.py

# Database optimization
python optimize_db.py

# Performance monitoring
# Built-in timing decorators provide performance metrics in logs
```

### **Architecture Principles**
- **Context is King**: Every feature builds and maintains user context
- **Proactive Intelligence**: Anticipate needs, don't just respond
- **Project-Centric**: Everything links back to strategic goals
- **Performance First**: Optimize for responsiveness and reliability
- **Design Consistency**: Use modern design tokens for all styling

## 📈 Development Todo List

### **High Priority - Foundation**
- [ ] **Email Management Interface**
  - [ ] Live Outlook email list with sorting/filtering
  - [ ] Rich email detail panel with inline actions
  - [ ] Context-aware action suggestions sidebar
  - [ ] Real-time email search with project context
  - [ ] Smart draft generation with recipient templates

- [ ] **User Context Acquisition System**
  - [ ] Guided onboarding for personal/work details
  - [ ] Contact import and categorization system
  - [ ] Organizational structure mapping
  - [ ] Work pattern and preference learning
  - [ ] Goal setting with timeline tracking

- [ ] **Enhanced Email Intelligence**
  - [ ] Content-based action recommendations
  - [ ] Conversation threading with visual indicators
  - [ ] Automatic email-to-project association
  - [ ] Priority scoring based on multiple factors

### **Medium Priority - Enhancement**
- [ ] **Multi-Channel Integration**
  - [ ] Outlook Calendar integration for meeting-aware scheduling
  - [ ] Microsoft Teams/Slack context extension
  - [ ] Document OCR and intelligent analysis
  - [ ] Mobile companion interface

- [ ] **Advanced AI Capabilities**
  - [ ] Custom agent training for domain-specific tasks
  - [ ] Multi-language support with translation
  - [ ] Voice interface for hands-free operation
  - [ ] Predictive analytics for project timelines

- [ ] **Collaboration Features**
  - [ ] Team dashboards with role-based access
  - [ ] Delegation tracking across team members
  - [ ] Knowledge base with searchable decisions
  - [ ] Performance analytics and insights

### **Long-term Vision**
- [ ] **Enterprise Integration**
  - [ ] SSO authentication (Azure AD/Google Workspace)
  - [ ] RESTful API for third-party integrations
  - [ ] Compliance features and audit trails
  - [ ] Multi-tenant cloud architecture

- [ ] **AI-Powered Insights**
  - [ ] Strategic planning with milestone prediction
  - [ ] Competitive intelligence monitoring
  - [ ] Performance optimization recommendations
  - [ ] Executive reporting automation

### **Technical Debt & Infrastructure**
- [ ] **Code Quality**
  - [ ] Comprehensive test coverage (unit, integration, e2e)
  - [ ] TypeScript migration for frontend
  - [ ] Centralized error handling
  - [ ] Performance monitoring integration

- [ ] **Security & Reliability**
  - [ ] End-to-end encryption for sensitive data
  - [ ] Automated backup and disaster recovery
  - [ ] Security audit and penetration testing
  - [ ] Production monitoring with alerting

## 🤝 Contributing

### **Development Environment**
- See `CLAUDE.md` for comprehensive development guidance
- Check `DEVELOPMENT.md` for detailed setup instructions
- Review `WINDOWS_SETUP.md` for Windows-specific configuration

### **Code Standards**
- **Design Tokens Only**: Use CSS custom properties, never hardcoded values
- **Legacy Outlook Methods**: Use standard property sync, avoid batch operations
- **WebSocket Events**: Follow `{event, data}` JSON message format
- **Status Consistency**: Use `not_started` for tasks, not `pending`

### **Architecture Guidelines**
- Maintain separation between agents and their specialized domains
- Ensure all AI interactions go through the COS Orchestrator
- Keep prompt files organized by category in `llm/prompts/`
- Use cascade relationships for database integrity

## 📄 License

This project is licensed under the ISC License - see the [LICENSE](LICENSE) file for details.

## 🔗 Related Documentation

- **[CLAUDE.md](CLAUDE.md)**: Comprehensive development guide for Claude Code instances
- **[DEVELOPMENT.md](DEVELOPMENT.md)**: Detailed development status and roadmap
- **[WINDOWS_SETUP.md](WINDOWS_SETUP.md)**: Windows-specific setup instructions

---

> **"Intelligence over automation, context over convenience, proactivity over reactivity."**
> 
> Built with ❤️ for productivity professionals who demand more than just another task manager.