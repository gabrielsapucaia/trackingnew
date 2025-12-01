/**
 * DeckGLMap Component
 * ============================================================
 * Main map component using deck.gl with MapLibre GL
 * Renders device markers, trails, and heatmaps
 */

import { 
  createSignal, 
  createEffect, 
  onMount, 
  onCleanup, 
  Show,
  For 
} from "solid-js";

// Types
export interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

export interface DeviceMarker {
  id: string;
  name: string;
  longitude: number;
  latitude: number;
  bearing: number;
  speed: number;
  status: "online" | "idle" | "offline";
}

import { Datum, convertDatum } from "~/lib/utils/geo";

export type MapStyle = 'cartoDark' | 'cartoLight' | 'osm' | 'osmBright';

interface DeckGLMapProps {
  devices?: DeviceMarker[];
  initialViewState?: Partial<ViewState>;
  onViewStateChange?: (viewState: ViewState) => void;
  onDeviceClick?: (device: DeviceMarker) => void;
  showTrails?: boolean;
  showHeatmap?: boolean;
  datum?: Datum; // Datum for coordinate system (default: WGS84)
  mapStyle?: MapStyle; // Map style/theme
  class?: string;
}

const DEFAULT_VIEW_STATE: ViewState = {
  longitude: -47.170456,
  latitude: -11.563234,
  zoom: 14,
  pitch: 0,
  bearing: 0,
};

const DEFAULT_DATUM: Datum = 'WGS84';

// Available map styles
const MAP_STYLES = {
  cartoDark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  cartoLight: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  osm: "https://demotiles.maplibre.org/style.json", // OpenStreetMap style
  osmBright: "https://demotiles.maplibre.org/style.json",
};

// Default map style
const DEFAULT_MAP_STYLE = MAP_STYLES.cartoDark;

