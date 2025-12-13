"use client"

import React, {
  useMemo,
  useRef,
  useState,
  useEffect,
  useCallback,
  useReducer,
  memo,
} from "react"
import "maplibre-gl/dist/maplibre-gl.css"
import { TextLayer, IconLayer } from "@deck.gl/layers"
import type { Layer, PickingInfo } from "@deck.gl/core"
import maplibregl from "maplibre-gl"
import Map, { useControl } from "react-map-gl/maplibre"
// @ts-ignore
import { MapboxOverlay } from "@deck.gl/mapbox"
import type { DeviceSummary } from "@/types/map/devices"
import type { ConnectionStatus } from "./useDeviceStream"
import { createOfflineScatterLayer } from "@/components/map/offlineLayers"

type MapViewProps = {
  devices: DeviceSummary[]
  isLoading: boolean
  error: string | null
  connectionStatus?: ConnectionStatus
  useCompactMarkers?: boolean
  colorBySpeed?: {
    breakpoints: number[] // ascending, length 3 e.g., [10,30,60]
    colors: [number, number, number, number?][] // 4 colors RGBA
  }
  extraLayers?: Layer[]
  onViewChange?: (view: { zoom: number }) => void
  basemapOpacity?: number
  orthoOpacity?: number
}

type ViewState = {
  latitude: number
  longitude: number
  zoom: number
  bearing: number
  pitch: number
}

const INITIAL_VIEW_STATE: ViewState = {
  latitude: -11.697240744252829,
  longitude: -47.16006885902949,
  zoom: 15,
  bearing: 0,
  pitch: 0,
}

const SATELLITE_STYLE = "/satellite-ortho-style.json"
const FALLBACK_STYLE = "/satellite-ortho-style-fallback.json"
const MAX_INIT_RETRIES = 2
const RENDER_DELAY_MS = 500
const TILE_ERROR_THRESHOLD = 5
const MIN_WEBGL_FRAMES = 5
const MAX_WEBGL_FRAMES = 7

type MapState =
  | { status: "checking-webgl" }
  | { status: "webgl-unsupported" }
  | { status: "loading-map" }
  | { status: "initializing-deckgl"; attempt: number }
  | { status: "ready" }
  | { status: "error"; message: string; canRetry: boolean }

type MapAction =
  | { type: "WEBGL_SUPPORTED" }
  | { type: "WEBGL_UNSUPPORTED" }
  | { type: "MAP_LOADED" }
  | { type: "DECKGL_INIT_START"; attempt: number }
  | { type: "DECKGL_INIT_SUCCESS" }
  | { type: "DECKGL_INIT_RETRY"; attempt: number }
  | { type: "DECKGL_ERROR"; message: string; canRetry: boolean }
  | { type: "RESET" }

function mapStateReducer(state: MapState, action: MapAction): MapState {
  switch (action.type) {
    case "WEBGL_SUPPORTED":
      if (state.status === "checking-webgl") return { status: "loading-map" }
      return state
    case "WEBGL_UNSUPPORTED":
      return { status: "webgl-unsupported" }
    case "MAP_LOADED":
      if (state.status === "loading-map") return { status: "initializing-deckgl", attempt: 0 }
      return state
    case "DECKGL_INIT_START":
      return { status: "initializing-deckgl", attempt: action.attempt }
    case "DECKGL_INIT_SUCCESS":
      return { status: "ready" }
    case "DECKGL_INIT_RETRY":
      if (action.attempt <= MAX_INIT_RETRIES) {
        return { status: "initializing-deckgl", attempt: action.attempt }
      }
      return { status: "error", message: "WebGL context not available after multiple attempts", canRetry: true }
    case "DECKGL_ERROR":
      return { status: "error", message: action.message, canRetry: action.canRetry }
    case "RESET":
      return { status: "checking-webgl" }
    default:
      return state
  }
}

