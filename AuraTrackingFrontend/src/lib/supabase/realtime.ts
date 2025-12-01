/**
 * ============================================================
 * Supabase Real-time Utilities
 * ============================================================
 * Funções para trabalhar com subscriptions em tempo real
 * ============================================================
 */

import { supabase } from './client'
import type { RealtimeChannel, RealtimePostgresChangesPayload } from '@supabase/supabase-js'
import type { Database } from './types'

// Tipos para real-time
export type TableName = keyof Database['public']['Tables']
export type RealtimePayload<T extends TableName> = RealtimePostgresChangesPayload<Database['public']['Tables'][T]['Row']>

// Callbacks para diferentes eventos
export type RealtimeCallback<T extends TableName> = {
  onInsert?: (payload: RealtimePayload<T>) => void
  onUpdate?: (payload: RealtimePayload<T>) => void
  onDelete?: (payload: RealtimePayload<T>) => void
  onAny?: (payload: RealtimePayload<T>) => void
}

// Classe para gerenciar subscriptions em tempo real
export class RealtimeManager {
  private channels: Map<string, RealtimeChannel> = new Map()

  // Inscrever em uma tabela
  subscribeToTable<T extends TableName>(
    table: T,
    callbacks: RealtimeCallback<T>,
    filter?: string
  ): string {
    const channelName = `table-${table}-${Date.now()}-${Math.random()}`

    let channel = supabase
      .channel(channelName)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: table,
          filter: filter
        },
        (payload: RealtimePayload<T>) => {
          // Chamar callback específico do evento
          switch (payload.eventType) {
            case 'INSERT':
              callbacks.onInsert?.(payload)
              break
            case 'UPDATE':
              callbacks.onUpdate?.(payload)
              break
            case 'DELETE':
              callbacks.onDelete?.(payload)
              break
          }

          // Chamar callback geral
          callbacks.onAny?.(payload)
        }
      )
      .subscribe()

    this.channels.set(channelName, channel)
    return channelName
  }

  // Inscrever em mudanças de dispositivo específico
  subscribeToDevice(deviceId: string, callbacks: RealtimeCallback<'devices'>): string {
    return this.subscribeToTable('devices', callbacks, `id=eq.${deviceId}`)
  }

  // Inscrever em alertas
  subscribeToAlerts(callbacks: RealtimeCallback<'alerts'>): string {
    return this.subscribeToTable('alerts', callbacks)
  }

  // Inscrever em alertas de um dispositivo específico
  subscribeToDeviceAlerts(deviceId: string, callbacks: RealtimeCallback<'alerts'>): string {
    return this.subscribeToTable('alerts', callbacks, `device_id=eq.${deviceId}`)
  }

  // Inscrever em mudanças de perfil
  subscribeToProfile(userId: string, callbacks: RealtimeCallback<'profiles'>): string {
    return this.subscribeToTable('profiles', callbacks, `id=eq.${userId}`)
  }

  // Cancelar inscrição
  unsubscribe(channelName: string): void {
    const channel = this.channels.get(channelName)
    if (channel) {
      supabase.removeChannel(channel)
      this.channels.delete(channelName)
    }
  }

  // Cancelar todas as inscrições
  unsubscribeAll(): void {
    for (const [channelName, channel] of this.channels) {
      supabase.removeChannel(channel)
    }
    this.channels.clear()
  }

  // Verificar status da conexão
  isConnected(): boolean {
    return supabase.realtime.isConnected()
  }

  // Obter lista de canais ativos
  getActiveChannels(): string[] {
    return Array.from(this.channels.keys())
  }
}

// Instância singleton
export const realtimeManager = new RealtimeManager()

// Hooks/utilities para SolidJS
export const createRealtimeSubscription = <T extends TableName>(
  table: T,
  callbacks: RealtimeCallback<T>,
  filter?: string
) => {
  let channelName: string | null = null

  const subscribe = () => {
    if (!channelName) {
      channelName = realtimeManager.subscribeToTable(table, callbacks, filter)
    }
  }

  const unsubscribe = () => {
    if (channelName) {
      realtimeManager.unsubscribe(channelName)
      channelName = null
    }
  }

  // Cleanup automático
  const cleanup = () => unsubscribe()

  return { subscribe, unsubscribe, cleanup }
}

// Utilitários para presence (usuários online)
export const createPresenceChannel = async (channelName: string) => {
  const { data: { user } } = await supabase.auth.getUser()
  const channel = supabase.channel(channelName, {
    config: {
      presence: {
        key: user?.id || 'anonymous'
      }
    }
  })

  return {
    subscribe: () => channel.subscribe(),
    track: (state: any) => channel.track(state),
    untrack: () => channel.untrack(),
    onSync: (callback: () => void) => channel.on('presence', { event: 'sync' }, callback),
    onJoin: (callback: (key: string, currentPresence: any, newPresence: any) => void) =>
      channel.on('presence', { event: 'join' }, ({ key, currentPresences, newPresences }) =>
        callback(key, currentPresences, newPresences)),
    onLeave: (callback: (key: string, currentPresence: any, leftPresence: any) => void) =>
      channel.on('presence', { event: 'leave' }, ({ key, currentPresences, leftPresences }) =>
        callback(key, currentPresences, leftPresences)),
    unsubscribe: () => supabase.removeChannel(channel)
  }
}
