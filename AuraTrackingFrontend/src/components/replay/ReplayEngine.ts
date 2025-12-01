/**
 * ReplayEngine
 * ============================================================
 * Engine for replaying telemetry data
 * Supports variable speed, seek, and interpolation
 */

import type { TelemetryRecord } from "~/lib/workers/shared-buffer";

export interface ReplayConfig {
  bufferWindow: number;      // ms to preload
  interpolate: boolean;      // smooth position interpolation
  showTrail: boolean;        // show trail behind vehicle
  trailLength: number;       // points in trail
}

export interface ReplayState {
  currentTime: number;
  playbackSpeed: number;
  isPlaying: boolean;
  progress: number;           // 0-100
  startTime: number;
  endTime: number;
}

export interface ReplayCallbacks {
  onFrame: (record: TelemetryRecord, trail: TelemetryRecord[]) => void;
  onStateChange: (state: ReplayState) => void;
  onComplete: () => void;
}

const DEFAULT_CONFIG: ReplayConfig = {
  bufferWindow: 60000,
  interpolate: true,
  showTrail: true,
  trailLength: 300,
};

export class ReplayEngine {
  private data: TelemetryRecord[] = [];
  private currentIndex = 0;
  private animationFrame: number | null = null;
  private lastFrameTime = 0;
  private config: ReplayConfig;
  private callbacks: ReplayCallbacks;
  
  private state: ReplayState = {
    currentTime: 0,
    playbackSpeed: 1,
    isPlaying: false,
    progress: 0,
    startTime: 0,
    endTime: 0,
  };
  
  constructor(
    callbacks: ReplayCallbacks,
    config: Partial<ReplayConfig> = {}
  ) {
    this.callbacks = callbacks;
    this.config = { ...DEFAULT_CONFIG, ...config };
  }
  
  /**
   * Load telemetry data for replay
   */
  loadData(data: TelemetryRecord[]): void {
    if (data.length === 0) {
      console.warn("[ReplayEngine] No data to load");
      return;
    }
    
    // Sort by timestamp
    this.data = [...data].sort((a, b) => a.timestamp - b.timestamp);
    
    // Update state
    this.state.startTime = this.data[0].timestamp;
    this.state.endTime = this.data[this.data.length - 1].timestamp;
    this.state.currentTime = this.state.startTime;
    this.state.progress = 0;
    this.currentIndex = 0;
    
    this.emitStateChange();
    this.emitCurrentFrame();
    
    console.log(`[ReplayEngine] Loaded ${data.length} records`);
  }
  
  /**
   * Start or resume playback
   */
  play(): void {
    if (this.data.length === 0) {
      console.warn("[ReplayEngine] No data loaded");
      return;
    }
    
    if (this.state.isPlaying) return;
    
    this.state.isPlaying = true;
    this.lastFrameTime = performance.now();
    this.tick();
    
    this.emitStateChange();
  }
  
  /**
   * Pause playback
   */
  pause(): void {
    if (!this.state.isPlaying) return;
    
    this.state.isPlaying = false;
    
    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
      this.animationFrame = null;
    }
    
