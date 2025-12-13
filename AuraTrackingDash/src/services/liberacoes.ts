export interface Liberacao {
  id: number
  quota: number
  sequence: number
  material_type_id: number
  planned_mass: number
  model_grade: number
  planned_grade: number
  status?: string | null
  created_at?: string | null
  updated_at?: string | null
  material_types?: {
    id: number
    name: string
    description?: string | null
    status?: string | null
  }
}

export interface MaterialType {
  id: number
  name: string
  description?: string | null
  status?: string | null
}

export const getLiberacoes = async () => {
  const res = await fetch("/api/liberacoes")
  if (!res.ok) {
    const { error } = await res.json()
    console.error("Erro ao buscar liberacoes:", error)
    return { data: [], error }
  }
  const { data } = (await res.json()) as { data: Liberacao[] }
  return { data, error: null }
}

export const getMaterialTypes = async () => {
  const res = await fetch("/api/material-types")
  if (!res.ok) {
    const { error } = await res.json()
    console.error("Erro ao buscar tipos de material:", error)
    return { data: [], error }
  }
  const { data } = (await res.json()) as { data: MaterialType[] }
  return { data, error: null }
}

export const addLiberacao = async (
  liberacao: Omit<Liberacao, "id" | "created_at" | "updated_at" | "material_types">
) => {
  const res = await fetch("/api/liberacoes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(liberacao),
  })
  const body = await res.json()
  if (!res.ok) {
    console.error("Erro ao adicionar liberacao:", body.error)
    return { data: null, error: body.error }
  }
  return { data: body.data as Liberacao, error: null }
}

export const updateLiberacao = async (
  id: number,
  updates: Partial<Omit<Liberacao, "id" | "created_at" | "material_types">>
) => {
  const res = await fetch("/api/liberacoes", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, ...updates }),
  })
  const body = await res.json()
  if (!res.ok) {
    console.error("Erro ao atualizar liberacao:", body.error)
    return { data: null, error: body.error }
  }
  return { data: body.data as Liberacao, error: null }
}

export const deleteLiberacao = async (id: number) => {
  const res = await fetch(`/api/liberacoes?id=${id}`, { method: "DELETE" })
  const body = await res.json()
  if (!res.ok) {
    console.error("Erro ao excluir liberacao:", body.error)
    return { success: false, error: body.error }
  }
  return { success: true, error: null }
}
