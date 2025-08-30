import React,{useEffect,useState} from "react"; import { on, send } from "../lib/ws";
type Msg={id:string;role:"user"|"agent"|"system";content:string};
export default function ChatInbox(){
  const [messages,setMessages]=useState<Msg[]>([]); const [text,setText]=useState("");
  useEffect(()=>{ const off=on("thread:append",(d:{message:Msg})=>setMessages(m=>[...m,d.message])); return ()=>{off?.();};},[]);
  function sendMsg(){ if(!text.trim()) return; send("thread:send",{text}); setMessages(m=>[...m,{id:String(Date.now()),role:"user",content:text}]); setText(""); }
  return (<div className="col"><div className="card" style={{minHeight:320}}>{messages.map(m=>(<div key={m.id} className="row" style={{gap:8,marginBottom:8}}><span className="pill">{m.role}</span><div>{m.content}</div></div>))}</div><div className="row"><input className="input" style={{flex:1}} value={text} onChange={e=>setText(e.target.value)} placeholder="Type /plan, /summarize, /triage inbox..."/><button className="btn primary" onClick={sendMsg}>Send</button></div></div>);
}
