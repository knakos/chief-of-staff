import React, { useEffect, useState, useCallback, useMemo } from "react";
import { on, send, isConnected } from "../lib/ws";
import type { EmailSummary, Suggestion } from "../state/models";

const SuggestionItem = React.memo(({ 
  suggestion, 
  onApply 
}: { 
  suggestion: Suggestion; 
  onApply: (action: string, payload?: any) => void;
}) => (
  <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
    <div>
      <strong>{suggestion.action}</strong>
      {suggestion.confidence && (
        <span className="small" style={{ marginLeft: 8 }}>
          ({Math.round(suggestion.confidence * 100)}% confident)
        </span>
      )}
      <div className="small">{suggestion.rationale || ""}</div>
    </div>
    <button 
      className="btn primary" 
      onClick={() => onApply(suggestion.action, suggestion.payload)}
      disabled={!isConnected()}
    >
      Apply
    </button>
  </div>
));

export default function EmailThreadView() {
  const [summary, setSummary] = useState<EmailSummary | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const unsubscribeSummary = on("email:summary", (data: EmailSummary) => {
      setSummary(data);
      setIsLoading(false);
      setError(null);
    });
    
    const unsubscribeSuggestions = on("email:suggestions", (data: any) => {
      setSuggestions(data.items || []);
    });
    
    const unsubscribeError = on("email:error", (data: any) => {
      setError(data.message || "An error occurred");
      setIsLoading(false);
    });
    
    const unsubscribeActionResult = on("email:action_applied", (data: any) => {
      console.log("Action applied:", data);
      // Could show a toast notification here
    });

    return () => {
      unsubscribeSummary?.();
      unsubscribeSuggestions?.();
      unsubscribeError?.();
      unsubscribeActionResult?.();
    };
  }, []);

  const apply = useCallback((action: string, payload?: any) => {
    if (!summary) return;
    
    if (!isConnected()) {
      setError("Not connected to server. Please wait for reconnection.");
      return;
    }
    
    setIsLoading(true);
    const success = send("email:apply_action", {
      thread_id: summary.thread_id,
      action,
      payload
    });
    
    if (!success) {
      setError("Failed to send action. Please try again.");
      setIsLoading(false);
    }
  }, [summary]);

  const renderedSuggestions = useMemo(() => 
    suggestions.map((suggestion, index) => (
      <SuggestionItem 
        key={`${suggestion.action}-${index}`} 
        suggestion={suggestion}
        onApply={apply}
      />
    )),
    [suggestions, apply]
  );

  return (
    <div className="card">
      <h2>Email Thread</h2>
      
      {error && (
        <div style={{ 
          padding: 8, 
          backgroundColor: '#fee', 
          border: '1px solid #fcc',
          borderRadius: 4,
          marginBottom: 16 
        }}>
          Error: {error}
        </div>
      )}
      
      {isLoading && (
        <div style={{ fontStyle: 'italic', opacity: 0.7, marginBottom: 16 }}>
          Processing...
        </div>
      )}
      
      {!summary && !isLoading && (
        <p className="small">Select a thread to view details.</p>
      )}
      
      {summary && (
        <>
          <h3>Summary</h3>
          <p>{summary.summary}</p>
          {summary.highlights && summary.highlights.length > 0 && (
            <ul>
              {summary.highlights.map((highlight, i) => (
                <li key={i}>{highlight}</li>
              ))}
            </ul>
          )}
        </>
      )}
      
      <hr />
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3>Suggested Actions</h3>
        {!isConnected() && (
          <span className="small" style={{ color: '#999' }}>
            Offline - actions disabled
          </span>
        )}
      </div>
      
      {!suggestions.length && !isLoading && (
        <p className="small">No suggestions available.</p>
      )}
      
      <div>
        {renderedSuggestions}
      </div>
    </div>
  );
}