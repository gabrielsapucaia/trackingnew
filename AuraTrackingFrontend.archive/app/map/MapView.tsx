"use client";

import React, { useMemo, useRef, useState, useEffect, useCallback, useReducer, memo } from "react";
import { ScatterplotLayer, TextLayer, IconLayer } from "@deck.gl/layers";
import type { Layer, PickingInfo } from "@deck.gl/core";
import maplibregl from "maplibre-gl";
import Map, { useControl } from "react-map-gl/maplibre";
// @ts-ignore
import { MapboxOverlay } from "@deck.gl/mapbox"; // @ts-ignore
import type { DeviceSummary } from "../../types/devices";
import type { ViewStateChangeEvent } from "react-map-gl/maplibre";
import type { ConnectionStatus } from "./useDeviceStream";

// Debug logging - only enabled in development
const isDev = process.env.NODE_ENV === 'development';
const debugLog = (...args: unknown[]) => {
  if (isDev) console.log(...args);
};
const debugWarn = (...args: unknown[]) => {
  if (isDev) console.warn(...args);
};
const debugError = (...args: unknown[]) => {
  if (isDev) console.error(...args);
};

type MapViewProps = {
  devices: DeviceSummary[];
  isLoading: boolean;
  error: string | null;
  connectionStatus?: ConnectionStatus;
};

type ViewState = {
  latitude: number;
  longitude: number;
  zoom: number;
  bearing: number;
  pitch: number;
};

const INITIAL_VIEW_STATE: ViewState = {
  latitude: -11.57,
  longitude: -47.18,
  zoom: 12,
  bearing: 0,
  pitch: 0
};

// Map style configuration with fallback
const SATELLITE_STYLE = "/satellite-ortho-style.json";
const FALLBACK_STYLE = "/satellite-ortho-style-fallback.json";

// Maximum retry attempts for DeckGL initialization
const MAX_INIT_RETRIES = 2;
// Delay before allowing DeckGL render after initialization
const RENDER_DELAY_MS = 500;
// Number of tile errors before switching to fallback
const TILE_ERROR_THRESHOLD = 5;
// Minimum frames to wait for WebGL stability
const MIN_WEBGL_FRAMES = 5;
const MAX_WEBGL_FRAMES = 7;

// Layer configuration

// ============================================================================
// Map State Machine
// ============================================================================

type MapState = 
  | { status: 'checking-webgl' }
  | { status: 'webgl-unsupported' }
  | { status: 'loading-map' }
  | { status: 'initializing-deckgl'; attempt: number }
  | { status: 'ready' }
  | { status: 'error'; message: string; canRetry: boolean };

type MapAction =
  | { type: 'WEBGL_SUPPORTED' }
  | { type: 'WEBGL_UNSUPPORTED' }
  | { type: 'MAP_LOADED' }
  | { type: 'DECKGL_INIT_START'; attempt: number }
  | { type: 'DECKGL_INIT_SUCCESS' }
  | { type: 'DECKGL_INIT_RETRY'; attempt: number }
  | { type: 'DECKGL_ERROR'; message: string; canRetry: boolean }
  | { type: 'RESET' };

function mapStateReducer(state: MapState, action: MapAction): MapState {
  debugLog('[MapState]', state.status, '->', action.type);
  
  switch (action.type) {
    case 'WEBGL_SUPPORTED':
      if (state.status === 'checking-webgl') {
        return { status: 'loading-map' };
      }
      return state;
      
    case 'WEBGL_UNSUPPORTED':
      return { status: 'webgl-unsupported' };
      
    case 'MAP_LOADED':
      if (state.status === 'loading-map') {
        return { status: 'initializing-deckgl', attempt: 0 };
      }
      return state;
      
    case 'DECKGL_INIT_START':
      return { status: 'initializing-deckgl', attempt: action.attempt };
      
    case 'DECKGL_INIT_SUCCESS':
      return { status: 'ready' };
      
    case 'DECKGL_INIT_RETRY':
      if (action.attempt <= MAX_INIT_RETRIES) {
        return { status: 'initializing-deckgl', attempt: action.attempt };
      }
      return { 
        status: 'error', 
        message: 'WebGL context not available after multiple attempts',
        canRetry: true 
      };
      
    case 'DECKGL_ERROR':
      return { 
        status: 'error', 
        message: action.message,
        canRetry: action.canRetry 
      };
      
    case 'RESET':
      return { status: 'checking-webgl' };
      
    default:
      return state;
  }
}