const createAndTestWebGLContext = (): WebGLRenderingContext | WebGL2RenderingContext | null => {
  if (typeof window === "undefined") return null
  const canvas = document.createElement("canvas")
  let gl = canvas.getContext("webgl2", {
    antialias: false,
    preserveDrawingBuffer: false,
    failIfMajorPerformanceCaveat: false,
  }) as WebGL2RenderingContext | null
  if (gl) {
    try {
      const maxTexSize = gl.getParameter(gl.MAX_TEXTURE_SIZE)
      const maxViewportDims = gl.getParameter(gl.MAX_VIEWPORT_DIMS)
      if (!maxTexSize || !maxViewportDims) {
        gl = null
      } else {
        gl.getExtension("WEBGL_lose_context")
        return gl
      }
    } catch {
      gl = null
    }
  }
  const gl1 = canvas.getContext("webgl", {
    antialias: false,
    preserveDrawingBuffer: false,
    failIfMajorPerformanceCaveat: false,
  }) as WebGLRenderingContext | null
  if (gl1) {
    try {
      const maxTexSize = gl1.getParameter(gl1.MAX_TEXTURE_SIZE)
      const maxViewportDims = gl1.getParameter(gl1.MAX_VIEWPORT_DIMS)
      if (!maxTexSize || !maxViewportDims) return null
      return gl1
    } catch {
      return null
    }
  }
  return null
}

const cleanupWebGLContext = (gl: WebGLRenderingContext | WebGL2RenderingContext) => {
  const loseContext = gl.getExtension("WEBGL_lose_context")
  if (loseContext) loseContext.loseContext()
}

const waitForWebGLContextReady = async (): Promise<boolean> => {
  if (typeof window === "undefined") return false
  return new Promise((resolve) => {
    let frameCount = 0
    const maxFrames = Math.floor(Math.random() * (MAX_WEBGL_FRAMES - MIN_WEBGL_FRAMES + 1)) + MIN_WEBGL_FRAMES
    const check = () => {
      const canvas = document.createElement("canvas")
      const gl = canvas.getContext("webgl2") || canvas.getContext("webgl")
      if (gl && gl.getParameter(gl.MAX_TEXTURE_SIZE)) {
        resolve(true)
        return
      }
      frameCount++
      if (frameCount < maxFrames) {
        requestAnimationFrame(check)
      } else {
        resolve(false)
      }
    }
    requestAnimationFrame(check)
  })
}

const loadImageAsync = (src: string): Promise<HTMLImageElement> =>
  new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = src
  })

type DeckGLOverlayProps = {
  layers: Layer[]
  onClick: (info: PickingInfo) => void
  onHover: (info: PickingInfo) => void
}

const DeckGLOverlay = memo(function DeckGLOverlay({ layers, onClick, onHover }: DeckGLOverlayProps) {
  const overlay = useControl<MapboxOverlay>(
    () =>
      new MapboxOverlay({
        interleaved: false, // render em canvas separado para manter deck acima do mapa
        layers,
        onClick,
        onHover,
      })
  )

  useEffect(() => {
    overlay.setProps({
      layers,
      onClick,
      onHover,
    })

    // Garantir que o canvas do DeckGL fique acima do mapa base
    // (evita esconder agregações como ScreenGrid/Heatmap sob o ortomosaico).
    const canvas = (overlay as any)?._deck?.canvas as HTMLCanvasElement | undefined
    if (canvas) {
      canvas.style.zIndex = "5"
      canvas.style.position = "absolute"
      // Mantém o comportamento padrão de eventos do MapboxOverlay (não força pointerEvents aqui)
    }
  }, [overlay, layers, onClick, onHover])

  return null
})

type DeviceTooltipProps = {
  device: DeviceSummary
  x: number
  y: number
}

