/**
 * AnalyticsWorker - Week 7
 * ============================================================
 * Web Worker for background analytics processing
 * - Computes heatmaps
 * - Detects anomalies (speeding, impacts, hard braking)
 * - Calculates KPIs and statistics
 * - Prepares data for charts
 */

import { SAB, type TelemetryRecord } from "./shared-buffer";
import type { 
  Anomaly, 
  VibrationAnalysis, 
  HeatmapCell, 
  GeoBounds 
} from "./types";

// ============================================================
// MESSAGE TYPES
// ============================================================

interface InitMessage {
  type: "INIT";
  sab: SharedArrayBuffer;
}

interface ComputeHeatmapMessage {
  type: "COMPUTE_HEATMAP";
  bounds: GeoBounds;
  resolution: number; // in degrees
}

interface DetectAnomaliesMessage {
  type: "DETECT_ANOMALIES";
  deviceHash?: number;
  timeRange?: { start: number; end: number };
}

interface AnalyzeVibrationMessage {
  type: "ANALYZE_VIBRATION";
  deviceHash: number;
  timeRange: { start: number; end: number };
}

interface ComputeKPIsMessage {
  type: "COMPUTE_KPIS";
  deviceHashes?: number[];
  timeRange?: { start: number; end: number };
}

type WorkerMessage = 
  | InitMessage 
  | ComputeHeatmapMessage 
  | DetectAnomaliesMessage
  | AnalyzeVibrationMessage
  | ComputeKPIsMessage;

// ============================================================
// WORKER STATE
// ============================================================

let sharedBuffer: SharedArrayBuffer | null = null;

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
      case "COMPUTE_HEATMAP":
        handleComputeHeatmap(message);
        break;
      case "DETECT_ANOMALIES":
        handleDetectAnomalies(message);
        break;
      case "ANALYZE_VIBRATION":
        handleAnalyzeVibration(message);
        break;
      case "COMPUTE_KPIS":
        handleComputeKPIs(message);
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
  sendResponse({ type: "READY" });
  console.log("[AnalyticsWorker] Initialized");
}

function handleComputeHeatmap(message: ComputeHeatmapMessage): void {
  if (!sharedBuffer) {
    sendError("Worker not initialized");
    return;
  }
  
  const heatmap = computeHeatmap(message.bounds, message.resolution);
  
  sendResponse({
    type: "HEATMAP_RESULT",
    data: heatmap,
  });
}

function handleDetectAnomalies(message: DetectAnomaliesMessage): void {
  if (!sharedBuffer) {
    sendError("Worker not initialized");
    return;
  }
  
  const anomalies = detectAnomalies(message.deviceHash, message.timeRange);
  
  sendResponse({
    type: "ANOMALIES_RESULT",
    data: anomalies,
  });
}

function handleAnalyzeVibration(message: AnalyzeVibrationMessage): void {
  if (!sharedBuffer) {
    sendError("Worker not initialized");
    return;
  }
  
  const analysis = analyzeVibration(message.deviceHash, message.timeRange);
  
  sendResponse({
    type: "VIBRATION_RESULT",
    data: analysis,
  });
}

function handleComputeKPIs(message: ComputeKPIsMessage): void {
  if (!sharedBuffer) {
    sendError("Worker not initialized");
    return;
  }
  
  // Placeholder KPIs
  const kpis = {
    totalDistance: 0,
    avgSpeed: 0,
    maxSpeed: 0,
    totalTime: 0,
    eventCount: 0,
  };
  
  sendResponse({
    type: "KPIS_RESULT",
    data: kpis,
  });
}

// ============================================================
// ANALYTICS FUNCTIONS
// ============================================================

function computeHeatmap(bounds: GeoBounds, resolution: number): HeatmapCell[] {
  // Placeholder implementation
  // Will read from SAB and aggregate by grid cells
  const cells: HeatmapCell[] = [];
  
  // TODO: Implement actual heatmap computation
  // 1. Read all records from SAB within bounds
  // 2. Map each point to a grid cell
  // 3. Count occurrences per cell
  // 4. Return cell array with weights
  
  return cells;
}

function detectAnomalies(
  deviceHash?: number,
  timeRange?: { start: number; end: number }
): Anomaly[] {
  // Placeholder implementation
  const anomalies: Anomaly[] = [];
  
  // TODO: Implement anomaly detection
  // 1. Read records from SAB
  // 2. Check for speeding (> 80 km/h)
  // 3. Check for hard braking (decel > 3 m/s²)
  // 4. Check for impacts (accel magnitude > 15 m/s²)
  // 5. Return list of anomalies
  
  return anomalies;
}

function analyzeVibration(
  deviceHash: number,
  timeRange: { start: number; end: number }
): VibrationAnalysis {
  // Placeholder implementation
  return {
    deviceId: "",
    period: timeRange,
    avgMagnitude: 9.81,
    maxMagnitude: 9.81,
    impactCount: 0,
    roughRoadScore: 0,
  };
}

// ============================================================
// UTILITY FUNCTIONS
// ============================================================

function mean(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function variance(values: number[]): number {
  if (values.length === 0) return 0;
  const m = mean(values);
  return mean(values.map(v => (v - m) * (v - m)));
}

function getGridCellKey(lat: number, lon: number, resolution: number): string {
  const cellLat = Math.floor(lat / resolution);
  const cellLon = Math.floor(lon / resolution);
  return `${cellLat}:${cellLon}`;
}

// ============================================================
// RESPONSE HELPERS
// ============================================================

function sendResponse(response: any): void {
  self.postMessage(response);
}

function sendError(error: string): void {
  self.postMessage({ type: "ERROR", error });
}

// Log startup
console.log("[AnalyticsWorker] Worker started");

