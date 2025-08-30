import React,{useEffect,useState} from "react";
import { on, send } from "../lib/ws";
import type { EmailSummary, Suggestion } from "../state/models";
export default function EmailThreadView(){
  const [summary,setSummary]=useState<EmailSummary|null>(null);
  const [suggestions,setSuggestions]=useState<Suggestion[]>([]);
  useEffect(()=>{ const a=on("email:summary",(d:EmailSummary)=>setSummary(d)); const b=on("email:suggestions",(d:any)=>setSuggestions(d.items||[])); return ()=>{a?.();b?.();};},[]);
  function apply(action:string,payload?:any){ if(!summary) return; send("email:apply_action",{thread_id:summary.thread_id,action,payload}); }
  return (<div className="card"><h2>Email Thread</h2>{!summary&&<p className="small">Select a thread.</p>}{summary&&(<><h3>Summary</h3><p>{summary.summary}</p><ul>{summary.highlights?.map((h,i)=>(<li key={i}>{h}</li>))}</ul></>)}<hr/><h3>Suggested Actions</h3>{!suggestions.length&&<p className="small">No suggestions yet.</p>}{suggestions.map((s,i)=>(<div key={i} className="row" style={{justifyContent:"space-between"}}><div><strong>{s.action}</strong><div className="small">{s.rationale||""}</div></div><button className="btn primary" onClick={()=>apply(s.action,s.payload)}>Apply</button></div>))}</div>);
}
