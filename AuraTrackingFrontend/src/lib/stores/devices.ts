/**
 * Devices Store
 * ============================================================
 * Device management and selection state
 */

import { createSignal, createMemo } from "solid-js";
import { createStore } from "solid-js/store";

export interface Device {
  id: string;
  name: string;
  model: string;
  operator?: string;
  operatorId?: string;
  status: "online" | "idle" | "offline";
  lastSeen: Date;
  firstSeen: Date;
  totalKm: number;
  todayKm: number;
  metadata?: {
    appVersion?: string;
    osVersion?: string;
    batteryLevel?: number;
    signalStrength?: number;
  };
}

export interface DevicesState {
  devices: Device[];
  selectedDeviceId: string | null;
  isLoading: boolean;
  error: string | null;
}

const [state, setState] = createStore<DevicesState>({
  devices: [],
  selectedDeviceId: null,
  isLoading: false,
  error: null,
});

// Derived state
export const selectedDevice = createMemo(() => {
  if (!state.selectedDeviceId) return null;
  return state.devices.find((d) => d.id === state.selectedDeviceId) || null;
});

export const onlineDevices = createMemo(() =>
  state.devices.filter((d) => d.status === "online")
);

export const offlineDevices = createMemo(() =>
  state.devices.filter((d) => d.status === "offline")
);

export const idleDevices = createMemo(() =>
  state.devices.filter((d) => d.status === "idle")
);

// Actions
export function setDevices(devices: Device[]) {
  setState("devices", devices);
}

export function selectDevice(deviceId: string | null) {
  setState("selectedDeviceId", deviceId);
}

export function updateDevice(deviceId: string, updates: Partial<Device>) {
  setState("devices", (d) => d.id === deviceId, updates);
}

export function updateDeviceStatus(
  deviceId: string,
  status: Device["status"]
) {
  setState("devices", (d) => d.id === deviceId, "status", status);
  setState("devices", (d) => d.id === deviceId, "lastSeen", new Date());
}

export function setLoading(isLoading: boolean) {
  setState("isLoading", isLoading);
}

export function setError(error: string | null) {
  setState("error", error);
}

// Export store
export const devicesStore = {
  state,
  selectedDevice,
  onlineDevices,
  offlineDevices,
  idleDevices,
  setDevices,
  selectDevice,
  updateDevice,
  updateDeviceStatus,
  setLoading,
  setError,
};

export default devicesStore;


