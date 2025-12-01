/**
 * TelemetryProvider
 * ============================================================
 * Context provider for telemetry data
 * Integrates Web Workers, SharedArrayBuffer, and MQTT for high-performance
 * real-time telemetry processing
 * ============================================================
 */

import { 
  createContext, 
  useContext, 
  ParentProps, 
  createSignal, 
  onMount, 
  onCleanup,
  createEffect 
} from "solid-js";
import { isServer } from "solid-js/web";
import { UI_CONFIG } from "~/lib/utils/constants";
import { 
  useTelemetryWorker, 
  type TelemetryWorkerState, 
  type TelemetryWorkerActions 
} from "~/lib/workers/useTelemetryWorker";
import type { TelemetryPacket } from "~/lib/workers/types";
import type { TelemetryRecord } from "~/lib/workers/shared-buffer";
import type { TelemetryPacket as MqttTelemetryPacket } from "~/lib/mqtt/types";

// Types
export interface TelemetryContextValue {
  // Worker state
  isWorkerReady: boolean;
  isWorkerSupported: boolean;
  workerError: string | null;
  
  // Connection state (for WebSocket - Week 3)
  isConnected: boolean;
  connectionState: "connected" | "connecting" | "disconnected" | "failed";
  
  // Data
  deviceCount: number;
  messagesPerSecond: number;
  recordCount: number;
  lastUpdate: number;
  
  // Actions
  connect: () => void;
  disconnect: () => void;
  
  // Worker actions
  sendTelemetry: (messages: TelemetryPacket[]) => void;
  getLatestRecords: (count: number) => TelemetryRecord[];
  getDevicePositions: () => Map<number, TelemetryRecord>;
  clearData: () => void;
}

// Context
const TelemetryContext = createContext<TelemetryContextValue>();

// Provider
export function TelemetryProvider(props: ParentProps) {
  // Initialize telemetry worker
  const [workerState, workerActions] = useTelemetryWorker();
  
  // Connection state (WebSocket - will be implemented in Week 3)
  const [isConnected, setIsConnected] = createSignal(false);
  const [connectionState, setConnectionState] = createSignal<"connected" | "connecting" | "disconnected" | "failed">("disconnected");
  const [lastUpdate, setLastUpdate] = createSignal(0);
  
  // Update interval for UI refresh
  let updateInterval: number | undefined;
  
  // Convert MQTT packet to worker format
  const convertMqttToWorkerPacket = (mqtt: MqttTelemetryPacket): TelemetryPacket => ({
    messageId: mqtt.messageId,
    deviceId: mqtt.deviceId,
    operatorId: mqtt.operatorId,
    timestamp: mqtt.timestamp,
    gps: {
      latitude: mqtt.gps.latitude,
      longitude: mqtt.gps.longitude,
      altitude: mqtt.gps.altitude ?? 0,
      speed: mqtt.gps.speed ?? 0,
      bearing: mqtt.gps.bearing ?? 0,
      accuracy: mqtt.gps.accuracy ?? 0,
    },
    imu: {
      accelX: mqtt.imu.accelX,
      accelY: mqtt.imu.accelY,
      accelZ: mqtt.imu.accelZ,
      gyroX: mqtt.imu.gyroX ?? 0,
      gyroY: mqtt.imu.gyroY ?? 0,
      gyroZ: mqtt.imu.gyroZ ?? 0,
    },
  });

  // Handle incoming MQTT telemetry events
  const handleTelemetryEvent = (event: CustomEvent<{ topic: string; packet: MqttTelemetryPacket }>) => {
    if (workerState.isReady) {
      const workerPacket = convertMqttToWorkerPacket(event.detail.packet);
      workerActions.sendMessages([workerPacket]);
      setIsConnected(true);
      setConnectionState("connected");
    }
  };
  
  onMount(() => {
    // Skip on server
    if (isServer) return;
    
    // Listen for MQTT telemetry events from MqttProvider
    if (typeof window !== 'undefined') {
      window.addEventListener('telemetry', handleTelemetryEvent as EventListener);
    }
    
    // Start periodic UI updates
    updateInterval = setInterval(() => {
      if (workerState.isReady) {
        setLastUpdate(Date.now());
      }
    }, UI_CONFIG.RENDER_INTERVAL) as unknown as number;
  });
  
  onCleanup(() => {
    // Skip on server
    if (isServer) return;
    
    if (typeof window !== 'undefined') {
      window.removeEventListener('telemetry', handleTelemetryEvent as EventListener);
    }
    if (updateInterval) {
      clearInterval(updateInterval);
    }
  });
  
  // Log worker state changes
  createEffect(() => {
    if (workerState.isReady) {
      console.log("[TelemetryProvider] Worker is ready");
    }
    if (workerState.error) {
      console.error("[TelemetryProvider] Worker error:", workerState.error);
    }
  });

  // Placeholder connection logic (will be replaced by WebSocket in Week 3)
  const connect = () => {
    console.log("[TelemetryProvider] Connect called");
    setConnectionState("connecting");
    
    // Simulate connection
    setTimeout(() => {
      if (workerState.isReady) {
        setIsConnected(true);
        setConnectionState("connected");
      } else {
        setConnectionState("failed");
      }
    }, 1000);
  };

  const disconnect = () => {
    console.log("[TelemetryProvider] Disconnect called");
    setIsConnected(false);
    setConnectionState("disconnected");
  };

  // Context value
  const value: TelemetryContextValue = {
    // Worker state
    get isWorkerReady() { return workerState.isReady; },
    get isWorkerSupported() { return workerState.isSupported; },
    get workerError() { return workerState.error; },
    
    // Connection state
    get isConnected() { return isConnected(); },
    get connectionState() { return connectionState(); },
    
    // Data from worker
    get deviceCount() { return workerState.deviceCount; },
    get messagesPerSecond() { return workerState.messagesPerSecond; },
    get recordCount() { return workerState.recordCount; },
    get lastUpdate() { return lastUpdate(); },
    
    // Connection actions
    connect,
    disconnect,
    
    // Worker actions
    sendTelemetry: workerActions.sendMessages,
    getLatestRecords: workerActions.getLatestRecords,
    getDevicePositions: workerActions.getDevicePositions,
    clearData: workerActions.clear,
  };

  return (
    <TelemetryContext.Provider value={value}>
      {props.children}
    </TelemetryContext.Provider>
  );
}

// Hook
export function useTelemetry() {
  const context = useContext(TelemetryContext);
  if (!context) {
    throw new Error("useTelemetry must be used within a TelemetryProvider");
  }
  return context;
}

export default TelemetryProvider;

