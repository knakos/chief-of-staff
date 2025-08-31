import React, { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { on, send, isConnected } from "../lib/ws";
import { Card, CardHeader, CardTitle, CardContent, Button, Input, Badge } from "./ui";

type Msg = {
  id: string;
  role: "user" | "agent" | "system";
  content: string;
  timestamp?: string;
};

const Message = React.memo(({ message }: { message: Msg }) => (
  <div className="message-container mb-4">
    <div className="message-header row gap-2 mb-2">
      <Badge variant={message.role} size="small">
        {message.role}
      </Badge>
      {message.timestamp && (
        <span className="text-xs text-muted">
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
      )}
    </div>
    <div className="message-content">
      <div className={`message-bubble ${message.role}`}>
        {message.content}
      </div>
    </div>
  </div>
));

const QuickAction = ({ action, description, icon, onClick }: {
  action: string;
  description: string;
  icon: React.ReactNode;
  onClick: (action: string) => void;
}) => (
  <button 
    className="quick-action-card"
    onClick={() => onClick(action)}
    disabled={!isConnected()}
  >
    <div className="quick-action-icon">
      {icon}
    </div>
    <div className="quick-action-content">
      <div className="font-medium text-sm">{action}</div>
      <div className="text-xs text-muted">{description}</div>
    </div>
  </button>
);

export default function ChatInbox() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [showQuickActions, setShowQuickActions] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);
  
  useEffect(() => {
    const off = on("thread:append", (d: { message: Msg }) => {
      const messageWithTimestamp = {
        ...d.message,
        timestamp: new Date().toISOString()
      };
      setMessages(m => [...m, messageWithTimestamp]);
      setIsTyping(false);
      setTimeout(scrollToBottom, 100);
    });
    return () => { off?.(); };
  }, [scrollToBottom]);
  
  const sendMsg = useCallback(() => {
    if (!text.trim()) return;
    
    if (!isConnected()) {
      alert('Not connected to server. Please wait for reconnection.');
      return;
    }
    
    const success = send("thread:send", { text });
    if (success) {
      const userMessage: Msg = {
        id: String(Date.now()),
        role: "user",
        content: text,
        timestamp: new Date().toISOString()
      };
      setMessages(m => [...m, userMessage]);
      setText("");
      setIsTyping(true);
      setShowQuickActions(false);
      setTimeout(scrollToBottom, 100);
    }
  }, [text, scrollToBottom]);
  
  const handleQuickAction = useCallback((action: string) => {
    setText(action);
    setShowQuickActions(false);
    inputRef.current?.focus();
  }, []);
  
  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMsg();
    }
  }, [sendMsg]);
  
  const clearChat = useCallback(() => {
    setMessages([]);
    setShowQuickActions(true);
    setIsTyping(false);
  }, []);
  
  const memoizedMessages = useMemo(() => 
    messages.map(m => <Message key={m.id} message={m} />),
    [messages]
  );

  const quickActions = [
    {
      action: "/plan",
      description: "Generate work plan",
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
          <line x1="16" y1="2" x2="16" y2="6"/>
          <line x1="8" y1="2" x2="8" y2="6"/>
          <line x1="3" y1="10" x2="21" y2="10"/>
        </svg>
      )
    },
    {
      action: "/summarize", 
      description: "Current work status",
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14,2 14,8 20,8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
        </svg>
      )
    },
    {
      action: "/triage",
      description: "Process inbox",
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
          <polyline points="22,6 12,13 2,6"/>
        </svg>
      )
    },
    {
      action: "/digest",
      description: "Daily summary", 
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12,6 12,12 16,14"/>
        </svg>
      )
    }
  ];
  
  return (
    <div className="chat-inbox">
      <Card elevated className="h-full">
        <CardHeader>
          <div className="row justify-between items-center">
            <CardTitle>Chat with your Chief of Staff</CardTitle>
            <div className="row gap-2">
              <div className={`connection-status ${isConnected() ? 'connected' : 'disconnected'}`}>
                <div className="status-dot" />
                <span className="text-sm">
                  {isConnected() ? 'Connected' : 'Offline'}
                </span>
              </div>
              {messages.length > 0 && (
                <Button variant="ghost" size="small" onClick={clearChat}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="3,6 5,6 21,6"/>
                    <path d="m19,6v14a2,2 0 0,1 -2,2H7a2,2 0 0,1 -2,-2V6m3,0V4a2,2 0 0,1 2,-2h4a2,2 0 0,1 2,2v2"/>
                  </svg>
                  Clear
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        
        <CardContent>
          <div className="messages-container">
            {messages.length === 0 && showQuickActions && (
              <div className="welcome-state">
                <div className="welcome-content text-center mb-8">
                  <h3 className="text-xl font-semibold mb-2">Welcome to your Chief of Staff</h3>
                  <p className="text-muted mb-6">
                    I'm here to help you stay organized and productive. Try one of these quick actions:
                  </p>
                </div>
                
                <div className="quick-actions-grid">
                  {quickActions.map(({ action, description, icon }) => (
                    <QuickAction
                      key={action}
                      action={action}
                      description={description}
                      icon={icon}
                      onClick={handleQuickAction}
                    />
                  ))}
                </div>
              </div>
            )}
            
            <div className="messages-list">
              {memoizedMessages}
              {isTyping && (
                <div className="message-container mb-4">
                  <div className="message-header row gap-2 mb-2">
                    <Badge variant="agent" size="small">agent</Badge>
                  </div>
                  <div className="message-content">
                    <div className="message-bubble agent typing">
                      <div className="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        </CardContent>
        
        <div className="chat-input-container">
          <div className="row gap-3">
            <Input
              ref={inputRef}
              value={text}
              onChange={e => setText(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type a message or try /plan, /summarize, /triage..."
              disabled={!isConnected()}
              className="flex-1"
            />
            <Button 
              variant="primary"
              onClick={sendMsg}
              disabled={!text.trim() || !isConnected()}
              loading={isTyping}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13"/>
                <polygon points="22,2 15,22 11,13 2,9 22,2"/>
              </svg>
              Send
            </Button>
          </div>
        </div>
      </Card>

      <style jsx>{`
        .chat-inbox {
          height: calc(100vh - 3rem);
          display: flex;
          flex-direction: column;
        }

        .messages-container {
          flex: 1;
          min-height: 400px;
          max-height: 600px;
          overflow-y: auto;
          padding: var(--space-4) 0;
        }

        .welcome-state {
          height: 100%;
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          padding: var(--space-8);
        }

        .quick-actions-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: var(--space-4);
          max-width: 600px;
          width: 100%;
        }

        .quick-action-card {
          display: flex;
          align-items: center;
          gap: var(--space-3);
          padding: var(--space-4);
          background: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: var(--radius-lg);
          cursor: pointer;
          transition: all var(--duration-base) var(--ease);
          text-align: left;
        }

        .quick-action-card:hover:not(:disabled) {
          background: var(--surface-hover);
          border-color: var(--border-hover);
          transform: translateY(-2px);
          box-shadow: var(--shadow-lg);
        }

        .quick-action-card:disabled {
          opacity: 0.5;
          cursor: not-allowed;
          transform: none !important;
        }

        .quick-action-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 2.5rem;
          height: 2.5rem;
          background: var(--brand-primary);
          border-radius: var(--radius-md);
          color: white;
          flex-shrink: 0;
        }

        .quick-action-content {
          flex: 1;
        }

        .message-bubble {
          padding: var(--space-3) var(--space-4);
          border-radius: var(--radius-lg);
          max-width: 80%;
          word-wrap: break-word;
          white-space: pre-wrap;
        }

        .message-bubble.user {
          background: var(--brand-primary);
          color: white;
          margin-left: auto;
          border-bottom-right-radius: var(--radius-base);
        }

        .message-bubble.agent {
          background: var(--surface);
          color: var(--text-primary);
          border: 1px solid var(--border);
          border-bottom-left-radius: var(--radius-base);
        }

        .message-bubble.system {
          background: var(--warning-bg);
          color: var(--warning);
          border: 1px solid var(--warning);
          font-size: var(--font-size-sm);
        }

        .message-bubble.typing {
          padding: var(--space-4);
        }

        .typing-indicator {
          display: flex;
          gap: 4px;
          align-items: center;
        }

        .typing-indicator span {
          width: 6px;
          height: 6px;
          background: var(--text-muted);
          border-radius: 50%;
          animation: typing 1.4s infinite ease-in-out;
        }

        .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
        .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

        @keyframes typing {
          0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
          40% { transform: scale(1); opacity: 1; }
        }

        .chat-input-container {
          border-top: 1px solid var(--border);
          padding: var(--space-4);
          background: var(--bg-secondary);
          border-radius: 0 0 var(--radius-lg) var(--radius-lg);
        }

        .connection-status {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          padding: var(--space-2) var(--space-3);
          border-radius: var(--radius-full);
          font-size: var(--font-size-sm);
        }

        .connection-status.connected {
          background: var(--success-bg);
          color: var(--success);
        }

        .connection-status.disconnected {
          background: var(--error-bg);
          color: var(--error);
        }

        .status-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: currentColor;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}