/**
 * WebSocket Client
 * ============================================================
 * Robust WebSocket client with:
 * - Exponential backoff reconnection
 * - Heartbeat/ping-pong for dead connection detection
 * - Message queuing during disconnection
 * - State machine management
 */

import type { 
  WebSocketConfig, 
  ConnectionState, 
  ConnectionEvents,
  ServerMessage,
} from "./types";
import { DEFAULT_WS_CONFIG } from "./types";

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private config: WebSocketConfig;
  private state: ConnectionState = "closed";
  private retryCount = 0;
  private retryTimeout: ReturnType<typeof setTimeout> | null = null;
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private heartbeatTimeout: ReturnType<typeof setTimeout> | null = null;
  private pongReceived = true;
  private messageQueue: any[] = [];
  private events: Partial<ConnectionEvents> = {};
  
  constructor(config: Partial<WebSocketConfig>) {
    this.config = { ...DEFAULT_WS_CONFIG, ...config };
  }
  
  // ============================================================
  // PUBLIC API
  // ============================================================
  
  /**
   * Connect to WebSocket server
   */
  connect(url?: string): void {
    if (url) {
      this.config.url = url;
    }
    
    if (!this.config.url) {
      throw new Error("WebSocket URL is required");
    }
    
    if (this.state === "connected" || this.state === "connecting") {
      console.warn("[WebSocket] Already connected or connecting");
      return;
    }
    
    this.setState("connecting");
    this.createConnection();
  }
  
  /**
   * Disconnect from server
   */
  disconnect(): void {
    this.stopReconnect();
    this.stopHeartbeat();
    
    if (this.ws) {
      // Use code 1000 for normal closure
      this.ws.close(1000, "Client disconnect");
      this.ws = null;
    }
    
    this.setState("closed");
    this.retryCount = 0;
  }
  
  /**
   * Send message to server
   */
  send(data: any): boolean {
    if (this.state !== "connected" || !this.ws) {
      // Queue message for later
      if (this.config.reconnect.enabled) {
        this.messageQueue.push(data);
        console.log("[WebSocket] Message queued, queue size:", this.messageQueue.length);
      }
      return false;
    }
    
    try {
      const message = typeof data === "string" ? data : JSON.stringify(data);
      this.ws.send(message);
      return true;
    } catch (error) {
      console.error("[WebSocket] Send error:", error);
      return false;
    }
  }
  
  /**
   * Get current connection state
   */
  getState(): ConnectionState {
    return this.state;
  }
  
  /**
   * Get retry count
   */
  getRetryCount(): number {
    return this.retryCount;
  }
  
  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.state === "connected";
  }
  
  // ============================================================
  // EVENT HANDLERS
  // ============================================================
  
  on<K extends keyof ConnectionEvents>(
    event: K, 
    handler: ConnectionEvents[K]
  ): void {
    this.events[event] = handler;
  }
  
  off<K extends keyof ConnectionEvents>(event: K): void {
    delete this.events[event];
  }
  
  // ============================================================
  // PRIVATE METHODS
  // ============================================================
  
  private createConnection(): void {
    try {
      this.ws = new WebSocket(
        this.config.url, 
        this.config.protocols
      );
      
      if (this.config.binaryType) {
        this.ws.binaryType = this.config.binaryType;
      }
      
      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
      this.ws.onerror = this.handleError.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      
    } catch (error) {
      console.error("[WebSocket] Connection error:", error);
      this.handleConnectionFailure();
    }
  }
  
  private handleOpen(): void {
    console.log("[WebSocket] Connected");
    
    this.setState("connected");
    this.retryCount = 0;
    
    // Start heartbeat
    if (this.config.heartbeat.enabled) {
      this.startHeartbeat();
    }
    
    // Flush message queue
    this.flushMessageQueue();
    
    // Notify listeners
    this.events.onOpen?.();
  }
  
  private handleClose(event: CloseEvent): void {
    console.log(`[WebSocket] Closed: ${event.code} ${event.reason}`);
    
    this.stopHeartbeat();
    this.ws = null;
    
    // Notify listeners
    this.events.onClose?.(event.code, event.reason);
    
    // Check if we should reconnect
    if (event.code === 1000) {
      // Normal closure, don't reconnect
      this.setState("closed");
    } else if (this.config.reconnect.enabled) {
      this.scheduleReconnect();
    } else {
      this.setState("closed");
    }
  }
  
  private handleError(event: Event): void {
    console.error("[WebSocket] Error:", event);
    this.events.onError?.(event);
  }
  
  private handleMessage(event: MessageEvent): void {
    try {
      let data: any;
      
      if (typeof event.data === "string") {
        data = JSON.parse(event.data);
      } else {
        data = event.data;
      }
      
      // Handle pong
      if (data.type === "pong") {
        this.pongReceived = true;
        return;
      }
      
      // Notify listeners
      this.events.onMessage?.(data);
      
    } catch (error) {
      console.error("[WebSocket] Message parse error:", error);
    }
  }
  
  private handleConnectionFailure(): void {
    if (this.config.reconnect.enabled) {
      this.scheduleReconnect();
    } else {
      this.setState("failed");
    }
  }
  
  // ============================================================
  // RECONNECTION
  // ============================================================
  
  private scheduleReconnect(): void {
    if (this.retryTimeout) {
      return; // Already scheduled
    }
    
    const maxRetries = this.config.reconnect.maxRetries;
    if (maxRetries > 0 && this.retryCount >= maxRetries) {
      console.error("[WebSocket] Max retries reached");
      this.setState("failed");
      return;
    }
    
    const delay = this.calculateReconnectDelay();
    this.retryCount++;
    
    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.retryCount})`);
    this.setState("reconnecting");
    
    this.events.onReconnecting?.(this.retryCount, delay);
    
    this.retryTimeout = setTimeout(() => {
      this.retryTimeout = null;
      this.createConnection();
    }, delay);
  }
  
  private calculateReconnectDelay(): number {
    const { initialDelay, maxDelay, multiplier, jitter } = this.config.reconnect;
    
    // Exponential backoff
    const base = initialDelay * Math.pow(multiplier, this.retryCount);
    const capped = Math.min(base, maxDelay);
    
    // Add jitter
    const jitterAmount = capped * jitter * (Math.random() * 2 - 1);
    
    return Math.floor(capped + jitterAmount);
  }
  
  private stopReconnect(): void {
    if (this.retryTimeout) {
      clearTimeout(this.retryTimeout);
      this.retryTimeout = null;
    }
  }
  
  // ============================================================
  // HEARTBEAT
  // ============================================================
  
  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.pongReceived = true;
    
    this.heartbeatInterval = setInterval(() => {
      if (!this.pongReceived) {
        // Connection is dead
        console.warn("[WebSocket] Heartbeat timeout, reconnecting");
        this.ws?.close(4000, "Heartbeat timeout");
        return;
      }
      
      this.pongReceived = false;
      this.sendPing();
      
      // Set timeout for pong
      this.heartbeatTimeout = setTimeout(() => {
        if (!this.pongReceived) {
          console.warn("[WebSocket] Pong not received");
        }
      }, this.config.heartbeat.timeout);
      
    }, this.config.heartbeat.interval);
  }
  
  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
  }
  
  private sendPing(): void {
    this.send({ type: "ping", ts: Date.now() });
  }
  
  // ============================================================
  // STATE MANAGEMENT
  // ============================================================
  
  private setState(newState: ConnectionState): void {
    if (this.state !== newState) {
      const oldState = this.state;
      this.state = newState;
      console.log(`[WebSocket] State: ${oldState} -> ${newState}`);
      this.events.onStateChange?.(newState);
    }
  }
  
  // ============================================================
  // MESSAGE QUEUE
  // ============================================================
  
  private flushMessageQueue(): void {
    if (this.messageQueue.length === 0) return;
    
    console.log(`[WebSocket] Flushing ${this.messageQueue.length} queued messages`);
    
    const queue = [...this.messageQueue];
    this.messageQueue = [];
    
    for (const message of queue) {
      this.send(message);
    }
  }
}

export default WebSocketClient;

