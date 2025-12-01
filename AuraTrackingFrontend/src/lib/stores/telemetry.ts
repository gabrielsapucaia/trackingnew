/**
 * Telemetry Store - Week 2
 * ============================================================
 * Reactive store for telemetry data using SolidJS signals
 * Will be integrated with SharedArrayBuffer and Web Workers
 */

import { createSignal, createMemo } from "solid-js";
import { createStore, reconcile } from "solid-js/store";

// Types
export interface TelemetryRecord {
  timestamp: number;
  deviceId: string;
  operatorId?: string;
  latitude: number;
  longitude: number;
  altitude: number;
  speed: number;  // m/s
  speedKmh: number;  // calculated
  bearing: number;
  gpsAccuracy: number;
  accelX: number;
  accelY: number;
  accelZ: number;
  accelMagnitude: number;  // calculated
}

export interface DeviceState {
  id: string;
  name: string;
  operatorId?: string;
  status: "online" | "idle" | "offline";
  lastRecord?: TelemetryRecord;
  trail: Array<{ lat: number; lon: number; speed: number; timestamp: number }>;
}

export interface TelemetryState {
  devices: Map<string, DeviceState>;
  lastUpdate: number;
  recordCount: number;
  messagesPerSecond: number;
}

// Create the store
const [state, setState] = createStore<TelemetryState>({
  devices: new Map(),
  lastUpdate: 0,
  recordCount: 0,
  messagesPerSecond: 0,
});

// Derived data
export const activeDevices = createMemo(() => {
  const now = Date.now();
  const devices: DeviceState[] = [];
  state.devices.forEach((device) => {
    if (device.lastRecord && now - device.lastRecord.timestamp < 60000) {
      devices.push(device);
    }
  });
  return devices;
});

export const deviceCount = createMemo(() => state.devices.size);

export const onlineCount = createMemo(() => {
  let count = 0;
  state.devices.forEach((device) => {
    if (device.status === "online") count++;
  });
  return count;
});

// Actions (to be implemented in Week 2 with SAB)
export function updateDevices(records: TelemetryRecord[]) {
  // Placeholder - will read from SharedArrayBuffer
  console.log("updateDevices called with", records.length, "records");
}

export function clearTelemetry() {
  setState({
    devices: new Map(),
    lastUpdate: 0,
    recordCount: 0,
    messagesPerSecond: 0,
  });
}

// Export store
export const telemetryStore = {
  state,
  activeDevices,
  deviceCount,
  onlineCount,
  updateDevices,
  clearTelemetry,
};

export default telemetryStore;


