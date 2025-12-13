import { ScatterplotLayer, PathLayer } from "@deck.gl/layers"
import { HexagonLayer, HeatmapLayer, ScreenGridLayer, GridLayer } from "@deck.gl/aggregation-layers"
import type { DeviceSummary } from "@/types/map/devices"
import type { Trajectory, PathSegment } from "@/lib/map/trajectories"
import type { HexPoint } from "@/lib/map/hex"

export type SpeedColorConfig = {
  breakpoints: number[] // length 3 (three thresholds -> four colors)
  colors: [number, number, number, number?][] // length 4
}

type OfflineScatterOptions = {
  data: DeviceSummary[]
  devicesKey: string
  colorBySpeed?: SpeedColorConfig
  id?: string
}

type OfflinePathOptions = {
  data: Array<Trajectory | PathSegment>
  colorBySpeed?: SpeedColorConfig
  id?: string
}

type OfflineHexOptions = {
  data: HexPoint[]
  colorBySpeed?: SpeedColorConfig
  id?: string
  visible?: boolean
  radiusMeters?: number
  extruded?: boolean
}

type OfflineHeatmapOptions = {
  data: HexPoint[]
  colorBySpeed?: SpeedColorConfig
  id?: string
  visible?: boolean
  radiusPixels?: number
  intensity?: number
}

type OfflineScreenGridOptions = {
  data: HexPoint[]
  colorBySpeed?: SpeedColorConfig
  id?: string
  visible?: boolean
  cellSizePixels?: number
  opacity?: number
}

type OfflineGridLayerOptions = {
  data: HexPoint[]
  colorBySpeed?: SpeedColorConfig
  id?: string
  visible?: boolean
  cellSizeMeters?: number
  opacity?: number
  useContinuous?: boolean
}

const STATUS_COLORS: Record<string, [number, number, number, number]> = {
  online: [34, 197, 94, 220],
  offline: [248, 113, 113, 220],
}

const toRgba = (color: number[]): [number, number, number, number] => {
  if (color.length === 4) return color as [number, number, number, number]
  if (color.length === 3) return [color[0], color[1], color[2], 220]
  return [255, 255, 255, 220]
}

export function createOfflineScatterLayer(options: OfflineScatterOptions) {
  const { data, devicesKey, colorBySpeed, id = "devices-compact-layer" } = options

  const getStatusColor = (d: DeviceSummary) =>
    STATUS_COLORS[d.status] ?? STATUS_COLORS.offline

  const getSpeedColor = (d: DeviceSummary) => {
    if (!colorBySpeed) return getStatusColor(d)
    const speed = d.speedKmh
    if (typeof speed !== "number" || Number.isNaN(speed)) return getStatusColor(d)
    const [c0, c1, c2, c3] = colorBySpeed.colors.map(toRgba)
    const [b0, b1, b2] = colorBySpeed.breakpoints
    if (speed <= b0) return c0
    if (speed <= b1) return c1
    if (speed <= b2) return c2
    return c3
  }

  return new ScatterplotLayer<DeviceSummary>({
    id,
    data,
    getPosition: (d) => [d.longitude as number, d.latitude as number],
    getRadius: 8,
    radiusUnits: "pixels",
    radiusMinPixels: 6,
    radiusMaxPixels: 10,
    getFillColor: (d) => getSpeedColor(d),
    pickable: true,
    updateTriggers: {
      getPosition: [devicesKey],
      getFillColor: [devicesKey, colorBySpeed],
    },
  })
}

export function createOfflinePathLayer(options: OfflinePathOptions) {
  const { data, colorBySpeed, id = "devices-path-layer" } = options

  const getSpeedColor = (t: Trajectory | PathSegment) => {
    if (!colorBySpeed) return STATUS_COLORS.offline
    const speed = "speedKmh" in t ? t.speedKmh : t.avgSpeed
    if (typeof speed !== "number" || Number.isNaN(speed)) return STATUS_COLORS.offline
    const [c0, c1, c2, c3] = colorBySpeed.colors.map(toRgba)
    const [b0, b1, b2] = colorBySpeed.breakpoints
    if (speed <= b0) return c0
    if (speed <= b1) return c1
    if (speed <= b2) return c2
    return c3
  }

  return new PathLayer<Trajectory>({
    id,
    data,
    getPath: (d) => d.path,
    getColor: (d) => getSpeedColor(d),
    widthUnits: "pixels",
    getWidth: 4,
    pickable: true,
    parameters: { depthTest: false },
    updateTriggers: {
      getColor: [colorBySpeed?.breakpoints, colorBySpeed?.colors],
    },
  })
}

