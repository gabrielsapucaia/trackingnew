import type { DeviceSummary } from "@/types/map/devices"

/**
 * A point suitable for hex/heatmap/grid aggregation layers.
 */
export type HexPoint = {
  position: [number, number] // [lng, lat]
  speedKmh: number
}

/**
 * Converts an array of DeviceSummary positions to HexPoint format
 * for use with deck.gl aggregation layers (HexagonLayer, HeatmapLayer, etc.)
 */
export function mapPositionsToHexPoints(positions: DeviceSummary[]): HexPoint[] {
  return positions
    .filter((d) => typeof d.longitude === "number" && typeof d.latitude === "number")
    .map((d) => ({
      position: [d.longitude as number, d.latitude as number],
      speedKmh: typeof d.speedKmh === "number" ? d.speedKmh : 0,
    }))
}
