import React, { useEffect, useState } from "react";
import { connectWS } from "./lib/ws";
import EmailThreadView from "./components/EmailThreadView";
import ChatInbox from "./components/ChatInbox";
export default function App(){
  const [route, setRoute] = useState("inbox");
  useEffect(()=>{ connectWS("ws://127.0.0.1:8788/ws"); },[]);
  return (<div style={{display:"grid",gridTemplateColumns:"240px 1fr",minHeight:"100vh"}}>
    <aside className="card"><h3>COS</h3><button className="btn" onClick={()=>setRoute("inbox")}>Inbox</button><button className="btn" onClick={()=>setRoute("email")}>Email</button></aside>
    <main style={{padding:16}}>{route==="inbox"?<ChatInbox/>:<EmailThreadView/>}</main>
  </div>);
}
