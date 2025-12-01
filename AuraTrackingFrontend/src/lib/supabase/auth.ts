/**
 * ============================================================
 * Supabase Authentication Utilities
 * ============================================================
 * Funções utilitárias para autenticação com Supabase
 * ============================================================
 */

import { supabase } from './client'
import type { Profile } from './types'

// Tipos de autenticação
export interface AuthUser {
  id: string
  email: string
  profile?: Profile
}

export interface SignUpData {
  email: string
  password: string
  full_name?: string
}

export interface SignInData {
  email: string
  password: string
}

export interface AuthResponse {
  user: AuthUser | null
  error: string | null
}

// Classe de gerenciamento de autenticação
export class AuthManager {
  // Verificar se usuário está autenticado
  static async isAuthenticated(): Promise<boolean> {
    try {
      const { data: { user } } = await supabase.auth.getUser()
      return !!user
    } catch {
      return false
    }
  }

  // Obter usuário atual com perfil
  static async getCurrentUser(): Promise<AuthUser | null> {
    try {
      const { data: { user }, error } = await supabase.auth.getUser()
      if (error || !user) return null

      // Buscar perfil do usuário
      const { data: profile } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', user.id)
        .single()

      return {
        id: user.id,
        email: user.email!,
        profile: profile || undefined
      }
    } catch {
      return null
    }
  }

  // Login com email e senha
  static async signIn({ email, password }: SignInData): Promise<AuthResponse> {
    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password
      })

      if (error) {
        return { user: null, error: error.message }
      }

      if (!data.user) {
        return { user: null, error: 'Login failed' }
      }

      // Buscar perfil
      const { data: profile } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', data.user.id)
        .single()

      const user: AuthUser = {
        id: data.user.id,
        email: data.user.email!,
        profile: profile || undefined
      }

      return { user, error: null }
    } catch (err) {
      return { user: null, error: 'Unexpected error during sign in' }
    }
  }

  // Registro de novo usuário
  static async signUp({ email, password, full_name }: SignUpData): Promise<AuthResponse> {
    try {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            full_name: full_name || ''
          }
        }
      })

      if (error) {
        return { user: null, error: error.message }
      }

      if (!data.user) {
        return { user: null, error: 'Registration failed' }
      }

      // Criar perfil automaticamente
      if (full_name) {
        await supabase.from('profiles').insert({
          id: data.user.id,
          email: data.user.email!,
          full_name,
          role: 'viewer'
        })
      }

      const user: AuthUser = {
        id: data.user.id,
        email: data.user.email!,
        profile: full_name ? {
          id: data.user.id,
          email: data.user.email!,
          full_name,
          avatar_url: null,
          role: 'viewer',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        } : undefined
      }

      return { user, error: null }
    } catch (err) {
      return { user: null, error: 'Unexpected error during sign up' }
    }
  }

  // Logout
  static async signOut(): Promise<{ error: string | null }> {
    try {
      const { error } = await supabase.auth.signOut()
      return { error: error?.message || null }
    } catch (err) {
      return { error: 'Unexpected error during sign out' }
    }
  }

  // Reset de senha
  static async resetPassword(email: string): Promise<{ error: string | null }> {
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`
      })
      return { error: error?.message || null }
    } catch (err) {
      return { error: 'Unexpected error during password reset' }
    }
  }

  // Atualizar senha
  static async updatePassword(newPassword: string): Promise<{ error: string | null }> {
    try {
      const { error } = await supabase.auth.updateUser({
        password: newPassword
      })
      return { error: error?.message || null }
    } catch (err) {
      return { error: 'Unexpected error during password update' }
    }
  }

  // Atualizar perfil
  static async updateProfile(updates: Partial<Pick<Profile, 'full_name' | 'avatar_url'>>): Promise<{ error: string | null }> {
    try {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) {
        return { error: 'User not authenticated' }
      }

      const { error } = await supabase
        .from('profiles')
        .update({
          ...updates,
          updated_at: new Date().toISOString()
        })
        .eq('id', user.id)

      return { error: error?.message || null }
    } catch (err) {
      return { error: 'Unexpected error during profile update' }
    }
  }

  // Ouvir mudanças de estado de autenticação
  static onAuthStateChange(callback: (user: AuthUser | null) => void) {
    return supabase.auth.onAuthStateChange(async (event, session) => {
      if (event === 'SIGNED_IN' && session?.user) {
        const user: AuthUser = {
          id: session.user.id,
          email: session.user.email!,
          profile: undefined // Será carregado conforme necessário
        }
        callback(user)
      } else if (event === 'SIGNED_OUT') {
        callback(null)
      }
    })
  }
}

// Funções utilitárias de exportação
export const authUtils = {
  isAuthenticated: AuthManager.isAuthenticated,
  getCurrentUser: AuthManager.getCurrentUser,
  signIn: AuthManager.signIn,
  signUp: AuthManager.signUp,
  signOut: AuthManager.signOut,
  resetPassword: AuthManager.resetPassword,
  updatePassword: AuthManager.updatePassword,
  updateProfile: AuthManager.updateProfile,
  onAuthStateChange: AuthManager.onAuthStateChange
}