// ============================================================================
// WebGL Utilities
// ============================================================================

const createAndTestWebGLContext = (): WebGLRenderingContext | WebGL2RenderingContext | null => {
  if (typeof window === "undefined") return null;
  
  const canvas = document.createElement("canvas");
  
  let gl = canvas.getContext("webgl2", {
    antialias: false,
    preserveDrawingBuffer: false,
    failIfMajorPerformanceCaveat: false
  }) as WebGL2RenderingContext | null;
  
  if (gl) {
    try {
      const maxTexSize = gl.getParameter(gl.MAX_TEXTURE_SIZE);
      const maxViewportDims = gl.getParameter(gl.MAX_VIEWPORT_DIMS);
      
      if (!maxTexSize || !maxViewportDims) {
        gl = null;
      } else {
        gl.getExtension("WEBGL_lose_context");
        return gl;
      }
    } catch {
      gl = null;
    }
  }
  
  const gl1 = canvas.getContext("webgl", {
    antialias: false,
    preserveDrawingBuffer: false,
    failIfMajorPerformanceCaveat: false
  }) as WebGLRenderingContext | null;
  
  if (gl1) {
    try {
      const maxTexSize = gl1.getParameter(gl1.MAX_TEXTURE_SIZE);
      const maxViewportDims = gl1.getParameter(gl1.MAX_VIEWPORT_DIMS);
      
      if (!maxTexSize || !maxViewportDims) {
        return null;
      }
      
      return gl1;
    } catch {
      return null;
    }
  }
  
  return null;
};

const cleanupWebGLContext = (gl: WebGLRenderingContext | WebGL2RenderingContext) => {
  const loseContext = gl.getExtension("WEBGL_lose_context");
  if (loseContext) {
    loseContext.loseContext();
  }
};

const waitForWebGLContextReady = async (): Promise<boolean> => {
  if (typeof window === "undefined") return false;
  
  let frameCount = 0;
  
  return new Promise((resolve) => {
    const check = () => {
      frameCount++;
      const testContext = createAndTestWebGLContext();
      
      if (testContext) {
        cleanupWebGLContext(testContext);
        
        if (frameCount >= MIN_WEBGL_FRAMES) {
          resolve(true);
        } else {
          requestAnimationFrame(check);
        }
      } else {
        if (frameCount < MAX_WEBGL_FRAMES) {
          requestAnimationFrame(check);
        } else {
          resolve(false);
        }
      }
    };
    requestAnimationFrame(check);
  });
};

// ============================================================================
// Tooltip Component
// ============================================================================

type TooltipProps = {
  device: DeviceSummary;
  x: number;
  y: number;
};

