/**
 * ============================================================
 * API Client
 * ============================================================
 * Cliente para consumir a REST API do Ingest Worker
 * Com integração opcional com Supabase para dados complementares
 * ============================================================
 */

import { supabase } from '../supabase'
import type { Device as SupabaseDevice, Alert, Profile } from '../supabase/types'

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export interface Device {
  device_id: string;
  operator_id: string;
  last_seen: string;
  latitude: number | null;
  longitude: number | null;
  speed_kmh: number | null;
  total_points_24h: number;
  status: 'online' | 'offline';
}

export interface TelemetryPoint {
  time: string;
  device_id: string;
  operator_id: string;
  latitude: number;
  longitude: number;
  altitude: number;
  speed: number;
  speed_kmh: number;
  bearing: number;
  gps_accuracy: number;
  accel_x: number;
  accel_y: number;
  accel_z: number;
  accel_magnitude: number;
}

export interface SystemSummary {
  period_hours: number;
  active_devices: number;
  total_telemetries: number;
  avg_speed_kmh: number;
  max_speed_kmh: number;
  max_acceleration: number;
  events: Record<string, number>;
  ingest_stats: {
    messages_received: number;
    messages_inserted: number;
    mqtt_connected: boolean;
    db_connected: boolean;
    uptime_seconds: number;
    messages_per_second: number;
  };
}

