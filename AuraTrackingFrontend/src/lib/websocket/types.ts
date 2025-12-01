/**
 * WebSocket Types
 * ============================================================
 * Type definitions for WebSocket communication
 */

// Connection states
export type ConnectionState = 
  | "closed" 
  | "connecting" 
  | "connected" 
  | "reconnecting" 
  | "failed";

// Configuration
export interface WebSocketConfig {
  url: string;
  
  // Reconnection settings
  reconnect: {
    enabled: boolean;
    initialDelay: number;    // ms
    maxDelay: number;        // ms
    multiplier: number;      // exponential factor
    jitter: number;          // 0-1, random variation
    maxRetries: number;      // 0 = unlimited
  };
  
  // Heartbeat settings
  heartbeat: {
    enabled: boolean;
    interval: number;        // ms between pings
    timeout: number;         // ms to wait for pong
  };
  
  // Message handling
  binaryType?: "arraybuffer" | "blob";
  protocols?: string[];
}

// Default configuration
export const DEFAULT_WS_CONFIG: WebSocketConfig = {
  url: "",
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
  binaryType: "arraybuffer",
};

// Message types from server
export interface ServerMessage {
  type: string;
  [key: string]: any;
}

export interface PingMessage {
  type: "ping";
  ts: number;
}

export interface PongMessage {
  type: "pong";
  ts: number;
}

export interface TelemetryMessage {
  type: "telemetry";
  data: TelemetryPayload[];
}

export interface TelemetryPayload {
  messageId?: string;
  deviceId: string;
  operatorId?: string;
  timestamp: number;
  gps: {
    latitude: number;
    longitude: number;
    altitude?: number;
    speed?: number;
    bearing?: number;
    accuracy?: number;
  };
  imu?: {
    accelX: number;
    accelY: number;
    accelZ: number;
    gyroX?: number;
    gyroY?: number;
    gyroZ?: number;
  };
}

export interface EventMessage {
  type: "event";
  data: {
    deviceId: string;
    eventType: string;
    timestamp: number;
    data: Record<string, any>;
  };
}

export interface ErrorMessage {
  type: "error";
  code: string;
  message: string;
}

// Connection events
export interface ConnectionEvents {
  onOpen: () => void;
  onClose: (code: number, reason: string) => void;
  onError: (error: Event) => void;
  onMessage: (data: any) => void;
  onStateChange: (state: ConnectionState) => void;
  onReconnecting: (attempt: number, delay: number) => void;
}

