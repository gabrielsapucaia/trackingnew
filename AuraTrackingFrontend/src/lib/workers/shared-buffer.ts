/**
 * SharedArrayBuffer Utilities
 * ============================================================
 * Memory layout and operations for high-performance telemetry storage
 * 
 * Layout:
 * - Header: 256 bytes (metadata)
 * - Records: 64 bytes each (telemetry data)
 * - Total: 256 + (64 * 180,000) = ~11.5MB
 */

// ============================================================
// CONSTANTS
// ============================================================

export const SAB = {
  // Header offsets (256 bytes total)
  MAGIC_OFFSET: 0,           // 4 bytes - Magic number (0x41555241 = "AURA")
  VERSION_OFFSET: 4,         // 4 bytes - Buffer version
  RECORD_COUNT_OFFSET: 8,    // 4 bytes - Current record count
  WRITE_INDEX_OFFSET: 12,    // 4 bytes - Write position (ring buffer)
  MAX_RECORDS_OFFSET: 16,    // 4 bytes - Maximum records
  RECORD_SIZE_OFFSET: 20,    // 4 bytes - Size of each record
  OLDEST_TS_OFFSET: 24,      // 8 bytes - Oldest timestamp (BigInt64)
  NEWEST_TS_OFFSET: 32,      // 8 bytes - Newest timestamp (BigInt64)
  DEVICE_COUNT_OFFSET: 40,   // 4 bytes - Active device count
  MSG_PER_SEC_OFFSET: 44,    // 4 bytes - Messages per second (Float32)
  HEADER_SIZE: 256,          // Total header size (with padding)
  
  // Record offsets (64 bytes total, aligned to 8 bytes)
  RECORD_SIZE: 64,
  REC_TIMESTAMP: 0,          // 8 bytes - Float64 (ms since epoch)
  REC_DEVICE_HASH: 8,        // 2 bytes - Uint16 (device ID hash)
  REC_FLAGS: 10,             // 2 bytes - Uint16 (status flags)
  REC_RESERVED: 12,          // 4 bytes - Reserved for alignment
  REC_LATITUDE: 16,          // 8 bytes - Float64 (degrees)
  REC_LONGITUDE: 24,         // 8 bytes - Float64 (degrees)
  REC_ALTITUDE: 32,          // 4 bytes - Float32 (meters)
  REC_SPEED: 36,             // 4 bytes - Float32 (m/s)
  REC_BEARING: 40,           // 4 bytes - Float32 (degrees)
  REC_ACCURACY: 44,          // 4 bytes - Float32 (meters)
  REC_ACCEL_X: 48,           // 4 bytes - Float32 (m/s²)
  REC_ACCEL_Y: 52,           // 4 bytes - Float32 (m/s²)
  REC_ACCEL_Z: 56,           // 4 bytes - Float32 (m/s²)
  REC_ACCEL_MAG: 60,         // 4 bytes - Float32 (m/s²)
  
  // Capacity
  MAX_RECORDS: 180_000,      // ~1h @ 50 devices @ 1Hz
  
  // Validation
  MAGIC_NUMBER: 0x41555241,  // "AURA" in ASCII
  VERSION: 1,
  
  // Flags
  FLAG_VALID: 0x0001,
  FLAG_GPS_FIX: 0x0002,
  FLAG_IMU_VALID: 0x0004,
  FLAG_SPEEDING: 0x0008,
  FLAG_IMPACT: 0x0010,
} as const;

// Calculate buffer size
export const BUFFER_SIZE = SAB.HEADER_SIZE + (SAB.RECORD_SIZE * SAB.MAX_RECORDS);

// ============================================================
// TYPES
// ============================================================

export interface TelemetryRecord {
  timestamp: number;
  deviceId: string;
  deviceHash: number;
  flags: number;
  latitude: number;
  longitude: number;
  altitude: number;
  speed: number;         // m/s
  speedKmh: number;      // km/h (derived)
  bearing: number;       // degrees
  gpsAccuracy: number;   // meters
  accelX: number;        // m/s²
  accelY: number;        // m/s²
  accelZ: number;        // m/s²
  accelMagnitude: number; // m/s² (derived)
}

export interface BufferStats {
  recordCount: number;
  writeIndex: number;
  oldestTimestamp: number;
  newestTimestamp: number;
  deviceCount: number;
  messagesPerSecond: number;
}

// ============================================================
// HASH FUNCTION
// ============================================================

