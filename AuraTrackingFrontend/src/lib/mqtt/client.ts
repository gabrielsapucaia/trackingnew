/**
 * ============================================================
 * MQTT Client over WebSocket
 * ============================================================
 * Conecta ao EMQX via WebSocket (porta 8083)
 * e faz subscribe nos tópicos de telemetria
 * ============================================================
 */

import mqtt, { MqttClient, IClientOptions } from 'mqtt';
import { TelemetryPacket, MqttConfig, ConnectionState } from './types';

const DEFAULT_CONFIG: MqttConfig = {
  brokerUrl: 'ws://localhost:8083/mqtt',
  clientId: `aura_frontend_${Math.random().toString(16).slice(2, 10)}`,
  topics: ['aura/tracking/#'],
  qos: 1,
  reconnectPeriod: 1000,
  connectTimeout: 30000,
};

export interface MqttClientCallbacks {
  onConnected: () => void;
  onDisconnected: () => void;
  onError: (error: Error) => void;
  onMessage: (topic: string, packet: TelemetryPacket) => void;
  onReconnecting: (attempt: number) => void;
}

export class AuraMqttClient {
  private client: MqttClient | null = null;
  private config: MqttConfig;
  private callbacks: MqttClientCallbacks;
  private connectionState: ConnectionState = 'DISCONNECTED';
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;

  constructor(config: Partial<MqttConfig>, callbacks: MqttClientCallbacks) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.callbacks = callbacks;
  }

  public connect(): void {
    if (this.client) {
      console.warn('[MQTT] Already connected or connecting');
      return;
    }

    this.connectionState = 'CONNECTING';
    console.log(`[MQTT] Connecting to ${this.config.brokerUrl}...`);

    const options: IClientOptions = {
      clientId: this.config.clientId,
      clean: true,
      connectTimeout: this.config.connectTimeout,
      reconnectPeriod: this.config.reconnectPeriod,
      keepalive: 60,
      // EMQX anonymous access
      username: this.config.username,
      password: this.config.password,
    };

    try {
      this.client = mqtt.connect(this.config.brokerUrl, options);
      this.setupEventHandlers();
    } catch (error) {
      console.error('[MQTT] Connection error:', error);
      this.callbacks.onError(error as Error);
    }
  }

  private setupEventHandlers(): void {
    if (!this.client) return;

    this.client.on('connect', () => {
      console.log('[MQTT] Connected successfully');
      this.connectionState = 'CONNECTED';
      this.reconnectAttempts = 0;
      
      // Subscribe to configured topics
      this.subscribeToTopics();
      this.callbacks.onConnected();
    });

    this.client.on('message', (topic: string, payload: Buffer) => {
      try {
        const message = JSON.parse(payload.toString()) as TelemetryPacket;
        this.callbacks.onMessage(topic, message);
      } catch (error) {
        console.error('[MQTT] Failed to parse message:', error);
      }
    });

    this.client.on('error', (error: Error) => {
      console.error('[MQTT] Error:', error);
      this.callbacks.onError(error);
    });

    this.client.on('close', () => {
      console.log('[MQTT] Connection closed');
      this.connectionState = 'DISCONNECTED';
      this.callbacks.onDisconnected();
    });

    this.client.on('reconnect', () => {
      this.reconnectAttempts++;
      console.log(`[MQTT] Reconnecting... attempt ${this.reconnectAttempts}`);
      this.connectionState = 'RECONNECTING';
      this.callbacks.onReconnecting(this.reconnectAttempts);

      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.error('[MQTT] Max reconnect attempts reached');
        this.disconnect();
      }
    });

    this.client.on('offline', () => {
      console.log('[MQTT] Client offline');
      this.connectionState = 'DISCONNECTED';
    });
  }

  private subscribeToTopics(): void {
    if (!this.client) return;

    this.config.topics.forEach((topic) => {
      this.client!.subscribe(topic, { qos: this.config.qos as 0 | 1 | 2 }, (err) => {
        if (err) {
          console.error(`[MQTT] Subscribe error for ${topic}:`, err);
        } else {
          console.log(`[MQTT] Subscribed to ${topic}`);
        }
      });
    });
  }

  public disconnect(): void {
    if (this.client) {
      console.log('[MQTT] Disconnecting...');
      this.client.end(true);
      this.client = null;
      this.connectionState = 'DISCONNECTED';
    }
  }

  public publish(topic: string, message: object): void {
    if (this.client && this.connectionState === 'CONNECTED') {
      this.client.publish(topic, JSON.stringify(message), { qos: this.config.qos as 0 | 1 | 2 });
    } else {
      console.warn('[MQTT] Cannot publish: not connected');
    }
  }

  public getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  public isConnected(): boolean {
    return this.connectionState === 'CONNECTED';
  }
}