export function createOfflineHexLayer(options: OfflineHexOptions) {
  const {
    data,
    colorBySpeed,
    id = "offline-hex",
    visible = true,
    radiusMeters = 40,
    extruded = false,
  } = options

  const getSpeedColor = (avgSpeed: number) => {
    if (!colorBySpeed) return STATUS_COLORS.offline
    const [c0, c1, c2, c3] = colorBySpeed.colors.map(toRgba)
    const [b0, b1, b2] = colorBySpeed.breakpoints
    if (avgSpeed <= b0) return c0
    if (avgSpeed <= b1) return c1
    if (avgSpeed <= b2) return c2
    return c3
  }

  return new HexagonLayer<HexPoint>({
    id,
    visible,
    data,
    getPosition: (p) => p.position,
    getColorWeight: (p) => p.speedKmh,
    colorAggregation: "MEAN",
    getElevationWeight: () => 1,
    elevationAggregation: "SUM",
    extruded,
    radius: radiusMeters,
    pickable: true,
    getFillColor: (obj) => {
      // deck.gl passes aggregation info via colorValue when using aggregation layers
      // colorValue is the aggregated color weight (mean speed here)
      // @ts-expect-error - colorValue injected by deck.gl
      const avg = typeof obj?.colorValue === "number" ? obj.colorValue : 0
      return getSpeedColor(avg)
    },
    updateTriggers: {
      getFillColor: [colorBySpeed],
      getPosition: [data],
    },
  })
}

export function createOfflineHeatmapLayer(options: OfflineHeatmapOptions) {
  const {
    data,
    colorBySpeed,
    id = "offline-heatmap",
    visible = true,
    radiusPixels = 40,
    intensity = 1,
  } = options

  const colorRange =
    colorBySpeed &&
    [
      toRgba([...colorBySpeed.colors[0].slice(0, 3), 255]),
      toRgba([...colorBySpeed.colors[1].slice(0, 3), 255]),
      toRgba([...colorBySpeed.colors[2].slice(0, 3), 255]),
      toRgba([...colorBySpeed.colors[3].slice(0, 3), 255]),
      toRgba([...colorBySpeed.colors[3].slice(0, 3), 255]),
      toRgba([...colorBySpeed.colors[3].slice(0, 3), 255]),
    ]

  const colorDomain =
    colorBySpeed && colorBySpeed.breakpoints.length === 3
      ? [colorBySpeed.breakpoints[0], colorBySpeed.breakpoints[2]]
      : undefined

  return new HeatmapLayer<HexPoint>({
    id,
    visible,
    data,
    getPosition: (p) => p.position,
    getWeight: (p) => (typeof p.speedKmh === "number" ? p.speedKmh : 0),
    aggregation: "MEAN",
    radiusPixels,
    intensity,
    pickable: true,
    getColorWeight: (p) => (typeof p.speedKmh === "number" ? p.speedKmh : 0),
    colorAggregation: "MEAN",
    colorDomain,
    updateTriggers: {
      getWeight: [data, colorBySpeed?.breakpoints],
      getColorWeight: [data, colorBySpeed?.breakpoints],
      colorDomain: [colorBySpeed?.breakpoints],
    },
    colorRange: colorRange ?? undefined,
    parameters: { depthTest: false },
  })
}

