export interface TipoMaterial {
  id: number
  name: string
  description?: string | null
  status?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export const getTiposMateriais = async (activeOnly = false) => {
  const query = activeOnly ? "/api/material-types?activeOnly=true" : "/api/material-types?activeOnly=false"
  const res = await fetch(query)
  const body = await res.json()
  if (!res.ok) {
    console.error("Erro ao buscar tipos de materiais:", body.error)
    return { data: [], error: body.error }
  }
  return { data: body.data as TipoMaterial[], error: null }
}

export const addTipoMaterial = async (tipo: Omit<TipoMaterial, "id" | "created_at" | "updated_at">) => {
  const res = await fetch("/api/material-types", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(tipo),
  })
  const body = await res.json()
  if (!res.ok) {
    console.error("Erro ao adicionar tipo de material:", body.error)
    return { data: null, error: body.error }
  }
  return { data: body.data as TipoMaterial, error: null }
}

export const updateTipoMaterial = async (id: number, updates: Partial<Omit<TipoMaterial, "id" | "created_at">>) => {
  const res = await fetch("/api/material-types", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, ...updates }),
  })
  const body = await res.json()
  if (!res.ok) {
    console.error("Erro ao atualizar tipo de material:", body.error)
    return { data: null, error: body.error }
  }
  return { data: body.data as TipoMaterial, error: null }
}

export const deleteTipoMaterial = async (id: number) => {
  const res = await fetch(`/api/material-types?id=${id}`, { method: "DELETE" })
  const body = await res.json()
  if (!res.ok) {
    console.error("Erro ao excluir tipo de material:", body.error)
    return { success: false, error: body.error }
  }
  return { success: true, error: null }
}