/**
 * Simple hash function for device IDs
 * Maps string to 16-bit unsigned integer
 */
export function hashDeviceId(deviceId: string): number {
  let hash = 0;
  for (let i = 0; i < deviceId.length; i++) {
    const char = deviceId.charCodeAt(i);
    hash = ((hash << 5) - hash + char) | 0;
  }
  return (hash & 0xFFFF) >>> 0; // Ensure positive 16-bit
}

// ============================================================
// BUFFER CREATION
// ============================================================

/**
 * Create and initialize a new SharedArrayBuffer
 */
export function createTelemetryBuffer(): SharedArrayBuffer {
  const sab = new SharedArrayBuffer(BUFFER_SIZE);
  initializeBuffer(sab);
  return sab;
}

/**
 * Initialize buffer header
 */
export function initializeBuffer(sab: SharedArrayBuffer): void {
  const view = new DataView(sab);
  
  // Write header
  view.setUint32(SAB.MAGIC_OFFSET, SAB.MAGIC_NUMBER, true);
  view.setUint32(SAB.VERSION_OFFSET, SAB.VERSION, true);
  view.setUint32(SAB.RECORD_COUNT_OFFSET, 0, true);
  view.setUint32(SAB.WRITE_INDEX_OFFSET, 0, true);
  view.setUint32(SAB.MAX_RECORDS_OFFSET, SAB.MAX_RECORDS, true);
  view.setUint32(SAB.RECORD_SIZE_OFFSET, SAB.RECORD_SIZE, true);
  view.setBigInt64(SAB.OLDEST_TS_OFFSET, BigInt(0), true);
  view.setBigInt64(SAB.NEWEST_TS_OFFSET, BigInt(0), true);
  view.setUint32(SAB.DEVICE_COUNT_OFFSET, 0, true);
  view.setFloat32(SAB.MSG_PER_SEC_OFFSET, 0, true);
}

/**
 * Validate buffer header
 */
export function validateBuffer(sab: SharedArrayBuffer): boolean {
  const view = new DataView(sab);
  
  const magic = view.getUint32(SAB.MAGIC_OFFSET, true);
  const version = view.getUint32(SAB.VERSION_OFFSET, true);
  
  return magic === SAB.MAGIC_NUMBER && version === SAB.VERSION;
}

// ============================================================
// WRITE OPERATIONS (Worker thread)
// ============================================================

/**
 * Write a telemetry record to the buffer
 * Returns the index where the record was written
 */
export function writeRecord(
  sab: SharedArrayBuffer,
  record: TelemetryRecord
): number {
  const headerView = new Int32Array(sab, 0, 64);
  const dataView = new DataView(sab);
  
  // Get current write index and increment atomically
  const currentIndex = Atomics.load(headerView, SAB.WRITE_INDEX_OFFSET / 4);
  const nextIndex = (currentIndex + 1) % SAB.MAX_RECORDS;
  
  // Calculate record offset
  const offset = SAB.HEADER_SIZE + (currentIndex * SAB.RECORD_SIZE);
  
  // Write record data
  dataView.setFloat64(offset + SAB.REC_TIMESTAMP, record.timestamp, true);
  dataView.setUint16(offset + SAB.REC_DEVICE_HASH, record.deviceHash, true);
  dataView.setUint16(offset + SAB.REC_FLAGS, record.flags, true);
  dataView.setFloat64(offset + SAB.REC_LATITUDE, record.latitude, true);
  dataView.setFloat64(offset + SAB.REC_LONGITUDE, record.longitude, true);
  dataView.setFloat32(offset + SAB.REC_ALTITUDE, record.altitude, true);
  dataView.setFloat32(offset + SAB.REC_SPEED, record.speed, true);
  dataView.setFloat32(offset + SAB.REC_BEARING, record.bearing, true);
  dataView.setFloat32(offset + SAB.REC_ACCURACY, record.gpsAccuracy, true);
  dataView.setFloat32(offset + SAB.REC_ACCEL_X, record.accelX, true);
  dataView.setFloat32(offset + SAB.REC_ACCEL_Y, record.accelY, true);
  dataView.setFloat32(offset + SAB.REC_ACCEL_Z, record.accelZ, true);
  dataView.setFloat32(offset + SAB.REC_ACCEL_MAG, record.accelMagnitude, true);
  
  // Update write index atomically
  Atomics.store(headerView, SAB.WRITE_INDEX_OFFSET / 4, nextIndex);
  
  // Update record count (capped at MAX_RECORDS)
  const oldCount = Atomics.load(headerView, SAB.RECORD_COUNT_OFFSET / 4);
  if (oldCount < SAB.MAX_RECORDS) {
    Atomics.add(headerView, SAB.RECORD_COUNT_OFFSET / 4, 1);
  }
  
  // Update newest timestamp
  const tsView = new BigInt64Array(sab, SAB.NEWEST_TS_OFFSET, 1);
  Atomics.store(tsView, 0, BigInt(Math.floor(record.timestamp)));
  
  // Update oldest timestamp if this is the first record
  if (oldCount === 0) {
    const oldestView = new BigInt64Array(sab, SAB.OLDEST_TS_OFFSET, 1);
    Atomics.store(oldestView, 0, BigInt(Math.floor(record.timestamp)));
  }
  
  // Notify readers
  Atomics.notify(headerView, SAB.WRITE_INDEX_OFFSET / 4);
  
  return currentIndex;
}

