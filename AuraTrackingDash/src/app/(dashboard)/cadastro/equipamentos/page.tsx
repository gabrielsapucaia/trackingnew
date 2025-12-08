
"use client"

import { useState, useEffect } from "react"
import { HardHat, Loader2, AlertCircle, ArrowUpDown, ArrowUp, ArrowDown, Plus, Edit, Trash2 } from "lucide-react"
import { getEquipamentos, addEquipamento, updateEquipamento, deleteEquipamento, getEquipmentTypes } from "@/services/equipamentos"
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

interface Equipamento {
  id: number
  tag: string
  type_id: number
  status?: string
  location?: string
  created_at?: string
  updated_at?: string
  equipment_types?: {
    id: number
    name: string
    description?: string
  }
}

interface EquipmentType {
  id: number
  name: string
  description?: string
}

export default function EquipamentosPage() {
  const [equipamentos, setEquipamentos] = useState<Equipamento[]>([])
  const [equipmentTypes, setEquipmentTypes] = useState<EquipmentType[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updatingEquipamentos, setUpdatingEquipamentos] = useState<Set<number>>(new Set())
  const [sortColumn, setSortColumn] = useState<keyof Equipamento | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [editingEquipamento, setEditingEquipamento] = useState<Equipamento | null>(null)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [deletingEquipamento, setDeletingEquipamento] = useState<Equipamento | null>(null)
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [newEquipamento, setNewEquipamento] = useState<Omit<Equipamento, 'id' | 'created_at' | 'updated_at' | 'equipment_types'>>({
    tag: '',
    type_id: 0,
    location: '',
    status: 'active',
  })

  const fetchEquipamentos = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const { data, error } = await getEquipamentos()
      
      if (error) {
        throw error
      }
      
      setEquipamentos(data || [])
    } catch (err) {
      console.error('Erro ao buscar equipamentos:', err)
      setError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setLoading(false)
    }
  }

  const fetchEquipmentTypes = async () => {
    try {
      const { data, error } = await getEquipmentTypes()
      
      if (error) {
        throw error
      }
      
      setEquipmentTypes(data || [])
    } catch (err) {
      console.error('Erro ao buscar tipos de equipamentos:', err)
    }
  }

  const toggleEquipamentoStatus = async (equipamentoId: number, currentStatus: string) => {
    const newStatus = currentStatus === 'active' ? 'inactive' : 'active'
    
    setUpdatingEquipamentos(prev => new Set([...prev, equipamentoId]))
    
    try {
      const { error } = await updateEquipamento(equipamentoId, { status: newStatus })
      
      if (error) {
        throw error
      }
      
      setEquipamentos(prev => prev.map(eq => 
        eq.id === equipamentoId 
          ? { ...eq, status: newStatus, updated_at: new Date().toISOString() }
          : eq
      ))
    } catch (err) {
      console.error('Erro ao atualizar status:', err)
      setError(err instanceof Error ? err.message : 'Erro ao atualizar status')
    } finally {
      setUpdatingEquipamentos(prev => {
        const newSet = new Set(prev)
        newSet.delete(equipamentoId)
        return newSet
      })
    }
  }

  const handleSort = (column: keyof Equipamento) => {
    if (sortColumn === column) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortColumn(column)
      setSortDirection('asc')
    }
  }

  const getSortedEquipamentos = () => {
    if (!sortColumn) return equipamentos

    return [...equipamentos].sort((a, b) => {
      const aValue = a[sortColumn]
      const bValue = b[sortColumn]

      if (!aValue && !bValue) return 0
      if (!aValue) return 1
      if (!bValue) return -1

      const aStr = String(aValue).toLowerCase()
      const bStr = String(bValue).toLowerCase()

      if (sortDirection === 'asc') {
        return aStr < bStr ? -1 : aStr > bStr ? 1 : 0
      } else {
        return aStr > bStr ? -1 : aStr < bStr ? 1 : 0
      }
    })
  }

  const getSortIcon = (column: keyof Equipamento) => {
    if (sortColumn !== column) {
      return <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
    }
    return sortDirection === 'asc' 
      ? <ArrowUp className="h-4 w-4 text-primary" />
      : <ArrowDown className="h-4 w-4 text-primary" />
  }

  const getSortableHeader = (column: keyof Equipamento, label: string) => (
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
    fetchEquipamentos()
    fetchEquipmentTypes()
  }, [])

  const handleEditClick = (equipamento: Equipamento) => {
    setEditingEquipamento({ ...equipamento })
    setIsEditDialogOpen(true)
  }

  const handleSaveEdit = async () => {
    if (!editingEquipamento || !editingEquipamento.id) {
      console.error("Nenhum equipamento selecionado para edição ou ID ausente.")
      return
    }

    try {
      setUpdatingEquipamentos(prev => new Set([...prev, editingEquipamento.id]))

      const { id, tag, type_id, status, location } = editingEquipamento
      const { error } = await updateEquipamento(id, { tag, type_id, status, location })

      if (error) {
        throw error
      }

      setEquipamentos(prev => prev.map(eq =>
        eq.id === id
          ? { ...eq, ...editingEquipamento, updated_at: new Date().toISOString() }
          : eq
      ))

      setIsEditDialogOpen(false)
      setEditingEquipamento(null)
    } catch (err) {
      console.error('Erro ao salvar edições do equipamento:', err)
      setError(err instanceof Error ? err.message : 'Erro ao salvar edições do equipamento')
    } finally {
      setUpdatingEquipamentos(prev => {
        const newSet = new Set(prev)
        newSet.delete(editingEquipamento.id)
        return newSet
      })
    }
  }

  const handleDeleteClick = (equipamento: Equipamento) => {
    setDeletingEquipamento(equipamento)
    setIsDeleteDialogOpen(true)
  }

  const handleConfirmDelete = async () => {
    if (!deletingEquipamento || !deletingEquipamento.id) {
      console.error("Nenhum equipamento selecionado para exclusão ou ID ausente.")
      return
    }

    try {
      setUpdatingEquipamentos(prev => new Set([...prev, deletingEquipamento.id]))

      const { error } = await deleteEquipamento(deletingEquipamento.id)

      if (error) {
        throw error
      }

      setEquipamentos(prev => prev.filter(eq => eq.id !== deletingEquipamento.id))

      setIsDeleteDialogOpen(false)
      setDeletingEquipamento(null)
    } catch (err) {
      console.error('Erro ao excluir equipamento:', err)
      setError(err instanceof Error ? err.message : 'Erro ao excluir equipamento')
    } finally {
      setUpdatingEquipamentos(prev => {
        const newSet = new Set(prev)
        newSet.delete(deletingEquipamento.id)
        return newSet
      })
    }
  }

  const handleAddEquipamento = async () => {
    try {
      setLoading(true)
      setError(null)

      const { data, error } = await addEquipamento(newEquipamento)

      if (error) {
        throw error
      }

      setEquipamentos(prev => [...prev, data])
      setIsAddDialogOpen(false)
      setNewEquipamento({ tag: '', type_id: 0, location: '', status: 'active' })
    } catch (err) {
      console.error('Erro ao adicionar equipamento:', err)
      setError(err instanceof Error ? err.message : 'Erro ao adicionar equipamento')
    } finally {
      setLoading(false)
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

  const getStatusBadge = (equipamento: Equipamento) => {
    const status = equipamento.status || 'pending'
    const isUpdating = updatingEquipamentos.has(equipamento.id)
    
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
        onClick={() => toggleEquipamentoStatus(equipamento.id, status)}
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
          <HardHat className="h-6 w-6" />
          <h1 className="text-3xl font-bold">Equipamentos</h1>
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
          <HardHat className="h-6 w-6" />
          <h1 className="text-3xl font-bold">Equipamentos</h1>
        </div>
        
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
          <div className="flex items-center space-x-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span className="font-medium">Erro ao carregar equipamentos</span>
          </div>
          <p className="text-muted-foreground mt-2">{error}</p>
          <Button 
            onClick={fetchEquipamentos} 
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
          <HardHat className="h-6 w-6" />
          <h1 className="text-3xl font-bold">Equipamentos</h1>
        </div>
        
        <div className="flex items-center gap-2">
          <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="h-4 w-4 mr-2" />
                Adicionar Equipamento
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[425px]">
              <DialogHeader>
                <DialogTitle>Adicionar Novo Equipamento</DialogTitle>
                <DialogDescription>
                  Preencha os detalhes do novo equipamento.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="newTag" className="text-right">
                    Tag
                  </Label>
                  <Input
                    id="newTag"
                    value={newEquipamento.tag}
                    onChange={(e) => setNewEquipamento(prev => ({ ...prev, tag: e.target.value }))}
                    className="col-span-3"
                  />
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="newType" className="text-right">
                    Tipo
                  </Label>
                  <Select
                    value={newEquipamento.type_id.toString()}
                    onValueChange={(value) => setNewEquipamento(prev => ({ ...prev, type_id: parseInt(value) }))}
                  >
                    <SelectTrigger className="col-span-3">
                      <SelectValue placeholder="Selecione o tipo" />
                    </SelectTrigger>
                    <SelectContent>
                      {equipmentTypes.map((type) => (
                        <SelectItem key={type.id} value={type.id.toString()}>
                          {type.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="newLocation" className="text-right">
                    Localização
                  </Label>
                  <Input
                    id="newLocation"
                    value={newEquipamento.location || ''}
                    onChange={(e) => setNewEquipamento(prev => ({ ...prev, location: e.target.value }))}
                    className="col-span-3"
                  />
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="newStatus" className="text-right">
                    Status
                  </Label>
                  <Select
                    value={newEquipamento.status || ''}
                    onValueChange={(value) => setNewEquipamento(prev => ({ ...prev, status: value }))}
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
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline">Cancelar</Button>
                </DialogClose>
                <Button type="submit" onClick={handleAddEquipamento}>Adicionar</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {equipamentos.length === 0 ? (
        <div className="text-center py-12">
          <HardHat className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium text-card-foreground mb-2">
            Nenhum equipamento encontrado
          </h3>
          <p className="text-muted-foreground">
            A tabela de equipamentos está vazia ou ainda não há dados cadastrados.
          </p>
        </div>
      ) : (
        <div className="bg-card rounded-lg shadow overflow-hidden border">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-muted/50">
                <tr>
                  {getSortableHeader('status', 'Status')}
                  {getSortableHeader('tag', 'Tag')}
                  {getSortableHeader('equipment_types.name', 'Tipo')}
                  {getSortableHeader('location', 'Localização')}
                  {getSortableHeader('created_at', 'Data de Criação')}
                  {getSortableHeader('updated_at', 'Data de Modificação')}
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Ações</th>
                </tr>
              </thead>
              <tbody className="bg-card divide-y divide-border">
                {getSortedEquipamentos().map((equipamento) => (
                  <tr key={equipamento.id} className="hover:bg-accent transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getStatusBadge(equipamento)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground font-mono">
                        {equipamento.tag || equipamento.id}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-card-foreground">
                        {equipamento.equipment_types?.name || '-'}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground font-mono">
                        {equipamento.location || '-'}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground">
                        {formatDate(equipamento.created_at)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground">
                        {formatDate(equipamento.updated_at)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => handleEditClick(equipamento)}
                          title="Editar Equipamento"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="destructive"
                          size="icon"
                          onClick={() => handleDeleteClick(equipamento)}
                          title="Excluir Equipamento"
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
        Total de equipamentos: {equipamentos.length}
      </div>

      {/* Edit Equipamento Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Editar Equipamento</DialogTitle>
            <DialogDescription>
              Faça as alterações no equipamento aqui. Clique em salvar quando terminar.
            </DialogDescription>
          </DialogHeader>
          {editingEquipamento && (
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="tag" className="text-right">
                  Tag
                </Label>
                <Input
                  id="tag"
                  value={editingEquipamento.tag || ''}
                  onChange={(e) => setEditingEquipamento(prev => prev ? { ...prev, tag: e.target.value } : null)}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="type" className="text-right">
                  Tipo
                </Label>
                <Select
                  value={editingEquipamento.type_id.toString()}
                  onValueChange={(value) => setEditingEquipamento(prev => prev ? { ...prev, type_id: parseInt(value) } : null)}
                >
                  <SelectTrigger className="col-span-3">
                    <SelectValue placeholder="Selecione o tipo" />
                  </SelectTrigger>
                  <SelectContent>
                    {equipmentTypes.map((type) => (
                      <SelectItem key={type.id} value={type.id.toString()}>
                        {type.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="location" className="text-right">
                  Localização
                </Label>
                <Input
                  id="location"
                  value={editingEquipamento.location || ''}
                  onChange={(e) => setEditingEquipamento(prev => prev ? { ...prev, location: e.target.value } : null)}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="status" className="text-right">
                  Status
                </Label>
                <Select
                  value={editingEquipamento.status || ''}
                  onValueChange={(value) => setEditingEquipamento(prev => prev ? { ...prev, status: value } : null)}
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
              Tem certeza que deseja excluir o equipamento abaixo? Esta ação não pode ser desfeita.
            </DialogDescription>
          </DialogHeader>
          {deletingEquipamento && (
            <div className="grid gap-2 py-4">
              <div className="flex items-center gap-2">
                <Label className="font-medium">Tag:</Label>
                <span>{deletingEquipamento.tag || deletingEquipamento.id}</span>
              </div>
              <div className="flex items-center gap-2">
                <Label className="font-medium">Tipo:</Label>
                <span>{deletingEquipamento.equipment_types?.name || '-'}</span>
              </div>
              <div className="flex items-center gap-2">
                <Label className="font-medium">Localização:</Label>
                <span>{deletingEquipamento.location || '-'}</span>
              </div>
            </div>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" onClick={() => setDeletingEquipamento(null)}>Cancelar</Button>
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
