import React from 'react';

interface EmailData {
  id: string;
  subject: string;
  sender: string;
  sender_name: string;
  body_preview: string;
  body_content?: string;
  received_at: string;
  is_read: boolean;
}

interface EmailAnalysis {
  email_id: string;
  summary: {
    key_points: string[];
    tone: 'urgent' | 'positive' | 'neutral' | 'concern';
    urgency_level: 'high' | 'medium' | 'low';
    requires_action: boolean;
  };
  context: {
    sender_relationship: string;
    is_internal: boolean;
    project_relevance: 'high' | 'medium' | 'low';
  };
  priority_score: number;
  recommendations: any[];
  analysis_timestamp: string;
}

interface AnalyzedEmail {
  email: EmailData;
  analysis: EmailAnalysis;
}

interface EmailDetailSimpleProps {
  email: AnalyzedEmail | null;
  onActionSelect: (email: AnalyzedEmail, action: any) => void;
  onClose: () => void;
}

const EmailDetailSimple: React.FC<EmailDetailSimpleProps> = ({ email, onClose }) => {
  console.log('EmailDetailSimple: Rendering with email:', email?.email?.subject);

  if (!email) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <h3>📧 Select an email to view details</h3>
        <p>Choose an email from the list to see details</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>{email?.email?.subject || 'No Subject'}</h2>
        <button onClick={onClose} style={{ 
          background: 'none', 
          border: '1px solid #ccc', 
          borderRadius: '4px', 
          padding: '5px 10px',
          cursor: 'pointer' 
        }}>
          ✕ Close
        </button>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <p><strong>From:</strong> {email?.email?.sender_name || email?.email?.sender || 'Unknown Sender'}</p>
        <p><strong>Received:</strong> {email?.email?.received_at || 'Unknown time'}</p>
        <p><strong>Read:</strong> {email?.email?.is_read ? 'Yes' : 'No'}</p>
      </div>

      <div style={{ 
        background: '#f5f5f5', 
        padding: '15px', 
        borderRadius: '8px', 
        marginBottom: '20px',
        border: '1px solid #ddd'
      }}>
        <h3 style={{ marginTop: 0 }}>Email Content</h3>
        <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.5' }}>
          {email?.email?.body_content || email?.email?.body_preview || 'No content available'}
        </div>
      </div>

      <div style={{ 
        background: '#e8f4fd', 
        padding: '15px', 
        borderRadius: '8px',
        border: '1px solid #bee5eb'
      }}>
        <h3 style={{ marginTop: 0 }}>🤖 AI Analysis</h3>
        <p><strong>Priority:</strong> {email?.analysis?.summary?.urgency_level || 'medium'}</p>
        <p><strong>Tone:</strong> {email?.analysis?.summary?.tone || 'neutral'}</p>
        <p><strong>Action Required:</strong> {email?.analysis?.summary?.requires_action ? 'Yes' : 'No'}</p>
        
        {(email?.analysis?.summary?.key_points || []).length > 0 && (
          <div>
            <strong>Key Points:</strong>
            <ul>
              {(email.analysis.summary.key_points || []).map((point, index) => (
                <li key={index}>{point}</li>
              ))}
            </ul>
          </div>
        )}

        <p><strong>Priority Score:</strong> {Math.round((email?.analysis?.priority_score || 0.5) * 100)}%</p>
        <p><strong>Recommendations:</strong> {(email?.analysis?.recommendations || []).length} available</p>
      </div>
    </div>
  );
};

export default EmailDetailSimple;