import { createBrowserSupabaseClient } from "@/lib/supabase/clientAuth"

export interface Profile {
  id: string
  email: string
  role: "admin" | "user"
  permission: "view" | "edit"
  status: "pending" | "active" | "blocked"
  created_at?: string
  updated_at?: string
}

const safeJson = async (res: Response) => {
  try {
    return await res.json()
  } catch {
    return null
  }
}

export const getCurrentProfile = async (): Promise<Profile | null> => {
  const supabase = createBrowserSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null
  const { data, error } = await supabase
    .from("profiles")
    .select("*")
    .eq("id", user.id)
    .maybeSingle()
  if (error) {
    console.error("Erro ao buscar perfil:", error.message)
    return null
  }
  return data as Profile | null
}

export const getProfilesAdmin = async (): Promise<{ data: Profile[]; error: any }> => {
  const res = await fetch("/api/profiles")
  const body = await safeJson(res)
  if (!res.ok) {
    return { data: [], error: body?.error || res.statusText || "Erro ao buscar usuários" }
  }
  return { data: body.data as Profile[], error: null }
}

export const createProfileAdmin = async (payload: { email: string; password: string; role?: Profile["role"]; permission?: Profile["permission"]; status?: Profile["status"] }) => {
  const res = await fetch("/api/profiles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  const body = await safeJson(res)
  if (!res.ok) {
    return { data: null, error: body?.error || res.statusText || "Erro ao criar usuário" }
  }
  return { data: body.data as Profile, error: null }
}

export const updateProfileAdmin = async (id: string, updates: Partial<Profile>) => {
  const res = await fetch("/api/profiles", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, ...updates }),
  })
  const body = await safeJson(res)
  if (!res.ok) {
    return { data: null, error: body?.error || res.statusText || "Erro ao atualizar usuário" }
  }
  return { data: body.data as Profile, error: null }
}

export const deleteProfileAdmin = async (id: string) => {
  const res = await fetch(`/api/profiles?id=${id}`, { method: "DELETE" })
  const body = await safeJson(res)
  if (!res.ok) {
    return { success: false, error: body?.error || res.statusText || "Erro ao excluir usuário" }
  }
  return { success: true, error: null }
}
