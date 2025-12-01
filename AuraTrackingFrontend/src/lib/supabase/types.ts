/**
 * ============================================================
 * Supabase Database Types
 * ============================================================
 * Tipos TypeScript para as tabelas do Supabase
 * Gerado automaticamente ou definido manualmente
 * ============================================================
 */

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export interface Database {
  public: {
    Tables: {
      // Tabela de health check básica
      health_check: {
        Row: {
          id: number
          created_at: string
          status: string
        }
        Insert: {
          id?: number
          created_at?: string
          status?: string
        }
        Update: {
          id?: number
          created_at?: string
          status?: string
        }
      }

      // Tabela de usuários (profiles)
      profiles: {
        Row: {
          id: string
          email: string
          full_name: string | null
          avatar_url: string | null
          role: 'admin' | 'operator' | 'viewer'
          created_at: string
          updated_at: string
        }
        Insert: {
          id: string
          email: string
          full_name?: string | null
          avatar_url?: string | null
          role?: 'admin' | 'operator' | 'viewer'
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          email?: string
          full_name?: string | null
          avatar_url?: string | null
          role?: 'admin' | 'operator' | 'viewer'
          created_at?: string
          updated_at?: string
        }
      }

      // Tabela de dispositivos (complementar ao TimescaleDB)
      devices: {
        Row: {
          id: string
          device_id: string
          operator_id: string
          name: string | null
          description: string | null
          device_type: string | null
          is_active: boolean
          created_at: string
          updated_at: string
          created_by: string | null
        }
        Insert: {
          id?: string
          device_id: string
          operator_id: string
          name?: string | null
          description?: string | null
          device_type?: string | null
          is_active?: boolean
          created_at?: string
          updated_at?: string
          created_by?: string | null
        }
        Update: {
          id?: string
          device_id?: string
          operator_id?: string
          name?: string | null
          description?: string | null
          device_type?: string | null
          is_active?: boolean
          created_at?: string
          updated_at?: string
          created_by?: string | null
        }
      }

      // Tabela de alertas/configurações
      alerts: {
        Row: {
          id: string
          device_id: string
          alert_type: string
          title: string
          message: string
          severity: 'low' | 'medium' | 'high' | 'critical'
          is_active: boolean
          conditions: Json
          created_at: string
          updated_at: string
          created_by: string
        }
        Insert: {
          id?: string
          device_id: string
          alert_type: string
          title: string
          message: string
          severity?: 'low' | 'medium' | 'high' | 'critical'
          is_active?: boolean
          conditions?: Json
          created_at?: string
          updated_at?: string
          created_by: string
        }
        Update: {
          id?: string
          device_id?: string
          alert_type?: string
          title?: string
          message?: string
          severity?: 'low' | 'medium' | 'high' | 'critical'
          is_active?: boolean
          conditions?: Json
          created_at?: string
          updated_at?: string
          created_by?: string
        }
      }

      // Tabela de logs/auditoria
      audit_logs: {
        Row: {
          id: string
          user_id: string | null
          action: string
          resource_type: string
          resource_id: string | null
          details: Json | null
          ip_address: string | null
          user_agent: string | null
          created_at: string
        }
        Insert: {
          id?: string
          user_id?: string | null
          action: string
          resource_type: string
          resource_id?: string | null
          details?: Json | null
          ip_address?: string | null
          user_agent?: string | null
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string | null
          action?: string
          resource_type?: string
          resource_id?: string | null
          details?: Json | null
          ip_address?: string | null
          user_agent?: string | null
          created_at?: string
        }
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      user_role: 'admin' | 'operator' | 'viewer'
      alert_severity: 'low' | 'medium' | 'high' | 'critical'
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

// Type helpers
export type Tables<T extends keyof Database['public']['Tables']> = Database['public']['Tables'][T]['Row']
export type Enums<T extends keyof Database['public']['Enums']> = Database['public']['Enums'][T]

// Common types for the application
export type Profile = Tables<'profiles'>
export type Device = Tables<'devices'>
export type Alert = Tables<'alerts'>
export type AuditLog = Tables<'audit_logs'>

