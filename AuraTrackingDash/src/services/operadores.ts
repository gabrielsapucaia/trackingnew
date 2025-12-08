import { supabase } from '@/lib/supabase/client'

// Get all operators (read-only)
export const getOperadores = async () => {
  const { data, error } = await supabase
    .from('operators')
    .select('*')
    .order('created_at', { ascending: false })

  if (error) {
    console.error('Error fetching operadores:', error)
    return { data: [], error }
  }

  return { data, error }
}

// Get table structure (for initial discovery)
export const getOperadoresTableStructure = async () => {
  const { data, error } = await supabase
    .from('operators')
    .select('*')
    .limit(1)

  return { data, error }
}