export default function DeckGLMap(props: DeckGLMapProps) {
  let containerRef: HTMLDivElement | undefined;
  let mapInstance: any = null;
  let deckInstance: any = null;
  
  const [viewState, setViewState] = createSignal<ViewState>({
    ...DEFAULT_VIEW_STATE,
    ...props.initialViewState,
  });
  const [isLoaded, setIsLoaded] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);
  const [hoveredDevice, setHoveredDevice] = createSignal<DeviceMarker | null>(null);
  
  // Initialize map (client-side only)
  onMount(async () => {
    if (typeof window === "undefined") return;
    
    try {
      // Dynamic imports for client-side only
      const [
        { Deck },
        { ScatterplotLayer, IconLayer, PathLayer },
        { default: maplibregl }
      ] = await Promise.all([
        import("@deck.gl/core"),
        import("@deck.gl/layers"),
        import("maplibre-gl")
      ]);
      
      if (!containerRef) return;

      // Get selected map style
      const selectedMapStyle = props.mapStyle || 'cartoDark';
      const mapStyleUrl = MAP_STYLES[selectedMapStyle];

      // Create MapLibre GL map
      mapInstance = new maplibregl.Map({
        container: containerRef,
        style: mapStyleUrl,
        center: [viewState().longitude, viewState().latitude],
        zoom: viewState().zoom,
        pitch: viewState().pitch,
        bearing: viewState().bearing,
        interactive: true,
      });
      
      mapInstance.on("load", () => {
        setIsLoaded(true);
      });
      
      mapInstance.on("move", () => {
        const center = mapInstance.getCenter();
        const newViewState: ViewState = {
          longitude: center.lng,
          latitude: center.lat,
          zoom: mapInstance.getZoom(),
          pitch: mapInstance.getPitch(),
          bearing: mapInstance.getBearing(),
        };
        setViewState(newViewState);
        props.onViewStateChange?.(newViewState);
      });
      
      mapInstance.on("error", (e: any) => {
        console.error("Map error:", e);
        setError("Failed to load map");
      });
      
      // Create deck.gl instance
      deckInstance = new Deck({
        parent: containerRef,
        viewState: viewState(),
        controller: false, // MapLibre handles interaction
        layers: [],
        onHover: (info: any) => {
          if (info.object) {
            setHoveredDevice(info.object);
          } else {
            setHoveredDevice(null);
          }
        },
        onClick: (info: any) => {
          if (info.object && props.onDeviceClick) {
            props.onDeviceClick(info.object);
          }
        },
      });
      
    } catch (err) {
      console.error("Failed to initialize map:", err);
      setError("Failed to initialize map");
    }
  });
  
  // Update deck.gl layers when devices change
  createEffect(async () => {
    if (!deckInstance || !isLoaded()) return;

    const devices = props.devices || [];
    const datum = props.datum || DEFAULT_DATUM;

    // Convert device coordinates to the selected datum
    const convertedDevices = devices.map(device => {
      // Assuming device coordinates are in WGS84 (from GPS)
      // Convert to the selected datum for display
      const converted = convertDatum(device.latitude, device.longitude, 'WGS84', datum);
      return {
        ...device,
        latitude: converted.lat,
        longitude: converted.lon,
      };
    });

    try {
      const { ScatterplotLayer, IconLayer, TextLayer } = await import("@deck.gl/layers");

      const layers = [
        // Device markers
        new ScatterplotLayer({
          id: "device-markers",
          data: convertedDevices,
          pickable: true,
          opacity: 0.8,
          stroked: true,
          filled: true,
          radiusScale: 6,
          radiusMinPixels: 8,
          radiusMaxPixels: 30,
          lineWidthMinPixels: 2,
          getPosition: (d: DeviceMarker) => [d.longitude, d.latitude],
          getRadius: (d: DeviceMarker) => d.speed > 0 ? 12 : 8,
          getFillColor: (d: DeviceMarker) => {
            switch (d.status) {
              case "online": return [34, 197, 94, 200]; // Green
              case "idle": return [234, 179, 8, 200];   // Yellow
              case "offline": return [239, 68, 68, 200]; // Red
              default: return [100, 100, 100, 200];
            }
          },
          getLineColor: [255, 255, 255, 255],
          updateTriggers: {
            getPosition: convertedDevices.map(d => `${d.id}-${d.longitude}-${d.latitude}`),
            getFillColor: convertedDevices.map(d => d.status),
          },
        }),

        // Device labels
        new TextLayer({
          id: "device-labels",
          data: convertedDevices.filter(d => d.status === "online"),
          pickable: false,
          getPosition: (d: DeviceMarker) => [d.longitude, d.latitude],
          getText: (d: DeviceMarker) => d.name,
          getSize: 12,
          getColor: [255, 255, 255, 255],
          getAngle: 0,
          getTextAnchor: "middle",
          getAlignmentBaseline: "top",
          getPixelOffset: [0, 20],
          fontFamily: "JetBrains Mono, monospace",
          fontWeight: "bold",
        }),
      ];

      deckInstance.setProps({ layers });

    } catch (err) {
      console.error("Failed to update layers:", err);
    }
  });
  
  // Sync deck.gl view with MapLibre
  createEffect(() => {
    if (!deckInstance || !mapInstance) return;
    
    const vs = viewState();
    deckInstance.setProps({ viewState: vs });
  });
  
  // Cleanup
  onCleanup(() => {
    if (deckInstance) {
      deckInstance.finalize();
      deckInstance = null;
    }
    if (mapInstance) {
      mapInstance.remove();
      mapInstance = null;
    }
  });
  
  // Zoom controls
  const zoomIn = () => {
    if (mapInstance) {
      mapInstance.zoomIn();
    }
  };
  
  const zoomOut = () => {
    if (mapInstance) {
      mapInstance.zoomOut();
    }
  };
  
  const resetView = () => {
    if (mapInstance) {
      mapInstance.flyTo({
        center: [DEFAULT_VIEW_STATE.longitude, DEFAULT_VIEW_STATE.latitude],
        zoom: DEFAULT_VIEW_STATE.zoom,
        pitch: DEFAULT_VIEW_STATE.pitch,
        bearing: DEFAULT_VIEW_STATE.bearing,
      });
    }
  };
  
  const getSpeedColor = (speed: number) => {
    if (speed === 0) return "var(--color-text-tertiary)";
    if (speed < 20) return "var(--color-speed-low)";
    if (speed < 40) return "var(--color-speed-medium)";
    if (speed < 60) return "var(--color-speed-high)";
    if (speed < 80) return "var(--color-speed-danger)";
    return "var(--color-speed-critical)";
  };
  
  return (
    <div 
      class={props.class}
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        "min-height": "400px",
        background: "var(--color-bg-tertiary)",
        "border-radius": "var(--radius-lg)",
        overflow: "hidden",
      }}
    >
      {/* Map container */}
      <div 
        ref={containerRef}
        style={{
          width: "100%",
          height: "100%",
          position: "absolute",
          top: 0,
          left: 0,
        }}
      />
      
      {/* Loading state */}
      <Show when={!isLoaded() && !error()}>
        <div style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: "flex",
          "align-items": "center",
          "justify-content": "center",
          background: "var(--color-bg-tertiary)",
          "z-index": 10,
        }}>
          <div class="text-center">
            <div style={{
              width: "40px",
              height: "40px",
              border: "3px solid var(--color-border-secondary)",
              "border-top-color": "var(--color-accent-primary)",
              "border-radius": "50%",
              animation: "spin 1s linear infinite",
              margin: "0 auto 16px",
            }} />
            <p class="text-muted">Carregando mapa...</p>
          </div>
        </div>
      </Show>
      
      {/* Error state */}
      <Show when={error()}>
        <div style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: "flex",
          "align-items": "center",
          "justify-content": "center",
          background: "var(--color-bg-tertiary)",
          "z-index": 10,
        }}>
          <div class="text-center">
            <div style={{
              color: "var(--color-error)",
              "margin-bottom": "16px",
            }}>
              <ErrorIcon />
            </div>
            <p style={{ color: "var(--color-error)" }}>{error()}</p>
            <button 
              class="btn btn-secondary mt-4"
              onClick={() => window.location.reload()}
            >
              Recarregar
            </button>
          </div>
        </div>
      </Show>
      
      {/* Hover tooltip */}
      <Show when={hoveredDevice()}>
        <div style={{
          position: "absolute",
          bottom: "80px",
          left: "16px",
          background: "var(--color-bg-secondary)",
          border: "1px solid var(--color-border-primary)",
          "border-radius": "var(--radius-lg)",
          padding: "var(--space-3)",
          "min-width": "200px",
          "z-index": 20,
        }}>
          <div style={{ "font-weight": "600", "margin-bottom": "var(--space-2)" }}>
            {hoveredDevice()!.name}
          </div>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span class="text-muted">Velocidade</span>
              <div style={{ 
                "font-weight": "600",
                color: getSpeedColor(hoveredDevice()!.speed * 3.6)
              }}>
                {(hoveredDevice()!.speed * 3.6).toFixed(1)} km/h
              </div>
            </div>
            <div>
              <span class="text-muted">Direção</span>
              <div style={{ "font-weight": "600" }}>
                {hoveredDevice()!.bearing.toFixed(0)}°
              </div>
            </div>
          </div>
        </div>
      </Show>
      
      {/* Zoom controls */}
      <div style={{
        position: "absolute",
        top: "16px",
        right: "16px",
        display: "flex",
        "flex-direction": "column",
        gap: "var(--space-2)",
        "z-index": 15,
      }}>
        <button 
          class="btn btn-secondary btn-icon" 
          onClick={zoomIn}
          title="Zoom In"
        >
          <ZoomInIcon />
        </button>
        <button 
          class="btn btn-secondary btn-icon" 
          onClick={zoomOut}
          title="Zoom Out"
        >
          <ZoomOutIcon />
        </button>
        <button 
          class="btn btn-secondary btn-icon" 
          onClick={resetView}
          title="Resetar Vista"
        >
          <TargetIcon />
        </button>
      </div>
      
      {/* Device count badge */}
      <Show when={props.devices && props.devices.length > 0}>
        <div style={{
          position: "absolute",
          top: "16px",
          left: "16px",
          background: "var(--color-bg-secondary)",
          border: "1px solid var(--color-border-primary)",
          "border-radius": "var(--radius-lg)",
          padding: "var(--space-2) var(--space-3)",
          "font-size": "var(--text-sm)",
          "z-index": 15,
        }}>
          <span style={{ color: "var(--color-accent-primary)", "font-weight": "600" }}>
            {props.devices!.length}
          </span>
          <span class="text-muted" style={{ "margin-left": "var(--space-2)" }}>
            dispositivos
          </span>
        </div>
      </Show>
      
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

// Icons
function ZoomInIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
      <line x1="11" y1="8" x2="11" y2="14" />
      <line x1="8" y1="11" x2="14" y2="11" />
    </svg>
  );
}

function ZoomOutIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
      <line x1="8" y1="11" x2="14" y2="11" />
    </svg>
  );
}

function TargetIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

