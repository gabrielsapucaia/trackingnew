/**
 * TelemetryWorker
 * ============================================================
 * Web Worker for processing telemetry messages
 * - Receives JSON messages from WebSocket
 * - Validates and transforms data
 * - Writes to SharedArrayBuffer
 * - Maintains device registry
 */

import {
  SAB,
  writeRecord,
  hashDeviceId,
  updateDeviceCount,
  updateMsgPerSec,
  type TelemetryRecord,
} from "./shared-buffer";

// ============================================================
// MESSAGE TYPES
// ============================================================

interface InitMessage {
  type: "INIT";
  sab: SharedArrayBuffer;
}

interface DataMessage {
  type: "DATA";
  messages: TelemetryPacket[];
}

interface QueryMessage {
  type: "QUERY";
  queryType: "latest" | "device" | "timeRange";
  params: {
    count?: number;
    deviceId?: string;
    startTime?: number;
    endTime?: number;
  };
}

interface ClearMessage {
  type: "CLEAR";
}

interface StatsMessage {
  type: "STATS";
}

type WorkerMessage = InitMessage | DataMessage | QueryMessage | ClearMessage | StatsMessage;

// Incoming telemetry packet format (from MQTT/WebSocket)
interface TelemetryPacket {
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

// Response types
interface WorkerResponse {
  type: "READY" | "PROCESSED" | "QUERY_RESULT" | "STATS" | "ERROR";
  data?: any;
  error?: string;
}

// ============================================================
// WORKER STATE
// ============================================================

let sharedBuffer: SharedArrayBuffer | null = null;
let deviceMap: Map<string, number> = new Map(); // deviceId -> hash
let hashToId: Map<number, string> = new Map();  // hash -> deviceId
let messageCount = 0;
let lastStatsTime = Date.now();
let messagesPerSecond = 0;

// ============================================================
// MESSAGE HANDLER
// ============================================================

self.onmessage = (event: MessageEvent<WorkerMessage>) => {
  const message = event.data;
  
  try {
    switch (message.type) {
      case "INIT":
        handleInit(message);
        break;
      case "DATA":
        handleData(message);
        break;
      case "QUERY":
        handleQuery(message);
        break;
      case "CLEAR":
        handleClear();
        break;
      case "STATS":
        handleStats();
        break;
      default:
        sendError(`Unknown message type: ${(message as any).type}`);
    }
  } catch (error) {
    sendError(error instanceof Error ? error.message : "Unknown error");
  }
};

// ============================================================
// HANDLERS
// ============================================================

function handleInit(message: InitMessage): void {
  sharedBuffer = message.sab;
  deviceMap.clear();
  hashToId.clear();
  messageCount = 0;
  lastStatsTime = Date.now();
  
  sendResponse({ type: "READY" });
  console.log("[TelemetryWorker] Initialized with SharedArrayBuffer");
}

function handleData(message: DataMessage): void {
  if (!sharedBuffer) {
    sendError("Worker not initialized");
    return;
  }
  
  const processed = processMessages(message.messages);
  
  // Update stats
  messageCount += message.messages.length;
  const now = Date.now();
  const elapsed = (now - lastStatsTime) / 1000;
  
  if (elapsed >= 1) {
    messagesPerSecond = messageCount / elapsed;
    updateMsgPerSec(sharedBuffer, messagesPerSecond);
    updateDeviceCount(sharedBuffer, deviceMap.size);
    messageCount = 0;
    lastStatsTime = now;
  }
  
  sendResponse({
    type: "PROCESSED",
    data: {
      count: processed,
      deviceCount: deviceMap.size,
      messagesPerSecond,
    },
  });
}

function handleQuery(message: QueryMessage): void {
  if (!sharedBuffer) {
    sendError("Worker not initialized");
    return;
  }
  
  // Query handling would go here
  // For now, just acknowledge
  sendResponse({
    type: "QUERY_RESULT",
    data: { queryType: message.queryType },
  });
}

function handleClear(): void {
  deviceMap.clear();
  hashToId.clear();
  messageCount = 0;
  messagesPerSecond = 0;
  
  sendResponse({ type: "READY" });
}

function handleStats(): void {
  sendResponse({
    type: "STATS",
    data: {
      deviceCount: deviceMap.size,
      messagesPerSecond,
      devices: Array.from(deviceMap.entries()).map(([id, hash]) => ({
        id,
        hash,
      })),
    },
  });
}

// ============================================================
// MESSAGE PROCESSING
// ============================================================

function processMessages(packets: TelemetryPacket[]): number {
  if (!sharedBuffer) return 0;
  
  let processed = 0;
  
  for (const packet of packets) {
    if (!validatePacket(packet)) {
      console.warn("[TelemetryWorker] Invalid packet:", packet);
      continue;
    }
    
    const record = transformPacket(packet);
    writeRecord(sharedBuffer, record);
    processed++;
  }
  
  return processed;
}

function validatePacket(packet: TelemetryPacket): boolean {
  if (!packet.deviceId || typeof packet.deviceId !== "string") {
    return false;
  }
  
  if (!packet.timestamp || typeof packet.timestamp !== "number") {
    return false;
  }
  
  if (!packet.gps || typeof packet.gps.latitude !== "number" || typeof packet.gps.longitude !== "number") {
    return false;
  }
  
  // Basic range checks
  if (packet.gps.latitude < -90 || packet.gps.latitude > 90) {
    return false;
  }
  
  if (packet.gps.longitude < -180 || packet.gps.longitude > 180) {
    return false;
  }
  
  return true;
}

function transformPacket(packet: TelemetryPacket): TelemetryRecord {
  // Get or create device hash
  let deviceHash = deviceMap.get(packet.deviceId);
  if (deviceHash === undefined) {
    deviceHash = hashDeviceId(packet.deviceId);
    deviceMap.set(packet.deviceId, deviceHash);
    hashToId.set(deviceHash, packet.deviceId);
  }
  
  // Calculate acceleration magnitude
  const accelX = packet.imu?.accelX ?? 0;
  const accelY = packet.imu?.accelY ?? 0;
  const accelZ = packet.imu?.accelZ ?? 0;
  const accelMagnitude = Math.sqrt(accelX * accelX + accelY * accelY + accelZ * accelZ);
  
  // Calculate flags
  let flags = SAB.FLAG_VALID;
  
  if (packet.gps.accuracy !== undefined && packet.gps.accuracy < 20) {
    flags |= SAB.FLAG_GPS_FIX;
  }
  
  if (packet.imu) {
    flags |= SAB.FLAG_IMU_VALID;
  }
  
  const speedKmh = (packet.gps.speed ?? 0) * 3.6;
  if (speedKmh > 80) {
    flags |= SAB.FLAG_SPEEDING;
  }
  
  if (accelMagnitude > 15) {
    flags |= SAB.FLAG_IMPACT;
  }
  
  return {
    timestamp: packet.timestamp,
    deviceId: packet.deviceId,
    deviceHash,
    flags,
    latitude: packet.gps.latitude,
    longitude: packet.gps.longitude,
    altitude: packet.gps.altitude ?? 0,
    speed: packet.gps.speed ?? 0,
    speedKmh,
    bearing: packet.gps.bearing ?? 0,
    gpsAccuracy: packet.gps.accuracy ?? 999,
    accelX,
    accelY,
    accelZ,
    accelMagnitude,
  };
}

// ============================================================
// RESPONSE HELPERS
// ============================================================

function sendResponse(response: WorkerResponse): void {
  self.postMessage(response);
}

function sendError(error: string): void {
  self.postMessage({ type: "ERROR", error });
}

// Log startup
console.log("[TelemetryWorker] Worker started");