/**
 * Write multiple records in batch
 */
export function writeRecordBatch(
  sab: SharedArrayBuffer,
  records: TelemetryRecord[]
): number {
  let lastIndex = 0;
  for (const record of records) {
    lastIndex = writeRecord(sab, record);
  }
  return lastIndex;
}

// ============================================================
// READ OPERATIONS (Main thread)
// ============================================================

/**
 * Read a single record by index
 */
export function readRecord(
  sab: SharedArrayBuffer,
  index: number
): TelemetryRecord | null {
  if (index < 0 || index >= SAB.MAX_RECORDS) {
    return null;
  }
  
  const dataView = new DataView(sab);
  const offset = SAB.HEADER_SIZE + (index * SAB.RECORD_SIZE);
  
  const timestamp = dataView.getFloat64(offset + SAB.REC_TIMESTAMP, true);
  if (timestamp === 0) {
    return null; // Empty slot
  }
  
  const speed = dataView.getFloat32(offset + SAB.REC_SPEED, true);
  const accelX = dataView.getFloat32(offset + SAB.REC_ACCEL_X, true);
  const accelY = dataView.getFloat32(offset + SAB.REC_ACCEL_Y, true);
  const accelZ = dataView.getFloat32(offset + SAB.REC_ACCEL_Z, true);
  
  return {
    timestamp,
    deviceHash: dataView.getUint16(offset + SAB.REC_DEVICE_HASH, true),
    deviceId: "", // Hash only, need to resolve from map
    flags: dataView.getUint16(offset + SAB.REC_FLAGS, true),
    latitude: dataView.getFloat64(offset + SAB.REC_LATITUDE, true),
    longitude: dataView.getFloat64(offset + SAB.REC_LONGITUDE, true),
    altitude: dataView.getFloat32(offset + SAB.REC_ALTITUDE, true),
    speed,
    speedKmh: speed * 3.6,
    bearing: dataView.getFloat32(offset + SAB.REC_BEARING, true),
    gpsAccuracy: dataView.getFloat32(offset + SAB.REC_ACCURACY, true),
    accelX,
    accelY,
    accelZ,
    accelMagnitude: dataView.getFloat32(offset + SAB.REC_ACCEL_MAG, true),
  };
}

/**
 * Read the N most recent records
 */
export function readLatestRecords(
  sab: SharedArrayBuffer,
  count: number
): TelemetryRecord[] {
  const headerView = new Int32Array(sab, 0, 64);
  
  const writeIndex = Atomics.load(headerView, SAB.WRITE_INDEX_OFFSET / 4);
  const recordCount = Atomics.load(headerView, SAB.RECORD_COUNT_OFFSET / 4);
  
  const actualCount = Math.min(count, recordCount);
  const records: TelemetryRecord[] = [];
  
  for (let i = 0; i < actualCount; i++) {
    // Calculate index going backwards from write position
    let index = (writeIndex - 1 - i + SAB.MAX_RECORDS) % SAB.MAX_RECORDS;
    const record = readRecord(sab, index);
    if (record) {
      records.push(record);
    }
  }
  
  return records;
}

/**
 * Read records for a specific device (by hash)
 */
