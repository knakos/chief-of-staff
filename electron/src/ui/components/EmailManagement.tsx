import React, { useEffect, useState } from 'react';
import ErrorBoundary from './ErrorBoundary';

// CSS-in-JS style for spinner animation
const spinnerStyle = `
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;

// Inject the CSS into the document head
if (!document.querySelector('#email-spinner-styles')) {
  const style = document.createElement('style');
  style.id = 'email-spinner-styles';
  style.textContent = spinnerStyle;
  document.head.appendChild(style);
}

// Email Detail component for displaying selected email
const EmailDetail: React.FC<{ email: any; onBack: () => void }> = ({ email, onBack }) => {
  return (
    <div style={{ height: '100%', padding: '20px', backgroundColor: 'red' }}>
      <div style={{ backgroundColor: 'yellow', color: 'black', padding: '50px', fontSize: '24px', textAlign: 'center', border: '10px solid blue' }}>
        TEST: CAN YOU SEE THIS BIG COLORED BOX WHEN YOU SELECT AN EMAIL?
      </div>
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
          <div><strong>From:</strong> {email?.sender_name || email?.sender_email || email?.sender || 'Unknown Sender'}</div>
          <div><strong>Date:</strong> {email?.received_at ? new Date(email.received_at).toLocaleString() : 'Unknown date'}</div>
          <div><strong>Priority:</strong> {email?.importance || 'Normal'}</div>
          <div><strong>Size:</strong> {email?.size ? `${Math.round(email.size / 1024)} KB` : 'Unknown'}</div>
          <div><strong>Read Status:</strong> {email?.is_read ? 'Read' : 'Unread'}</div>
          {email?.has_attachments && <div><strong>📎 Has Attachments</strong></div>}
          {email?.categories && <div><strong>Categories:</strong> {email.categories}</div>}
          
          {/* Recipients Section */}
          <div>
            {email?.to_recipients && email.to_recipients.length > 0 && (
              <div style={{ marginTop: '10px' }}>
                <strong>To:</strong> {email.to_recipients.map((recip: any, index: number) => (
                  <span key={index}>
                    {recip.name ? `${recip.name} <${recip.address}>` : recip.address}
                    {index < email.to_recipients.length - 1 ? ', ' : ''}
                  </span>
                ))}
              </div>
            )}
            
            {email?.cc_recipients && email.cc_recipients.length > 0 && (
              <div style={{ marginTop: '5px' }}>
                <strong>CC:</strong> {email.cc_recipients.map((recip: any, index: number) => (
                  <span key={index}>
                    {recip.name ? `${recip.name} <${recip.address}>` : recip.address}
                    {index < email.cc_recipients.length - 1 ? ', ' : ''}
                  </span>
                ))}
              </div>
            )}
            
            {email?.bcc_recipients && email.bcc_recipients.length > 0 && (
              <div style={{ marginTop: '5px' }}>
                <strong>BCC:</strong> {email.bcc_recipients.map((recip: any, index: number) => (
                  <span key={index}>
                    {recip.name ? `${recip.name} <${recip.address}>` : recip.address}
                    {index < email.bcc_recipients.length - 1 ? ', ' : ''}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* COS Properties Section */}
        {(email?.project_id || email?.analysis || email?.confidence) && (
          <div style={{ 
            marginBottom: '20px', 
            padding: '15px', 
            backgroundColor: '#e0f2fe', 
            borderRadius: '8px', 
            border: '1px solid #0891b2' 
          }}>
            <h3 style={{ margin: '0 0 10px 0', color: '#0f172a', fontSize: '16px' }}>
              🤖 AI Analysis
            </h3>
            
            {email?.project_id && (
              <div style={{ marginBottom: '8px', fontSize: '14px' }}>
                <strong>Project ID:</strong> <span style={{ color: '#0891b2', fontFamily: 'monospace' }}>{email.project_id}</span>
              </div>
            )}
            
            {email?.confidence && (
              <div style={{ marginBottom: '8px', fontSize: '14px' }}>
                <strong>Confidence:</strong> <span style={{ color: '#059669' }}>{Math.round(email.confidence * 100)}%</span>
              </div>
            )}
            
            {email?.provenance && (
              <div style={{ marginBottom: '8px', fontSize: '14px' }}>
                <strong>Source:</strong> <span style={{ color: '#6b7280' }}>{email.provenance}</span>
              </div>
            )}
            
            {email?.analysis && (
              <div style={{ marginTop: '12px' }}>
                <div style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '8px', color: '#0f172a' }}>
                  Analysis Details:
                </div>
                
                {email.analysis.priority && (
                  <div style={{ marginBottom: '6px', fontSize: '13px' }}>
                    <strong>Priority:</strong> 
                    <span style={{ 
                      marginLeft: '8px',
                      padding: '2px 8px',
                      borderRadius: '12px',
                      backgroundColor: email.analysis.priority === 'high' ? '#fecaca' : 
                                       email.analysis.priority === 'medium' ? '#fed7aa' : '#d1fae5',
                      color: email.analysis.priority === 'high' ? '#991b1b' : 
                             email.analysis.priority === 'medium' ? '#9a3412' : '#065f46',
                      fontSize: '12px'
                    }}>
                      {email.analysis.priority}
                    </span>
                  </div>
                )}
                
                {email.analysis.urgency && (
                  <div style={{ marginBottom: '6px', fontSize: '13px' }}>
                    <strong>Urgency:</strong>
                    <span style={{ 
                      marginLeft: '8px',
                      padding: '2px 8px',
                      borderRadius: '12px',
                      backgroundColor: email.analysis.urgency === 'high' ? '#fecaca' : 
                                       email.analysis.urgency === 'medium' ? '#fed7aa' : '#d1fae5',
                      color: email.analysis.urgency === 'high' ? '#991b1b' : 
                             email.analysis.urgency === 'medium' ? '#9a3412' : '#065f46',
                      fontSize: '12px'
                    }}>
                      {email.analysis.urgency}
                    </span>
                  </div>
                )}
                
                {email.analysis.tone && (
                  <div style={{ marginBottom: '6px', fontSize: '13px' }}>
                    <strong>Tone:</strong>
                    <span style={{ 
                      marginLeft: '8px',
                      padding: '2px 8px',
                      borderRadius: '12px',
                      backgroundColor: '#e0e7ff',
                      color: '#3730a3',
                      fontSize: '12px'
                    }}>
                      {email.analysis.tone}
                    </span>
                  </div>
                )}
                
                {email.analysis.summary && (
                  <div style={{ marginTop: '10px' }}>
                    <strong style={{ fontSize: '13px' }}>AI Summary:</strong>
                    <div style={{ 
                      marginTop: '6px',
                      padding: '10px',
                      backgroundColor: 'white',
                      borderRadius: '6px',
                      border: '1px solid #cbd5e1',
                      fontSize: '13px',
                      lineHeight: '1.4',
                      color: '#374151',
                      fontStyle: 'italic'
                    }}>
                      {email.analysis.summary}
                    </div>
                  </div>
                )}
                
                {email.analysis.confidence && (
                  <div style={{ marginTop: '8px', fontSize: '12px', color: '#6b7280' }}>
                    Analysis confidence: {Math.round(email.analysis.confidence * 100)}%
                  </div>
                )}
              </div>
            )}
          </div>
        )}
        
        <div className="green-email-body" style={{ fontSize: '14px', lineHeight: '1.5', color: '#374151' }}>
          <strong>Body:</strong>
          <textarea 
            value={email?.body_content || 'No body content available'} 
            readOnly
            style={{ 
              marginTop: '10px', 
              width: '100%', 
              minHeight: '300px',
              padding: '15px', 
              backgroundColor: 'white', 
              borderRadius: '4px', 
              border: '1px solid #e5e7eb',
              fontSize: '13px',
              lineHeight: '1.5',
              fontFamily: 'inherit',
              resize: 'vertical'
            }}
          />
        </div>

        {/* Debug: Show all properties */}
        <details style={{ marginTop: '20px' }}>
          <summary style={{ cursor: 'pointer', color: '#6b7280', fontSize: '12px' }}>
            🔍 Debug: Show All Properties ({Object.keys(email || {}).length} total)
          </summary>
          <div style={{ 
            marginTop: '10px', 
            padding: '15px', 
            backgroundColor: '#f9fafb', 
            borderRadius: '4px', 
            border: '1px solid #e5e7eb',
            fontSize: '11px',
            fontFamily: 'monospace'
          }}>
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {JSON.stringify(email, null, 2)}
            </pre>
          </div>
        </details>
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
  const [contextMenu, setContextMenu] = useState<{x: number, y: number, email: any} | null>(null);
  const [analyzingEmails, setAnalyzingEmails] = useState<Set<string>>(new Set());

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
        
        if (message.event === "email:analyzed") {
          // Update the analyzed email in the list
          const emailId = message.data?.email_id;
          const emailData = message.data?.email_data;
          if (emailId && emailData) {
            setEmails(prev => prev.map(email => 
              email.id === emailId ? emailData : email
            ));
            // Remove from analyzing set
            setAnalyzingEmails(prev => {
              const newSet = new Set(prev);
              newSet.delete(emailId);
              return newSet;
            });
            // Update selected email if it's the one being viewed
            if (selectedEmail?.id === emailId) {
              setSelectedEmail(emailData);
            }
          }
        }
        
        if (message.event === "email:analysis_error") {
          // Remove from analyzing set on error
          const emailId = message.data?.email_id;
          if (emailId) {
            setAnalyzingEmails(prev => {
              const newSet = new Set(prev);
              newSet.delete(emailId);
              return newSet;
            });
          }
          console.error('Email analysis failed:', message.data?.message);
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

  const handleRightClick = (event: React.MouseEvent, email: any) => {
    event.preventDefault();
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
      email: email
    });
  };

  const handleAnalyzeEmail = (email: any) => {
    if (analyzingEmails.has(email.id)) {
      return; // Already analyzing
    }
    
    // Add to analyzing set
    setAnalyzingEmails(prev => new Set(prev).add(email.id));
    
    // Send analysis request
    const ws = (window as any).ws;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        event: "email:analyze",
        data: { email_id: email.id }
      }));
    }
    
    setContextMenu(null);
  };

  const closeContextMenu = () => {
    setContextMenu(null);
  };

  // Close context menu on clicks outside
  useEffect(() => {
    const handleClickOutside = () => {
      if (contextMenu) {
        setContextMenu(null);
      }
    };

    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, [contextMenu]);

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
              onContextMenu={(e) => handleRightClick(e, email)}
              style={{
                padding: '16px',
                borderBottom: index < emails.length - 1 ? '1px solid #f3f4f6' : 'none',
                cursor: 'pointer',
                transition: 'background-color 0.2s',
                position: 'relative'
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
                <strong>From:</strong> {email.sender_name || email.sender_email || email.sender || 'Unknown'}
                {(email.to_recipients?.length > 0 || email.cc_recipients?.length > 0) && (
                  <span style={{ marginLeft: '10px', fontSize: '12px', color: '#9ca3af' }}>
                    • To: {email.to_recipients?.length || 0}
                    {email.cc_recipients?.length > 0 && `, CC: ${email.cc_recipients.length}`}
                  </span>
                )}
              </div>
              
              <div style={{ fontSize: '13px', color: '#9ca3af', marginBottom: '8px' }}>
                {email.body_content || email.body_preview || 'No body content available'}
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
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
                  {/* Analyzing indicator */}
                  {analyzingEmails.has(email.id) && (
                    <span style={{ 
                      backgroundColor: '#fef3c7', 
                      color: '#d97706', 
                      padding: '2px 6px', 
                      borderRadius: '4px', 
                      fontSize: '11px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}>
                      <span style={{ 
                        width: '8px', 
                        height: '8px', 
                        border: '1px solid #d97706', 
                        borderTop: '1px solid transparent', 
                        borderRadius: '50%', 
                        animation: 'spin 1s linear infinite' 
                      }}></span>
                      Analyzing...
                    </span>
                  )}
                  
                  {/* Analyze button for emails without analysis */}
                  {!analyzingEmails.has(email.id) && !email.analysis?.priority && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleAnalyzeEmail(email);
                      }}
                      style={{
                        backgroundColor: '#f0f9ff',
                        color: '#0369a1',
                        border: '1px solid #bae6fd',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        cursor: 'pointer',
                        transition: 'background-color 0.2s'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#e0f2fe';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = '#f0f9ff';
                      }}
                    >
                      🤖 Analyze
                    </button>
                  )}

                  {email.has_attachments && (
                    <span style={{ backgroundColor: '#ddd6fe', color: '#7c3aed', padding: '2px 6px', borderRadius: '4px', fontSize: '11px' }}>
                      📎
                    </span>
                  )}
                  
                  {/* COS Analysis Indicator */}
                  {(email.analysis || email.project_id) && (
                    <span style={{ backgroundColor: '#e0f2fe', color: '#0891b2', padding: '2px 6px', borderRadius: '4px', fontSize: '11px' }}>
                      🤖 AI
                    </span>
                  )}
                  
                  {/* Priority indicator */}
                  {email.analysis?.priority && (
                    <span style={{ 
                      backgroundColor: email.analysis.priority === 'high' ? '#fecaca' : 
                                       email.analysis.priority === 'medium' ? '#fed7aa' : '#d1fae5',
                      color: email.analysis.priority === 'high' ? '#dc2626' : 
                             email.analysis.priority === 'medium' ? '#ea580c' : '#059669',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      textTransform: 'capitalize'
                    }}>
                      {email.analysis.priority}
                    </span>
                  )}
                  
                  {/* Urgency indicator */}
                  {email.analysis?.urgency && email.analysis.urgency !== 'normal' && (
                    <span style={{ 
                      backgroundColor: email.analysis.urgency === 'high' ? '#fecaca' : '#fed7aa',
                      color: email.analysis.urgency === 'high' ? '#dc2626' : '#ea580c',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      fontSize: '11px'
                    }}>
                      ⚡ {email.analysis.urgency}
                    </span>
                  )}
                  
                  {/* Project indicator */}
                  {email.project_id && (
                    <span style={{ backgroundColor: '#f0fdf4', color: '#16a34a', padding: '2px 6px', borderRadius: '4px', fontSize: '11px' }}>
                      📁 Project
                    </span>
                  )}
                  
                  {/* Regular importance fallback */}
                  {!email.analysis?.priority && (
                    <span style={{ 
                      backgroundColor: email.importance === 'high' ? '#fecaca' : '#f3f4f6',
                      color: email.importance === 'high' ? '#dc2626' : '#6b7280',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      textTransform: 'capitalize'
                    }}>
                      {email.importance || 'normal'}
                    </span>
                  )}
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
      
      {/* Context Menu */}
      {contextMenu && (
        <div
          style={{
            position: 'fixed',
            top: contextMenu.y,
            left: contextMenu.x,
            backgroundColor: 'white',
            border: '1px solid #e5e7eb',
            borderRadius: '6px',
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
            zIndex: 1000,
            minWidth: '160px',
            overflow: 'hidden'
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div
            onClick={() => {
              handleEmailSelect(contextMenu.email);
              closeContextMenu();
            }}
            style={{
              padding: '8px 12px',
              cursor: 'pointer',
              fontSize: '14px',
              color: '#374151',
              transition: 'background-color 0.15s',
              borderBottom: '1px solid #f3f4f6'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#f9fafb';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'white';
            }}
          >
            📄 View Details
          </div>
          
          <div
            onClick={() => handleAnalyzeEmail(contextMenu.email)}
            style={{
              padding: '8px 12px',
              cursor: 'pointer',
              fontSize: '14px',
              color: '#374151',
              transition: 'background-color 0.15s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#f9fafb';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'white';
            }}
          >
            🤖 Analyze with AI
          </div>
        </div>
      )}
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