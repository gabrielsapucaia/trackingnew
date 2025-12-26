import type { DeviceSummary } from "@/types/map/devices"

/**
 * A trajectory is a collection of coordinates forming a path,
 * with an associated speed value.
 */
export type Trajectory = {
  path: [number, number][] // Array of [lng, lat] coordinates
  speedKmh: number
  deviceId: string
}

/**
 * A path segment represents a portion of a device's movement path.
 * Used for coloring paths by speed.
 */
export type PathSegment = {
  path: [number, number][] // Array of [lng, lat] coordinates
  avgSpeed: number
  deviceId: string
}

/**
 * Groups consecutive positions by device to form trajectories.
 * Each device gets its own trajectory with the average speed.
 */
export function buildTrajectories(positions: DeviceSummary[]): Trajectory[] {
  const byDevice = new Map<string, DeviceSummary[]>()

  for (const pos of positions) {
    if (typeof pos.longitude !== "number" || typeof pos.latitude !== "number") continue
    const deviceId = pos.deviceId ?? "unknown"
    const list = byDevice.get(deviceId) ?? []
    list.push(pos)
    byDevice.set(deviceId, list)
  }

  const trajectories: Trajectory[] = []

  for (const [deviceId, points] of byDevice) {
    if (points.length < 2) continue

    const path: [number, number][] = points.map((p) => [
      p.longitude as number,
      p.latitude as number,
    ])

    const speeds = points
      .map((p) => p.speedKmh)
      .filter((s): s is number => typeof s === "number" && !Number.isNaN(s))

    const avgSpeed = speeds.length > 0 ? speeds.reduce((a, b) => a + b, 0) / speeds.length : 0

    trajectories.push({
      path,
      speedKmh: avgSpeed,
      deviceId,
    })
  }

  return trajectories
}

/**
 * Converts an array of DeviceSummary positions to path segments.
 * Creates one segment per device with its average speed.
 */
export function buildPathSegments(positions: DeviceSummary[]): PathSegment[] {
  const byDevice = new Map<string, DeviceSummary[]>()

  for (const pos of positions) {
    if (typeof pos.longitude !== "number" || typeof pos.latitude !== "number") continue
    const deviceId = pos.deviceId ?? "unknown"
    const list = byDevice.get(deviceId) ?? []
    list.push(pos)
    byDevice.set(deviceId, list)
  }

  const segments: PathSegment[] = []

  for (const [deviceId, points] of byDevice) {
    if (points.length < 2) continue

    const path: [number, number][] = points.map((p) => [
      p.longitude as number,
      p.latitude as number,
    ])

    const speeds = points
      .map((p) => p.speedKmh)
      .filter((s): s is number => typeof s === "number" && !Number.isNaN(s))

    const avgSpeed = speeds.length > 0 ? speeds.reduce((a, b) => a + b, 0) / speeds.length : 0

    segments.push({
      path,
      avgSpeed,
      deviceId,
    })
  }

  return segments
}
