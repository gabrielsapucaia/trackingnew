"use client"

import MapView from "@/components/map/MapView"
import type { SpeedColorConfig } from "@/components/map/offlineLayers"
import type { DeviceSummary } from "@/types/map/devices"
import type { ConnectionStatus } from "@/components/map/useDeviceStream"
import { buildTrajectories, buildPathSegments } from "@/lib/map/trajectories"
import {
  createOfflinePathLayer,
  createOfflineHexLayer,
  createOfflineHeatmapLayer,
  createOfflineScreenGridLayer,
  createOfflineGridLayer,
} from "@/components/map/offlineLayers"
import type { Layer } from "@deck.gl/core"
import { mapPositionsToHexPoints } from "@/lib/map/hex"
import { useMemo, useState } from "react"

type OfflineMapMode = "scatter" | "path" | "hex" | "heatmap" | "screengrid" | "grid"

type OfflineMapProps = {
  mode: OfflineMapMode
  positions: DeviceSummary[]
  colorBySpeed?: SpeedColorConfig
  connectionStatus?: ConnectionStatus
  isLoading: boolean
  error: string | null
  hexOptions?: {
    radiusMeters?: number
    extruded?: boolean
  }
  heatmapOptions?: {
    radiusPixels?: number
    intensity?: number
  }
  screenGridOptions?: {
    cellSizePixels?: number
    opacity?: number
  }
  gridOptions?: {
    cellSizeMeters?: number
    opacity?: number
    useContinuous?: boolean
    autoAdjustCell?: boolean
  }
  basemapOpacity?: number
  orthoOpacity?: number
}

export function OfflineMap({
  mode,
  positions,
  colorBySpeed,
  connectionStatus,
  isLoading,
  error,
  hexOptions,
  heatmapOptions,
  screenGridOptions,
  gridOptions,
  basemapOpacity,
  orthoOpacity,
}: OfflineMapProps) {
  const [viewZoom, setViewZoom] = useState(15)

  const effectiveMode =
    mode === "path"
      ? "path"
      : mode === "hex"
        ? "hex"
        : mode === "heatmap"
          ? "heatmap"
          : mode === "screengrid"
            ? "screengrid"
            : mode === "grid"
              ? "grid"
              : "scatter"

  const { extraLayers, devicesToPass } = useMemo(() => {
    let layers: Layer[] = []
    let devices = positions

    if (effectiveMode === "path") {
      const segments = buildPathSegments(positions)
      layers = [
        createOfflinePathLayer({
          data: segments,
          colorBySpeed,
        }),
      ]
      devices = []
    } else if (effectiveMode === "hex") {
      const hexPoints = mapPositionsToHexPoints(positions)
      layers = [
        createOfflineHexLayer({
          data: hexPoints,
          colorBySpeed,
          radiusMeters: hexOptions?.radiusMeters ?? 40,
          extruded: hexOptions?.extruded ?? false,
        }),
      ]
      devices = []
    } else if (effectiveMode === "heatmap") {
      const heatPoints = mapPositionsToHexPoints(positions)
      layers = [
        createOfflineHeatmapLayer({
          data: heatPoints,
          colorBySpeed,
          radiusPixels: heatmapOptions?.radiusPixels ?? 40,
          intensity: heatmapOptions?.intensity ?? 1,
        }),
      ]
      devices = []
    } else if (effectiveMode === "screengrid") {
      const gridPoints = mapPositionsToHexPoints(positions)
      layers = [
        createOfflineScreenGridLayer({
          data: gridPoints,
          colorBySpeed,
          cellSizePixels: screenGridOptions?.cellSizePixels ?? 40,
          opacity: screenGridOptions?.opacity ?? 0.8,
        }),
      ]
      devices = []
    } else if (effectiveMode === "grid") {
      const gridPoints = mapPositionsToHexPoints(positions)
      const baseCell = gridOptions?.cellSizeMeters ?? 40
      const autoSize = gridOptions?.autoAdjustCell ?? false
      const computedCellSize = autoSize
        ? Math.min(200, Math.max(5, baseCell * Math.pow(2, viewZoom - 15)))
        : baseCell
      layers = [
        createOfflineGridLayer({
          data: gridPoints,
          colorBySpeed,
          cellSizeMeters: computedCellSize,
          opacity: gridOptions?.opacity ?? 0.8,
          useContinuous: gridOptions?.useContinuous ?? false,
        }),
      ]
      devices = []
    }

    return { extraLayers: layers, devicesToPass: devices }
  }, [
    effectiveMode,
    positions,
    colorBySpeed,
    hexOptions?.radiusMeters,
    hexOptions?.extruded,
    heatmapOptions?.radiusPixels,
    heatmapOptions?.intensity,
    screenGridOptions?.cellSizePixels,
    screenGridOptions?.opacity,
    gridOptions?.cellSizeMeters,
    gridOptions?.opacity,
    gridOptions?.useContinuous,
    gridOptions?.autoAdjustCell,
    viewZoom,
  ])

  return (
    <MapView
      devices={devicesToPass}
      useCompactMarkers={effectiveMode === "scatter"}
      colorBySpeed={colorBySpeed}
      connectionStatus={connectionStatus}
      isLoading={isLoading}
      error={error}
      extraLayers={extraLayers}
      basemapOpacity={basemapOpacity}
      orthoOpacity={orthoOpacity}
      onViewChange={(v) => {
        if (typeof v.zoom === "number") setViewZoom(v.zoom)
      }}
    />
  )
}
