/**
 * WebSocketProvider
 * ============================================================
 * Context provider for WebSocket connection management
 * Implements reconnection with exponential backoff
 */

import { 
  createContext, 
  useContext, 
  ParentProps, 
  createSignal, 
  onMount, 
  onCleanup 
} from "solid-js";
import { WebSocketClient } from "~/lib/websocket/client";
import type { ConnectionState, TelemetryPayload } from "~/lib/websocket/types";
import { API_CONFIG } from "~/lib/utils/constants";

// Context value type
export interface WebSocketContextValue {
  // State
  state: ConnectionState;
  retryCount: number;
  lastError: string | null;
  isConnected: boolean;
  
  // Actions
  connect: (url?: string) => void;
  disconnect: () => void;
  send: (data: any) => boolean;
  
  // Event handlers
  onMessage: (handler: (data: any) => void) => () => void;
  onTelemetry: (handler: (data: TelemetryPayload[]) => void) => () => void;
}

// Context
const WebSocketContext = createContext<WebSocketContextValue>();

// Provider
export function WebSocketProvider(props: ParentProps) {
  // State signals
  const [state, setState] = createSignal<ConnectionState>("closed");
  const [retryCount, setRetryCount] = createSignal(0);
  const [lastError, setLastError] = createSignal<string | null>(null);
  
  // Message handlers
  const messageHandlers = new Set<(data: any) => void>();
  const telemetryHandlers = new Set<(data: TelemetryPayload[]) => void>();
  
  // WebSocket client
  let client: WebSocketClient | null = null;
  
  // Initialize client
  onMount(() => {
    client = new WebSocketClient({
      reconnect: {
        enabled: true,
        initialDelay: 1000,
        maxDelay: 30000,
        multiplier: 2,
        jitter: 0.3,
        maxRetries: 10,
      },
      heartbeat: {
        enabled: true,
        interval: 30000,
        timeout: 5000,
      },
    });
    
    // Set up event handlers
    client.on("onStateChange", (newState: ConnectionState) => {
      setState(newState);
      
      if (newState === "connected") {
        setLastError(null);
      }
    });
    
    client.on("onReconnecting", (attempt: number, delay: number) => {
      setRetryCount(attempt);
      console.log(`[WebSocketProvider] Reconnecting: attempt ${attempt}, delay ${delay}ms`);
    });
    
    client.on("onMessage", (data: any) => {
      // Distribute to all handlers
      messageHandlers.forEach(handler => handler(data));
      
      // Handle telemetry specifically
      if (data.type === "telemetry" && data.data) {
        telemetryHandlers.forEach(handler => handler(data.data));
      }
    });
    
    client.on("onError", (event: Event) => {
      setLastError("Connection error");
      console.error("[WebSocketProvider] Error:", event);
    });
    
    client.on("onClose", (code: number, reason: string) => {
      if (code !== 1000) {
        setLastError(`Connection closed: ${code} ${reason}`);
      }
    });
  });
  
  // Cleanup
  onCleanup(() => {
    if (client) {
      client.disconnect();
      client = null;
    }
    messageHandlers.clear();
    telemetryHandlers.clear();
  });
  
  // Actions
  const connect = (url?: string) => {
    if (!client) return;
    
    const wsUrl = url || API_CONFIG.WS_URL;
    console.log(`[WebSocketProvider] Connecting to ${wsUrl}`);
    
    setLastError(null);
    client.connect(wsUrl);
  };
  
  const disconnect = () => {
    if (!client) return;
    
    console.log("[WebSocketProvider] Disconnecting");
    client.disconnect();
    setRetryCount(0);
  };
  
  const send = (data: any): boolean => {
    if (!client) return false;
    return client.send(data);
  };
  
  const onMessage = (handler: (data: any) => void) => {
    messageHandlers.add(handler);
    return () => messageHandlers.delete(handler);
  };
  
  const onTelemetry = (handler: (data: TelemetryPayload[]) => void) => {
    telemetryHandlers.add(handler);
    return () => telemetryHandlers.delete(handler);
  };
  
  // Context value
  const value: WebSocketContextValue = {
    get state() { return state(); },
    get retryCount() { return retryCount(); },
    get lastError() { return lastError(); },
    get isConnected() { return state() === "connected"; },
    connect,
    disconnect,
    send,
    onMessage,
    onTelemetry,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {props.children}
    </WebSocketContext.Provider>
  );
}

// Hook
export function useWebSocket() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  }
  return context;
}

export default WebSocketProvider;

