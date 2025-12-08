import { Settings, Shield, Database, Bell } from "lucide-react"

export default function AdminPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Administrador</h1>
        <p className="text-muted-foreground">
          Configurações do sistema e administração geral.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border bg-card p-6 hover:bg-accent/50 cursor-pointer transition-colors">
          <div className="flex items-center gap-2">
            <Settings className="h-5 w-5 text-gray-500" />
            <h3 className="font-semibold">Configurações Gerais</h3>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Configure parâmetros do sistema
          </p>
        </div>

        <div className="rounded-lg border bg-card p-6 hover:bg-accent/50 cursor-pointer transition-colors">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-red-500" />
            <h3 className="font-semibold">Segurança</h3>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Gerencie políticas de segurança e acessos
          </p>
        </div>

        <div className="rounded-lg border bg-card p-6 hover:bg-accent/50 cursor-pointer transition-colors">
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-blue-500" />
            <h3 className="font-semibold">Banco de Dados</h3>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Backup, restauração e manutenção
          </p>
        </div>

        <div className="rounded-lg border bg-card p-6 hover:bg-accent/50 cursor-pointer transition-colors">
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-yellow-500" />
            <h3 className="font-semibold">Notificações</h3>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Configure alertas e notificações
          </p>
        </div>
      </div>

      <div className="rounded-lg border bg-card p-6">
        <h3 className="font-semibold mb-4">Logs do Sistema</h3>
        <div className="h-[250px] bg-muted rounded-md flex items-center justify-center">
          <p className="text-muted-foreground">Visualização de logs em desenvolvimento</p>
        </div>
      </div>
    </div>
  )
}
