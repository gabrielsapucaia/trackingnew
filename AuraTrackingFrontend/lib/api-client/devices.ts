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

const DEFAULT_TIMEOUT_MS = 10000; // 10 seconds

export async function fetchDevices(externalSignal?: AbortSignal): Promise<DevicesResponse> {
  const url = `${API_BASE_URL}/api/devices`;

  // Create internal AbortController for timeout
  const timeoutController = new AbortController();
  const timeoutId = setTimeout(() => timeoutController.abort(), DEFAULT_TIMEOUT_MS);

  // Combine external signal with timeout signal
  const combinedSignal = externalSignal
    ? combineAbortSignals(externalSignal, timeoutController.signal)
    : timeoutController.signal;

  try {
    const res = await fetch(url, { 
      cache: "no-cache",
      signal: combinedSignal
    });
    
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
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      // Distinguish between timeout and external abort
      if (timeoutController.signal.aborted && !externalSignal?.aborted) {
        throw new Error(`Request timeout after ${DEFAULT_TIMEOUT_MS}ms`);
      }
      throw new Error('Request was cancelled');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Combines multiple AbortSignals into one.
 * The combined signal aborts when any of the input signals abort.
 */
function combineAbortSignals(...signals: AbortSignal[]): AbortSignal {
  const controller = new AbortController();
  
  for (const signal of signals) {
    if (signal.aborted) {
      controller.abort();
      return controller.signal;
    }
    signal.addEventListener('abort', () => controller.abort(), { once: true });
  }
  
  return controller.signal;
}
