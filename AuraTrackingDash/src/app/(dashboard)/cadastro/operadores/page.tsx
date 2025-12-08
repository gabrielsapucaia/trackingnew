"use client"

import { useState, useEffect } from "react"
import { Users, Loader2, AlertCircle, ArrowUpDown, ArrowUp, ArrowDown, Plus, Edit, Trash2 } from "lucide-react"
import { getOperadores } from "@/services/operadores"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { supabase } from "@/lib/supabase/client"
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select"

interface Operador {
  id: string
  name: string
  pin?: string
  status?: string
  registration?: string
  created_at?: string
  updated_at?: string
}

export default function OperadoresPage() {
  const [operadores, setOperadores] = useState<Operador[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updatingOperators, setUpdatingOperators] = useState<Set<string>>(new Set())
  const [sortColumn, setSortColumn] = useState<keyof Operador | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [editingOperator, setEditingOperator] = useState<Operador | null>(null)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false) // New state for delete dialog
  const [deletingOperator, setDeletingOperator] = useState<Operador | null>(null) // New state for operator to be deleted

  const fetchOperadores = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const { data, error } = await getOperadores()
      
      if (error) {
        throw error
      }
      
      setOperadores(data || [])
    } catch (err) {
      console.error('Erro ao buscar operadores:', err)
      setError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setLoading(false)
    }
  }

  const toggleOperatorStatus = async (operatorId: string, currentStatus: string) => {
    const newStatus = currentStatus === 'active' ? 'inactive' : 'active'
    
    // Add to updating set
    setUpdatingOperators(prev => new Set([...prev, operatorId]))
    
    try {
      const { error } = await supabase
        .from('operators')
        .update({ 
          status: newStatus,
          updated_at: new Date().toISOString()
        })
        .eq('id', operatorId)
      
      if (error) {
        throw error
      }
      
      // Update local state
      setOperadores(prev => prev.map(op => 
        op.id === operatorId 
          ? { ...op, status: newStatus, updated_at: new Date().toISOString() }
          : op
      ))
    } catch (err) {
      console.error('Erro ao atualizar status:', err)
      setError(err instanceof Error ? err.message : 'Erro ao atualizar status')
    } finally {
      // Remove from updating set
      setUpdatingOperators(prev => {
        const newSet = new Set(prev)
        newSet.delete(operatorId)
        return newSet
      })
    }
  }

  const handleSort = (column: keyof Operador) => {
    if (sortColumn === column) {
      // Toggle direction if same column
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      // Set new column and default to ascending
      setSortColumn(column)
      setSortDirection('asc')
    }
  }

  const getSortedOperadores = () => {
    if (!sortColumn) return operadores

    return [...operadores].sort((a, b) => {
      const aValue = a[sortColumn]
      const bValue = b[sortColumn]

      // Handle null/undefined values
      if (!aValue && !bValue) return 0
      if (!aValue) return 1
      if (!bValue) return -1

      // Convert to string for comparison
      const aStr = String(aValue).toLowerCase()
      const bStr = String(bValue).toLowerCase()

      if (sortDirection === 'asc') {
        return aStr < bStr ? -1 : aStr > bStr ? 1 : 0
      } else {
        return aStr > bStr ? -1 : aStr < bStr ? 1 : 0
      }
    })
  }

  const getSortIcon = (column: keyof Operador) => {
    if (sortColumn !== column) {
      return <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
    }
    return sortDirection === 'asc' 
      ? <ArrowUp className="h-4 w-4 text-primary" />
      : <ArrowDown className="h-4 w-4 text-primary" />
  }

  const getSortableHeader = (column: keyof Operador, label: string) => (
    <th 
      className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-muted/80 transition-colors select-none"
      onClick={() => handleSort(column)}
    >
      <div className="flex items-center gap-2">
        {label}
        {getSortIcon(column)}
      </div>
    </th>
  )

  useEffect(() => {
    fetchOperadores()
  }, [])

  const handleEditClick = (operador: Operador) => {
    setEditingOperator({ ...operador }) // Create a copy to edit
    setIsEditDialogOpen(true)
  }

  const handleSaveEdit = async () => {
    if (!editingOperator || !editingOperator.id) {
      console.error("Nenhum operador selecionado para edição ou ID ausente.")
      return
    }

    try {
      setUpdatingOperators(prev => new Set([...prev, editingOperator.id!]))

      const { id, name, pin, status, registration } = editingOperator
      const { error } = await supabase
        .from('operators')
        .update({
          name: name,
          pin: pin,
          status: status,
          registration: registration,
          updated_at: new Date().toISOString(),
        })
        .eq('id', id)

      if (error) {
        throw error
      }

      setOperadores(prev => prev.map(op =>
        op.id === id
          ? { ...op, ...editingOperator, updated_at: new Date().toISOString() }
          : op
      ))

      setIsEditDialogOpen(false)
      setEditingOperator(null)
    } catch (err) {
      console.error('Erro ao salvar edições do operador:', err)
      setError(err instanceof Error ? err.message : 'Erro ao salvar edições do operador')
    } finally {
      setUpdatingOperators(prev => {
        const newSet = new Set(prev)
        newSet.delete(editingOperator.id!)
        return newSet
      })
    }
  }

  // New functions for delete confirmation modal
  const handleDeleteClick = (operador: Operador) => {
    setDeletingOperator(operador)
    setIsDeleteDialogOpen(true)
  }

  const handleConfirmDelete = async () => {
    if (!deletingOperator || !deletingOperator.id) {
      console.error("Nenhum operador selecionado para exclusão ou ID ausente.")
      return
    }

    try {
      setUpdatingOperators(prev => new Set([...prev, deletingOperator.id!]))

      const { error } = await supabase
        .from('operators')
        .delete()
        .eq('id', deletingOperator.id)

      if (error) {
        throw error
      }

      // Remove o operador do estado local
      setOperadores(prev => prev.filter(op => op.id !== deletingOperator.id))

      // Fecha o modal e limpa o operador em exclusão
      setIsDeleteDialogOpen(false)
      setDeletingOperator(null)
    } catch (err) {
      console.error('Erro ao excluir operador:', err)
      setError(err instanceof Error ? err.message : 'Erro ao excluir operador')
    } finally {
      setUpdatingOperators(prev => {
        const newSet = new Set(prev)
        newSet.delete(deletingOperator.id!)
        return newSet
      })
    }
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return '-'
    return new Date(dateString).toLocaleDateString('pt-BR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getStatusBadge = (operador: Operador) => {
    const status = operador.status || 'pending'
    const isUpdating = updatingOperators.has(operador.id)
    
    const statusMap: Record<string, { label: string; className: string }> = {
      'active': { label: 'Ativo', className: 'bg-green-500/10 text-green-700 border border-green-300 cursor-pointer hover:bg-green-500/20' },
      'inactive': { label: 'Inativo', className: 'bg-destructive/10 text-destructive border border-destructive/20 cursor-pointer hover:bg-destructive/20' },
      'pending': { label: 'Pendente', className: 'bg-yellow-50 text-yellow-700 border border-yellow-200 cursor-pointer hover:bg-yellow-100' }
    }
    
    const statusInfo = statusMap[status.toLowerCase()] || { 
      label: status, 
      className: 'bg-muted text-muted-foreground cursor-not-allowed' 
    }
    
    if (isUpdating) {
      return (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusInfo.className} flex items-center gap-1`}>
          <Loader2 className="h-3 w-3 animate-spin" />
          Alterando...
        </span>
      )
    }
    
    return (
      <button
        onClick={() => toggleOperatorStatus(operador.id, status)}
        className={`px-2 py-1 rounded-full text-xs font-medium ${statusInfo.className} transition-colors`}
        disabled={isUpdating}
        title={`Clique para alterar status de ${statusInfo.label.toLowerCase()}`}
      >
        {statusInfo.label}
      </button>
    )
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center space-x-2">
          <Users className="h-6 w-6" />
          <h1 className="text-3xl font-bold">Operadores</h1>
        </div>
        
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center space-x-2">
          <Users className="h-6 w-6" />
          <h1 className="text-3xl font-bold">Operadores</h1>
        </div>
        
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
          <div className="flex items-center space-x-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span className="font-medium">Erro ao carregar operadores</span>
          </div>
          <p className="text-muted-foreground mt-2">{error}</p>
          <Button 
            onClick={fetchOperadores} 
            variant="outline" 
            className="mt-4"
            size="sm"
          >
            Tentar novamente
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Users className="h-6 w-6" />
          <h1 className="text-3xl font-bold">Operadores</h1>
        </div>
        
        <div className="flex items-center gap-2">
          <Button size="sm">
            <Plus className="h-4 w-4 mr-2" />
            Adicionar Operador
          </Button>
        </div>
      </div>

      {operadores.length === 0 ? (
        <div className="text-center py-12">
          <Users className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium text-card-foreground mb-2">
            Nenhum operador encontrado
          </h3>
          <p className="text-muted-foreground">
            A tabela de operadores está vazia ou ainda não há dados cadastrados.
          </p>
        </div>
      ) : (
        <div className="bg-card rounded-lg shadow overflow-hidden border">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-muted/50">
                <tr>
                  {getSortableHeader('status', 'Status')}
                  {getSortableHeader('registration', 'Registro')}
                  {getSortableHeader('name', 'Nome')}
                  {getSortableHeader('pin', 'PIN')}
                  {getSortableHeader('created_at', 'Data de Criação')}
                  {getSortableHeader('updated_at', 'Data de Modificação')}
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Ações</th>
                </tr>
              </thead>
              <tbody className="bg-card divide-y divide-border">
                {getSortedOperadores().map((operador) => (
                  <tr key={operador.id} className="hover:bg-accent transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getStatusBadge(operador)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground font-mono">
                        {operador.registration || operador.id}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-card-foreground">
                        {operador.name || '-'}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground font-mono">
                        {operador.pin || '-'}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground">
                        {formatDate(operador.created_at)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground">
                        {formatDate(operador.updated_at)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => handleEditClick(operador)}
                          title="Editar Operador"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="destructive"
                          size="icon"
                          onClick={() => handleDeleteClick(operador)} // Call new delete handler
                          title="Excluir Operador"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="text-sm text-muted-foreground">
        Total de operadores: {operadores.length}
      </div>

      {/* Edit Operator Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Editar Operador</DialogTitle>
            <DialogDescription>
              Faça as alterações no operador aqui. Clique em salvar quando terminar.
            </DialogDescription>
          </DialogHeader>
          {editingOperator && (
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="name" className="text-right">
                  Nome
                </Label>
                <Input
                  id="name"
                  value={editingOperator.name || ''}
                  onChange={(e) => setEditingOperator(prev => prev ? { ...prev, name: e.target.value } : null)}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="registration" className="text-right">
                  Registro
                </Label>
                <Input
                  id="registration"
                  value={editingOperator.registration || ''}
                  onChange={(e) => setEditingOperator(prev => prev ? { ...prev, registration: e.target.value } : null)}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="pin" className="text-right">
                  PIN
                </Label>
                <Input
                  id="pin"
                  value={editingOperator.pin || ''}
                  onChange={(e) => setEditingOperator(prev => prev ? { ...prev, pin: e.target.value } : null)}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="status" className="text-right">
                  Status
                </Label>
                <Select
                  value={editingOperator.status || ''}
                  onValueChange={(value) => setEditingOperator(prev => prev ? { ...prev, status: value } : null)}
                >
                  <SelectTrigger className="col-span-3">
                    <SelectValue placeholder="Selecione o status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Ativo</SelectItem>
                    <SelectItem value="inactive">Inativo</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancelar</Button>
            </DialogClose>
            <Button type="submit" onClick={handleSaveEdit}>Salvar alterações</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Confirmar Exclusão</DialogTitle>
            <DialogDescription>
              Tem certeza que deseja excluir o operador abaixo? Esta ação não pode ser desfeita.
            </DialogDescription>
          </DialogHeader>
          {deletingOperator && (
            <div className="grid gap-2 py-4">
              <div className="flex items-center gap-2">
                <Label className="font-medium">Registro:</Label>
                <span>{deletingOperator.registration || deletingOperator.id}</span>
              </div>
              <div className="flex items-center gap-2">
                <Label className="font-medium">Nome:</Label>
                <span>{deletingOperator.name || '-'}</span>
              </div>
            </div>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" onClick={() => setDeletingOperator(null)}>Cancelar</Button>
            </DialogClose>
            <Button variant="destructive" onClick={handleConfirmDelete}>
              Confirmar Exclusão
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}