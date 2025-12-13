"use client"

import { MapPin, Radio, ShieldCheck, Satellite, Clock } from "lucide-react"
import { useMemo } from "react"
import MapView from "@/components/map/MapView"
import { useDeviceStream } from "@/components/map/useDeviceStream"

export default function MonitoramentoTempoRealPage() {
  const { devices, status, lastUpdated, error, isInitialLoading } = useDeviceStream()

  const stats = useMemo(() => {
    const total = devices.length
    const online = devices.filter((d) => d.status === "online").length
    const offline = total - online
    return { total, online, offline }
  }, [devices])

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-xl border bg-card shadow-sm">
        <div className="p-2 sm:p-4">
          <MapView
            devices={devices}
            isLoading={isInitialLoading}
            error={error}
            connectionStatus={status}
          />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
              <MapPin className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold">Dispositivos</p>
              <p className="text-xs text-muted-foreground">
                Totais: {stats.total} · Online: {stats.online} · Offline: {stats.offline}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-orange-500/10 text-orange-500">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold">Stream</p>
              <p className="text-xs text-muted-foreground">
                Status: {status.toUpperCase()}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-500/10 text-blue-500">
              <Clock className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold">Última atualização</p>
              <p className="text-xs text-muted-foreground">
                {lastUpdated ? lastUpdated.toLocaleString("pt-BR") : "—"}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
