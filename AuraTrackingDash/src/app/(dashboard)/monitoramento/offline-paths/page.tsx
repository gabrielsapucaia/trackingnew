"use client"

import { AlertTriangle, Clock, MapPin, CalendarRange, Timer, HardHat } from "lucide-react"
import { useMemo, useState, useEffect } from "react"
import { useDeviceStream } from "@/components/map/useDeviceStream"
import { getEquipamentos } from "@/services/equipamentos"
import { useOfflinePositions } from "@/hooks/useOfflinePositions"
import { OfflineMap } from "@/components/offline/OfflineMap"

export default function MonitoramentoOfflinePathsPage() {
  const { devices, status, lastUpdated, error, isInitialLoading } = useDeviceStream()

  const formatDate = (d: Date) => d.toISOString().slice(0, 10)
  const formatTime = (d: Date) => d.toTimeString().slice(0, 5)

  const [dateStart, setDateStart] = useState("")
  const [dateEnd, setDateEnd] = useState("")
  const [timeStart, setTimeStart] = useState("")
  const [timeEnd, setTimeEnd] = useState("")
  const [equipmentId, setEquipmentId] = useState<string>("all")
  const [equipments, setEquipments] = useState<{ id: number; tag: string }[]>([])
  const { data: historicalDevices, isLoading: loadingHistory, errorMessage: historyError, refetch } =
    useOfflinePositions()
  const [hydrated, setHydrated] = useState(false)
  const [periodEnabled, setPeriodEnabled] = useState(true)
  const [speedBreakpoints, setSpeedBreakpoints] = useState<{ b0: string; b1: string; b2: string }>({
    b0: "10",
    b1: "30",
    b2: "60",
  })
  const [speedHydrated, setSpeedHydrated] = useState(false)

  useEffect(() => {
    const current = new Date()
    setDateStart(formatDate(current))
    setDateEnd(formatDate(current))
    setTimeEnd(formatTime(current))
    setTimeStart(formatTime(new Date(current.getTime() - 60 * 60 * 1000)))
    setHydrated(true)
    setSpeedHydrated(true)
  }, [])

  useEffect(() => {
    const loadEquipments = async () => {
      const { data } = await getEquipamentos()
      if (data) {
        const mapped = (data as any[]).map((e) => ({ id: e.id, tag: e.tag }))
        setEquipments(mapped)
      }
    }
    loadEquipments()
  }, [])

  const offlineDevices = useMemo(() => devices.filter((d) => d.status === "offline"), [devices])

  const stats = useMemo(() => {
    const total = devices.length
    const offline = offlineDevices.length
    const online = total - offline
    return { total, online, offline }
  }, [devices, offlineDevices.length])

  const filteredDevices = useMemo(() => {
    if (equipmentId === "all") return offlineDevices
    return offlineDevices.filter((d) => String((d as any).equipmentId ?? (d as any).deviceId) === equipmentId)
  }, [equipmentId, offlineDevices])

  const devicesToShow = historicalDevices.length > 0 ? historicalDevices : filteredDevices

  const handleLoadHistory = async () => {
    try {
      const toUTC = (date: string, time: string, endOfDay = false) => {
        const [h, m] = (time || (endOfDay ? "23:59" : "00:00")).split(":").map((v) => parseInt(v, 10))
        const dt = new Date(`${date}T${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:00-03:00`)
        return dt.toISOString()
      }
      const startIso = toUTC(dateStart, timeStart || "00:00")
      const endIso = toUTC(dateEnd, timeEnd || "23:59", true)
      await refetch({
        equipmentId,
        start: startIso,
        end: endIso,
        limit: 20000,
      })
    } catch {
      // handled in hook
    }
  }

  const speedConfig = useMemo(() => {
    const b0 = parseFloat(speedBreakpoints.b0) || 0
    const b1 = parseFloat(speedBreakpoints.b1) || b0 + 1
    const b2 = parseFloat(speedBreakpoints.b2) || b1 + 1
    return {
      breakpoints: [b0, b1, b2],
      colors: [
        [34, 197, 94, 220],
        [234, 179, 8, 220],
        [249, 115, 22, 220],
        [239, 68, 68, 220],
      ] as [number, number, number, number][],
    }
  }, [speedBreakpoints])

  return (
    <div className="grid gap-4 items-start" style={{ gridTemplateColumns: "12% 1fr" }}>
      <aside className="rounded-lg border bg-card p-4 shadow-sm sticky top-4 self-start">
        <div className="space-y-3">
          <div>
            <p className="text-sm font-semibold">Filtro de período</p>
            <p className="text-xs text-muted-foreground">
              Selecione intervalo histórico para visualizar dispositivos offline
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm text-white">
            <input
              type="checkbox"
              checked={periodEnabled}
              onChange={(e) => setPeriodEnabled(e.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            <span>Ativar filtro de período</span>
          </label>
          <label className="flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm text-white">
            <HardHat className="h-4 w-4 text-white" />
            <select
              className="w-full bg-transparent text-white outline-none"
              value={equipmentId}
              onChange={(e) => setEquipmentId(e.target.value)}
            >
              <option value="all">Todos os equipamentos</option>
              {equipments.map((eq) => (
                <option key={eq.id} value={String(eq.id)}>
                  {eq.tag}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm text-white">
            <CalendarRange className="h-4 w-4 text-white" />
            <input
              type="date"
              className="w-full bg-transparent outline-none"
              value={periodEnabled && hydrated ? dateStart : ""}
              onChange={(e) => setDateStart(e.target.value)}
              suppressHydrationWarning
              disabled={!periodEnabled}
            />
          </label>
          <label className="flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm text-white">
            <CalendarRange className="h-4 w-4 text-white" />
            <input
              type="date"
              className="w-full bg-transparent outline-none"
              value={periodEnabled && hydrated ? dateEnd : ""}
              onChange={(e) => setDateEnd(e.target.value)}
              suppressHydrationWarning
              disabled={!periodEnabled}
            />
          </label>
          <label className="flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm text-white">
            <Timer className="h-4 w-4 text-white" />
            <input
              type="time"
              className="w-full bg-transparent outline-none"
              value={periodEnabled && hydrated ? timeStart : ""}
              onChange={(e) => setTimeStart(e.target.value)}
              suppressHydrationWarning
              disabled={!periodEnabled}
            />
          </label>
          <label className="flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm text-white">
            <Timer className="h-4 w-4 text-white" />
            <input
              type="time"
              className="w-full bg-transparent outline-none"
              value={periodEnabled && hydrated ? timeEnd : ""}
              onChange={(e) => setTimeEnd(e.target.value)}
              suppressHydrationWarning
              disabled={!periodEnabled}
            />
          </label>
          <div className="pt-2 space-y-2 border-t border-white/10">
            <p className="text-sm font-semibold">Faixas de velocidade (km/h)</p>
            <div className="grid grid-cols-1 gap-2 text-xs text-white">
              <label className="flex items-center gap-2">
                <span className="inline-block h-3 w-3 rounded-sm bg-green-500" />
                <input
                  type="number"
                  className="w-full rounded bg-background px-2 py-1 text-xs outline-none"
                  value={speedHydrated ? speedBreakpoints.b0 : ""}
                  onChange={(e) => setSpeedBreakpoints((s) => ({ ...s, b0: e.target.value }))}
                  placeholder="<= Verde"
                  suppressHydrationWarning
                />
              </label>
              <label className="flex items-center gap-2">
                <span className="inline-block h-3 w-3 rounded-sm bg-yellow-500" />
                <input
                  type="number"
                  className="w-full rounded bg-background px-2 py-1 text-xs outline-none"
                  value={speedHydrated ? speedBreakpoints.b1 : ""}
                  onChange={(e) => setSpeedBreakpoints((s) => ({ ...s, b1: e.target.value }))}
                  placeholder="<= Amarelo"
                  suppressHydrationWarning
                />
              </label>
              <label className="flex items-center gap-2">
                <span className="inline-block h-3 w-3 rounded-sm bg-orange-500" />
                <input
                  type="number"
                  className="w-full rounded bg-background px-2 py-1 text-xs outline-none"
                  value={speedHydrated ? speedBreakpoints.b2 : ""}
                  onChange={(e) => setSpeedBreakpoints((s) => ({ ...s, b2: e.target.value }))}
                  placeholder="<= Laranja"
                  suppressHydrationWarning
                />
              </label>
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <span className="inline-block h-3 w-3 rounded-sm bg-red-500" />
                <span>{"\u003e"} último valor = Vermelho</span>
              </div>
            </div>
          </div>
          <button
            className="w-full rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:brightness-110"
            type="button"
            onClick={handleLoadHistory}
            disabled={loadingHistory}
          >
            {loadingHistory ? "Carregando..." : "Carregar"}
          </button>
          {historyError && <p className="text-xs text-red-400">{historyError}</p>}
        </div>
      </aside>

      <div className="space-y-4">
        <div className="overflow-hidden rounded-xl border bg-card shadow-sm">
          <div className="p-2 sm:p-4">
            <OfflineMap
              mode="path"
              positions={devicesToShow}
              colorBySpeed={speedConfig}
              connectionStatus={status}
              isLoading={isInitialLoading || loadingHistory}
              error={historyError || error}
            />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border bg-card p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-500/10 text-red-500">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-semibold">Dispositivos offline</p>
                <p className="text-xs text-muted-foreground">
                  Offline: {stats.offline} · Total: {stats.total}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-lg border bg-card p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                <MapPin className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-semibold">Online x Offline</p>
                <p className="text-xs text-muted-foreground">
                  Online: {stats.online} · Offline: {stats.offline}
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
    </div>
  )
}
