import React, { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { on, send, isConnected } from "../lib/ws";

type Msg = {
  id: string;
  role: "user" | "agent" | "system";
  content: string;
};

const Message = React.memo(({ message }: { message: Msg }) => (
  <div className="row" style={{ gap: 8, marginBottom: 8 }}>
    <span className="pill">{message.role}</span>
    <div>{message.content}</div>
  </div>
));

export default function ChatInbox() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);
  
  useEffect(() => {
    const off = on("thread:append", (d: { message: Msg }) => {
      setMessages(m => [...m, d.message]);
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
        content: text
      };
      setMessages(m => [...m, userMessage]);
      setText("");
      setIsTyping(true);
      setTimeout(scrollToBottom, 100);
    }
  }, [text, scrollToBottom]);
  
  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMsg();
    }
  }, [sendMsg]);
  
  const memoizedMessages = useMemo(() => 
    messages.map(m => <Message key={m.id} message={m} />),
    [messages]
  );
  
  return (
    <div className="col">
      <div className="card" style={{ minHeight: 320, maxHeight: 500, overflowY: 'auto' }}>
        {memoizedMessages}
        {isTyping && (
          <div className="row" style={{ gap: 8, marginBottom: 8 }}>
            <span className="pill">agent</span>
            <div style={{ fontStyle: 'italic', opacity: 0.7 }}>Thinking...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="row">
        <input 
          className="input" 
          style={{ flex: 1 }} 
          value={text} 
          onChange={e => setText(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type /plan, /summarize, /triage inbox..." 
          disabled={!isConnected()}
        />
        <button 
          className="btn primary" 
          onClick={sendMsg}
          disabled={!text.trim() || !isConnected()}
        >
          Send
        </button>
      </div>
    </div>
  );
}