const DeviceTooltip = memo(function DeviceTooltip({ device, x, y }: TooltipProps) {
  // Format last seen time
  const lastSeenFormatted = device.lastSeen 
    ? new Date(device.lastSeen).toLocaleTimeString('pt-BR', { 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
      })
    : 'N/A';
  
  // Format speed
  const speedFormatted = device.speedKmh !== null 
    ? `${device.speedKmh.toFixed(1)} km/h`
    : 'N/A';
  
  // Format vibration (placeholder)
  const vibrationFormatted = device.vibration !== null && device.vibration !== undefined
    ? `${device.vibration.toFixed(2)}`
    : 'N/A';

  // Calculate position to avoid going off-screen
  const tooltipWidth = 200;
  const tooltipHeight = 140;
  const padding = 10;
  
  let left = x + 15;
  let top = y - tooltipHeight / 2;
  
  // Adjust if going off right edge
  if (typeof window !== 'undefined' && left + tooltipWidth > window.innerWidth - padding) {
    left = x - tooltipWidth - 15;
  }
  
  // Adjust if going off bottom
  if (typeof window !== 'undefined' && top + tooltipHeight > window.innerHeight - padding) {
    top = window.innerHeight - tooltipHeight - padding;
  }
  
  // Adjust if going off top
  if (top < padding) {
    top = padding;
  }

  // Shared transition style for smooth updates without flickering
  const valueTransition = 'color 0.3s ease-out';

  return (
    <div
      style={{
        position: 'fixed',
        left,
        top,
        width: tooltipWidth,
        background: 'rgba(15, 23, 42, 0.95)',
        borderRadius: '10px',
        padding: '12px 14px',
        color: '#e2e8f0',
        fontSize: '13px',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
        border: '1px solid rgba(148, 163, 184, 0.2)',
        zIndex: 2000,
        pointerEvents: 'none',
        backdropFilter: 'blur(8px)',
      }}
    >
      {/* Header */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '8px',
        marginBottom: '10px',
        paddingBottom: '8px',
        borderBottom: '1px solid rgba(148, 163, 184, 0.2)'
      }}>
        <span style={{ fontSize: '18px' }}>🚚</span>
        <span style={{ 
          fontWeight: 600, 
          fontSize: '14px',
          color: '#f1f5f9'
        }}>
          {device.deviceId}
        </span>
        <span 
          style={{ 
            marginLeft: 'auto',
            padding: '2px 8px',
            borderRadius: '12px',
            fontSize: '11px',
            fontWeight: 500,
            background: device.status === 'online' 
              ? 'rgba(34, 197, 94, 0.2)' 
              : 'rgba(148, 163, 184, 0.2)',
            color: device.status === 'online' ? '#4ade80' : '#94a3b8',
            transition: 'background 0.3s ease-out, color 0.3s ease-out'
          }}
        >
          {device.status === 'online' ? 'Online' : 'Offline'}
        </span>
      </div>
      
      {/* Info rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#94a3b8' }}>Velocidade</span>
          <span style={{ fontWeight: 500, transition: valueTransition }}>{speedFormatted}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#94a3b8' }}>Vibração</span>
          <span style={{ fontWeight: 500, transition: valueTransition }}>{vibrationFormatted}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#94a3b8' }}>Última vez visto</span>
          <span style={{ fontWeight: 500, transition: valueTransition }}>{lastSeenFormatted}</span>
        </div>
      </div>
    </div>
  );
});

// ============================================================================
// DeckGL Overlay Component (using MapboxOverlay)
// ============================================================================

type DeckGLOverlayProps = {
  layers: Layer[];
  onClick: (info: PickingInfo) => void;
};

const DeckGLOverlay = memo(function DeckGLOverlay({ layers, onClick }: DeckGLOverlayProps) {
  const overlay = useControl<MapboxOverlay>(() => new MapboxOverlay({
    interleaved: true,
    layers,
    onClick
  }));

  useEffect(() => {
    overlay.setProps({
      layers,
      onClick
    });
  }, [overlay, layers, onClick]);

  return null;
});



// ============================================================================
// Main MapView Component
// ============================================================================

export default function MapView({ devices, isLoading, error, connectionStatus }: MapViewProps) {
  const mapRef = useRef<any>(null);
  const deckClickRef = useRef(false);
  const initTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const tileErrorCountRef = useRef(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const [mapState, dispatch] = useReducer(mapStateReducer, { status: 'checking-webgl' });
  const [mapStyle, setMapStyle] = useState(SATELLITE_STYLE);
  const [usingFallbackTiles, setUsingFallbackTiles] = useState(false);
  
  // Selected device for tooltip - store ID and derive device from props
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ x: number; y: number } | null>(null);
  
  // Derive selected device from current devices array (auto-updates on refresh)
  const selectedDevice = selectedDeviceId 
    ? devices.find(d => d.deviceId === selectedDeviceId) ?? null 
    : null;
  
  // Clear selection if device is no longer in the list
  useEffect(() => {
    if (selectedDeviceId && !devices.find(d => d.deviceId === selectedDeviceId)) {
      setSelectedDeviceId(null);
      setTooltipPosition(null);
    }
  }, [devices, selectedDeviceId]);

  // Check WebGL support on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const testContext = createAndTestWebGLContext();
      if (testContext) {
        cleanupWebGLContext(testContext);
        dispatch({ type: 'WEBGL_SUPPORTED' });
      } else {
        dispatch({ type: 'WEBGL_UNSUPPORTED' });
      }
    }
    
    return () => {
      if (initTimeoutRef.current) {
        clearTimeout(initTimeoutRef.current);
      }
    };
  }, []);

  // Handle click outside to close tooltip
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setSelectedDeviceId(null);
        setTooltipPosition(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Monitor global WebGL errors
  useEffect(() => {
    if (typeof window === "undefined") return;
    
    const handleError = (event: ErrorEvent) => {
      if (event.message && (
        event.message.includes("maxTextureDimension2D") ||
        event.message.includes("WebGL") ||
        event.message.includes("DeckGL")
      )) {
        debugWarn("[Global Error Handler] WebGL/DeckGL error detected:", event.message);
        
        if (mapState.status === 'ready' || mapState.status === 'initializing-deckgl') {
          dispatch({ 
            type: 'DECKGL_ERROR', 
            message: 'WebGL context error detected',
            canRetry: true 
          });
        }
      }
    };
    
    window.addEventListener("error", handleError);
    return () => window.removeEventListener("error", handleError);
  }, [mapState.status]);

  // Initialize DeckGL when map is loaded
  const initializeDeckGL = useCallback(async (attempt: number) => {
    if (mapState.status !== 'initializing-deckgl') return;
    
    debugLog("[DeckGL Init] Starting initialization, attempt:", attempt);

    try {
      const contextReady = await waitForWebGLContextReady();
      
      if (!contextReady) {
        debugWarn("[DeckGL Init] WebGL context not ready after waiting");
        if (attempt < MAX_INIT_RETRIES) {
          initTimeoutRef.current = setTimeout(() => {
            dispatch({ type: 'DECKGL_INIT_RETRY', attempt: attempt + 1 });
          }, 1000);
        } else {
          dispatch({ 
            type: 'DECKGL_ERROR', 
            message: 'WebGL context not available after multiple attempts',
            canRetry: true 
          });
        }
        return;
      }

      initTimeoutRef.current = setTimeout(() => {
        const finalCheck = createAndTestWebGLContext();
        if (finalCheck) {
          cleanupWebGLContext(finalCheck);
          debugLog("[DeckGL Init] Final check passed, marking ready");
          dispatch({ type: 'DECKGL_INIT_SUCCESS' });
        } else {
          debugWarn("[DeckGL Init] Final check failed");
          dispatch({ 
            type: 'DECKGL_ERROR', 
            message: 'WebGL context lost during initialization',
            canRetry: true 
          });
        }
      }, RENDER_DELAY_MS);

    } catch (e) {
      debugError("[DeckGL Init] Error during initialization:", e);
      dispatch({ 
        type: 'DECKGL_ERROR', 
        message: `Initialization error: ${e instanceof Error ? e.message : String(e)}`,
        canRetry: true 
      });
    }
  }, [mapState.status]);

  // Trigger initialization when entering initializing-deckgl state
  useEffect(() => {
    if (mapState.status === 'initializing-deckgl') {
      initializeDeckGL(mapState.attempt);
    }
  }, [mapState, initializeDeckGL]);

  // Handle tile loading errors and switch to fallback if needed
  const handleTileError = useCallback(() => {
    tileErrorCountRef.current++;
    debugWarn(`[Map] Tile error #${tileErrorCountRef.current}`);
    
    if (tileErrorCountRef.current >= TILE_ERROR_THRESHOLD && !usingFallbackTiles) {
      debugLog("[Map] Switching to fallback tile source");
      setMapStyle(FALLBACK_STYLE);
      setUsingFallbackTiles(true);
      tileErrorCountRef.current = 0;
    }
  }, [usingFallbackTiles]);

  const onMapLoad = useCallback(() => {
    debugLog("[Map] Loaded");

    if (mapRef.current) {
      const map = mapRef.current.getMap();
      if (map) {
        map.on('error', (e: { error?: { status?: number }; sourceId?: string }) => {
          if (e.error && e.sourceId) {
            handleTileError();
          }
        });

        // Add viewport bounds tracking for Phase 1 optimization
        map.on('moveend', () => {
          if (map.getBounds()) {
            const bounds = map.getBounds();
            setMapBounds([
              bounds.getWest(),
              bounds.getSouth(),
              bounds.getEast(),
              bounds.getNorth()
            ]);
          }
        });

        // Initial bounds setup
        if (map.getBounds()) {
          const bounds = map.getBounds();
          setMapBounds([
            bounds.getWest(),
            bounds.getSouth(),
            bounds.getEast(),
            bounds.getNorth()
          ]);
        }
      }
    }

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (mapRef.current) {
          const map = mapRef.current.getMap();
          if (map && map.isStyleLoaded()) {
            dispatch({ type: 'MAP_LOADED' });
          } else {
            setTimeout(() => {
              if (mapRef.current?.getMap()?.isStyleLoaded()) {
                dispatch({ type: 'MAP_LOADED' });
              }
            }, 300);
          }
        }
      });
    });
  }, [handleTileError]);



  const handleDeckGLError = useCallback((error: Error) => {
    debugError("[DeckGL] Error:", error.message);
  }, []);

  const handleRetry = useCallback(() => {
    dispatch({ type: 'RESET' });
  }, []);

  // Handle map click - close tooltip if not clicking a device
  const handleMapClick = useCallback(() => {
    if (deckClickRef.current) {
      deckClickRef.current = false;
      return;
    }
    setSelectedDeviceId(null);
    setTooltipPosition(null);
  }, []);


  // Handle DeckGL click
  const handleDeckClick = useCallback((info: PickingInfo) => {
    if (info.object && info.layer?.id === 'devices-icon-layer') {
      deckClickRef.current = true;
      const clickedDevice = info.object as DeviceSummary;
      
      // If clicking the same device, close tooltip
      if (selectedDeviceId === clickedDevice.deviceId) {
        setSelectedDeviceId(null);
        setTooltipPosition(null);
      } else {
        setSelectedDeviceId(clickedDevice.deviceId);
        setTooltipPosition({ x: info.x, y: info.y });
      }
    }
  }, [selectedDeviceId]);

  // Memoized device filtering
  const validDevices = useMemo(
    () => devices.filter((d) => d.latitude !== null && d.longitude !== null),
    [devices]
  );

  // Viewport-based device filtering (Phase 1 Optimization)
  const [mapBounds, setMapBounds] = useState<[number, number, number, number] | null>(null);

  // Filter devices by viewport visibility
  const visibleDevices = useMemo(() => {
    if (!mapBounds || !mapRef.current) return validDevices;

    const [west, south, east, north] = mapBounds;
    return validDevices.filter(device => {
      const lon = device.longitude as number;
      const lat = device.latitude as number;
      return lon >= west && lon <= east && lat >= south && lat <= north;
    });
  }, [validDevices, mapBounds]);

  // Create a stable key for update triggers
  const devicesKey = useMemo(
    () => validDevices.map(d => `${d.deviceId}:${d.status}:${d.latitude}:${d.longitude}`).join('|'),
    [validDevices]
  );

  // Layers - ScatterplotLayer for background + IconLayer for truck image + TextLayer for device tag with background
  const layers = useMemo(() => {
    if (mapState.status !== 'ready') return [];

    // Use visible devices for viewport-based rendering (Phase 1 optimization)
    const renderDevices = visibleDevices.length > 0 ? visibleDevices : validDevices;

    return [
      // Background circle layer (pickable for clicks)
      new ScatterplotLayer<DeviceSummary>({
        id: 'devices-icon-layer',
        data: renderDevices,
        getPosition: (d) => [d.longitude as number, d.latitude as number],
        getRadius: 18,
        radiusUnits: 'pixels',
        radiusMinPixels: 16,
        radiusMaxPixels: 20,
        getFillColor: (d) => d.status === 'online'
          ? [34, 197, 94, 220]    // Green for online
          : [148, 163, 184, 180], // Gray for offline
        getLineColor: [255, 255, 255, 255],
        getLineWidth: 2,
        lineWidthMinPixels: 1.5,
        lineWidthMaxPixels: 2,
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 100],
        updateTriggers: {
          getPosition: [devicesKey],
          getFillColor: [devicesKey]
        }
      }),

      // Dump truck icon layer
      new IconLayer<DeviceSummary>({
        id: 'devices-truck-icon-layer',
        data: renderDevices,
        getPosition: (d) => [d.longitude as number, d.latitude as number],
        getIcon: () => ({
          url: '/dump-truck.svg',
          width: 128,
          height: 128,
          anchorY: 64,
          anchorX: 64
        }),
        getSize: 32,
        sizeUnits: 'pixels',
        sizeMinPixels: 24,
        sizeMaxPixels: 40,
        pickable: false,
        updateTriggers: {
          getPosition: [devicesKey]
        }
      }),

      // Device tag layer (above the icon) with improved visibility
      new TextLayer<DeviceSummary>({
        id: 'devices-label-layer',
        data: renderDevices,
        getPosition: (d) => [d.longitude as number, d.latitude as number],
        getText: (d) => d.deviceId,
        getSize: 14,
        sizeUnits: 'pixels',
        getColor: [255, 255, 255, 255],
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'center',
        getPixelOffset: [0, -36], // Position above the icon
        fontFamily: 'system-ui, -apple-system, sans-serif',
        fontWeight: 700,
        background: true,
        getBackgroundColor: [0, 0, 0, 102], // 40% black background
        backgroundPadding: [6, 3, 6, 3],
        pickable: false,
        updateTriggers: {
          getPosition: [devicesKey],
          getText: [devicesKey]
        }
      })
    ];
  }, [visibleDevices, validDevices, mapState.status, devicesKey]);

  // Derive display states from state machine
  const showDeckGL = mapState.status === 'ready';
  const showError = mapState.status === 'error';
  const showWebGLWarning = mapState.status === 'webgl-unsupported';

  return (
    <section
      ref={containerRef}
      style={{
        position: "relative",
        width: "100%",
        height: "80vh",
        borderRadius: "12px",
        overflow: "hidden",
        border: "1px solid #2d2d2d",
        background: "#0b0b0b"
      }}
    >
      {/* Status Indicator */}
      <div style={{
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
        border: "1px solid rgba(255,255,255,0.1)",
        color: "white",
        fontSize: "11px",
        fontWeight: 600,
        letterSpacing: "0.5px"
      }}>
        <div style={{
          width: "8px",
          height: "8px",
          borderRadius: "50%",
          background: connectionStatus === 'live' ? '#22c55e' :
                     connectionStatus === 'reconnecting' ? '#eab308' :
                     connectionStatus === 'fallback_polling' ? '#f97316' :
                     '#ef4444',
          boxShadow: connectionStatus === 'live' ? '0 0 8px #22c55e' : 'none',
          transition: 'background 0.3s ease'
        }} />
        <span>
          {connectionStatus === 'live' ? 'LIVE' :
           connectionStatus === 'reconnecting' ? 'RECONNECTING' :
           connectionStatus === 'fallback_polling' ? 'FALLBACK' :
           'OFFLINE'}
        </span>
        <span style={{
          borderLeft: "1px solid rgba(255,255,255,0.2)",
          paddingLeft: "8px",
          marginLeft: "4px",
          color: "rgba(255,255,255,0.6)"
        }}>
          {validDevices.length} DEVICES
        </span>
      </div>


      {/* Map Container */}
      <div style={{
        width: "100%",
        height: "100%",
        position: "relative"
      }}>
        {/* Map - receives all interaction events */}
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
          <DeckGLOverlay
            layers={layers}
            onClick={handleDeckClick}
          />
        )}
      </Map>
    </div>

      {/* Device tooltip */}
      {selectedDevice && tooltipPosition && (
        <DeviceTooltip
          device={selectedDevice}
          x={tooltipPosition.x}
          y={tooltipPosition.y}
        />
      )}

      {/* Loading indicator */}
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
            zIndex: 1000
          }}
        >
          Carregando dispositivos…
        </div>
      )}

      {/* Data error indicator */}
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
            zIndex: 1000
          }}
        >
          Erro: {error}
        </div>
      )}

      {/* WebGL unsupported warning */}
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
            maxWidth: "300px"
          }}
        >
          WebGL não disponível - dispositivos não serão exibidos no mapa
        </div>
      )}

      {/* DeckGL error with retry option */}
      {showError && mapState.status === 'error' && (
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
            maxWidth: "300px",
            display: "flex",
            flexDirection: "column",
            gap: "6px"
          }}
        >
          <span>Erro DeckGL: {mapState.message}</span>
          {mapState.canRetry && (
            <button
              onClick={handleRetry}
              style={{
                padding: "4px 8px",
                background: "#2563eb",
                color: "#fff",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
                fontSize: 11
              }}
            >
              Tentar Novamente
            </button>
          )}
        </div>
      )}

      {/* Fallback tiles indicator */}
      {usingFallbackTiles && (
        <div
          style={{
            position: "absolute",
            top: 12,
            left: 12,
            padding: "4px 8px",
            borderRadius: 4,
            background: "rgba(251, 191, 36, 0.8)",
            color: "#111",
            fontSize: 10,
            zIndex: 1000
          }}
          title="Servidor de tiles primário indisponível, usando OpenStreetMap"
        >
          Usando tiles de fallback
        </div>
      )}

      {/* Initialization status (dev only) */}
      {isDev && mapState.status === 'initializing-deckgl' && (
        <div
          style={{
            position: "absolute",
            bottom: 12,
            right: 12,
            padding: "4px 8px",
            borderRadius: 4,
            background: "rgba(0,0,0,0.5)",
            color: "#94a3b8",
            fontSize: 10,
            zIndex: 1000
          }}
        >
          Inicializando DeckGL (tentativa {mapState.attempt + 1})
        </div>
      )}
    </section>
  );
}
