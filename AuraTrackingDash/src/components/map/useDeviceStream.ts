"use client"

import { useEffect, useState, useRef, useCallback } from "react"
import { fetchDevices } from "@/lib/map/api-client/devices"
import type { DeviceSummary } from "@/types/map/devices"
import { API_BASE_URL } from "@/lib/map/config"

const SSE_URL = `${API_BASE_URL}/api/events/stream`
const FLUSH_INTERVAL_MS = 1000
const POLLING_FALLBACK_MS = 5000
// Marca como online se o último sinal chegou há até 6s (stream envia a cada ~5s)
const ONLINE_THRESHOLD_MS = 6000
// Após 24h sem sinal, oculta; antes disso marca como offline
const HIDDEN_THRESHOLD_MS = 24 * 60 * 60 * 1000
const RECONNECT_DELAY_MS = 5000
const IDLE_TIMEOUT_MS = 30000
const IDLE_CHECK_MS = 5000

type InternalDeviceStatus = "online" | "offline" | "hidden"

function computeDeviceStatus(lastSeen: string | null): InternalDeviceStatus {
  if (!lastSeen) return "hidden"
  const lastSeenTime = new Date(lastSeen).getTime()
  const now = Date.now()
  const delta = now - lastSeenTime
  if (delta <= ONLINE_THRESHOLD_MS) return "online"
  if (delta <= HIDDEN_THRESHOLD_MS) return "offline"
  return "hidden"
}

export type ConnectionStatus = "connecting" | "live" | "reconnecting" | "fallback_polling" | "offline"

type UseDeviceStreamResult = {
  devices: DeviceSummary[]
  status: ConnectionStatus
  lastUpdated: Date | null
  error: string | null
  isInitialLoading: boolean
}

type DeviceUpdate = {
  id: string
  ts: number
  lat: number | string
  lon?: number | string
  lng?: number | string
  st?: string
  sp?: number | string
  op?: string
}

