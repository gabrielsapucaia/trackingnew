"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { fetchDevices } from "../../lib/api-client/devices";
import type { DeviceSummary } from "../../types/devices";
import { API_BASE_URL } from "../../lib/config";

// Configuration
const SSE_URL = `${API_BASE_URL}/api/events/stream`;
const FLUSH_INTERVAL_MS = 2000; // Update UI every 2s (reduced from 1s)
const HEARTBEAT_TIMEOUT_MS = 30000; // 30s without heartbeat = stale
const POLLING_FALLBACK_MS = 5000; // Poll every 5s in fallback mode

// Device visibility thresholds
const ONLINE_THRESHOLD_MS = 30_000; // 30 seconds - device is ONLINE
const HIDDEN_THRESHOLD_MS = 24 * 60 * 60 * 1000; // 24 hours - device is HIDDEN (not shown on map)

// Internal status type (includes 'hidden' which is filtered out before exposing to UI)
type InternalDeviceStatus = 'online' | 'offline' | 'hidden';

/**
 * Compute device status based on lastSeen timestamp.
 * - ONLINE: lastSeen within 30 seconds
 * - OFFLINE: lastSeen between 30s and 24h
 * - HIDDEN: lastSeen > 24h (should not appear on map)
 */
function computeDeviceStatus(lastSeen: string | null): InternalDeviceStatus {
  if (!lastSeen) return 'hidden'; // No lastSeen = treat as hidden
  
  const lastSeenTime = new Date(lastSeen).getTime();
  const now = Date.now();
  const delta = now - lastSeenTime;
  
  if (delta <= ONLINE_THRESHOLD_MS) {
    return 'online';
  } else if (delta <= HIDDEN_THRESHOLD_MS) {
    return 'offline';
  } else {
    return 'hidden';
  }
}

export type ConnectionStatus = 'connecting' | 'live' | 'reconnecting' | 'fallback_polling' | 'offline';

type UseDeviceStreamResult = {
  devices: DeviceSummary[];
  status: ConnectionStatus;
  lastUpdated: Date | null;
  error: string | null;
  isInitialLoading: boolean;
};

type DeviceUpdate = {
  id: string;
  ts: number;
  lat: number;
  lon: number;
  st: string;
};

