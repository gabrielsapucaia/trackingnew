"use client"

import { useEffect, useState } from "react"
import { getProfilesAdmin, updateProfileAdmin, deleteProfileAdmin, createProfileAdmin, type Profile } from "@/services/profiles"
import { AlertCircle, Check, Loader2, Trash2, UserCog } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DialogClose } from "@radix-ui/react-dialog"
import { Input } from "@/components/ui/input"

const statusOptions: Profile["status"][] = ["pending", "active", "blocked"]
const permissionOptions: Profile["permission"][] = ["view", "edit"]
const roleOptions: Profile["role"][] = ["user", "admin"]

export default function UsuariosAdminPage() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Profile | null>(null)
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [newEmail, setNewEmail] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [newRole, setNewRole] = useState<Profile["role"]>("user")
  const [newPermission, setNewPermission] = useState<Profile["permission"]>("view")
  const [newStatus, setNewStatus] = useState<Profile["status"]>("pending")

  const fetchProfiles = async () => {
    setLoading(true)
    const { data, error } = await getProfilesAdmin()
    if (error) {
      setError(String(error))
    } else {
      setProfiles(data)
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchProfiles()
  }, [])

  const handleUpdate = async (id: string, updates: Partial<Profile>) => {
    setSavingId(id)
    const { data, error } = await updateProfileAdmin(id, updates)
    if (error) {
      setError(String(error))
    } else if (data) {
      setProfiles((prev) => prev.map((p) => (p.id === id ? { ...p, ...data } : p)))
    }
    setSavingId(null)
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <UserCog className="h-6 w-6" />
          <h1 className="text-2xl font-bold">Usuários</h1>
        </div>
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <UserCog className="h-6 w-6" />
          <h1 className="text-2xl font-bold">Usuários</h1>
        </div>
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4 flex items-start gap-2 text-destructive">
          <AlertCircle className="h-5 w-5" />
          <div>
            <p className="font-semibold">Erro ao carregar usuários</p>
            <p className="text-sm">{error}</p>
          </div>
        </div>
        <Button variant="outline" onClick={fetchProfiles}>Tentar novamente</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <UserCog className="h-6 w-6" />
        <h1 className="text-2xl font-bold">Usuários</h1>
      </div>

      <div className="flex justify-end">
        <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
          <Button onClick={() => setIsAddOpen(true)}>Adicionar usuário</Button>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Novo usuário</DialogTitle>
              <DialogDescription>Crie um usuário corporativo e defina as permissões.</DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <div>
                <label className="text-sm text-muted-foreground block mb-1">Email</label>
                <Input
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  placeholder="nome@auraminerals.com"
                />
              </div>
              <div>
                <label className="text-sm text-muted-foreground block mb-1">Senha</label>
                <Input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Senha temporária"
                />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-1">
                  <label className="text-sm text-muted-foreground block">Status</label>
                  <Select value={newStatus} onValueChange={(v) => setNewStatus(v as Profile["status"])}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {statusOptions.map((s) => (
                        <SelectItem key={s} value={s}>{s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <label className="text-sm text-muted-foreground block">Permissão</label>
                  <Select value={newPermission} onValueChange={(v) => setNewPermission(v as Profile["permission"])}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {permissionOptions.map((p) => (
                        <SelectItem key={p} value={p}>{p}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <label className="text-sm text-muted-foreground block">Role</label>
                  <Select value={newRole} onValueChange={(v) => setNewRole(v as Profile["role"])}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {roleOptions.map((r) => (
                        <SelectItem key={r} value={r}>{r}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
            <DialogFooter className="justify-end gap-2">
              <DialogClose asChild>
                <Button variant="outline">Cancelar</Button>
              </DialogClose>
              <Button
                onClick={async () => {
                  setError(null)
                  const email = newEmail.trim().toLowerCase()
                  if (!email.endsWith("@auraminerals.com")) {
                    setError("Use um email @auraminerals.com")
                    return
                  }
                  if (!newPassword || newPassword.length < 6) {
                    setError("Senha precisa ter ao menos 6 caracteres")
                    return
                  }
                  setSavingId("new")
                  const { data, error } = await createProfileAdmin({
                    email,
                    password: newPassword,
                    role: newRole,
                    permission: newPermission,
                    status: newStatus,
                  })
                  if (error) {
                    setError(String(error))
                  } else if (data) {
                    setProfiles((prev) => [data, ...prev])
                    setIsAddOpen(false)
                    setNewEmail("")
                    setNewPassword("")
                    setNewRole("user")
                    setNewPermission("view")
                    setNewStatus("pending")
                  }
                  setSavingId(null)
                }}
                disabled={savingId === "new"}
              >
                {savingId === "new" ? "Criando..." : "Criar usuário"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="bg-card rounded-lg border overflow-hidden">
        <div className="grid grid-cols-5 gap-4 px-4 py-3 bg-muted/50 text-xs font-semibold uppercase text-muted-foreground">
          <span>Email</span>
          <span>Status</span>
          <span>Permissão</span>
              <span>Role</span>
              <span>Ações</span>
            </div>
            <div className="divide-y divide-border">
          {profiles.map((profile) => (
            <div key={profile.id} className="grid grid-cols-5 gap-4 px-4 py-3 items-center">
              <div className="text-sm">{profile.email}</div>
              <div>
                <Select
                  value={profile.status}
                  onValueChange={(value) => handleUpdate(profile.id, { status: value as Profile["status"] })}
                  disabled={savingId === profile.id}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {statusOptions.map((s) => (
                      <SelectItem key={s} value={s}>{s}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Select
                  value={profile.permission}
                  onValueChange={(value) => handleUpdate(profile.id, { permission: value as Profile["permission"] })}
                  disabled={savingId === profile.id}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {permissionOptions.map((p) => (
                      <SelectItem key={p} value={p}>{p}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Select
                  value={profile.role}
                  onValueChange={(value) => handleUpdate(profile.id, { role: value as Profile["role"] })}
                  disabled={savingId === profile.id}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {roleOptions.map((r) => (
                      <SelectItem key={r} value={r}>{r}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-2">
                {savingId === profile.id ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <div className="flex items-center gap-2 justify-end">
                    <span className="text-green-600 flex items-center gap-1 text-xs">
                      <Check className="h-4 w-4" /> pronto
                    </span>
                    {profile.role !== "admin" && (
                      <Button
                        variant="destructive"
                        size="icon"
                        onClick={() => setDeleteTarget(profile)}
                        title="Excluir usuário"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmar exclusão</DialogTitle>
            <DialogDescription>
              Tem certeza que deseja excluir o usuário {deleteTarget?.email}? Esta ação não pode ser desfeita.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="justify-end gap-2">
            <DialogClose asChild>
              <Button variant="outline" onClick={() => setDeleteTarget(null)}>
                Cancelar
              </Button>
            </DialogClose>
            <Button
              variant="destructive"
              onClick={async () => {
                if (!deleteTarget) return
                setSavingId(deleteTarget.id)
                const { error } = await deleteProfileAdmin(deleteTarget.id)
                if (error) {
                  setError(String(error))
                } else {
                  setProfiles((prev) => prev.filter((p) => p.id !== deleteTarget.id))
                  setDeleteTarget(null)
                }
                setSavingId(null)
              }}
            >
              Confirmar exclusão
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
