import { API_BASE_URL } from "../config";
import { DeviceSummary, DevicesResponse } from "../../types/devices";

type BackendDevice = {
  device_id: string;
  operator_id: string | null;
  last_seen: string | null;
  latitude: number | null;
  longitude: number | null;
  speed_kmh: number | null;
  total_points_24h: number;
  status: "online" | "offline";
};

type BackendResponse = {
  devices: BackendDevice[];
  count: number;
};

export async function fetchDevices(): Promise<DevicesResponse> {
  const url = `${API_BASE_URL}/api/devices`;

  const res = await fetch(url, { cache: "no-cache" });
  if (!res.ok) {
    throw new Error(`Failed to fetch devices: ${res.status} ${res.statusText}`);
  }

  const json = (await res.json()) as BackendResponse;
  const devices: DeviceSummary[] = (json.devices || []).map((d) => ({
    deviceId: d.device_id,
    operatorId: d.operator_id,
    lastSeen: d.last_seen,
    latitude: d.latitude,
    longitude: d.longitude,
    speedKmh: d.speed_kmh,
    totalPoints24h: d.total_points_24h,
    status: d.status
  }));

  return { devices, count: json.count ?? devices.length };
}
