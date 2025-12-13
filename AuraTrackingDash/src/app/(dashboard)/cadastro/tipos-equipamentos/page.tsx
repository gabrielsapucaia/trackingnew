"use client"

import { useEffect, useMemo, useState } from "react"
import {
  Wrench,
  Loader2,
  AlertCircle,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Plus,
  Edit,
  Trash2,
  Hash,
  Info,
} from "lucide-react"
import {
  getTiposEquipamentos,
  addTipoEquipamento,
  updateTipoEquipamento,
  deleteTipoEquipamento,
  type TipoEquipamento,
} from "@/services/tiposEquipamentos"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
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
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"

type SortColumn = keyof TipoEquipamento | "seq_id"

export default function TiposEquipamentosPage() {
  const [tipos, setTipos] = useState<TipoEquipamento[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updating, setUpdating] = useState<Set<number>>(new Set())
  const [sortColumn, setSortColumn] = useState<SortColumn | null>("seq_id")
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc")
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [editing, setEditing] = useState<TipoEquipamento | null>(null)
  const [deleting, setDeleting] = useState<TipoEquipamento | null>(null)
  const [form, setForm] = useState<Omit<TipoEquipamento, "id" | "created_at" | "updated_at">>({
    name: "",
    description: "",
    seq_id: undefined,
    status: "active",
  })

  const fetchTipos = async () => {
    try {
      setLoading(true)
      setError(null)
      const { data, error } = await getTiposEquipamentos()
      if (error) throw error
      setTipos(data || [])
    } catch (err) {
      console.error("Erro ao buscar tipos de equipamentos:", err)
      setError(err instanceof Error ? err.message : "Erro desconhecido")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTipos()
  }, [])

  const toggleStatus = async (id: number, status: string | null | undefined) => {
    const newStatus = status === "active" ? "inactive" : "active"
    setUpdating((prev) => new Set([...prev, id]))
    try {
      const { data, error } = await updateTipoEquipamento(id, { status: newStatus })
      if (error) throw error
      setTipos((prev) => prev.map((t) => (t.id === id ? { ...t, status: data?.status ?? newStatus } : t)))
    } catch (err) {
      console.error("Erro ao atualizar status:", err)
      setError(err instanceof Error ? err.message : "Erro ao atualizar status")
    } finally {
      setUpdating((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"))
    } else {
      setSortColumn(column)
      setSortDirection("asc")
    }
  }

  const sortedTipos = useMemo(() => {
    if (!sortColumn) return tipos
    return [...tipos].sort((a, b) => {
      const aVal = (a as any)[sortColumn]
      const bVal = (b as any)[sortColumn]
      if (aVal == null && bVal == null) return 0
      if (aVal == null) return 1
      if (bVal == null) return -1
      const aStr = String(aVal).toLowerCase()
      const bStr = String(bVal).toLowerCase()
      if (sortDirection === "asc") return aStr < bStr ? -1 : aStr > bStr ? 1 : 0
      return aStr > bStr ? -1 : aStr < bStr ? 1 : 0
    })
  }, [tipos, sortColumn, sortDirection])

  const getSortIcon = (column: SortColumn) => {
    if (sortColumn !== column) return <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
    return sortDirection === "asc" ? (
      <ArrowUp className="h-4 w-4 text-primary" />
    ) : (
      <ArrowDown className="h-4 w-4 text-primary" />
    )
  }

  const getSortableHeader = (column: SortColumn, label: string) => (
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

  const handleAdd = async () => {
    try {
      setError(null)
      const { data, error } = await addTipoEquipamento(form)
      if (error) throw error
      if (data) setTipos((prev) => [...prev, data])
      setIsAddDialogOpen(false)
      setForm({ name: "", description: "", seq_id: undefined, status: "active" })
    } catch (err) {
      console.error("Erro ao adicionar tipo:", err)
      setError(err instanceof Error ? err.message : "Erro ao adicionar tipo")
    }
  }

  const handleEdit = async () => {
    if (!editing?.id) return
    try {
      setUpdating((prev) => new Set([...prev, editing.id]))
      const { error, data } = await updateTipoEquipamento(editing.id, {
        name: editing.name,
        description: editing.description,
        status: editing.status,
        seq_id: editing.seq_id,
      })
      if (error) throw error
      setTipos((prev) => prev.map((t) => (t.id === editing.id ? { ...t, ...editing, ...data } : t)))
      setIsEditDialogOpen(false)
      setEditing(null)
    } catch (err) {
      console.error("Erro ao salvar tipo:", err)
      setError(err instanceof Error ? err.message : "Erro ao salvar tipo")
    } finally {
      setUpdating((prev) => {
        const next = new Set(prev)
        if (editing?.id) next.delete(editing.id)
        return next
      })
    }
  }

  const handleDelete = async () => {
    if (!deleting?.id) return
    try {
      setUpdating((prev) => new Set([...prev, deleting.id]))
      const { error } = await deleteTipoEquipamento(deleting.id)
      if (error) throw error
      setTipos((prev) => prev.filter((t) => t.id !== deleting.id))
      setIsDeleteDialogOpen(false)
      setDeleting(null)
    } catch (err) {
      console.error("Erro ao excluir tipo:", err)
      setError(err instanceof Error ? err.message : "Erro ao excluir tipo")
    } finally {
      setUpdating((prev) => {
        const next = new Set(prev)
        if (deleting?.id) next.delete(deleting.id)
        return next
      })
    }
  }

  const formatDate = (dateString?: string | null) => {
    if (!dateString) return "-"
    return new Date(dateString).toLocaleDateString("pt-BR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  const statusBadge = (tipo: TipoEquipamento) => {
    const status = tipo.status || "pending"
    const isUpdating = updating.has(tipo.id)
    const statusMap: Record<string, { label: string; className: string }> = {
      active: {
        label: "Ativo",
        className: "bg-green-500/10 text-green-700 border border-green-300 cursor-pointer hover:bg-green-500/20",
      },
      inactive: {
        label: "Inativo",
        className: "bg-destructive/10 text-destructive border border-destructive/20 cursor-pointer hover:bg-destructive/20",
      },
      pending: { label: "Pendente", className: "bg-yellow-50 text-yellow-700 border border-yellow-200 cursor-pointer hover:bg-yellow-100" },
    }
    const statusInfo = statusMap[status.toLowerCase()] || { label: status, className: "bg-muted text-muted-foreground cursor-not-allowed" }
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
        onClick={() => toggleStatus(tipo.id, status)}
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
          <Wrench className="h-6 w-6" />
          <h1 className="text-3xl font-bold">Tipos de Equipamento</h1>
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
          <Wrench className="h-6 w-6" />
          <h1 className="text-3xl font-bold">Tipos de Equipamento</h1>
        </div>
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
          <div className="flex items-center space-x-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span className="font-medium">Erro ao carregar tipos</span>
          </div>
          <p className="text-muted-foreground mt-2">{error}</p>
          <Button onClick={fetchTipos} variant="outline" className="mt-4" size="sm">
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
          <Wrench className="h-6 w-6" />
          <h1 className="text-3xl font-bold">Tipos de Equipamento</h1>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="h-4 w-4 mr-2" />
              Adicionar Tipo
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[460px]">
            <DialogHeader>
              <DialogTitle>Novo Tipo de Equipamento</DialogTitle>
              <DialogDescription>Cadastre um tipo para relacionar aos equipamentos.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="name" className="text-right">
                  Nome
                </Label>
                <Input
                  id="name"
                  value={form.name}
                  onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="description" className="text-right">
                  Descrição
                </Label>
                <Input
                  id="description"
                  value={form.description ?? ""}
                  onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="seq" className="text-right">
                  Sequência
                </Label>
                <Input
                  id="seq"
                  type="number"
                  value={form.seq_id ?? ""}
                  onChange={(e) => setForm((prev) => ({ ...prev, seq_id: e.target.value ? Number(e.target.value) : undefined }))}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="status" className="text-right">
                  Status
                </Label>
                <Select value={form.status || ""} onValueChange={(value) => setForm((prev) => ({ ...prev, status: value }))}>
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
              <Button onClick={handleAdd}>Salvar</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {tipos.length === 0 ? (
        <div className="text-center py-12">
          <Wrench className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium text-card-foreground mb-2">Nenhum tipo cadastrado</h3>
          <p className="text-muted-foreground">Cadastre o primeiro tipo de equipamento para começar.</p>
        </div>
      ) : (
        <div className="bg-card rounded-lg shadow overflow-hidden border">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-muted/50">
                <tr>
                  {getSortableHeader("status", "Status")}
                  {getSortableHeader("seq_id", "Seq")}
                  {getSortableHeader("name", "Nome")}
                  {getSortableHeader("description", "Descrição")}
                  {getSortableHeader("created_at", "Criado em")}
                  {getSortableHeader("updated_at", "Atualizado em")}
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Ações</th>
                </tr>
              </thead>
              <tbody className="bg-card divide-y divide-border">
                {sortedTipos.map((tipo) => (
                  <tr key={tipo.id} className="hover:bg-accent transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">{statusBadge(tipo)}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground font-mono">
                        <Hash className="h-4 w-4 opacity-60" />
                        {tipo.seq_id ?? "-"}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-card-foreground">{tipo.name || "-"}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground max-w-sm">
                        <Info className="h-4 w-4 opacity-60" />
                        <span className="truncate">{tipo.description || "-"}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground">{formatDate(tipo.created_at)}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground">{formatDate(tipo.updated_at)}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => {
                            setEditing({ ...tipo })
                            setIsEditDialogOpen(true)
                          }}
                          title="Editar tipo"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="destructive"
                          size="icon"
                          onClick={() => {
                            setDeleting(tipo)
                            setIsDeleteDialogOpen(true)
                          }}
                          title="Excluir tipo"
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

      <div className="text-sm text-muted-foreground">Total de tipos: {tipos.length}</div>

      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="sm:max-w-[460px]">
          <DialogHeader>
            <DialogTitle>Editar Tipo</DialogTitle>
            <DialogDescription>Atualize as informações do tipo de equipamento.</DialogDescription>
          </DialogHeader>
          {editing && (
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="edit-name" className="text-right">
                  Nome
                </Label>
                <Input
                  id="edit-name"
                  value={editing.name || ""}
                  onChange={(e) => setEditing((prev) => (prev ? { ...prev, name: e.target.value } : prev))}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="edit-description" className="text-right">
                  Descrição
                </Label>
                <Input
                  id="edit-description"
                  value={editing.description ?? ""}
                  onChange={(e) => setEditing((prev) => (prev ? { ...prev, description: e.target.value } : prev))}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="edit-seq" className="text-right">
                  Sequência
                </Label>
                <Input
                  id="edit-seq"
                  type="number"
                  value={editing.seq_id ?? ""}
                  onChange={(e) => setEditing((prev) => (prev ? { ...prev, seq_id: e.target.value ? Number(e.target.value) : undefined } : prev))}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="edit-status" className="text-right">
                  Status
                </Label>
                <Select
                  value={editing.status || ""}
                  onValueChange={(value) => setEditing((prev) => (prev ? { ...prev, status: value } : prev))}
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
            <Button onClick={handleEdit}>Salvar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Confirmar Exclusão</DialogTitle>
            <DialogDescription>Esta ação não pode ser desfeita.</DialogDescription>
          </DialogHeader>
          {deleting && (
            <div className="grid gap-2 py-4">
              <div className="flex items-center gap-2">
                <Label className="font-medium">Nome:</Label>
                <span>{deleting.name}</span>
              </div>
              <div className="flex items-center gap-2">
                <Label className="font-medium">Descrição:</Label>
                <span>{deleting.description || "-"}</span>
              </div>
            </div>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" onClick={() => setDeleting(null)}>
                Cancelar
              </Button>
            </DialogClose>
            <Button variant="destructive" onClick={handleDelete}>
              Confirmar Exclusão
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