export interface ApiResponse<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  // ========== Devices ==========

  async getDevices(): Promise<{ devices: Device[]; count: number }> {
    return this.fetch('/api/devices');
  }

  // ========== Telemetry ==========

  async getTelemetry(params: {
    device_id: string;
    start?: string;
    end?: string;
    limit?: number;
    granularity?: 'raw' | '1min' | '1hour';
  }): Promise<{
    device_id: string;
    start: string;
    end: string;
    granularity: string;
    count: number;
    data: TelemetryPoint[];
  }> {
    const searchParams = new URLSearchParams();
    searchParams.set('device_id', params.device_id);
    if (params.start) searchParams.set('start', params.start);
    if (params.end) searchParams.set('end', params.end);
    if (params.limit) searchParams.set('limit', params.limit.toString());
    if (params.granularity) searchParams.set('granularity', params.granularity);

    return this.fetch(`/api/telemetry?${searchParams.toString()}`);
  }

  // ========== Summary ==========

  async getSummary(hours: number = 24): Promise<SystemSummary> {
    return this.fetch(`/api/summary?hours=${hours}`);
  }

  // ========== Health ==========

  async getHealth(): Promise<{
    status: string;
    mqtt_connected: boolean;
    db_connected: boolean;
    uptime_seconds: number;
  }> {
    return this.fetch('/health');
  }

  // ========== Events ==========

  async getEvents(params?: {
    device_id?: string;
    event_type?: string;
    start?: string;
    end?: string;
    limit?: number;
  }): Promise<{ events: any[]; count: number }> {
    const searchParams = new URLSearchParams();
    if (params?.device_id) searchParams.set('device_id', params.device_id);
    if (params?.event_type) searchParams.set('event_type', params.event_type);
    if (params?.start) searchParams.set('start', params.start);
    if (params?.end) searchParams.set('end', params.end);
    if (params?.limit) searchParams.set('limit', params.limit.toString());

    return this.fetch(`/api/events?${searchParams.toString()}`);
  }

  // ========== Supabase Integration ==========

  // Dispositivos (complementar ao TimescaleDB)
  async getDevicesFromSupabase(): Promise<{ devices: SupabaseDevice[]; count: number }> {
    try {
      const { data, error, count } = await supabase
        .from('devices')
        .select('*', { count: 'exact' })
        .order('created_at', { ascending: false })

      // Se a tabela não existe, retorna lista vazia ao invés de erro
      if (error) {
        if (error.message.includes('Could not find the table') || error.code === 'PGRST116') {
          console.warn('Tabela devices não encontrada no Supabase. Retornando lista vazia.');
          return { devices: [], count: 0 }
        }
        throw new Error(`Supabase error: ${error.message}`)
      }
      return { devices: data || [], count: count || 0 }
    } catch (err: any) {
      // Tratamento adicional para erros de conexão ou schema
      if (err.message?.includes('Could not find the table') || err.message?.includes('schema cache')) {
        console.warn('Tabela devices não encontrada no Supabase. Retornando lista vazia.');
        return { devices: [], count: 0 }
      }
      throw err
    }
  }

  async createDevice(device: Omit<SupabaseDevice, 'id' | 'created_at' | 'updated_at'>): Promise<SupabaseDevice> {
    try {
      const { data, error } = await supabase
        .from('devices')
        .insert(device)
        .select()
        .single()

      if (error) {
        if (error.message.includes('Could not find the table') || error.code === 'PGRST116') {
          throw new Error('Tabela devices não existe no Supabase. Execute o script SQL de criação primeiro.')
        }
        throw new Error(`Supabase error: ${error.message}`)
      }
      return data
    } catch (err: any) {
      if (err.message?.includes('Could not find the table') || err.message?.includes('schema cache')) {
        throw new Error('Tabela devices não existe no Supabase. Execute o script SQL de criação primeiro.')
      }
      throw err
    }
  }

  async updateDevice(id: string, updates: Partial<SupabaseDevice>): Promise<SupabaseDevice> {
    try {
      const { data, error } = await supabase
        .from('devices')
        .update({ ...updates, updated_at: new Date().toISOString() })
        .eq('id', id)
        .select()
        .single()

      if (error) {
        if (error.message.includes('Could not find the table') || error.code === 'PGRST116') {
          throw new Error('Tabela devices não existe no Supabase. Execute o script SQL de criação primeiro.')
        }
        throw new Error(`Supabase error: ${error.message}`)
      }
      return data
    } catch (err: any) {
      if (err.message?.includes('Could not find the table') || err.message?.includes('schema cache')) {
        throw new Error('Tabela devices não existe no Supabase. Execute o script SQL de criação primeiro.')
      }
      throw err
    }
  }

  async deleteDevice(id: string): Promise<void> {
    try {
      const { error } = await supabase
        .from('devices')
        .delete()
        .eq('id', id)

      if (error) {
        if (error.message.includes('Could not find the table') || error.code === 'PGRST116') {
          throw new Error('Tabela devices não existe no Supabase. Execute o script SQL de criação primeiro.')
        }
        throw new Error(`Supabase error: ${error.message}`)
      }
    } catch (err: any) {
      if (err.message?.includes('Could not find the table') || err.message?.includes('schema cache')) {
        throw new Error('Tabela devices não existe no Supabase. Execute o script SQL de criação primeiro.')
      }
      throw err
    }
  }

  // Alertas
  async getAlerts(): Promise<{ alerts: Alert[]; count: number }> {
    try {
      const { data, error, count } = await supabase
        .from('alerts')
        .select('*', { count: 'exact' })
        .order('created_at', { ascending: false })

      if (error) {
        if (error.message.includes('Could not find the table') || error.code === 'PGRST116') {
          console.warn('Tabela alerts não encontrada no Supabase. Retornando lista vazia.');
          return { alerts: [], count: 0 }
        }
        throw new Error(`Supabase error: ${error.message}`)
      }
      return { alerts: data || [], count: count || 0 }
    } catch (err: any) {
      if (err.message?.includes('Could not find the table') || err.message?.includes('schema cache')) {
        console.warn('Tabela alerts não encontrada no Supabase. Retornando lista vazia.');
        return { alerts: [], count: 0 }
      }
      throw err
    }
  }

  async createAlert(alert: Omit<Alert, 'id' | 'created_at' | 'updated_at'>): Promise<Alert> {
    const { data, error } = await supabase
      .from('alerts')
      .insert(alert)
      .select()
      .single()

    if (error) throw new Error(`Supabase error: ${error.message}`)
    return data
  }

  async updateAlert(id: string, updates: Partial<Alert>): Promise<Alert> {
    const { data, error } = await supabase
      .from('alerts')
      .update({ ...updates, updated_at: new Date().toISOString() })
      .eq('id', id)
      .select()
      .single()

    if (error) throw new Error(`Supabase error: ${error.message}`)
    return data
  }

  // Perfis de usuário
  async getProfiles(): Promise<{ profiles: Profile[]; count: number }> {
    try {
      const { data, error, count } = await supabase
        .from('profiles')
        .select('*', { count: 'exact' })
        .order('created_at', { ascending: false })

      if (error) {
        if (error.message.includes('Could not find the table') || error.code === 'PGRST116') {
          console.warn('Tabela profiles não encontrada no Supabase. Retornando lista vazia.');
          return { profiles: [], count: 0 }
        }
        throw new Error(`Supabase error: ${error.message}`)
      }
      return { profiles: data || [], count: count || 0 }
    } catch (err: any) {
      if (err.message?.includes('Could not find the table') || err.message?.includes('schema cache')) {
        console.warn('Tabela profiles não encontrada no Supabase. Retornando lista vazia.');
        return { profiles: [], count: 0 }
      }
      throw err
    }
  }

  async getProfile(id: string): Promise<Profile | null> {
    const { data, error } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', id)
      .single()

    if (error && error.code !== 'PGRST116') throw new Error(`Supabase error: ${error.message}`)
    return data
  }

  // Verificar saúde do Supabase
  async checkSupabaseHealth(): Promise<{ healthy: boolean; error?: string }> {
    try {
      const { error } = await supabase.from('health_check').select('*').limit(1)
      return { healthy: !error, error: error?.message }
    } catch (err) {
      return { healthy: false, error: 'Connection failed' }
    }
  }
}

// Singleton instance
export const api = new ApiClient();

export default api;

