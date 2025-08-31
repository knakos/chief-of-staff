import React, { useEffect, useState } from "react";
import { connectWS, isConnected } from "./lib/ws";
import EmailThreadView from "./components/EmailThreadView";
import ChatInbox from "./components/ChatInbox";
import { Card } from "./components/ui";

export default function App() {
  const [route, setRoute] = useState("inbox");
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');

  useEffect(() => {
    connectWS("ws://127.0.0.1:8788/ws");
    
    // Check connection status periodically
    const checkConnection = () => {
      setConnectionStatus(isConnected() ? 'connected' : 'disconnected');
    };
    
    checkConnection();
    const interval = setInterval(checkConnection, 1000);
    
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = () => {
    switch (connectionStatus) {
      case 'connected': return 'var(--success)';
      case 'connecting': return 'var(--warning)';
      case 'disconnected': return 'var(--error)';
    }
  };

  return (
    <div className="app-layout">
      <link rel="stylesheet" href="../../../design/modern-tokens.css" />
      
      {/* Sidebar */}
      <aside className="sidebar">
        <Card padding="medium" className="h-full">
          <div className="sidebar-header mb-6">
            <div className="row gap-3 mb-4">
              <div className="logo">
                <div className="w-8 h-8 bg-brand-primary rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-sm">COS</span>
                </div>
              </div>
              <div>
                <h1 className="text-lg font-semibold">Chief of Staff</h1>
                <div className="row gap-2 items-center">
                  <div 
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: getStatusColor() }}
                  />
                  <span className="text-sm text-muted">
                    {connectionStatus}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <nav className="sidebar-nav">
            <div className="nav-section mb-6">
              <h3 className="text-sm font-medium text-muted mb-3 uppercase tracking-wide">
                Main
              </h3>
              <div className="nav-items col gap-2">
                <button 
                  className={`nav-item ${route === "inbox" ? "active" : ""}`}
                  onClick={() => setRoute("inbox")}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                    <polyline points="22,6 12,13 2,6"/>
                  </svg>
                  Inbox
                </button>
                <button 
                  className={`nav-item ${route === "email" ? "active" : ""}`}
                  onClick={() => setRoute("email")}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14,2 14,8 20,8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                    <polyline points="10,9 9,9 8,9"/>
                  </svg>
                  Email Threads
                </button>
              </div>
            </div>

            <div className="nav-section">
              <h3 className="text-sm font-medium text-muted mb-3 uppercase tracking-wide">
                Quick Actions
              </h3>
              <div className="nav-items col gap-2">
                <button className="nav-item ghost">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2h-4"/>
                    <polyline points="9,11 12,14 15,11"/>
                    <line x1="12" y1="14" x2="12" y2="3"/>
                  </svg>
                  Triage Inbox
                </button>
                <button className="nav-item ghost">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12,6 12,12 16,14"/>
                  </svg>
                  Daily Digest
                </button>
                <button className="nav-item ghost">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 19c-5 0-8-3-8-6 0-3 3-6 8-6 2.4 0 4.5.85 6 2.25A6.97 6.97 0 0 1 21 13c0 3-3 6-8 6z"/>
                    <path d="M12 19c5 0 8-3 8-6 0-1.17-.29-2.27-.78-3.25A6.97 6.97 0 0 0 15 11c-3 0-6 1.34-6 4 0 3 3 6 8 6z"/>
                  </svg>
                  Context Interview
                </button>
              </div>
            </div>
          </nav>
        </Card>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <div className="content-wrapper p-6">
          {route === "inbox" ? <ChatInbox /> : <EmailThreadView />}
        </div>
      </main>

      <style jsx>{`
        .app-layout {
          display: grid;
          grid-template-columns: var(--sidebar-width) 1fr;
          min-height: 100vh;
          background: var(--bg-primary);
        }

        .sidebar {
          background: var(--bg-secondary);
          border-right: 1px solid var(--border);
          height: 100vh;
          overflow-y: auto;
        }

        .main-content {
          background: var(--bg-primary);
          overflow-y: auto;
          height: 100vh;
        }

        .content-wrapper {
          max-width: var(--container-max);
          margin: 0 auto;
        }

        .logo .w-8 {
          width: 2rem;
          height: 2rem;
        }

        .nav-item {
          display: flex;
          align-items: center;
          gap: var(--space-3);
          width: 100%;
          padding: var(--space-3) var(--space-4);
          font-size: var(--font-size-sm);
          font-weight: var(--font-weight-medium);
          color: var(--text-secondary);
          background: transparent;
          border: 1px solid transparent;
          border-radius: var(--radius-md);
          cursor: pointer;
          transition: all var(--duration-fast) var(--ease);
          text-align: left;
        }

        .nav-item:hover {
          color: var(--text-primary);
          background: var(--surface-hover);
          border-color: var(--border);
        }

        .nav-item.active {
          color: white;
          background: var(--brand-primary);
          border-color: var(--brand-primary);
        }

        .nav-item.ghost {
          color: var(--text-muted);
        }

        .nav-item.ghost:hover {
          color: var(--text-secondary);
        }

        .nav-item svg {
          flex-shrink: 0;
        }
      `}</style>
    </div>
  );
}