    this.emitStateChange();
  }
  
  /**
   * Toggle play/pause
   */
  toggle(): void {
    if (this.state.isPlaying) {
      this.pause();
    } else {
      this.play();
    }
  }
  
  /**
   * Seek to specific timestamp
   */
  seek(timestamp: number): void {
    // Clamp to valid range
    timestamp = Math.max(this.state.startTime, Math.min(this.state.endTime, timestamp));
    
    this.state.currentTime = timestamp;
    this.currentIndex = this.findIndexForTime(timestamp);
    this.updateProgress();
    
    this.emitStateChange();
    this.emitCurrentFrame();
  }
  
  /**
   * Seek by progress percentage (0-100)
   */
  seekProgress(progress: number): void {
    const duration = this.state.endTime - this.state.startTime;
    const timestamp = this.state.startTime + (duration * progress / 100);
    this.seek(timestamp);
  }
  
  /**
   * Set playback speed
   */
  setSpeed(speed: number): void {
    this.state.playbackSpeed = Math.max(0.1, Math.min(16, speed));
    this.emitStateChange();
  }
  
  /**
   * Skip forward by seconds
   */
  skipForward(seconds: number): void {
    this.seek(this.state.currentTime + (seconds * 1000));
  }
  
  /**
   * Skip backward by seconds
   */
  skipBackward(seconds: number): void {
    this.seek(this.state.currentTime - (seconds * 1000));
  }
  
  /**
   * Get current state
   */
  getState(): Readonly<ReplayState> {
    return { ...this.state };
  }
  
  /**
   * Get current record
   */
  getCurrentRecord(): TelemetryRecord | null {
    if (this.currentIndex < 0 || this.currentIndex >= this.data.length) {
      return null;
    }
    return this.data[this.currentIndex];
  }
  
  /**
   * Get trail (recent positions)
   */
  getTrail(): TelemetryRecord[] {
    const startIdx = Math.max(0, this.currentIndex - this.config.trailLength);
    return this.data.slice(startIdx, this.currentIndex + 1);
  }
  
  /**
   * Cleanup
   */
  destroy(): void {
    this.pause();
    this.data = [];
  }
  
  // ============================================================
  // PRIVATE METHODS
  // ============================================================
  
  private tick(): void {
    if (!this.state.isPlaying) return;
    
    const now = performance.now();
    const deltaReal = now - this.lastFrameTime;
    const deltaSimulated = deltaReal * this.state.playbackSpeed;
    
    this.lastFrameTime = now;
    this.state.currentTime += deltaSimulated;
    
    // Check if we've reached the end
    if (this.state.currentTime >= this.state.endTime) {
      this.state.currentTime = this.state.endTime;
      this.state.progress = 100;
      this.pause();
      this.callbacks.onComplete();
      return;
    }
    
    // Advance to correct record
    this.advanceToTime(this.state.currentTime);
    this.updateProgress();
    
    this.emitCurrentFrame();
    
    // Schedule next frame
    this.animationFrame = requestAnimationFrame(() => this.tick());
  }
  
  private advanceToTime(targetTime: number): void {
    while (
      this.currentIndex < this.data.length - 1 &&
      this.data[this.currentIndex + 1].timestamp <= targetTime
    ) {
      this.currentIndex++;
    }
  }
  
  private findIndexForTime(timestamp: number): number {
    // Binary search
    let low = 0;
    let high = this.data.length - 1;
    
    while (low < high) {
      const mid = Math.floor((low + high + 1) / 2);
      if (this.data[mid].timestamp <= timestamp) {
        low = mid;
      } else {
        high = mid - 1;
      }
    }
    
    return low;
  }
  
  private updateProgress(): void {
    const duration = this.state.endTime - this.state.startTime;
    if (duration === 0) {
      this.state.progress = 0;
    } else {
      this.state.progress = 
        ((this.state.currentTime - this.state.startTime) / duration) * 100;
    }
  }
  
  private emitCurrentFrame(): void {
    const current = this.getCurrentRecord();
    if (current) {
      const trail = this.config.showTrail ? this.getTrail() : [];
      
      if (this.config.interpolate && this.currentIndex < this.data.length - 1) {
        const next = this.data[this.currentIndex + 1];
        const t = (this.state.currentTime - current.timestamp) / 
                  (next.timestamp - current.timestamp);
        
        const interpolated = this.interpolateRecord(current, next, t);
        this.callbacks.onFrame(interpolated, trail);
      } else {
        this.callbacks.onFrame(current, trail);
      }
    }
  }
  
  private interpolateRecord(
    a: TelemetryRecord,
    b: TelemetryRecord,
    t: number
  ): TelemetryRecord {
    t = Math.max(0, Math.min(1, t));
    
    return {
      ...a,
      timestamp: a.timestamp + (b.timestamp - a.timestamp) * t,
      latitude: a.latitude + (b.latitude - a.latitude) * t,
      longitude: a.longitude + (b.longitude - a.longitude) * t,
      altitude: a.altitude + (b.altitude - a.altitude) * t,
      speed: a.speed + (b.speed - a.speed) * t,
      speedKmh: a.speedKmh + (b.speedKmh - a.speedKmh) * t,
      bearing: this.lerpAngle(a.bearing, b.bearing, t),
    };
  }
  
  private lerpAngle(a: number, b: number, t: number): number {
    let diff = b - a;
    if (diff > 180) diff -= 360;
    if (diff < -180) diff += 360;
    return ((a + diff * t) + 360) % 360;
  }
  
  private emitStateChange(): void {
    this.callbacks.onStateChange({ ...this.state });
  }
}

export default ReplayEngine;