export function useDeviceStream(): UseDeviceStreamResult {
  const [devices, setDevices] = useState<DeviceSummary[]>([])
  const [status, setStatus] = useState<ConnectionStatus>("connecting")
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isInitialLoading, setIsInitialLoading] = useState(true)

  const devicesMapRef = useRef<Map<string, DeviceSummary>>(new Map())
  const updateBufferRef = useRef<Map<string, DeviceUpdate>>(new Map())
  const eventSourceRef = useRef<EventSource | null>(null)
  const flushTimerRef = useRef<NodeJS.Timeout | null>(null)
  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null)
  const idleTimerRef = useRef<NodeJS.Timeout | null>(null)
  const connectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const connectSSERef = useRef<() => void>(() => {})
  const isMountedRef = useRef(false)
  const lastEventTsRef = useRef<number>(0)
  const statusRef = useRef<ConnectionStatus>("connecting")
  const initializedRef = useRef(false)
  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }, [])
  const globalKey = "__device_event_source__"

  const normalizeTimestamp = (ts: number | string | undefined): number => {
    if (!ts) return Date.now()
    if (typeof ts === "string") {
      const parsed = Date.parse(ts)
      return Number.isNaN(parsed) ? Date.now() : parsed
    }
    // if already milliseconds
    if (ts > 1e12) return ts
    // if seconds (unix)
    if (ts > 1e9) return ts * 1000
    return Date.now()
  }

  const applySnapshot = useCallback((list: DeviceSummary[]) => {
    devicesMapRef.current.clear()
    list.forEach((d) => devicesMapRef.current.set(d.deviceId, d))
    const visibleDevices: DeviceSummary[] = []
    devicesMapRef.current.forEach((device) => {
      const computedStatus = computeDeviceStatus(device.lastSeen)
      if (computedStatus !== "hidden") {
        visibleDevices.push({ ...device, status: computedStatus as "online" | "offline" })
      }
    })
    setDevices(visibleDevices)
    setLastUpdated(new Date())
    setError(null)
    setIsInitialLoading(false)
  }, [])

  const flushUpdates = useCallback(() => {
    const now = new Date()
    let hasBufferUpdates = false

    if (updateBufferRef.current.size > 0) {
      updateBufferRef.current.forEach((update) => {
        const current = devicesMapRef.current.get(update.id)
        const lonVal = update.lon ?? update.lng
        const lon = typeof lonVal === "number" ? lonVal : lonVal !== undefined ? parseFloat(lonVal) : NaN
        const lat = typeof update.lat === "number" ? update.lat : parseFloat(update.lat)
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return

        const currentTs = current?.lastSeen ? new Date(current.lastSeen).getTime() : 0
        const incomingTs = normalizeTimestamp(update.ts)
        const positionChanged =
          !current ||
          current.latitude !== lat ||
          current.longitude !== lon ||
          current.speedKmh !== (typeof update.sp === "number" ? update.sp : parseFloat(String(update.sp)))
        const shouldUpdate = !current || positionChanged || incomingTs >= currentTs

        if (shouldUpdate) {
          const effectiveTs = Math.max(incomingTs, Date.now(), currentTs)
          const speed = typeof update.sp === "number" ? update.sp : parseFloat(String(update.sp))
          const updatedDevice: DeviceSummary = {
            deviceId: update.id,
            operatorId: current?.operatorId || update.op || null,
            latitude: lat,
            longitude: lon,
            lastSeen: new Date(effectiveTs).toISOString(),
            status: update.st === "offline" ? "offline" : "online",
            speedKmh: Number.isFinite(speed) ? speed : current?.speedKmh || null,
            totalPoints24h: (current?.totalPoints24h || 0) + 1,
          }
          devicesMapRef.current.set(update.id, updatedDevice)
          hasBufferUpdates = true
        }
      })
      updateBufferRef.current.clear()
    }

    const visibleDevices: DeviceSummary[] = []
    devicesMapRef.current.forEach((device) => {
      const computedStatus = computeDeviceStatus(device.lastSeen)
      if (computedStatus !== "hidden") {
        visibleDevices.push({
          ...device,
          status: computedStatus as "online" | "offline",
        })
      }
    })

    setDevices(visibleDevices)
    if (hasBufferUpdates) {
      setLastUpdated(now)
      setIsInitialLoading(false)
      lastEventTsRef.current = now.getTime()
    }
  }, [])

  const startPolling = useCallback(() => {
    if (pollingTimerRef.current) return
    setStatus("fallback_polling")

    const poll = async () => {
      try {
        const data = await fetchDevices()
        applySnapshot(data.devices)
      } catch (err) {
        console.error("[Stream] Polling error:", err)
      }
    }

    poll()
    pollingTimerRef.current = setInterval(poll, POLLING_FALLBACK_MS)
  }, [applySnapshot])

  const stopPolling = useCallback(() => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current)
      pollingTimerRef.current = null
    }
  }, [])

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimerRef.current) return
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null
      connectSSERef.current()
    }, RECONNECT_DELAY_MS)
  }, [])

  const connectSSE = useCallback(() => {
    try {
      if (eventSourceRef.current && eventSourceRef.current.readyState === EventSource.OPEN) {
        return
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
      if (typeof window !== "undefined" && (window as any)[globalKey]) {
        try {
          ;(window as any)[globalKey].close()
        } catch {
          // ignore
        }
      }

      const es = new EventSource(SSE_URL)
      eventSourceRef.current = es
      if (typeof window !== "undefined") {
        ;(window as any)[globalKey] = es
      }
      setStatus("connecting")
      setError(null)

      const handleUpdate = (event: MessageEvent) => {
        try {
          const payload = JSON.parse(event.data) as DeviceUpdate
          updateBufferRef.current.set(payload.id, payload)
          lastEventTsRef.current = Date.now()
        } catch (err) {
          console.error("[Stream] Invalid SSE payload:", err)
        }
      }

      es.onmessage = handleUpdate
      es.addEventListener("device-update", handleUpdate)
      es.addEventListener("heartbeat", () => {
        lastEventTsRef.current = Date.now()
      })

      es.onerror = (err) => {
        console.error("[Stream] SSE Error:", err)
        setStatus("reconnecting")
        statusRef.current = "reconnecting"
        es.close()
        startPolling()
        scheduleReconnect()
      }

      es.onopen = () => {
        console.log("[Stream] SSE connected")
        setStatus("live")
        setError(null)
        stopPolling()
        lastEventTsRef.current = Date.now()
        clearReconnectTimer()
        statusRef.current = "live"
        if (connectTimeoutRef.current) {
          clearTimeout(connectTimeoutRef.current)
          connectTimeoutRef.current = null
        }
      }
    } catch (err) {
      console.error("[Stream] SSE init error:", err)
      setStatus("offline")
      setError("Falha na conexão SSE")
      startPolling()
      scheduleReconnect()
    }
  }, [scheduleReconnect, startPolling, stopPolling])

  useEffect(() => {
    statusRef.current = status
  }, [status])

  useEffect(() => {
    connectSSERef.current = connectSSE
  }, [connectSSE])

  useEffect(() => {
    if (initializedRef.current) return
    initializedRef.current = true
    isMountedRef.current = true

    connectSSE()
    if (connectTimeoutRef.current) clearTimeout(connectTimeoutRef.current)
    connectTimeoutRef.current = setTimeout(() => {
      if (statusRef.current === "connecting") {
        console.warn("[Stream] Still connecting - forcing reconnect")
        eventSourceRef.current?.close()
        startPolling()
        scheduleReconnect()
      }
    }, 4000)

    flushTimerRef.current = setInterval(flushUpdates, FLUSH_INTERVAL_MS)
    idleTimerRef.current = setInterval(() => {
      const now = Date.now()
      if (now - lastEventTsRef.current > IDLE_TIMEOUT_MS && statusRef.current !== "reconnecting") {
        console.warn("[Stream] Idle timeout - restarting SSE")
        setStatus("reconnecting")
        eventSourceRef.current?.close()
        startPolling()
        scheduleReconnect()
      }
    }, IDLE_CHECK_MS)

    const loadInitial = async () => {
      try {
        const data = await fetchDevices()
        applySnapshot(data.devices)
      } catch (err) {
        console.error("[Stream] Initial fetch error:", err)
        setIsInitialLoading(false)
      }
    }
    loadInitial()

    return () => {
      isMountedRef.current = false
      eventSourceRef.current?.close()
      if (flushTimerRef.current) clearInterval(flushTimerRef.current)
      if (pollingTimerRef.current) clearInterval(pollingTimerRef.current)
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      if (idleTimerRef.current) clearInterval(idleTimerRef.current)
      if (connectTimeoutRef.current) clearTimeout(connectTimeoutRef.current)
      initializedRef.current = false
    }
  }, [applySnapshot, connectSSE, flushUpdates, startPolling, stopPolling])

  return {
    devices,
    status,
    lastUpdated,
    error,
    isInitialLoading,
  }
}
