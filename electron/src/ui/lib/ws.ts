export type Listener = (data: any) => void;

class WSManager {
  private listeners = new Map<string, Set<Listener>>();
  private socket: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private url = "";
  private isConnecting = false;
  
  connect(url: string) {
    this.url = url;
    this._connect();
    return this.socket;
  }
  
  private _connect() {
    if (this.isConnecting) return;
    this.isConnecting = true;
    
    try {
      this.socket = new WebSocket(this.url);
      
      this.socket.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.isConnecting = false;
      };
      
      this.socket.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg?.event) {
            const eventListeners = this.listeners.get(msg.event);
            if (eventListeners) {
              eventListeners.forEach(fn => {
                try {
                  fn(msg.data);
                } catch (error) {
                  console.error('Error in event listener:', error);
                }
              });
            }
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      this.socket.onclose = () => {
        console.log('WebSocket disconnected');
        this.isConnecting = false;
        this._handleReconnect();
      };
      
      this.socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.isConnecting = false;
      };
      
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.isConnecting = false;
      this._handleReconnect();
    }
  }
  
  private _handleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
      
      setTimeout(() => {
        this._connect();
      }, delay);
    } else {
      console.error('Max reconnection attempts reached');
    }
  }
  
  on(event: string, fn: Listener): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(fn);
    
    return () => {
      const eventListeners = this.listeners.get(event);
      if (eventListeners) {
        eventListeners.delete(fn);
        if (eventListeners.size === 0) {
          this.listeners.delete(event);
        }
      }
    };
  }
  
  send(event: string, data: any): boolean {
    if (this.socket?.readyState === WebSocket.OPEN) {
      try {
        this.socket.send(JSON.stringify({ event, data }));
        return true;
      } catch (error) {
        console.error('Error sending WebSocket message:', error);
        return false;
      }
    }
    console.warn('WebSocket not ready, message queued or dropped:', { event, data });
    return false;
  }
  
  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }
}

const wsManager = new WSManager();

export function connectWS(url: string) {
  return wsManager.connect(url);
}

export function on(event: string, fn: Listener) {
  return wsManager.on(event, fn);
}

export function send(event: string, data: any) {
  return wsManager.send(event, data);
}

export function isConnected() {
  return wsManager.isConnected();
}