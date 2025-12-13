import { supabase } from "@/lib/supabase/client"

export interface TipoEquipamento {
  id: number
  name: string
  description?: string | null
  seq_id?: number | null
  status?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export const getTiposEquipamentos = async () => {
  const { data, error } = await supabase
    .from("equipment_types")
    .select("*")
    .order("seq_id", { ascending: true })
    .order("name", { ascending: true })

  if (error) {
    console.error("Erro ao buscar tipos de equipamentos:", error)
    return { data: [], error }
  }

  return { data, error }
}

export const addTipoEquipamento = async (tipo: Omit<TipoEquipamento, "id" | "created_at" | "updated_at">) => {
  const { data, error } = await supabase
    .from("equipment_types")
    .insert([{ ...tipo, created_at: new Date().toISOString(), updated_at: new Date().toISOString() }])
    .select()
    .single()

  if (error) {
    console.error("Erro ao adicionar tipo de equipamento:", error)
    return { data: null, error }
  }

  return { data, error: null }
}

export const updateTipoEquipamento = async (
  id: number,
  updates: Partial<Omit<TipoEquipamento, "id" | "created_at">>
) => {
  const { data, error } = await supabase
    .from("equipment_types")
    .update({ ...updates, updated_at: new Date().toISOString() })
    .eq("id", id)
    .select()
    .single()

  if (error) {
    console.error("Erro ao atualizar tipo de equipamento:", error)
    return { data: null, error }
  }

  return { data, error: null }
}

export const deleteTipoEquipamento = async (id: number) => {
  const { error } = await supabase.from("equipment_types").delete().eq("id", id)

  if (error) {
    console.error("Erro ao excluir tipo de equipamento:", error)
    return { success: false, error }
  }

  return { success: true, error: null }
}