const DeviceTooltip = memo(function DeviceTooltip({ device, x, y }: DeviceTooltipProps) {
  const padding = 12
  const tooltipWidth = 200
  const tooltipHeight = 140
  let left = x - tooltipWidth / 2
  let top = y + 8
  if (typeof window !== "undefined" && left < padding) {
    left = padding
  }
  if (typeof window !== "undefined" && left + tooltipWidth > window.innerWidth - padding) {
    left = window.innerWidth - tooltipWidth - padding
  }
  if (typeof window !== "undefined" && top + tooltipHeight > window.innerHeight - padding) {
    top = y - tooltipHeight - 8
  }
  if (top < padding) top = padding

  const lastSeen = device.lastSeen ? new Date(device.lastSeen).toLocaleString("pt-BR") : "N/A"

  return (
    <div
      style={{
        position: "fixed",
        left,
        top,
        width: tooltipWidth,
        height: tooltipHeight,
        background: "rgba(15,23,42,0.9)",
        color: "#e2e8f0",
        border: "1px solid rgba(148,163,184,0.3)",
        borderRadius: 10,
        padding: "10px 12px",
        boxShadow: "0 10px 40px rgba(0,0,0,0.35)",
        zIndex: 2000,
        pointerEvents: "none",
        backdropFilter: "blur(6px)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700 }}>{device.deviceId}</div>
          <div style={{ fontSize: 12, color: "#94a3b8" }}>Operador: {device.operatorId || "N/A"}</div>
        </div>
        <span
          style={{
            fontSize: 11,
            color: device.status === "online" ? "#22c55e" : "#f97316",
            fontWeight: 600,
          }}
        >
          {device.status.toUpperCase()}
        </span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 4 }}>
        <div style={{ fontSize: 12, color: "#cbd5e1" }}>
          <div style={{ color: "#94a3b8", fontSize: 11 }}>Lat</div>
          <div style={{ fontWeight: 600 }}>{device.latitude?.toFixed(5) ?? "N/A"}</div>
        </div>
        <div style={{ fontSize: 12, color: "#cbd5e1" }}>
          <div style={{ color: "#94a3b8", fontSize: 11 }}>Lon</div>
          <div style={{ fontWeight: 600 }}>{device.longitude?.toFixed(5) ?? "N/A"}</div>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8 }}>
        <div style={{ fontSize: 12, color: "#cbd5e1" }}>
          <div style={{ color: "#94a3b8", fontSize: 11 }}>Vel. (km/h)</div>
          <div style={{ fontWeight: 600 }}>
            {typeof device.speedKmh === "number" ? device.speedKmh.toFixed(1) : "N/A"}
          </div>
        </div>
        <div style={{ fontSize: 12, color: "#cbd5e1" }}>
          <div style={{ color: "#94a3b8", fontSize: 11 }}>Pts 24h</div>
          <div style={{ fontWeight: 600 }}>{device.totalPoints24h ?? 0}</div>
        </div>
      </div>
      <div style={{ marginTop: 10, fontSize: 11, color: "#f8fafc" }}>Último sinal: {lastSeen}</div>
    </div>
  )
})

