/**
 * ============================================================
 * MQTT Provider
 * ============================================================
 * Gerencia conexão MQTT via WebSocket com EMQX
 * e distribui mensagens de telemetria para a aplicação
 * ============================================================
 */

import { createContext, useContext, createSignal, onMount, onCleanup, ParentProps } from 'solid-js';
import { isServer } from 'solid-js/web';
import type { TelemetryPacket, ConnectionState } from '../lib/mqtt/types';

interface MqttContextType {
  connectionState: () => ConnectionState;
  isConnected: () => boolean;
  reconnectAttempts: () => number;
  messagesReceived: () => number;
  lastMessage: () => TelemetryPacket | null;
  connect: () => void;
  disconnect: () => void;
}

const MqttContext = createContext<MqttContextType>();

// Configuração do broker - pode vir de env ou config
const MQTT_CONFIG = {
  // Em produção, usar o IP do EMQX (10.10.10.10:8083)
  // Em dev local com Docker, usar localhost:8083
  brokerUrl: 'ws://localhost:8083/mqtt',
  topics: ['aura/tracking/#'],
  qos: 1,
};

export function MqttProvider(props: ParentProps) {
  const [connectionState, setConnectionState] = createSignal<ConnectionState>('DISCONNECTED');
  const [reconnectAttempts, setReconnectAttempts] = createSignal(0);
  const [messagesReceived, setMessagesReceived] = createSignal(0);
  const [lastMessage, setLastMessage] = createSignal<TelemetryPacket | null>(null);

  // Skip MQTT on server
  if (isServer) {
    return (
      <MqttContext.Provider
        value={{
          connectionState,
          isConnected: () => false,
          reconnectAttempts,
          messagesReceived,
          lastMessage,
          connect: () => {},
          disconnect: () => {},
        }}
      >
        {props.children}
      </MqttContext.Provider>
    );
  }

  let mqttClient: any = null;

  // Callback para processar mensagens recebidas
  const handleMessage = (topic: string, packet: TelemetryPacket) => {
    setMessagesReceived((prev) => prev + 1);
    setLastMessage(packet);

    // Log a cada 100 mensagens para não poluir console
    if (messagesReceived() % 100 === 0) {
      console.log(`[MqttProvider] Received ${messagesReceived()} messages. Last from ${packet.deviceId}`);
    }

    // Dispatch evento customizado para outros componentes interessados
    if (typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('telemetry', {
          detail: { topic, packet },
        })
      );
    }
  };

  onMount(async () => {
    console.log('[MqttProvider] Initializing MQTT client...');
    console.log(`[MqttProvider] Broker URL: ${MQTT_CONFIG.brokerUrl}`);

    // Dynamic import to avoid SSR issues
    const { AuraMqttClient } = await import('../lib/mqtt/client');

    mqttClient = new AuraMqttClient(MQTT_CONFIG, {
      onConnected: () => {
        setConnectionState('CONNECTED');
        setReconnectAttempts(0);
        console.log('[MqttProvider] Connected to EMQX');
        // Dispatch status event
        window.dispatchEvent(new CustomEvent('mqtt-status', { 
          detail: { state: 'CONNECTED', attempts: 0 } 
        }));
      },
      onDisconnected: () => {
        setConnectionState('DISCONNECTED');
        console.log('[MqttProvider] Disconnected from EMQX');
        // Dispatch status event
        window.dispatchEvent(new CustomEvent('mqtt-status', { 
          detail: { state: 'DISCONNECTED' } 
        }));
      },
      onError: (error) => {
        console.error('[MqttProvider] MQTT Error:', error);
        // Dispatch status event
        window.dispatchEvent(new CustomEvent('mqtt-status', { 
          detail: { state: 'FAILED' } 
        }));
      },
      onMessage: handleMessage,
      onReconnecting: (attempt) => {
        setConnectionState('RECONNECTING');
        setReconnectAttempts(attempt);
        // Dispatch status event
        window.dispatchEvent(new CustomEvent('mqtt-status', { 
          detail: { state: 'RECONNECTING', attempts: attempt } 
        }));
      },
    });

    // Auto-connect on mount
    mqttClient.connect();
  });

  onCleanup(() => {
    console.log('[MqttProvider] Cleaning up MQTT connection...');
    mqttClient?.disconnect();
  });

  const connect = () => {
    mqttClient?.connect();
  };

  const disconnect = () => {
    mqttClient?.disconnect();
  };

  const isConnected = () => connectionState() === 'CONNECTED';

  return (
    <MqttContext.Provider
      value={{
        connectionState,
        isConnected,
        reconnectAttempts,
        messagesReceived,
        lastMessage,
        connect,
        disconnect,
      }}
    >
      {props.children}
    </MqttContext.Provider>
  );
}

export function useMqtt() {
  const context = useContext(MqttContext);
  if (!context) {
    throw new Error('useMqtt must be used within a MqttProvider');
  }
  return context;
}

