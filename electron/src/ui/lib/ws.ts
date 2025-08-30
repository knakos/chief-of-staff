export type Listener=(data:any)=>void; const listeners=new Map<string,Set<Listener>>(); let socket:WebSocket|null=null;
export function connectWS(url:string){ socket=new WebSocket(url); socket.onmessage=ev=>{ try{ const msg=JSON.parse(ev.data); if(msg?.event) listeners.get(msg.event)?.forEach(fn=>fn(msg.data)); }catch{} }; return socket; }
export function on(event:string,fn:Listener){ if(!listeners.has(event)) listeners.set(event,new Set()); listeners.get(event)!.add(fn); return ()=>listeners.get(event)!.delete(fn); }
export function send(event:string,data:any){ if(socket?.readyState===WebSocket.OPEN) socket.send(JSON.stringify({event,data})); }
