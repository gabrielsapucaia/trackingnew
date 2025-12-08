import { BarChart3, TrendingUp, Calendar } from "lucide-react"

export default function AnalisePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Análise</h1>
        <p className="text-muted-foreground">
          Visualize relatórios e métricas de desempenho.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-purple-500" />
            <h3 className="font-semibold">Relatórios</h3>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Gere relatórios customizados de telemetria
          </p>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-green-500" />
            <h3 className="font-semibold">Tendências</h3>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Analise padrões e comportamentos
          </p>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-2">
            <Calendar className="h-5 w-5 text-blue-500" />
            <h3 className="font-semibold">Histórico</h3>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Consulte dados históricos
          </p>
        </div>
      </div>

      <div className="rounded-lg border bg-card p-6">
        <h3 className="font-semibold mb-4">Gráficos de Análise</h3>
        <div className="h-[400px] bg-muted rounded-md flex items-center justify-center">
          <p className="text-muted-foreground">Gráficos em desenvolvimento</p>
        </div>
      </div>
    </div>
  )
}
