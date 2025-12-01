/**
 * ============================================================
 * Supabase Client Configuration
 * ============================================================
 * Cliente para integração com Supabase (PostgreSQL + Auth + Real-time)
 * ============================================================
 */

import { createClient } from '@supabase/supabase-js'

// TODO: Move these to environment variables (.env file)
// For now, using direct credentials - in production, use VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY
const supabaseUrl = 'https://nucqowewuqeveocmsdnq.supabase.co'
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im51Y3Fvd2V3dXFldmVvY21zZG5xIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjMyODMyMzUsImV4cCI6MjA3ODg1OTIzNX0.uyV_zEE8wgmxzKY61xf6BJyZaXVBbD6nk6NFPUNPYR4'

// Create Supabase client with real-time capabilities
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true
  },
  realtime: {
    params: {
      eventsPerSecond: 10
    }
  }
})

// Service role client for server-side operations (use with caution)
// Only use this for operations that require elevated privileges
export const supabaseAdmin = createClient(supabaseUrl, 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im51Y3Fvd2V3dXFldmVvY21zZG5xIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzI4MzIzNSwiZXhwIjoyMDc4ODU5MjM1fQ.2u1FZbp9G2U8T_P351613K1bcEQNxB8Y6GZA4ucaSqI', {
  auth: {
    autoRefreshToken: false,
    persistSession: false
  }
})

// Helper functions for common operations
export const supabaseHelpers = {
  // Check if user is authenticated
  isAuthenticated: () => {
    return supabase.auth.getUser().then(({ data: { user } }) => !!user)
  },

  // Get current user
  getCurrentUser: () => {
    return supabase.auth.getUser()
  },

  // Sign out
  signOut: () => {
    return supabase.auth.signOut()
  },

  // Health check
  healthCheck: async () => {
    try {
      const { data, error } = await supabase.from('health_check').select('*').limit(1)
      return { healthy: !error, error: error?.message }
    } catch (err) {
      return { healthy: false, error: 'Connection failed' }
    }
  }
}

export default supabase

