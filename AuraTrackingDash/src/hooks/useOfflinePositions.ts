"use client"

import { useCallback, useState } from "react"
import type { DeviceSummary } from "@/types/map/devices"

export type OfflinePositionsParams = {
  equipmentId?: string
  start: string
  end: string
  limit?: number
}

export type OfflinePositionsResult = {
  data: DeviceSummary[]
  isLoading: boolean
  isError: boolean
  errorMessage: string | null
  refetch: (params: OfflinePositionsParams) => Promise<void>
}

type ApiResponsePoint = {
  device_id?: string
  operator_id?: string | null
  lat?: number
  lon?: number
  ts?: string
  speed_kmh?: number | null
  speed?: number | null
  // GPS detalhado
  satellites?: number | null
  h_acc?: number | null
  v_acc?: number | null
  s_acc?: number | null
  // IMU expandido
  accel_magnitude?: number | null
  gyro_magnitude?: number | null
  mag_x?: number | null
  mag_y?: number | null
  mag_z?: number | null
  mag_magnitude?: number | null
  linear_accel_magnitude?: number | null
  // Orientação
  azimuth?: number | null
  pitch?: number | null
  roll?: number | null
  // Sistema
  battery_level?: number | null
  battery_status?: string | null
  battery_temperature?: number | null
  wifi_rssi?: number | null
  cellular_network_type?: string | null
  cellular_operator?: string | null
  cellular_rsrp?: number | null
  // Flag de transmissão
  transmission_mode?: "online" | "queued"
}

export function useOfflinePositions(): OfflinePositionsResult {
  const [data, setData] = useState<DeviceSummary[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const refetch = useCallback(async (params: OfflinePositionsParams) => {
    setIsLoading(true)
    setErrorMessage(null)
    setData([])
    try {
      const res = await fetch("/api/offline/positions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          equipmentId: params.equipmentId,
          start: params.start,
          end: params.end,
          limit: params.limit ?? 20000,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err?.error || "Falha ao carregar histórico")
      }
      const json = await res.json()
      const points: ApiResponsePoint[] = Array.isArray(json.points) ? json.points : []
      const mapped: DeviceSummary[] = points.map((p) => {
        const rawSpeed =
          typeof p.speed_kmh === "number" ? p.speed_kmh : typeof p.speed === "number" ? p.speed : null
        // normaliza para km/h: se vier em m/s, converte; se já vier em km/h (speed_kmh), mantém
        const speedKmh =
          rawSpeed == null
            ? null
            : typeof p.speed_kmh === "number"
              ? rawSpeed
              : rawSpeed * 3.6
        return {
          deviceId: p.device_id || "unknown",
          operatorId: p.operator_id || null,
          latitude: p.lat ?? null,
          longitude: p.lon ?? null,
          lastSeen: p.ts || null,
          status: "offline",
          speedKmh,
          totalPoints24h: null,
          // GPS detalhado
          satellites: p.satellites ?? null,
          hAcc: p.h_acc ?? null,
          vAcc: p.v_acc ?? null,
          sAcc: p.s_acc ?? null,
          // IMU expandido
          accelMagnitude: p.accel_magnitude ?? null,
          gyroMagnitude: p.gyro_magnitude ?? null,
          magX: p.mag_x ?? null,
          magY: p.mag_y ?? null,
          magZ: p.mag_z ?? null,
          magMagnitude: p.mag_magnitude ?? null,
          linearAccelMagnitude: p.linear_accel_magnitude ?? null,
          // Orientação
          azimuth: p.azimuth ?? null,
          pitch: p.pitch ?? null,
          roll: p.roll ?? null,
          // Sistema
          batteryLevel: p.battery_level ?? null,
          batteryStatus: p.battery_status ?? null,
          batteryTemperature: p.battery_temperature ?? null,
          wifiRssi: p.wifi_rssi ?? null,
          cellularNetworkType: p.cellular_network_type ?? null,
          cellularOperator: p.cellular_operator ?? null,
          cellularRsrp: p.cellular_rsrp ?? null,
          // Flag de transmissão
          transmissionMode: p.transmission_mode || "online",
        }
      })
      setData(mapped)
    } catch (err: any) {
      setErrorMessage(err?.message || "Erro ao carregar histórico")
    } finally {
      setIsLoading(false)
    }
  }, [])

  return {
    data,
    isLoading,
    isError: Boolean(errorMessage),
    errorMessage,
    refetch,
  }
}
