import React, { useEffect, useState } from 'react';
import ErrorBoundary from './ErrorBoundary';

// Email Detail component for displaying selected email
const EmailDetail: React.FC<{ email: any; onBack: () => void }> = ({ email, onBack }) => {
  return (
    <div style={{ height: '100%', padding: '20px' }}>
      <div style={{ marginBottom: '20px' }}>
        <button 
          onClick={onBack}
          style={{
            padding: '8px 16px',
            backgroundColor: '#3b82f6',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          ← Back to List
        </button>
      </div>
      
      <div style={{ backgroundColor: '#f8f9fa', padding: '20px', borderRadius: '8px' }}>
        <h2 style={{ margin: '0 0 15px 0', color: '#1f2937' }}>
          {email?.subject || 'No Subject'}
        </h2>
        
        <div style={{ marginBottom: '15px', fontSize: '14px', color: '#6b7280' }}>
          <div><strong>From:</strong> {email?.sender_name || email?.sender_email || 'Unknown Sender'}</div>
          <div><strong>Date:</strong> {email?.received_at ? new Date(email.received_at).toLocaleString() : 'Unknown date'}</div>
          <div><strong>Priority:</strong> {email?.importance || 'Normal'}</div>
        </div>
        
        <div style={{ fontSize: '14px', lineHeight: '1.5', color: '#374151' }}>
          <strong>Preview:</strong>
          <div style={{ marginTop: '10px', padding: '15px', backgroundColor: 'white', borderRadius: '4px', border: '1px solid #e5e7eb' }}>
            {email?.body_preview || 'No preview available'}
          </div>
        </div>
      </div>
    </div>
  );
};

// Main Smart Email List component
const SmartEmailList: React.FC = () => {
  const [emails, setEmails] = useState<any[]>([]);
  const [selectedEmail, setSelectedEmail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [connectionStatus, setConnectionStatus] = useState('connecting');

  useEffect(() => {
    const connectAndLoad = () => {
      const ws = (window as any).ws;
      if (ws && ws.readyState === WebSocket.OPEN) {
        setConnectionStatus('connected');
        // Request emails from Outlook using the correct event
        ws.send(JSON.stringify({
          event: "email:get_recent",
          data: { limit: 50 }
        }));
      } else {
        setConnectionStatus('disconnected');
      }
    };

    // Initial connection attempt
    connectAndLoad();

    // Listen for WebSocket messages
    const handleMessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data);
        
        if (message.event === "email:recent_list" && message.data?.emails) {
          setEmails(message.data.emails);
          setLoading(false);
        }
        
        if (message.event === "connection_status") {
          setConnectionStatus(message.data?.status || 'disconnected');
        }
      } catch (error) {
        console.error("Failed to parse WebSocket message:", error);
      }
    };

    // Attach message listener
    const ws = (window as any).ws;
    if (ws) {
      ws.addEventListener('message', handleMessage);
      
      // Check connection status
      ws.addEventListener('open', () => setConnectionStatus('connected'));
      ws.addEventListener('close', () => setConnectionStatus('disconnected'));
    }

    return () => {
      if (ws) {
        ws.removeEventListener('message', handleMessage);
      }
    };
  }, []);

  const handleEmailSelect = (email: any) => {
    setSelectedEmail(email);
  };

  const handleBackToList = () => {
    setSelectedEmail(null);
  };

  // Show email detail if one is selected
  if (selectedEmail) {
    return (
      <ErrorBoundary>
        <EmailDetail email={selectedEmail} onBack={handleBackToList} />
      </ErrorBoundary>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', height: '100%' }}>
        <h2 style={{ color: '#1f2937', marginBottom: '10px' }}>📧 Smart Email Management</h2>
        <p style={{ color: '#6b7280' }}>
          {connectionStatus === 'connected' ? 'Loading emails...' : `Connection status: ${connectionStatus}`}
        </p>
        {connectionStatus === 'disconnected' && (
          <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#fee2e2', borderRadius: '8px', border: '1px solid #fecaca' }}>
            <p style={{ color: '#dc2626', margin: 0 }}>
              Backend disconnected. Please check if the backend is running on port 8787.
            </p>
          </div>
        )}
      </div>
    );
  }

  // Main email list view
  return (
    <div style={{ height: '100%', padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 style={{ color: '#1f2937', margin: 0 }}>📧 Smart Email Management</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div 
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: connectionStatus === 'connected' ? '#10b981' : '#ef4444'
            }}
          />
          <span style={{ fontSize: '14px', color: '#6b7280', textTransform: 'capitalize' }}>
            {connectionStatus}
          </span>
        </div>
      </div>
      
      <p style={{ color: '#6b7280', marginBottom: '20px' }}>
        {emails.length} emails with AI-powered insights
      </p>
      
      <div style={{ 
        maxHeight: 'calc(100vh - 200px)', 
        overflowY: 'auto',
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        backgroundColor: 'white'
      }}>
        {emails.length > 0 ? (
          emails.map((email, index) => (
            <div
              key={email.id || index}
              onClick={() => handleEmailSelect(email)}
              style={{
                padding: '16px',
                borderBottom: index < emails.length - 1 ? '1px solid #f3f4f6' : 'none',
                cursor: 'pointer',
                transition: 'background-color 0.2s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#f9fafb';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'white';
              }}
            >
              <div style={{ 
                fontWeight: 'bold', 
                fontSize: '16px', 
                marginBottom: '6px', 
                color: email.is_read ? '#6b7280' : '#1f2937'
              }}>
                {email.subject || 'No Subject'}
              </div>
              
              <div style={{ fontSize: '14px', color: '#6b7280', marginBottom: '6px' }}>
                <strong>From:</strong> {email.sender_name || email.sender_email || 'Unknown'}
              </div>
              
              <div style={{ fontSize: '13px', color: '#9ca3af', marginBottom: '8px' }}>
                {email.body_preview || 'No preview available'}
              </div>
              
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                fontSize: '12px',
                color: '#9ca3af'
              }}>
                <span>
                  {email.received_at ? new Date(email.received_at).toLocaleDateString() : 'Unknown date'}
                </span>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {email.has_attachments && (
                    <span style={{ backgroundColor: '#ddd6fe', color: '#7c3aed', padding: '2px 6px', borderRadius: '4px' }}>
                      📎
                    </span>
                  )}
                  <span style={{ 
                    backgroundColor: email.importance === 'high' ? '#fecaca' : '#f3f4f6',
                    color: email.importance === 'high' ? '#dc2626' : '#6b7280',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    textTransform: 'capitalize'
                  }}>
                    {email.importance || 'normal'}
                  </span>
                </div>
              </div>
            </div>
          ))
        ) : (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: '#6b7280' }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>📭</div>
            <p style={{ fontSize: '18px', fontWeight: '500', marginBottom: '8px' }}>No emails found</p>
            <p style={{ fontSize: '14px' }}>
              Make sure Outlook is connected and try refreshing.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

const EmailManagement: React.FC = () => {
  return (
    <ErrorBoundary>
      <SmartEmailList />
    </ErrorBoundary>
  );
};

export default EmailManagement;