export default function MapView({
  devices,
  isLoading,
  error,
  connectionStatus,
  useCompactMarkers = false,
  colorBySpeed,
  extraLayers = [],
  onViewChange,
  basemapOpacity = 1,
  orthoOpacity = 1,
}: MapViewProps) {
  const mapRef = useRef<any>(null)
  const deckClickRef = useRef(false)
  const initTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const tileErrorCountRef = useRef(0)
  const containerRef = useRef<HTMLDivElement>(null)

  const [mapState, dispatch] = useReducer(mapStateReducer, { status: "checking-webgl" })
  const [mapStyle, setMapStyle] = useState(SATELLITE_STYLE)
  const [usingFallbackTiles, setUsingFallbackTiles] = useState(false)

  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null)
  const [hoveredDeviceId, setHoveredDeviceId] = useState<string | null>(null)
  const [tooltipPosition, setTooltipPosition] = useState<{ x: number; y: number } | null>(null)

  const selectedDevice = selectedDeviceId ? devices.find((d) => d.deviceId === selectedDeviceId) ?? null : null

  useEffect(() => {
    if (selectedDeviceId && !devices.find((d) => d.deviceId === selectedDeviceId)) {
      setSelectedDeviceId(null)
      setTooltipPosition(null)
    }
  }, [devices, selectedDeviceId])

  useEffect(() => {
    if (!selectedDevice) return
    if (selectedDevice.latitude == null || selectedDevice.longitude == null) return
    const map = mapRef.current?.getMap?.()
    if (!map) return

    const updatePosition = () => {
      const point = map.project([selectedDevice.longitude as number, selectedDevice.latitude as number])
      const rect = containerRef.current?.getBoundingClientRect()
      const x = point.x + (rect?.left ?? 0)
      const y = point.y + (rect?.top ?? 0)
      setTooltipPosition({ x, y })
    }

    updatePosition()
    map.on("move", updatePosition)
    map.on("zoom", updatePosition)
    map.on("resize", updatePosition)

    return () => {
      map.off("move", updatePosition)
      map.off("zoom", updatePosition)
      map.off("resize", updatePosition)
    }
  }, [selectedDevice])

  useEffect(() => {
    if (typeof window === "undefined") return
    const testContext = createAndTestWebGLContext()
    if (testContext) {
      cleanupWebGLContext(testContext)
      dispatch({ type: "WEBGL_SUPPORTED" })
    } else {
      dispatch({ type: "WEBGL_UNSUPPORTED" })
    }
    return () => {
      if (initTimeoutRef.current) clearTimeout(initTimeoutRef.current)
    }
  }, [])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setSelectedDeviceId(null)
        setTooltipPosition(null)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  useEffect(() => {
    if (typeof window === "undefined") return
    const handleError = (event: ErrorEvent) => {
      if (
        event.message &&
        (event.message.includes("maxTextureDimension2D") ||
          event.message.includes("WebGL") ||
          event.message.includes("DeckGL"))
      ) {
        if (mapState.status === "ready" || mapState.status === "initializing-deckgl") {
          dispatch({ type: "DECKGL_ERROR", message: "WebGL context error detected", canRetry: true })
        }
      }
    }
    window.addEventListener("error", handleError)
    return () => window.removeEventListener("error", handleError)
  }, [mapState.status])

  const checkStyleHealth = useCallback(async () => {
    try {
      await loadImageAsync("/ortho.webp")
      await loadImageAsync("/dump-truck.png")
      return true
    } catch {
      return false
    }
  }, [])

  const handleTileError = useCallback(async () => {
    tileErrorCountRef.current += 1
    if (tileErrorCountRef.current >= TILE_ERROR_THRESHOLD && !usingFallbackTiles) {
      setUsingFallbackTiles(true)
      setMapStyle(FALLBACK_STYLE)
    }
  }, [usingFallbackTiles])

  // aplica opacidades quando props mudam e o mapa existe
  useEffect(() => {
    const map = mapRef.current?.getMap?.()
    if (!map) return
    try {
      if (map.getLayer("satellite-layer")) {
        map.setPaintProperty("satellite-layer", "raster-opacity", basemapOpacity)
      }
      if (map.getLayer("ortho-layer")) {
        map.setPaintProperty("ortho-layer", "raster-opacity", orthoOpacity)
      }
    } catch {
      // ignore paint errors
    }
  }, [basemapOpacity, orthoOpacity, mapState.status])

  const onMapLoad = useCallback(
    async (event: maplibregl.MapLibreEvent) => {
      const map = event.target
      await waitForWebGLContextReady()
      const isStyleHealthy = await checkStyleHealth()
      if (!isStyleHealthy) {
        setUsingFallbackTiles(true)
        setMapStyle(FALLBACK_STYLE)
      }
      const retryDeckGLInit = (attempt: number) => {
        dispatch({ type: "DECKGL_INIT_START", attempt })
        initTimeoutRef.current = setTimeout(() => {
          if (map.isStyleLoaded()) {
            const canvas = map.getCanvas()
            const gl = canvas?.getContext("webgl2") || canvas?.getContext("webgl")
            if (gl && gl.getParameter(gl.MAX_TEXTURE_SIZE)) {
              dispatch({ type: "DECKGL_INIT_SUCCESS" })
            } else if (attempt < MAX_INIT_RETRIES) {
              retryDeckGLInit(attempt + 1)
            } else {
              dispatch({
                type: "DECKGL_ERROR",
                message: "WebGL context not available",
                canRetry: true,
              })
            }
          } else {
            dispatch({
              type: "DECKGL_ERROR",
              message: "Map style not loaded",
              canRetry: true,
            })
          }
        }, RENDER_DELAY_MS)
      }

      if (map.isStyleLoaded()) {
        retryDeckGLInit(0)
      } else {
        map.on("load", () => retryDeckGLInit(0))
      }

      if (map.getStyle()?.sources?.["satellite"]) {
        map.on("error", (e) => {
          if ((e as any).error?.status === 404) handleTileError()
        })
      }

      if (map.on) {
        map.on("moveend", () => {
          if (map.getBounds()) {
            const bounds = map.getBounds()
            setMapBounds([bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()])
          }
          onViewChange?.({ zoom: map.getZoom() })
        })
        map.on("move", () => {
          onViewChange?.({ zoom: map.getZoom() })
        })

        if (map.getBounds()) {
          const bounds = map.getBounds()
          setMapBounds([bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()])
        }
        onViewChange?.({ zoom: map.getZoom() })
      }

    // aplica opacidades iniciais se as camadas existirem
    try {
      if (map.getLayer("satellite-layer")) map.setPaintProperty("satellite-layer", "raster-opacity", basemapOpacity)
      if (map.getLayer("ortho-layer")) map.setPaintProperty("ortho-layer", "raster-opacity", orthoOpacity)
    } catch {
      // ignore paint errors
    }

      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (mapRef.current) {
            const innerMap = mapRef.current.getMap()
            if (innerMap && innerMap.isStyleLoaded()) {
              dispatch({ type: "MAP_LOADED" })
            } else {
              setTimeout(() => {
                if (mapRef.current?.getMap()?.isStyleLoaded()) dispatch({ type: "MAP_LOADED" })
              }, 300)
            }
          }
        })
      })
    },
    [checkStyleHealth, handleTileError]
  )

  const handleMapClick = useCallback(() => {
    if (deckClickRef.current) {
      deckClickRef.current = false
      return
    }
    setSelectedDeviceId(null)
    setTooltipPosition(null)
  }, [])

  const handleDeckClick = useCallback(
    (info: PickingInfo) => {
      if (
        info.object &&
        (info.layer?.id === "devices-truck-icon-layer" || info.layer?.id === "devices-label-layer")
      ) {
        deckClickRef.current = true
        const clickedDevice = info.object as DeviceSummary
        const rect = containerRef.current?.getBoundingClientRect()
        const screenX = rect ? rect.left + info.x : info.x
        const screenY = rect ? rect.top + info.y : info.y
        if (selectedDeviceId === clickedDevice.deviceId) {
          setSelectedDeviceId(null)
          setTooltipPosition(null)
        } else {
          setSelectedDeviceId(clickedDevice.deviceId)
          setTooltipPosition({ x: screenX, y: screenY })
        }
      }
    },
    [selectedDeviceId]
  )

  const handleDeckHover = useCallback((info: PickingInfo) => {
    if (
      info.object &&
      (info.layer?.id === "devices-truck-icon-layer" || info.layer?.id === "devices-label-layer")
    ) {
      setHoveredDeviceId((info.object as DeviceSummary).deviceId)
    } else {
      setHoveredDeviceId(null)
    }
  }, [])

  const validDevices = useMemo(() => devices.filter((d) => d.latitude !== null && d.longitude !== null), [devices])
  const [mapBounds, setMapBounds] = useState<[number, number, number, number] | null>(null)
  const visibleDevices = useMemo(() => {
    if (!mapBounds || !mapRef.current) return validDevices
    const [west, south, east, north] = mapBounds
    return validDevices.filter((device) => {
      const lon = device.longitude as number
      const lat = device.latitude as number
      return lon >= west && lon <= east && lat >= south && lat <= north
    })
  }, [validDevices, mapBounds])

  const devicesKey = useMemo(
    () => validDevices.map((d) => `${d.deviceId}:${d.status}:${d.latitude}:${d.longitude}`).join("|"),
    [validDevices]
  )

  const layers = useMemo(() => {
    if (mapState.status !== "ready") return []
    const renderDevices = visibleDevices.length > 0 ? visibleDevices : validDevices

    if (useCompactMarkers) {
      return [
        createOfflineScatterLayer({
          data: renderDevices,
          devicesKey,
          colorBySpeed,
        }),
      ]
    }

    const baseLayers = useCompactMarkers
      ? [
          createOfflineScatterLayer({
            data: renderDevices,
            devicesKey,
            colorBySpeed,
          }),
        ]
      : [
          new IconLayer<DeviceSummary>({
            id: "devices-truck-icon-layer",
            data: renderDevices,
            getPosition: (d) => [d.longitude as number, d.latitude as number],
            getIcon: () => ({
              url: "/dump-truck.png",
              width: 512,
              height: 512,
              mask: false,
              anchorX: 256,
              anchorY: 480,
            }),
            getSize: 43,
            sizeUnits: "pixels",
            sizeMinPixels: 40,
            sizeMaxPixels: 50,
            pickable: true,
            parameters: {
              depthTest: false,
            },
            updateTriggers: {
              getPosition: [devicesKey],
            },
          }),

          new TextLayer<DeviceSummary>({
            id: "devices-label-layer",
            data: renderDevices,
            getPosition: (d) => [d.longitude as number, d.latitude as number],
            getText: (d) => d.deviceId,
            getSize: 11,
            sizeUnits: "pixels",
            getColor: [255, 255, 255, 255],
            getTextAnchor: "middle",
            getAlignmentBaseline: "center",
            getPixelOffset: [0, -40],
            fontFamily: "system-ui, -apple-system, sans-serif",
            fontWeight: 700,
            background: true,
            getBackgroundColor: (d) => {
              const isHighlighted = hoveredDeviceId === d.deviceId || selectedDeviceId === d.deviceId
              return isHighlighted ? [59, 130, 246, 200] : [0, 0, 0, 102]
            },
            backgroundPadding: [6, 3, 6, 3],
            pickable: true,
            updateTriggers: {
              getPosition: [devicesKey],
              getText: [devicesKey],
              getBackgroundColor: [hoveredDeviceId, selectedDeviceId],
            },
          }),
        ]

    return [
      ...baseLayers,
      ...extraLayers,
    ]
  }, [
    visibleDevices,
    validDevices,
    mapState.status,
    devicesKey,
    hoveredDeviceId,
    selectedDeviceId,
    useCompactMarkers,
    colorBySpeed,
    extraLayers,
  ])

  const showDeckGL = mapState.status === "ready"
  const showError = mapState.status === "error"
  const showWebGLWarning = mapState.status === "webgl-unsupported"

  return (
    <section
      ref={containerRef}
      style={{
        position: "relative",
        width: "100%",
        height: "70vh",
        borderRadius: "12px",
        overflow: "hidden",
        border: "1px solid #2d2d2d",
        background: "#0b0b0b",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 12,
          right: 12,
          zIndex: 1000,
          display: "flex",
          alignItems: "center",
          gap: "8px",
          background: "rgba(0,0,0,0.6)",
          backdropFilter: "blur(4px)",
          padding: "6px 12px",
          borderRadius: "20px",
          border: "1px solid rgba(255,255,255,0.08)",
          boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
        }}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            fontSize: 12,
            color:
              connectionStatus === "live"
                ? "#22c55e"
                : connectionStatus === "reconnecting"
                  ? "#f59e0b"
                  : "#94a3b8",
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "9999px",
              background:
                connectionStatus === "live"
                  ? "#22c55e"
                  : connectionStatus === "reconnecting"
                    ? "#f59e0b"
                    : "#94a3b8",
            }}
          />
          {connectionStatus === "connecting"
            ? "CONNECTING"
            : connectionStatus === "live"
              ? "LIVE"
              : connectionStatus === "reconnecting"
                ? "RECONNECTING"
                : connectionStatus === "fallback_polling"
                  ? "FALLBACK"
                  : "OFFLINE"}
        </span>
        <span
          style={{
            borderLeft: "1px solid rgba(255,255,255,0.2)",
            paddingLeft: "8px",
            marginLeft: "4px",
            color: "rgba(255,255,255,0.6)",
          }}
        >
          {validDevices.length} DEVICES
        </span>
      </div>

      <div style={{ width: "100%", height: "100%", position: "relative" }}>
        <Map
          ref={mapRef}
          mapLib={maplibregl}
          mapStyle={mapStyle}
          initialViewState={INITIAL_VIEW_STATE}
          onLoad={onMapLoad}
          onClick={handleMapClick}
          style={{ width: "100%", height: "100%", position: "relative", zIndex: 1 }}
        >
          {showDeckGL && (
            <DeckGLOverlay layers={layers} onClick={handleDeckClick} onHover={handleDeckHover} />
          )}
        </Map>
      </div>

      {selectedDevice && tooltipPosition && (
        <DeviceTooltip device={selectedDevice} x={tooltipPosition.x} y={tooltipPosition.y} />
      )}

      {isLoading && (
        <div
          style={{
            position: "absolute",
            top: 12,
            left: 12,
            padding: "6px 10px",
            borderRadius: 8,
            background: "rgba(0,0,0,0.65)",
            color: "#e2e8f0",
            fontSize: 12,
            pointerEvents: "none",
            zIndex: 1000,
          }}
        >
          Carregando dispositivos…
        </div>
      )}

      {error && (
        <div
          style={{
            position: "absolute",
            top: 50,
            right: 12,
            padding: "6px 10px",
            borderRadius: 8,
            background: "rgba(248,113,113,0.8)",
            color: "#111",
            fontSize: 12,
            zIndex: 1000,
          }}
        >
          Erro: {error}
        </div>
      )}

      {showWebGLWarning && (
        <div
          style={{
            position: "absolute",
            bottom: 12,
            left: 12,
            padding: "8px 12px",
            borderRadius: 8,
            background: "rgba(251, 191, 36, 0.9)",
            color: "#111",
            fontSize: 11,
            zIndex: 1000,
            boxShadow: "0 6px 20px rgba(0,0,0,0.25)",
          }}
        >
          Seu navegador ou dispositivo não suporta WebGL suficiente para esta visualização.
        </div>
      )}

      {showError && (
        <div
          style={{
            position: "absolute",
            bottom: 12,
            right: 12,
            padding: "8px 12px",
            borderRadius: 8,
            background: "rgba(248,113,113,0.9)",
            color: "#111",
            fontSize: 11,
            zIndex: 1000,
            boxShadow: "0 6px 20px rgba(0,0,0,0.25)",
          }}
        >
          Erro ao renderizar mapa.{" "}
          <button
            style={{ textDecoration: "underline", fontWeight: 700 }}
            onClick={() => dispatch({ type: "RESET" })}
          >
            Tentar novamente
          </button>
        </div>
      )}

      {usingFallbackTiles && (
        <div
          style={{
            position: "absolute",
            bottom: 12,
            left: "50%",
            transform: "translateX(-50%)",
            padding: "8px 12px",
            borderRadius: 8,
            background: "rgba(59, 130, 246, 0.9)",
            color: "#f8fafc",
            fontSize: 11,
            zIndex: 1000,
            boxShadow: "0 6px 20px rgba(0,0,0,0.25)",
          }}
        >
          Usando tiles em fallback devido a erros de carregamento.
        </div>
      )}
    </section>
  )
}
