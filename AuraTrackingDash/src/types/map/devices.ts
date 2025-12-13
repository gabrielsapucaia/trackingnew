export type DeviceSummary = {
  deviceId: string
  operatorId: string | null
  lastSeen: string | null
  latitude: number | null
  longitude: number | null
  speedKmh: number | null
  totalPoints24h: number
  status: "online" | "offline"
  vibration?: number | null
  // GPS detalhado
  satellites?: number | null
  hAcc?: number | null
  vAcc?: number | null
  sAcc?: number | null
  // IMU expandido
  accelMagnitude?: number | null
  gyroMagnitude?: number | null
  magX?: number | null
  magY?: number | null
  magZ?: number | null
  magMagnitude?: number | null
  linearAccelMagnitude?: number | null
  // Orientação
  azimuth?: number | null
  pitch?: number | null
  roll?: number | null
  // Sistema
  batteryLevel?: number | null
  batteryStatus?: string | null
  batteryTemperature?: number | null
  wifiRssi?: number | null
  cellularNetworkType?: string | null
  cellularOperator?: string | null
  cellularRsrp?: number | null
  // Flag de transmissão
  transmissionMode?: "online" | "queued"
}

export type DevicesResponse = {
  devices: DeviceSummary[]
  count: number
}
