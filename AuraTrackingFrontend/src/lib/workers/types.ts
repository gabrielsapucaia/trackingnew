/**
 * Worker Types
 * ============================================================
 * Shared type definitions for Web Workers
 */

// ============================================================
// TELEMETRY PACKET (from MQTT/WebSocket)
// ============================================================

export interface GpsData {
  latitude: number;
  longitude: number;
  altitude?: number;
  speed?: number;       // m/s
  bearing?: number;     // degrees
  accuracy?: number;    // meters
}

export interface ImuData {
  accelX: number;       // m/s²
  accelY: number;       // m/s²
  accelZ: number;       // m/s²
  gyroX?: number;       // rad/s
  gyroY?: number;       // rad/s
  gyroZ?: number;       // rad/s
}

export interface TelemetryPacket {
  messageId?: string;
  deviceId: string;
  operatorId?: string;
  timestamp: number;    // ms since epoch
  gps: GpsData;
  imu?: ImuData;
}

export interface EventPacket {
  messageId?: string;
  deviceId: string;
  operatorId?: string;
  timestamp: number;
  eventType: string;
  data: Record<string, any>;
}

// ============================================================
// WORKER MESSAGES
// ============================================================

// Messages TO workers
export type WorkerInMessage =
  | { type: "INIT"; sab: SharedArrayBuffer }
  | { type: "DATA"; messages: TelemetryPacket[] }
  | { type: "QUERY"; queryType: string; params: Record<string, any> }
  | { type: "CLEAR" }
  | { type: "STATS" }
  | { type: "COMPUTE"; task: string; params: Record<string, any> };

// Messages FROM workers
export type WorkerOutMessage =
  | { type: "READY" }
  | { type: "PROCESSED"; data: { count: number; deviceCount: number; messagesPerSecond: number } }
  | { type: "QUERY_RESULT"; data: any }
  | { type: "STATS"; data: WorkerStats }
  | { type: "COMPUTED"; task: string; result: any }
  | { type: "ERROR"; error: string };

export interface WorkerStats {
  deviceCount: number;
  messagesPerSecond: number;
  devices: Array<{ id: string; hash: number }>;
}

// ============================================================
// DEVICE STATE
// ============================================================

export interface DevicePosition {
  deviceId: string;
  timestamp: number;
  latitude: number;
  longitude: number;
  altitude: number;
  speed: number;
  speedKmh: number;
  bearing: number;
  status: "online" | "idle" | "offline";
}

export interface DeviceTrail {
  deviceId: string;
  points: Array<{
    lat: number;
    lon: number;
    speed: number;
    timestamp: number;
  }>;
}

// ============================================================
// ANALYTICS
// ============================================================

export interface Anomaly {
  type: "HARD_BRAKE" | "HARD_ACCEL" | "IMPACT" | "SPEEDING";
  deviceId: string;
  timestamp: number;
  value: number;
  location?: { lat: number; lon: number };
}

export interface VibrationAnalysis {
  deviceId: string;
  period: { start: number; end: number };
  avgMagnitude: number;
  maxMagnitude: number;
  impactCount: number;
  roughRoadScore: number;
}

export interface HeatmapCell {
  lat: number;
  lon: number;
  weight: number;
}

// ============================================================
// UTILITY TYPES
// ============================================================

export interface GeoBounds {
  minLat: number;
  maxLat: number;
  minLon: number;
  maxLon: number;
}

export interface TimeRange {
  start: number;
  end: number;
}


