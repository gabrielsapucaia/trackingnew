/**
 * useTelemetryWorker Hook
 * ============================================================
 * Manages the TelemetryWorker lifecycle and communication
 */

import { createSignal, onMount, onCleanup, createMemo } from "solid-js";
import { isServer } from "solid-js/web";
import {
  createTelemetryBuffer,
  isSharedArrayBufferAvailable,
  isAtomicsAvailable,
  getBufferStats,
  readLatestRecords,
  getLatestDevicePositions,
  type TelemetryRecord,
  type BufferStats,
} from "./shared-buffer";
import type { TelemetryPacket, WorkerOutMessage } from "./types";

export interface TelemetryWorkerState {
  isReady: boolean;
  isSupported: boolean;
  deviceCount: number;
  messagesPerSecond: number;
  recordCount: number;
  error: string | null;
}

export interface TelemetryWorkerActions {
  sendMessages: (messages: TelemetryPacket[]) => void;
  getLatestRecords: (count: number) => TelemetryRecord[];
  getDevicePositions: () => Map<number, TelemetryRecord>;
  getStats: () => BufferStats | null;
  clear: () => void;
}

export function useTelemetryWorker(): [TelemetryWorkerState, TelemetryWorkerActions] {
  // Check browser support - skip on server
  const isSupported = isServer ? false : (isSharedArrayBufferAvailable() && isAtomicsAvailable());
  
  // State
  const [isReady, setIsReady] = createSignal(false);
  const [deviceCount, setDeviceCount] = createSignal(0);
  const [messagesPerSecond, setMessagesPerSecond] = createSignal(0);
  const [recordCount, setRecordCount] = createSignal(0);
  const [error, setError] = createSignal<string | null>(null);
  
  // References
  let worker: Worker | null = null;
  let sharedBuffer: SharedArrayBuffer | null = null;
  
  // Initialize worker
  onMount(() => {
    // Skip on server
    if (isServer) return;
    
    if (!isSupported) {
      setError("SharedArrayBuffer not supported. Requires COOP/COEP headers.");
      return;
    }
    
    try {
      // Create SharedArrayBuffer
      sharedBuffer = createTelemetryBuffer();
      
      // Create worker
      // Note: In production, this would use a bundled worker file
      // For now, we'll create an inline worker or use dynamic import
      worker = new Worker(
        new URL("./telemetry.worker.ts", import.meta.url),
        { type: "module" }
      );
      
      // Handle messages from worker
      worker.onmessage = (event: MessageEvent<WorkerOutMessage>) => {
        const message = event.data;
        
        switch (message.type) {
          case "READY":
            setIsReady(true);
            setError(null);
            console.log("[useTelemetryWorker] Worker ready");
            break;
            
          case "PROCESSED":
            setDeviceCount(message.data.deviceCount);
            setMessagesPerSecond(message.data.messagesPerSecond);
            // Update record count from buffer
            if (sharedBuffer) {
              const stats = getBufferStats(sharedBuffer);
              setRecordCount(stats.recordCount);
            }
            break;
            
          case "STATS":
            setDeviceCount(message.data.deviceCount);
            setMessagesPerSecond(message.data.messagesPerSecond);
            break;
            
          case "ERROR":
            setError(message.error);
            console.error("[useTelemetryWorker] Worker error:", message.error);
            break;
        }
      };
      
      worker.onerror = (event) => {
        setError(`Worker error: ${event.message}`);
        console.error("[useTelemetryWorker] Worker error:", event);
      };
      
      // Initialize worker with SharedArrayBuffer
      worker.postMessage({
        type: "INIT",
        sab: sharedBuffer,
      });
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to create worker";
      setError(errorMessage);
      console.error("[useTelemetryWorker] Initialization error:", err);
    }
  });
  
  // Cleanup
  onCleanup(() => {
    // Skip on server
    if (isServer) return;
    
    if (worker) {
      worker.terminate();
      worker = null;
    }
    sharedBuffer = null;
  });
  
  // Actions
  const sendMessages = (messages: TelemetryPacket[]) => {
    if (!worker || !isReady()) {
      console.warn("[useTelemetryWorker] Worker not ready, dropping messages");
      return;
    }
    
    worker.postMessage({
      type: "DATA",
      messages,
    });
  };
  
  const getLatestRecords = (count: number): TelemetryRecord[] => {
    if (!sharedBuffer) return [];
    return readLatestRecords(sharedBuffer, count);
  };
  
  const getDevicePositions = (): Map<number, TelemetryRecord> => {
    if (!sharedBuffer) return new Map();
    return getLatestDevicePositions(sharedBuffer);
  };
  
  const getStats = (): BufferStats | null => {
    if (!sharedBuffer) return null;
    return getBufferStats(sharedBuffer);
  };
  
  const clear = () => {
    if (worker) {
      worker.postMessage({ type: "CLEAR" });
    }
    setRecordCount(0);
    setDeviceCount(0);
    setMessagesPerSecond(0);
  };
  
  // Return state and actions
  const state: TelemetryWorkerState = {
    get isReady() { return isReady(); },
    get isSupported() { return isSupported; },
    get deviceCount() { return deviceCount(); },
    get messagesPerSecond() { return messagesPerSecond(); },
    get recordCount() { return recordCount(); },
    get error() { return error(); },
  };
  
  const actions: TelemetryWorkerActions = {
    sendMessages,
    getLatestRecords,
    getDevicePositions,
    getStats,
    clear,
  };
  
  return [state, actions];
}

export default useTelemetryWorker;

