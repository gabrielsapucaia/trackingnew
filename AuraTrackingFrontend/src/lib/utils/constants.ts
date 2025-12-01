/**
 * AuraTracking Frontend Constants
 * ============================================================
 * Centralized configuration values for the application
 */

// API Configuration
export const API_CONFIG = {
  BASE_URL: import.meta.env.VITE_API_URL || "http://localhost:8080",
  WS_URL: import.meta.env.VITE_WS_URL || "ws://localhost:8083/mqtt",
  TIMEOUT: 30000,
} as const;

// WebSocket Configuration
export const WS_CONFIG = {
  RECONNECT_INITIAL_DELAY: 1000,
  RECONNECT_MAX_DELAY: 30000,
  RECONNECT_MULTIPLIER: 2,
  RECONNECT_JITTER: 0.3,
  RECONNECT_MAX_RETRIES: 10,
  HEARTBEAT_INTERVAL: 30000,
  HEARTBEAT_TIMEOUT: 5000,
} as const;

// SharedArrayBuffer Configuration (for Week 2)
export const SAB_CONFIG = {
  // Header offsets
  MAGIC_OFFSET: 0,
  VERSION_OFFSET: 4,
  RECORD_COUNT_OFFSET: 8,
  WRITE_INDEX_OFFSET: 12,
  MAX_RECORDS_OFFSET: 16,
  RECORD_SIZE_OFFSET: 20,
  OLDEST_TS_OFFSET: 24,
  NEWEST_TS_OFFSET: 32,
  HEADER_SIZE: 256,
  
  // Record offsets (within each 64-byte record)
  RECORD_SIZE: 64,
  TS_OFFSET: 0,
  DEVICE_HASH_OFFSET: 8,
  FLAGS_OFFSET: 10,
  LAT_OFFSET: 16,
  LON_OFFSET: 24,
  ALT_OFFSET: 32,
  SPEED_OFFSET: 36,
  BEARING_OFFSET: 40,
  ACCURACY_OFFSET: 44,
  ACCEL_X_OFFSET: 48,
  ACCEL_Y_OFFSET: 52,
  ACCEL_Z_OFFSET: 56,
  ACCEL_MAG_OFFSET: 60,
  
  // Capacity
  MAX_RECORDS: 180_000,  // ~1h @ 50 devices @ 1Hz
  BUFFER_SIZE: 256 + (64 * 180_000),  // ~11.5MB
  
  // Magic number for validation
  MAGIC_NUMBER: 0x41555241,  // "AURA"
  VERSION: 1,
} as const;

// UI Configuration
export const UI_CONFIG = {
  RENDER_INTERVAL: 100,  // 10 FPS for UI updates
  CHART_UPDATE_INTERVAL: 1000,  // 1 FPS for charts
  MAP_UPDATE_INTERVAL: 100,  // 10 FPS for map
  
  CHART_BUFFER_SIZE: 3600,  // 1h of data @ 1Hz
  DOWNSAMPLE_THRESHOLD: 1000,  // Downsample above this
  
  TRAIL_LENGTH: 300,  // 5 min @ 1Hz
} as const;

// Speed thresholds (km/h)
export const SPEED_THRESHOLDS = {
  LOW: 20,
  MEDIUM: 40,
  HIGH: 60,
  DANGER: 80,
} as const;

// Acceleration thresholds (m/s²)
export const ACCEL_THRESHOLDS = {
  NORMAL: 12,
  WARNING: 15,
  IMPACT: 20,
} as const;

// Speed color scale for visualization
export const SPEED_COLORS = [
  { threshold: 0, color: [34, 197, 94] as const, name: "low" },      // Green
  { threshold: 20, color: [234, 179, 8] as const, name: "medium" },   // Yellow
  { threshold: 40, color: [249, 115, 22] as const, name: "high" },    // Orange
  { threshold: 60, color: [239, 68, 68] as const, name: "danger" },   // Red
  { threshold: 80, color: [168, 85, 247] as const, name: "critical" }, // Purple
] as const;

// Device status types
export const DEVICE_STATUS = {
  ONLINE: "online",
  IDLE: "idle",
  OFFLINE: "offline",
} as const;

// Connection states
export const CONNECTION_STATE = {
  CLOSED: "closed",
  CONNECTING: "connecting",
  CONNECTED: "connected",
  RECONNECTING: "reconnecting",
  FAILED: "failed",
} as const;

// Event types
export const EVENT_TYPES = {
  HARD_BRAKE: "HARD_BRAKE",
  HARD_ACCEL: "HARD_ACCEL",
  IMPACT: "IMPACT",
  SPEEDING: "SPEEDING",
  IDLE_ENGINE: "IDLE_ENGINE",
  GEOFENCE_EXIT: "GEOFENCE_EXIT",
} as const;

// Time intervals
export const TIME_INTERVALS = {
  MINUTE: 60 * 1000,
  HOUR: 60 * 60 * 1000,
  DAY: 24 * 60 * 60 * 1000,
} as const;


