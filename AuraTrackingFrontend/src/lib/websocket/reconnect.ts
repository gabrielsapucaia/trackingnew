/**
 * Reconnection Strategy
 * ============================================================
 * Utilities for handling WebSocket reconnection
 */

export interface ReconnectConfig {
  initialDelay: number;    // Starting delay in ms
  maxDelay: number;        // Maximum delay cap
  multiplier: number;      // Exponential multiplier
  jitter: number;          // Random jitter factor (0-1)
  maxRetries: number;      // Max attempts (0 = unlimited)
}

export const DEFAULT_RECONNECT_CONFIG: ReconnectConfig = {
  initialDelay: 1000,
  maxDelay: 30000,
  multiplier: 2,
  jitter: 0.3,
  maxRetries: 10,
};

/**
 * Calculate reconnection delay with exponential backoff and jitter
 */
export function calculateDelay(
  attempt: number,
  config: ReconnectConfig = DEFAULT_RECONNECT_CONFIG
): number {
  const { initialDelay, maxDelay, multiplier, jitter } = config;
  
  // Base exponential delay
  const exponentialDelay = initialDelay * Math.pow(multiplier, attempt);
  
  // Cap at max delay
  const cappedDelay = Math.min(exponentialDelay, maxDelay);
  
  // Add jitter (-jitter% to +jitter%)
  const jitterRange = cappedDelay * jitter;
  const jitterOffset = (Math.random() * 2 - 1) * jitterRange;
  
  return Math.floor(cappedDelay + jitterOffset);
}

/**
 * Calculate total wait time for N retries
 */
export function totalWaitTime(
  retries: number,
  config: ReconnectConfig = DEFAULT_RECONNECT_CONFIG
): number {
  let total = 0;
  for (let i = 0; i < retries; i++) {
    total += calculateDelay(i, config);
  }
  return total;
}

/**
 * Determine if we should give up reconnecting
 */
export function shouldGiveUp(
  attempt: number,
  config: ReconnectConfig = DEFAULT_RECONNECT_CONFIG
): boolean {
  return config.maxRetries > 0 && attempt >= config.maxRetries;
}

/**
 * Format delay for display
 */
export function formatDelay(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`;
  }
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Create a reconnection state machine
 */
export class ReconnectionState {
  private attempt = 0;
  private config: ReconnectConfig;
  private timer: ReturnType<typeof setTimeout> | null = null;
  
  constructor(config: Partial<ReconnectConfig> = {}) {
    this.config = { ...DEFAULT_RECONNECT_CONFIG, ...config };
  }
  
  /**
   * Schedule next reconnection attempt
   */
  schedule(callback: () => void): number {
    this.cancel();
    
    if (this.shouldGiveUp()) {
      return -1;
    }
    
    const delay = this.getNextDelay();
    this.attempt++;
    
    this.timer = setTimeout(callback, delay);
    
    return delay;
  }
  
  /**
   * Cancel scheduled reconnection
   */
  cancel(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }
  
  /**
   * Reset state after successful connection
   */
  reset(): void {
    this.attempt = 0;
    this.cancel();
  }
  
  /**
   * Get current attempt number
   */
  getAttempt(): number {
    return this.attempt;
  }
  
  /**
   * Get delay for next attempt
   */
  getNextDelay(): number {
    return calculateDelay(this.attempt, this.config);
  }
  
  /**
   * Check if we should give up
   */
  shouldGiveUp(): boolean {
    return shouldGiveUp(this.attempt, this.config);
  }
}

export default ReconnectionState;