export function useDeviceStream(): UseDeviceStreamResult {
  // State
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);

  // Refs for mutable state (avoid re-renders)
  const devicesMapRef = useRef<Map<string, DeviceSummary>>(new Map());
  const updateBufferRef = useRef<Map<string, DeviceUpdate>>(new Map());
  const eventSourceRef = useRef<EventSource | null>(null);
  const heartbeatTimerRef = useRef<NodeJS.Timeout | null>(null);
  const flushTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(false);

  // Helper: Update devices state from map
  const flushUpdates = useCallback(() => {
    const now = new Date();
    let hasBufferUpdates = false;

    // Apply buffered updates from SSE
    if (updateBufferRef.current.size > 0) {
      updateBufferRef.current.forEach((update) => {
        const current = devicesMapRef.current.get(update.id);
        
        // Only update if newer
        if (!current || (update.ts * 1000) > new Date(current.lastSeen || 0).getTime()) {
          const updatedDevice: DeviceSummary = {
            deviceId: update.id,
            operatorId: current?.operatorId || null, // Preserve static data
            latitude: update.lat,
            longitude: update.lon,
            lastSeen: new Date(update.ts * 1000).toISOString(),
            status: 'online', // Will be recalculated below
            speedKmh: current?.speedKmh || null, // Not in minimal payload yet
            totalPoints24h: (current?.totalPoints24h || 0) + 1
          };
          
          devicesMapRef.current.set(update.id, updatedDevice);
          hasBufferUpdates = true;
        }
      });

      // Clear buffer
      updateBufferRef.current.clear();
    }

    // Recalculate status for ALL devices and filter out hidden ones
    const visibleDevices: DeviceSummary[] = [];
    devicesMapRef.current.forEach((device) => {
      const computedStatus = computeDeviceStatus(device.lastSeen);
      
      if (computedStatus !== 'hidden') {
        // Update status based on lastSeen
        visibleDevices.push({
          ...device,
          status: computedStatus as 'online' | 'offline'
        });
      }
    });

    // Always update state to reflect status changes (online -> offline transitions)
    setDevices(visibleDevices);
    if (hasBufferUpdates) {
      setLastUpdated(now);
    }
  }, []);

  // Helper: Start Polling Fallback
  const startPolling = useCallback(() => {
    if (pollingTimerRef.current) return;
    
    console.log("[Stream] Switching to polling fallback");
    setStatus('fallback_polling');
    
    const poll = async () => {
      try {
        const data = await fetchDevices();
        
        // Clear existing devices before merging new data
        devicesMapRef.current.clear();
        
        // Merge into map
        data.devices.forEach(d => {
          devicesMapRef.current.set(d.deviceId, d);
        });
        
        // Filter out hidden devices and recalculate status
        const visibleDevices: DeviceSummary[] = [];
        devicesMapRef.current.forEach((device) => {
          const computedStatus = computeDeviceStatus(device.lastSeen);
          
          if (computedStatus !== 'hidden') {
            visibleDevices.push({
              ...device,
              status: computedStatus as 'online' | 'offline'
            });
          }
        });
        
        setDevices(visibleDevices);
        setLastUpdated(new Date());
        setError(null);
      } catch (err) {
        console.error("[Stream] Polling error:", err);
        // Keep fallback status but log error
      }
    };

    // Initial poll
    poll();
    // Interval poll
    pollingTimerRef.current = setInterval(poll, POLLING_FALLBACK_MS);
  }, []);

  // Helper: Stop Polling
  const stopPolling = useCallback(() => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  }, []);

  // Helper: Reset Heartbeat Watchdog
  const resetHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) clearTimeout(heartbeatTimerRef.current);
    
    heartbeatTimerRef.current = setTimeout(() => {
      console.warn("[Stream] Heartbeat timeout - reconnecting...");
      setStatus('reconnecting');
      eventSourceRef.current?.close();
      // Logic to trigger reconnection or fallback will be handled by effect cleanup/retry
      startPolling(); // Fail-safe to polling
    }, HEARTBEAT_TIMEOUT_MS);
  }, [startPolling]);

  // Effect: Bootstrap & SSE Connection
  useEffect(() => {
    isMountedRef.current = true;

    const init = async () => {
      try {
        // 1. Initial Snapshot (REST) - Get only online devices
        const data = await fetchDevices();
        data.devices.forEach(d => devicesMapRef.current.set(d.deviceId, d));
        setDevices(data.devices);
        setIsInitialLoading(false);

        // 2. Setup SSE
        const es = new EventSource(SSE_URL);
        eventSourceRef.current = es;

        es.onopen = () => {
          console.log("[Stream] SSE Connected");
          setStatus('live');
          setError(null);
          stopPolling();
          resetHeartbeat();
        };

        es.onerror = (err) => {
          console.error("[Stream] SSE Error:", err);
          setStatus('reconnecting');
          es.close();
          // Browser will try to reconnect, but if it fails too much, we might want to fallback
          // For now, let's start polling as safety net until it reconnects
          startPolling();
        };

        es.addEventListener('device-update', (e) => {
          try {
            const update: DeviceUpdate = JSON.parse(e.data);
            updateBufferRef.current.set(update.id, update);
            resetHeartbeat();
          } catch (err) {
            console.error("[Stream] Parse error:", err);
          }
        });

        es.addEventListener('heartbeat', () => {
          resetHeartbeat();
        });

      } catch (err) {
        console.error("[Stream] Bootstrap failed:", err);
        setError("Failed to initialize stream");
        setIsInitialLoading(false);
        startPolling(); // Fallback immediately
      }
    };

    init();

    // 3. Flush Loop
    flushTimerRef.current = setInterval(flushUpdates, FLUSH_INTERVAL_MS);

    return () => {
      isMountedRef.current = false;
      eventSourceRef.current?.close();
      if (flushTimerRef.current) clearInterval(flushTimerRef.current);
      if (heartbeatTimerRef.current) clearTimeout(heartbeatTimerRef.current);
      stopPolling();
    };
  }, [flushUpdates, resetHeartbeat, startPolling, stopPolling]);

  return {
    devices,
    status,
    lastUpdated,
    error,
    isInitialLoading
  };
}
