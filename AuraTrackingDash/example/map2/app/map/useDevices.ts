"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { fetchDevices } from "../../lib/api-client/devices";
import type { DeviceSummary } from "../../types/devices";

// Data is considered stale after 30 seconds without a successful update
const STALE_THRESHOLD_MS = 30000;

// Backoff configuration
const BASE_INTERVAL_MS = 5000;
const MAX_BACKOFF_MS = 40000;
const BACKOFF_MULTIPLIER = 2;

// Active device threshold - device must have been seen within this time
const ACTIVE_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes

type ConnectionStatus = 'connected' | 'degraded' | 'disconnected';

type UseDevicesResult = {
  devices: DeviceSummary[];
  activeDevices: DeviceSummary[];
  isInitialLoading: boolean;
  isRefreshing: boolean;
  error: string | null;
  lastUpdated: Date | null;
  isStale: boolean;
  connectionStatus: ConnectionStatus;
  retryCount: number;
};

/**
 * Calculates the next poll interval with exponential backoff
 */
function calculateBackoffInterval(baseInterval: number, consecutiveErrors: number): number {
  if (consecutiveErrors === 0) return baseInterval;
  const backoff = baseInterval * Math.pow(BACKOFF_MULTIPLIER, consecutiveErrors);
  return Math.min(backoff, MAX_BACKOFF_MS);
}

/**
 * Determines connection status based on error count
 */
function getConnectionStatus(consecutiveErrors: number): ConnectionStatus {
  if (consecutiveErrors === 0) return 'connected';
  if (consecutiveErrors <= 2) return 'degraded';
  return 'disconnected';
}

/**
 * Filters devices that are online AND have been seen recently
 */
function filterActiveDevices(devices: DeviceSummary[]): DeviceSummary[] {
  const now = new Date();
  return devices.filter(device => {
    // Must be online
    if (device.status !== 'online') return false;
    
    // Must have been seen recently
    if (!device.lastSeen) return false;
    
    const lastSeenDate = new Date(device.lastSeen);
    const timeSinceLastSeen = now.getTime() - lastSeenDate.getTime();
    
    return timeSinceLastSeen < ACTIVE_THRESHOLD_MS;
  });
}

export function useDevices(pollIntervalMs = BASE_INTERVAL_MS): UseDevicesResult {
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isStale, setIsStale] = useState(false);
  const [consecutiveErrors, setConsecutiveErrors] = useState(0);
  
  const abortControllerRef = useRef<AbortController | null>(null);
  const staleTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isVisibleRef = useRef(true);
  const hasLoadedOnceRef = useRef(false);
  const consecutiveErrorsRef = useRef(0);
  
  // Keep ref in sync with state for use in callbacks
  useEffect(() => {
    consecutiveErrorsRef.current = consecutiveErrors;
  }, [consecutiveErrors]);

  // Reset stale timer on successful update
  const resetStaleTimer = useCallback(() => {
    if (staleTimerRef.current) {
      clearTimeout(staleTimerRef.current);
    }
    setIsStale(false);
    staleTimerRef.current = setTimeout(() => {
      setIsStale(true);
    }, STALE_THRESHOLD_MS);
  }, []);

  // Load function - uses refs to avoid stale closures
  const load = useCallback(async () => {
    // Abort any in-flight request before starting a new one
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();
    
    // Only show refreshing indicator after initial load
    if (hasLoadedOnceRef.current) {
      setIsRefreshing(true);
    }
    
    try {
      const { devices: fetchedDevices } = await fetchDevices(abortControllerRef.current.signal);
      
      setDevices(fetchedDevices);
      setError(null);
      setIsInitialLoading(false);
      setIsRefreshing(false);
      setLastUpdated(new Date());
      setConsecutiveErrors(0);
      consecutiveErrorsRef.current = 0;
      hasLoadedOnceRef.current = true;
      resetStaleTimer();
      
      // Schedule next poll with no backoff (success resets)
      scheduleNextPoll(0);
      
    } catch (err) {
      // Don't update error state for cancelled requests
      if (err instanceof Error && err.message === 'Request was cancelled') {
        return;
      }
      
      const newErrorCount = consecutiveErrorsRef.current + 1;
      setConsecutiveErrors(newErrorCount);
      consecutiveErrorsRef.current = newErrorCount;
      setError(err instanceof Error ? err.message : "Unknown error");
      setIsInitialLoading(false);
      setIsRefreshing(false);
      // Note: We keep the previous devices data (last known good)
      
      // Schedule next poll with backoff
      scheduleNextPoll(newErrorCount);
    }
  }, [resetStaleTimer]); // Removed scheduleNextPoll and consecutiveErrors

  // Schedule next poll with backoff - defined after load to use it
  const scheduleNextPoll = useCallback((currentErrors: number) => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
    }
    
    // Don't schedule if tab is hidden
    if (!isVisibleRef.current) return;
    
    const interval = calculateBackoffInterval(pollIntervalMs, currentErrors);
    pollTimerRef.current = setTimeout(() => {
      // Re-check visibility before polling
      if (isVisibleRef.current) {
        load();
      }
    }, interval);
  }, [pollIntervalMs, load]);

  // Handle visibility changes
  useEffect(() => {
    const handleVisibilityChange = () => {
      const wasHidden = !isVisibleRef.current;
      isVisibleRef.current = document.visibilityState === 'visible';
      
      if (isVisibleRef.current && wasHidden) {
        // Tab became visible - immediately fetch fresh data
        load();
      } else if (!isVisibleRef.current) {
        // Tab became hidden - cancel pending poll
        if (pollTimerRef.current) {
          clearTimeout(pollTimerRef.current);
          pollTimerRef.current = null;
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [load]);

  // Initial load - runs only once on mount
  useEffect(() => {
    load();

    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (staleTimerRef.current) {
        clearTimeout(staleTimerRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Intentionally empty - only run on mount

  // Derive connection status
  const connectionStatus = getConnectionStatus(consecutiveErrors);
  
  // Filter active devices (online + recent)
  const activeDevices = filterActiveDevices(devices);

  return { 
    devices, 
    activeDevices,
    isInitialLoading, 
    isRefreshing,
    error, 
    lastUpdated, 
    isStale,
    connectionStatus,
    retryCount: consecutiveErrors
  };
}
