import { Smartphone, Users, Building2, Wrench } from "lucide-react"

export default function CadastroPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Cadastro</h1>
        <p className="text-muted-foreground">
          Gerencie dispositivos, operadores e entidades.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border bg-card p-6 hover:bg-accent/50 cursor-pointer transition-colors">
          <div className="flex items-center gap-2">
            <Smartphone className="h-5 w-5 text-blue-500" />
            <h3 className="font-semibold">Dispositivos</h3>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Cadastre e gerencie dispositivos de rastreamento
          </p>
        </div>

        <div className="rounded-lg border bg-card p-6 hover:bg-accent/50 cursor-pointer transition-colors">
          <div className="flex items-center gap-2">
            <Users className="h-5 w-5 text-green-500" />
            <h3 className="font-semibold">Operadores</h3>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Gerencie operadores e suas permissões
          </p>
        </div>

        <div className="rounded-lg border bg-card p-6 hover:bg-accent/50 cursor-pointer transition-colors">
          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-orange-500" />
            <h3 className="font-semibold">Entidades</h3>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Configure empresas e organizações
          </p>
        </div>

        <div className="rounded-lg border bg-card p-6 hover:bg-accent/50 cursor-pointer transition-colors">
          <div className="flex items-center gap-2">
            <Wrench className="h-5 w-5 text-purple-500" />
            <h3 className="font-semibold">Equipamentos</h3>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Visualize equipamentos cadastrados
          </p>
        </div>
      </div>

      <div className="rounded-lg border bg-card p-6">
        <h3 className="font-semibold mb-4">Lista de Registros</h3>
        <div className="h-[300px] bg-muted rounded-md flex items-center justify-center">
          <p className="text-muted-foreground">Tabela de cadastros em desenvolvimento</p>
        </div>
      </div>
    </div>
  )
}
