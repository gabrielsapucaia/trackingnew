"use client"

import { useEffect, useMemo, useState } from "react"
import {
  Layers,
  Loader2,
  AlertCircle,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Plus,
  Edit,
  Trash2,
  ListOrdered,
} from "lucide-react"
import {
  getLiberacoes,
  addLiberacao,
  updateLiberacao,
  deleteLiberacao,
  getMaterialTypes,
  type Liberacao,
  type MaterialType,
} from "@/services/liberacoes"
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

type SortColumn =
  | "status"
  | "sequence"
  | "quota"
  | "materialTypeName"
  | "planned_mass"
  | "model_grade"
  | "planned_grade"
  | "created_at"
  | "updated_at"

export default function LiberacoesPage() {
  const [liberacoes, setLiberacoes] = useState<Liberacao[]>([])
  const [materialTypes, setMaterialTypes] = useState<MaterialType[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updating, setUpdating] = useState<Set<number>>(new Set())
  const [sortColumn, setSortColumn] = useState<SortColumn | null>("sequence")
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc")
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [editing, setEditing] = useState<Liberacao | null>(null)
  const [deleting, setDeleting] = useState<Liberacao | null>(null)
  const [form, setForm] = useState<Omit<Liberacao, "id" | "created_at" | "updated_at" | "material_types">>({
    quota: 0,
    sequence: 0,
    material_type_id: 0,
    planned_mass: 0,
    model_grade: 0,
    planned_grade: 0,
    status: "active",
  })

  const fetchLiberacoes = async () => {
    try {
      setLoading(true)
      setError(null)
      const { data, error } = await getLiberacoes()
      if (error) throw error
      setLiberacoes(data || [])
    } catch (err) {
      console.error("Erro ao buscar liberacoes:", err)
      setError(err instanceof Error ? err.message : "Erro desconhecido")
    } finally {
      setLoading(false)
    }
  }

  const fetchMaterialTypes = async () => {
    try {
      const { data, error } = await getMaterialTypes()
      if (error) throw error
      setMaterialTypes(data || [])
    } catch (err) {
      console.error("Erro ao buscar tipos de material:", err)
    }
  }

  useEffect(() => {
    fetchLiberacoes()
    fetchMaterialTypes()
  }, [])

  useEffect(() => {
    if (materialTypes.length > 0 && !form.material_type_id) {
      setForm((prev) => ({ ...prev, material_type_id: materialTypes[0].id }))
    }
  }, [materialTypes, form.material_type_id])

  const toggleStatus = async (id: number, current: string | null | undefined) => {
    const newStatus = current === "active" ? "inactive" : "active"
    setUpdating((prev) => new Set([...prev, id]))
    try {
      const { data, error } = await updateLiberacao(id, { status: newStatus })
      if (error) throw error
      setLiberacoes((prev) => prev.map((l) => (l.id === id ? { ...l, status: data?.status ?? newStatus } : l)))
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

  const sortedLiberacoes = useMemo(() => {
    if (!sortColumn) return liberacoes
    return [...liberacoes].sort((a, b) => {
      const aVal =
        sortColumn === "materialTypeName" ? a.material_types?.name : (a as any)[sortColumn]
      const bVal =
        sortColumn === "materialTypeName" ? b.material_types?.name : (b as any)[sortColumn]
      if (aVal == null && bVal == null) return 0
      if (aVal == null) return 1
      if (bVal == null) return -1
      const aStr = String(aVal).toLowerCase()
      const bStr = String(bVal).toLowerCase()
      if (sortDirection === "asc") return aStr < bStr ? -1 : aStr > bStr ? 1 : 0
      return aStr > bStr ? -1 : aStr < bStr ? 1 : 0
    })
  }, [liberacoes, sortColumn, sortDirection])

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
      const { data, error } = await addLiberacao(form)
      if (error) throw error
      if (data) setLiberacoes((prev) => [...prev, data])
      setIsAddDialogOpen(false)
      setForm({
        quota: 0,
        sequence: 0,
        material_type_id: 0,
        planned_mass: 0,
        model_grade: 0,
        planned_grade: 0,
        status: "active",
      })
    } catch (err) {
      console.error("Erro ao adicionar liberacao:", err)
      setError(err instanceof Error ? err.message : "Erro ao adicionar liberacao")
    }
  }

  const handleEdit = async () => {
    if (!editing?.id) return
    try {
      setUpdating((prev) => new Set([...prev, editing.id]))
      const { data, error } = await updateLiberacao(editing.id, {
        quota: editing.quota,
        sequence: editing.sequence,
        material_type_id: editing.material_type_id,
        planned_mass: editing.planned_mass,
        model_grade: editing.model_grade,
        planned_grade: editing.planned_grade,
        status: editing.status,
      })
      if (error) throw error
      setLiberacoes((prev) => prev.map((l) => (l.id === editing.id ? { ...l, ...editing, ...data } : l)))
      setIsEditDialogOpen(false)
      setEditing(null)
    } catch (err) {
      console.error("Erro ao salvar liberacao:", err)
      setError(err instanceof Error ? err.message : "Erro ao salvar liberacao")
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
      const { error } = await deleteLiberacao(deleting.id)
      if (error) throw error
      setLiberacoes((prev) => prev.filter((l) => l.id !== deleting.id))
      setIsDeleteDialogOpen(false)
      setDeleting(null)
    } catch (err) {
      console.error("Erro ao excluir liberacao:", err)
      setError(err instanceof Error ? err.message : "Erro ao excluir liberacao")
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

  const statusBadge = (item: Liberacao) => {
    const status = item.status || "pending"
    const isUpdating = updating.has(item.id)
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
    const info = statusMap[status.toLowerCase()] || { label: status, className: "bg-muted text-muted-foreground cursor-not-allowed" }
    if (isUpdating) {
      return (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${info.className} flex items-center gap-1`}>
          <Loader2 className="h-3 w-3 animate-spin" />
          Alterando...
        </span>
      )
    }
    return (
      <button
        onClick={() => toggleStatus(item.id, status)}
        className={`px-2 py-1 rounded-full text-xs font-medium ${info.className} transition-colors`}
        disabled={isUpdating}
        title={`Clique para alterar status de ${info.label.toLowerCase()}`}
      >
        {info.label}
      </button>
    )
  }

  const numericInput = (
    label: string,
    id: string,
    value: number | string,
    onChange: (v: number) => void,
    step: string = "1"
  ) => (
    <div className="grid grid-cols-4 items-center gap-4">
      <Label htmlFor={id} className="text-right">
        {label}
      </Label>
      <Input
        id={id}
        type="number"
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value === "" ? 0 : Number(e.target.value))}
        className="col-span-3"
      />
    </div>
  )

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center space-x-2">
          <Layers className="h-6 w-6" />
          <h1 className="text-3xl font-bold">Liberações</h1>
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
          <Layers className="h-6 w-6" />
          <h1 className="text-3xl font-bold">Liberações</h1>
        </div>
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
          <div className="flex items-center space-x-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span className="font-medium">Erro ao carregar liberações</span>
          </div>
          <p className="text-muted-foreground mt-2">{error}</p>
          <Button onClick={fetchLiberacoes} variant="outline" className="mt-4" size="sm">
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
          <Layers className="h-6 w-6" />
          <h1 className="text-3xl font-bold">Liberações</h1>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="h-4 w-4 mr-2" />
              Adicionar Liberação
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[520px]">
            <DialogHeader>
              <DialogTitle>Nova Liberação</DialogTitle>
              <DialogDescription>Cadastre uma nova liberação de produção.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              {numericInput("Sequência", "seq", form.sequence ?? "", (v) => setForm((p) => ({ ...p, sequence: v })))}
              {numericInput("Quota", "quota", form.quota ?? "", (v) => setForm((p) => ({ ...p, quota: v })))}
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="materialType" className="text-right">
                  Tipo de Material
                </Label>
                <Select
                  value={form.material_type_id ? form.material_type_id.toString() : ""}
                  onValueChange={(value) => setForm((prev) => ({ ...prev, material_type_id: Number(value) }))}
                >
                  <SelectTrigger className="col-span-3">
                    <SelectValue placeholder="Selecione o tipo" />
                  </SelectTrigger>
                  <SelectContent>
                    {materialTypes.map((mt) => (
                      <SelectItem key={mt.id} value={mt.id.toString()}>
                        {mt.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {numericInput("Massa Planejada", "planned_mass", form.planned_mass ?? "", (v) => setForm((p) => ({ ...p, planned_mass: v })), "0.01")}
              {numericInput("Lei Modelo", "model_grade", form.model_grade ?? "", (v) => setForm((p) => ({ ...p, model_grade: v })), "0.01")}
              {numericInput("Lei Planejada", "planned_grade", form.planned_grade ?? "", (v) => setForm((p) => ({ ...p, planned_grade: v })), "0.01")}
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

      {liberacoes.length === 0 ? (
        <div className="text-center py-12">
          <Layers className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium text-card-foreground mb-2">Nenhuma liberação cadastrada</h3>
          <p className="text-muted-foreground">Cadastre a primeira liberação para começar.</p>
        </div>
      ) : (
        <div className="bg-card rounded-lg shadow overflow-hidden border">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-muted/50">
                <tr>
                  {getSortableHeader("status", "Status")}
                  {getSortableHeader("sequence", "Seq")}
                  {getSortableHeader("quota", "Quota")}
                  {getSortableHeader("materialTypeName", "Tipo de Material")}
                  {getSortableHeader("planned_mass", "Massa Plan.")}
                  {getSortableHeader("model_grade", "Lei Modelo")}
                  {getSortableHeader("planned_grade", "Lei Plan.")}
                  {getSortableHeader("created_at", "Criado em")}
                  {getSortableHeader("updated_at", "Atualizado em")}
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Acoes</th>
                </tr>
              </thead>
              <tbody className="bg-card divide-y divide-border">
                {sortedLiberacoes.map((item) => (
                  <tr key={item.id} className="hover:bg-accent transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">{statusBadge(item)}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground font-mono">
                        <ListOrdered className="h-4 w-4 opacity-60" />
                        {item.sequence ?? "-"}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-card-foreground">{item.quota ?? "-"}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-card-foreground">{item.material_types?.name || "-"}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground font-mono">{item.planned_mass ?? "-"}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground font-mono">{item.model_grade ?? "-"}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground font-mono">{item.planned_grade ?? "-"}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground">{formatDate(item.created_at)}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-muted-foreground">{formatDate(item.updated_at)}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => {
                            setEditing({ ...item })
                            setIsEditDialogOpen(true)
                          }}
                          title="Editar liberação"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="destructive"
                          size="icon"
                          onClick={() => {
                            setDeleting(item)
                            setIsDeleteDialogOpen(true)
                          }}
                          title="Excluir liberação"
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

      <div className="text-sm text-muted-foreground">Total de liberações: {liberacoes.length}</div>

      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle>Editar Liberação</DialogTitle>
            <DialogDescription>Atualize as informações da liberação.</DialogDescription>
          </DialogHeader>
          {editing && (
            <div className="grid gap-4 py-4">
              {numericInput("Sequência", "edit-seq", editing.sequence ?? "", (v) =>
                setEditing((prev) => (prev ? { ...prev, sequence: v } : prev))
              )}
              {numericInput("Quota", "edit-quota", editing.quota ?? "", (v) =>
                setEditing((prev) => (prev ? { ...prev, quota: v } : prev))
              )}
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="edit-materialType" className="text-right">
                  Tipo de Material
                </Label>
                <Select
                  value={editing.material_type_id ? editing.material_type_id.toString() : ""}
                  onValueChange={(value) =>
                    setEditing((prev) => (prev ? { ...prev, material_type_id: Number(value) } : prev))
                  }
                >
                  <SelectTrigger className="col-span-3">
                    <SelectValue placeholder="Selecione o tipo" />
                  </SelectTrigger>
                  <SelectContent>
                    {materialTypes.map((mt) => (
                      <SelectItem key={mt.id} value={mt.id.toString()}>
                        {mt.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {numericInput(
                "Massa Planejada",
                "edit-planned_mass",
                editing.planned_mass ?? "",
                (v) => setEditing((prev) => (prev ? { ...prev, planned_mass: v } : prev)),
                "0.01"
              )}
              {numericInput(
                "Lei Modelo",
                "edit-model_grade",
                editing.model_grade ?? "",
                (v) => setEditing((prev) => (prev ? { ...prev, model_grade: v } : prev)),
                "0.01"
              )}
              {numericInput(
                "Lei Planejada",
                "edit-planned_grade",
                editing.planned_grade ?? "",
                (v) => setEditing((prev) => (prev ? { ...prev, planned_grade: v } : prev)),
                "0.01"
              )}
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
            <DialogTitle>Confirmar Exclusao</DialogTitle>
            <DialogDescription>Esta acao nao pode ser desfeita.</DialogDescription>
          </DialogHeader>
          {deleting && (
            <div className="grid gap-2 py-4">
              <div className="flex items-center gap-2">
                <Label className="font-medium">Seq:</Label>
                <span>{deleting.sequence}</span>
              </div>
              <div className="flex items-center gap-2">
                <Label className="font-medium">Tipo:</Label>
                <span>{deleting.material_types?.name || "-"}</span>
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
              Confirmar Exclusao
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