export function readDeviceRecords(
  sab: SharedArrayBuffer,
  deviceHash: number,
  maxRecords: number = 3600
): TelemetryRecord[] {
  const headerView = new Int32Array(sab, 0, 64);
  const recordCount = Atomics.load(headerView, SAB.RECORD_COUNT_OFFSET / 4);
  const writeIndex = Atomics.load(headerView, SAB.WRITE_INDEX_OFFSET / 4);
  
  const records: TelemetryRecord[] = [];
  const searchCount = Math.min(recordCount, SAB.MAX_RECORDS);
  
  for (let i = 0; i < searchCount && records.length < maxRecords; i++) {
    const index = (writeIndex - 1 - i + SAB.MAX_RECORDS) % SAB.MAX_RECORDS;
    const record = readRecord(sab, index);
    
    if (record && record.deviceHash === deviceHash) {
      records.push(record);
    }
  }
  
  return records.reverse(); // Oldest first
}

/**
 * Read records in a time range
 */
export function readTimeRange(
  sab: SharedArrayBuffer,
  startTime: number,
  endTime: number
): TelemetryRecord[] {
  const headerView = new Int32Array(sab, 0, 64);
  const recordCount = Atomics.load(headerView, SAB.RECORD_COUNT_OFFSET / 4);
  const writeIndex = Atomics.load(headerView, SAB.WRITE_INDEX_OFFSET / 4);
  
  const records: TelemetryRecord[] = [];
  const searchCount = Math.min(recordCount, SAB.MAX_RECORDS);
  
  for (let i = 0; i < searchCount; i++) {
    const index = (writeIndex - 1 - i + SAB.MAX_RECORDS) % SAB.MAX_RECORDS;
    const record = readRecord(sab, index);
    
    if (record) {
      if (record.timestamp < startTime) {
        break; // We've gone past the start time
      }
      if (record.timestamp <= endTime) {
        records.push(record);
      }
    }
  }
  
  return records.reverse(); // Oldest first
}

/**
 * Get buffer statistics
 */
export function getBufferStats(sab: SharedArrayBuffer): BufferStats {
  const headerView = new Int32Array(sab, 0, 64);
  const dataView = new DataView(sab);
  
  return {
    recordCount: Atomics.load(headerView, SAB.RECORD_COUNT_OFFSET / 4),
    writeIndex: Atomics.load(headerView, SAB.WRITE_INDEX_OFFSET / 4),
    oldestTimestamp: Number(dataView.getBigInt64(SAB.OLDEST_TS_OFFSET, true)),
    newestTimestamp: Number(dataView.getBigInt64(SAB.NEWEST_TS_OFFSET, true)),
    deviceCount: Atomics.load(headerView, SAB.DEVICE_COUNT_OFFSET / 4),
    messagesPerSecond: dataView.getFloat32(SAB.MSG_PER_SEC_OFFSET, true),
  };
}

/**
 * Update messages per second metric
 */
export function updateMsgPerSec(sab: SharedArrayBuffer, value: number): void {
  const dataView = new DataView(sab);
  dataView.setFloat32(SAB.MSG_PER_SEC_OFFSET, value, true);
}

/**
 * Update device count
 */
export function updateDeviceCount(sab: SharedArrayBuffer, count: number): void {
  const headerView = new Int32Array(sab, 0, 64);
  Atomics.store(headerView, SAB.DEVICE_COUNT_OFFSET / 4, count);
}

// ============================================================
// UTILITY FUNCTIONS
// ============================================================

/**
 * Get latest position for each device
 */
export function getLatestDevicePositions(
  sab: SharedArrayBuffer
): Map<number, TelemetryRecord> {
  const headerView = new Int32Array(sab, 0, 64);
  const recordCount = Atomics.load(headerView, SAB.RECORD_COUNT_OFFSET / 4);
  const writeIndex = Atomics.load(headerView, SAB.WRITE_INDEX_OFFSET / 4);
  
  const devicePositions = new Map<number, TelemetryRecord>();
  const searchCount = Math.min(recordCount, SAB.MAX_RECORDS);
  
  for (let i = 0; i < searchCount; i++) {
    const index = (writeIndex - 1 - i + SAB.MAX_RECORDS) % SAB.MAX_RECORDS;
    const record = readRecord(sab, index);
    
    if (record && !devicePositions.has(record.deviceHash)) {
      devicePositions.set(record.deviceHash, record);
    }
  }
  
  return devicePositions;
}

/**
 * Check if SharedArrayBuffer is available
 */
export function isSharedArrayBufferAvailable(): boolean {
  try {
    new SharedArrayBuffer(1);
    return true;
  } catch {
    return false;
  }
}

/**
 * Check if Atomics is available
 */
export function isAtomicsAvailable(): boolean {
  return typeof Atomics !== 'undefined';
}