export function createOfflineScreenGridLayer(options: OfflineScreenGridOptions) {
  const {
    data,
    colorBySpeed,
    id = "offline-screengrid",
    visible = true,
    cellSizePixels = 40,
    opacity = 0.8,
  } = options

  const toSpeedValue = (value: number | null | undefined) =>
    typeof value === "number" && Number.isFinite(value) ? value : 0

  const colorRange = colorBySpeed
    ? [
        toRgba(colorBySpeed.colors[0]),
        toRgba(colorBySpeed.colors[1]),
        toRgba(colorBySpeed.colors[2]),
        toRgba(colorBySpeed.colors[3]),
        toRgba(colorBySpeed.colors[3]),
        toRgba(colorBySpeed.colors[3]),
      ]
    : undefined

  const bucketize = (speedKmh: number) => {
    if (!colorBySpeed) return speedKmh
    const [b0, b1, b2] = colorBySpeed.breakpoints
    if (speedKmh <= b0) return 0
    if (speedKmh <= b1) return 1
    if (speedKmh <= b2) return 2
    return 3
  }

  return new ScreenGridLayer<HexPoint>({
    id,
    visible,
    data,
    getPosition: (p) => p.position,
    getWeight: (p) => bucketize(toSpeedValue(p.speedKmh)),
    // média dos buckets por célula para refletir velocidade média daquela célula
    colorAggregation: "MEAN",
    colorDomain: [0, 3],
    cellSizePixels,
    opacity,
    pickable: true,
    colorRange,
    parameters: { depthTest: false, depthMask: false, blend: true },
    // manter acima das tiles do mapa
    extensions: [],
    updateTriggers: {
      getPosition: [data],
      getWeight: [data, colorBySpeed?.breakpoints],
      colorDomain: [colorBySpeed?.breakpoints],
      colorRange: [colorBySpeed?.colors],
    },
  })
}

export function createOfflineGridLayer(options: OfflineGridLayerOptions) {
  const {
    data,
    colorBySpeed,
    id = "offline-gridlayer",
    visible = true,
    cellSizeMeters = 40,
    opacity = 0.8,
    useContinuous = false,
  } = options

  const toSpeedValue = (value: number | null | undefined) =>
    typeof value === "number" && Number.isFinite(value) ? value : 0

  // Para bucket mode usamos 4 cores (0..3). Em contínuo, usamos o mesmo range interpolado.
  const colorRange =
    colorBySpeed && !useContinuous
      ? [
          toRgba(colorBySpeed.colors[0]),
          toRgba(colorBySpeed.colors[1]),
          toRgba(colorBySpeed.colors[2]),
          toRgba(colorBySpeed.colors[3]),
        ]
      : colorBySpeed && useContinuous
        ? [
            toRgba(colorBySpeed.colors[0]),
            toRgba(colorBySpeed.colors[1]),
            toRgba(colorBySpeed.colors[2]),
            toRgba(colorBySpeed.colors[3]),
          ]
        : undefined

  const bucketize = (speed: number) => {
    if (!colorBySpeed) return speed
    const [b0, b1, b2] = colorBySpeed.breakpoints
    if (speed <= b0) return 0
    if (speed <= b1) return 1
    if (speed <= b2) return 2
    return 3
  }

  return new GridLayer<HexPoint>({
    id,
    visible,
    data,
    getPosition: (p) => p.position,
    getWeight: (p) => {
      const speed = toSpeedValue(p.speedKmh)
      return useContinuous ? speed : bucketize(speed)
    },
    getColorWeight: (p) => {
      const speed = toSpeedValue(p.speedKmh)
      return useContinuous ? speed : bucketize(speed)
    },
    cellSize: cellSizeMeters,
    colorAggregation: "MEAN",
    colorDomain: useContinuous
      ? colorBySpeed
        ? [colorBySpeed.breakpoints[0], colorBySpeed.breakpoints[2]]
        : undefined
      : [0, 3],
    colorRange,
    opacity,
    pickable: true,
    parameters: { depthTest: false, depthMask: false, blend: true },
    updateTriggers: {
      getPosition: [data],
      getWeight: [data, colorBySpeed?.breakpoints],
      getColorWeight: [data, colorBySpeed?.breakpoints],
      colorDomain: [colorBySpeed?.breakpoints],
      colorRange: [colorBySpeed?.colors],
      useContinuous,
    },
  })
}
