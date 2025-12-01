/**
 * ============================================================
 * MQTT Types
 * ============================================================
 */

export type ConnectionState = 
  | 'DISCONNECTED'
  | 'CONNECTING'
  | 'CONNECTED'
  | 'RECONNECTING'
  | 'FAILED';

export interface MqttConfig {
  brokerUrl: string;
  clientId: string;
  topics: string[];
  qos: number;
  reconnectPeriod: number;
  connectTimeout: number;
  username?: string;
  password?: string;
}

export interface GpsData {
  latitude: number;
  longitude: number;
  altitude?: number;
  speed?: number;      // m/s
  bearing?: number;
  accuracy?: number;
}

export interface ImuData {
  accelX: number;
  accelY: number;
  accelZ: number;
  gyroX?: number;
  gyroY?: number;
  gyroZ?: number;
}

export interface TelemetryPacket {
  messageId?: string;
  deviceId: string;
  operatorId?: string;
  timestamp: number;
  gps: GpsData;
  imu: ImuData;
}

export interface EventPacket {
  messageId?: string;
  deviceId: string;
  operatorId?: string;
  timestamp: number;
  eventType: string;
  severity: 'info' | 'warning' | 'critical';
  data?: Record<string, unknown>;
}


