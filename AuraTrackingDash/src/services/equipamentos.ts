import { supabase } from '@/lib/supabase/client'

interface Equipamento {
  id: number
  tag: string
  type_id: number
  status?: string
  location?: string
  created_at?: string
  updated_at?: string
}

interface EquipmentType {
  id: number
  name: string
  description?: string
}

export const getEquipamentos = async () => {
  const { data, error } = await supabase
    .from('equipment')
    .select(`
      *,
      equipment_types (
        id,
        name,
        description
      )
    `)
    .order('created_at', { ascending: false })

  if (error) {
    console.error('Error fetching equipamentos:', error)
    return { data: [], error }
  }

  return { data, error }
}

export const getEquipmentTypes = async (): Promise<{ data: EquipmentType[] | null, error: any }> => {
  const { data, error } = await supabase
    .from('equipment_types')
    .select('id, name, description')
    .eq('status', 'active')
    .order('name')

  if (error) {
    console.error('Error fetching equipment types:', error)
    return { data: [], error }
  }

  return { data, error }
}

export const addEquipamento = async (equipamento: Omit<Equipamento, 'id' | 'created_at' | 'updated_at'>) => {
  const { data, error } = await supabase
    .from('equipment')
    .insert([{ ...equipamento, created_at: new Date().toISOString(), updated_at: new Date().toISOString() }])
    .select(`
      *,
      equipment_types (
        id,
        name,
        description
      )
    `)

  if (error) {
    console.error('Error adding equipamento:', error)
    return { data: null, error }
  }

  return { data: data[0], error: null }
}

export const updateEquipamento = async (id: number, updates: Partial<Omit<Equipamento, 'id' | 'created_at'>>) => {
  const { data, error } = await supabase
    .from('equipment')
    .update({ ...updates, updated_at: new Date().toISOString() })
    .eq('id', id)
    .select(`
      *,
      equipment_types (
        id,
        name,
        description
      )
    `)

  if (error) {
    console.error('Error updating equipamento:', error)
    return { data: null, error }
  }

  return { data: data[0], error: null }
}

export const deleteEquipamento = async (id: number) => {
  const { error } = await supabase
    .from('equipment')
    .delete()
    .eq('id', id)

  if (error) {
    console.error('Error deleting equipamento:', error)
    return { success: false, error }
  }

  return { success: true, error: null }
}

export const getEquipamentosTableStructure = async () => {
  const { data, error } = await supabase
    .from('equipment')
    .select('*')
    .limit(1)

  return { data, error }
}