import { Activity, MapPin, Radio } from "lucide-react"

export default function MonitoramentoPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Monitoramento</h1>
        <p className="text-muted-foreground">
          Acompanhe em tempo real a telemetria dos dispositivos.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-2">
            <Radio className="h-5 w-5 text-green-500" />
            <h3 className="font-semibold">Dispositivos Online</h3>
          </div>
          <p className="mt-2 text-3xl font-bold">--</p>
          <p className="text-sm text-muted-foreground">Aguardando dados...</p>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-2">
            <MapPin className="h-5 w-5 text-blue-500" />
            <h3 className="font-semibold">Última Posição</h3>
          </div>
          <p className="mt-2 text-3xl font-bold">--</p>
          <p className="text-sm text-muted-foreground">Aguardando dados...</p>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-orange-500" />
            <h3 className="font-semibold">Eventos (24h)</h3>
          </div>
          <p className="mt-2 text-3xl font-bold">--</p>
          <p className="text-sm text-muted-foreground">Aguardando dados...</p>
        </div>
      </div>

      <div className="rounded-lg border bg-card p-6">
        <h3 className="font-semibold mb-4">Mapa de Dispositivos</h3>
        <div className="h-[400px] bg-muted rounded-md flex items-center justify-center">
          <p className="text-muted-foreground">Integração com mapa em desenvolvimento</p>
        </div>
      </div>
    </div>
  )
}
