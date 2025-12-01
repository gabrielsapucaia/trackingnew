import { createSignal, createResource, createEffect, createMemo, For, Show, onCleanup, onMount } from "solid-js";
import AppLayout from "~/layouts/AppLayout";
import { api, type TelemetryPoint } from "~/lib/api/client";

export default function ReplayPage() {
  const [selectedDevice, setSelectedDevice] = createSignal<string>("");
  const [isPlaying, setIsPlaying] = createSignal(false);
  const [playbackSpeed, setPlaybackSpeed] = createSignal(1);
  const [currentIndex, setCurrentIndex] = createSignal(0);
  const [showTrail, setShowTrail] = createSignal(true);
  const [hoursBack, setHoursBack] = createSignal(1);
  const [mapLoaded, setMapLoaded] = createSignal(false);
  const [mapStyle, setMapStyle] = createSignal<'google-satellite' | 'esri-satellite' | 'osm'>('esri-satellite');
  
  // Map references
  let mapContainer: HTMLDivElement | undefined;
  let map: any = null;
  let trailSource: any = null;
  let markerEl: HTMLDivElement | null = null;
  let marker: any = null;
  
  // For smooth animation
  const [animationProgress, setAnimationProgress] = createSignal(0);
  let animationFrame: number;

  // Fetch devices
  const [devicesData] = createResource(() => api.getDevices());

  // Fetch telemetry for replay
  const [replayData, { refetch }] = createResource(
    () => ({ device: selectedDevice(), hours: hoursBack() }),
    async ({ device, hours }) => {
      if (!device) return null;
      const end = new Date();
      const start = new Date(end.getTime() - hours * 60 * 60 * 1000);
      return api.getTelemetry({
        device_id: device,
        start: start.toISOString(),
        end: end.toISOString(),
        limit: 100000,
        granularity: "raw"
      });
    }
  );

  // Auto-select first device
  createEffect(() => {
    const devices = devicesData()?.devices;
    if (devices?.length && !selectedDevice()) {
      setSelectedDevice(devices[0].device_id);
    }
  });

  // Helper to interpolate angles properly
  function lerpAngle(a: number, b: number, t: number): number {
    const diff = ((b - a + 540) % 360) - 180;
    return (a + diff * t + 360) % 360;
  }

  // Smooth playback with interpolation
  createEffect(() => {
    if (!isPlaying()) {
      if (animationFrame) cancelAnimationFrame(animationFrame);
      return;
    }
    
    const data = replayData()?.data;
    if (!data?.length) return;

    let lastTime = performance.now();
    
    const animate = (currentTime: number) => {
      const deltaTime = currentTime - lastTime;
      lastTime = currentTime;
      
      const progressIncrement = (deltaTime / 1000) * playbackSpeed();
      
      setAnimationProgress(prev => {
        const newProgress = prev + progressIncrement;
        const newIndex = Math.floor(newProgress);
        
        if (newIndex >= data.length - 1) {
          setIsPlaying(false);
          setCurrentIndex(data.length - 1);
          return data.length - 1;
        }
        
        setCurrentIndex(newIndex);
        return newProgress;
      });
      
      if (isPlaying()) {
        animationFrame = requestAnimationFrame(animate);
      }
    };
    
    animationFrame = requestAnimationFrame(animate);
    
    onCleanup(() => {
      if (animationFrame) cancelAnimationFrame(animationFrame);
    });
  });

  // Current point with interpolation
  const interpolatedPoint = createMemo(() => {
    const data = replayData()?.data;
    if (!data?.length) return null;
    
    const progress = animationProgress();
    const index = Math.floor(progress);
    const fraction = progress - index;
    
    // Ensure we don't go out of bounds
    if (index >= data.length - 1) {
      return data[data.length - 1];
    }
    
    const current = data[index];
    const next = data[index + 1];
    
    // Safety check
    if (!current || !next) {
      return current || data[data.length - 1];
    }
    
    return {
      ...current,
      latitude: current.latitude + (next.latitude - current.latitude) * fraction,
      longitude: current.longitude + (next.longitude - current.longitude) * fraction,
      speed_kmh: current.speed_kmh + (next.speed_kmh - current.speed_kmh) * fraction,
      bearing: lerpAngle(current.bearing || 0, next.bearing || 0, fraction)
    };
  });

  // Trail GeoJSON
  const trailGeoJSON = createMemo(() => {
    const data = replayData()?.data;
    if (!data?.length) return null;
    
    const end = Math.min(Math.floor(animationProgress()) + 1, data.length);
    const start = Math.max(0, end - 500);
    
    const coordinates = data.slice(start, end).map(p => [p.longitude, p.latitude]);
    
    return {
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates
      },
      properties: {}
    };
  });

  // Initialize MapLibre GL
  onMount(async () => {
    if (typeof window === "undefined" || !mapContainer) return;
    
    try {
      const maplibregl = (await import("maplibre-gl")).default;
      
      // Add MapLibre CSS
      if (!document.getElementById("maplibre-css")) {
        const link = document.createElement("link");
        link.id = "maplibre-css";
        link.rel = "stylesheet";
        link.href = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css";
        document.head.appendChild(link);
      }
      
      const createMapStyle = (style: string) => {
        if (style === 'osm') {
          return {
            version: 8 as const,
            sources: { osm: { type: "raster" as const, tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256 } },
            layers: [{ id: "osm-layer", type: "raster" as const, source: "osm", minzoom: 0, maxzoom: 19 }]
          };
        } else if (style === 'esri-satellite') {
          return {
            version: 8 as const,
            sources: { esri: { type: "raster" as const, tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"], tileSize: 256 } },
            layers: [{ id: "esri-layer", type: "raster" as const, source: "esri", minzoom: 0, maxzoom: 19 }]
          };
        } else {
          return {
            version: 8 as const,
            sources: { satellite: { type: "raster" as const, tiles: ["https://mt0.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"], tileSize: 256 } },
            layers: [{ id: "satellite-layer", type: "raster" as const, source: "satellite", minzoom: 0, maxzoom: 22 }]
          };
        }
      };

      map = new maplibregl.Map({
        container: mapContainer,
        style: createMapStyle(mapStyle()),
        center: [-47.1706, -11.5637],
        zoom: 16,
        pitch: 0,
        bearing: 0,
        attributionControl: false
      });
      
      map.addControl(new maplibregl.NavigationControl({ showCompass: true, showZoom: true }), "bottom-right");
      map.addControl(new maplibregl.ScaleControl({ maxWidth: 100, unit: "metric" }), "bottom-left");
      
      // Create marker element
      markerEl = document.createElement("div");
      markerEl.style.cssText = `
        width: 32px;
        height: 32px;
        background: #f59e0b;
        border: 4px solid white;
        border-radius: 50%;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        cursor: pointer;
      `;
      
      marker = new maplibregl.Marker({ element: markerEl })
        .setLngLat([-47.1706, -11.5637])
        .addTo(map);
      
      map.on("load", () => {
        // Add trail source and layer
        map.addSource("trail", {
          type: "geojson",
          data: {
            type: "Feature",
            geometry: { type: "LineString", coordinates: [] },
            properties: {}
          }
        });
        
        map.addLayer({
          id: "trail-line",
          type: "line",
          source: "trail",
          layout: {
            "line-join": "round",
            "line-cap": "round"
          },
          paint: {
            "line-color": "#f59e0b",
            "line-width": 5,
            "line-opacity": 0.9
          }
        });
        
        trailSource = map.getSource("trail");
        setMapLoaded(true);
      });
      
    } catch (err) {
      console.error("Failed to initialize map:", err);
    }
  });
  
  // Update marker position - track animationProgress explicitly
  createEffect(() => {
    // Track these signals explicitly
    const progress = animationProgress();
    const loaded = mapLoaded();
    
    if (!map || !loaded || !marker) return;
    
    const point = interpolatedPoint();
    if (!point) return;
    
    // Update marker position
    marker.setLngLat([point.longitude, point.latitude]);
    
    // Center map on first load
    if (progress < 1) {
      map.jumpTo({ center: [point.longitude, point.latitude], zoom: 16 });
    }
  });
  
  // Update trail separately
  createEffect(() => {
    const loaded = mapLoaded();
    const trail = trailGeoJSON();
    const showIt = showTrail();
    
    if (!map || !loaded || !trailSource) return;
    
    if (trail && showIt) {
      trailSource.setData(trail);
    } else {
      trailSource.setData({ type: "Feature", geometry: { type: "LineString", coordinates: [] }, properties: {} });
    }
  });
  
  // Update map style
  createEffect(() => {
    if (!map || !mapLoaded()) return;
    
    const style = mapStyle();
    const getStyle = (s: string) => {
      if (s === 'osm') return { version: 8 as const, sources: { osm: { type: "raster" as const, tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256 } }, layers: [{ id: "osm-layer", type: "raster" as const, source: "osm" }] };
      if (s === 'esri-satellite') return { version: 8 as const, sources: { esri: { type: "raster" as const, tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"], tileSize: 256 } }, layers: [{ id: "esri-layer", type: "raster" as const, source: "esri" }] };
      return { version: 8 as const, sources: { satellite: { type: "raster" as const, tiles: ["https://mt0.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"], tileSize: 256 } }, layers: [{ id: "satellite-layer", type: "raster" as const, source: "satellite" }] };
    };
    
    map.once('style.load', () => {
      // Re-add trail source and layer after style change
      if (!map.getSource('trail')) {
        map.addSource("trail", {
          type: "geojson",
          data: trailGeoJSON() || { type: "Feature", geometry: { type: "LineString", coordinates: [] }, properties: {} }
        });
        
        map.addLayer({
          id: "trail-line",
          type: "line",
          source: "trail",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: { "line-color": "#f59e0b", "line-width": 5, "line-opacity": 0.9 }
        });
        
        trailSource = map.getSource("trail");
      }
    });
    
    map.setStyle(getStyle(style));
  });

  // Cleanup
  onCleanup(() => {
    if (marker) {
      marker.remove();
      marker = null;
    }
    if (map) {
      map.remove();
      map = null;
    }
  });

  const formatTime = (point: TelemetryPoint | null) => {
    if (!point) return "--:--:--";
    return new Date(point.time).toLocaleTimeString();
  };

  const events = createMemo(() => {
    const data = replayData()?.data;
    if (!data?.length) return [];
    
    const eventList: { index: number; time: string; type: string; message: string }[] = [];
    
    for (let i = 1; i < data.length; i++) {
      const prev = data[i - 1];
      const curr = data[i];
      
      if (curr.speed_kmh > 50) eventList.push({ index: i, time: new Date(curr.time).toLocaleTimeString(), type: "speed", message: `Velocidade: ${curr.speed_kmh.toFixed(1)} km/h` });
      if (curr.accel_magnitude > 12) eventList.push({ index: i, time: new Date(curr.time).toLocaleTimeString(), type: "impact", message: `Impacto: ${curr.accel_magnitude.toFixed(1)} m/s²` });
      if (prev.speed_kmh > 10 && curr.speed_kmh < 1) eventList.push({ index: i, time: new Date(curr.time).toLocaleTimeString(), type: "brake", message: "Frenagem brusca" });
    }
    
    return eventList.slice(0, 50);
  });

  const jumpToEvent = (index: number) => {
    setAnimationProgress(index);
    setCurrentIndex(index);
    setIsPlaying(false);
    
    // Center map on event
    const data = replayData()?.data;
    if (data && data[index] && map) {
      map.flyTo({ center: [data[index].longitude, data[index].latitude], zoom: 17, duration: 500 });
    }
  };

  const handlePlay = () => {
    if (!isPlaying()) {
      setAnimationProgress(currentIndex());
    }
    setIsPlaying(!isPlaying());
  };

  const handleSeek = (index: number) => {
    setAnimationProgress(index);
    setCurrentIndex(index);
    setIsPlaying(false);
    
    // Center map on seek position
    const data = replayData()?.data;
    if (data && data[index] && map) {
      map.flyTo({ center: [data[index].longitude, data[index].latitude], duration: 300 });
    }
  };

  return (
    <AppLayout>
      <div class="flex flex-col gap-4" style={{ height: "calc(100vh - 120px)" }}>
        {/* Controls Bar */}
        <div class="card">
          <div class="card-body" style={{ padding: "var(--space-3) var(--space-4)" }}>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-4">
                <select 
                  value={selectedDevice()}
                  onChange={(e) => {
                    setSelectedDevice(e.target.value);
                    setCurrentIndex(0);
                    setAnimationProgress(0);
                    setIsPlaying(false);
                  }}
                  class="btn btn-secondary"
                  style={{ "min-width": "180px" }}
                >
                  <option value="">Selecionar dispositivo</option>
                  <For each={devicesData()?.devices || []}>
                    {(device) => <option value={device.device_id}>{device.device_id}</option>}
                  </For>
                </select>

                <select
                  value={hoursBack()}
                  onChange={(e) => {
                    setHoursBack(parseInt(e.target.value));
                    setCurrentIndex(0);
                    setAnimationProgress(0);
                    setIsPlaying(false);
                  }}
                  class="btn btn-secondary"
                >
                  <option value={1}>Última 1 hora</option>
                  <option value={2}>Últimas 2 horas</option>
                  <option value={6}>Últimas 6 horas</option>
                  <option value={24}>Últimas 24 horas</option>
                </select>

                <button class="btn btn-primary" onClick={() => { refetch(); setCurrentIndex(0); setAnimationProgress(0); }}>
                  Carregar
                </button>

                <Show when={replayData()?.data?.length}>
                  <span class="badge" style={{ background: "var(--color-accent-primary)", color: "black" }}>
                    {replayData()!.data.length.toLocaleString()} pontos
                  </span>
                </Show>
              </div>

              <div class="flex items-center gap-3">
                <select
                  value={mapStyle()}
                  onChange={(e) => setMapStyle(e.target.value as 'google-satellite' | 'esri-satellite' | 'osm')}
                  class="btn btn-secondary"
                >
                  <option value="esri-satellite">Esri Satélite</option>
                  <option value="google-satellite">Google Satélite</option>
                  <option value="osm">OpenStreetMap</option>
                </select>
                
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={showTrail()} onChange={(e) => setShowTrail(e.target.checked)} />
                  <span class="text-sm">Trilha</span>
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div class="flex gap-4" style={{ "min-height": "450px", flex: "1 1 auto" }}>
          {/* Map Area */}
          <div class="card" style={{ flex: "1 1 auto", "min-height": "450px", overflow: "hidden", position: "relative", padding: 0 }}>
            <div ref={mapContainer} style={{ width: "100%", height: "100%", "min-height": "450px" }} />
            
            {/* Stats Overlay */}
            <Show when={interpolatedPoint()}>
              <div style={{
                position: "absolute",
                top: "16px",
                left: "16px",
                background: "rgba(0,0,0,0.85)",
                "backdrop-filter": "blur(8px)",
                padding: "10px 14px",
                "border-radius": "var(--radius-lg)",
                "font-size": "var(--text-xs)",
                "z-index": 20,
                border: "1px solid var(--color-border-primary)"
              }}>
                <div class="flex items-center gap-2 mb-1">
                  <span style={{ color: isPlaying() ? "#22c55e" : "#f59e0b" }}>●</span>
                  <span style={{ "font-weight": "600" }}>{isPlaying() ? "Reproduzindo" : "Pausado"}</span>
                </div>
                <div style={{ color: "#888", "font-family": "monospace" }}>
                  <div>Lat: {interpolatedPoint()?.latitude?.toFixed(6)}</div>
                  <div>Lon: {interpolatedPoint()?.longitude?.toFixed(6)}</div>
                </div>
              </div>

              <div style={{
                position: "absolute",
                bottom: "40px",
                left: "50%",
                transform: "translateX(-50%)",
                display: "flex",
                gap: "8px",
                "z-index": 20
              }}>
                <div style={{ background: "rgba(0,0,0,0.85)", padding: "6px 12px", "border-radius": "8px", "text-align": "center" }}>
                  <div style={{ "font-size": "10px", color: "#888" }}>Velocidade</div>
                  <div style={{ "font-weight": "600", color: "#f59e0b" }}>{interpolatedPoint()?.speed_kmh?.toFixed(1)} km/h</div>
                </div>
                <div style={{ background: "rgba(0,0,0,0.85)", padding: "6px 12px", "border-radius": "8px", "text-align": "center" }}>
                  <div style={{ "font-size": "10px", color: "#888" }}>Aceleração</div>
                  <div style={{ "font-weight": "600" }}>{interpolatedPoint()?.accel_magnitude?.toFixed(1)} m/s²</div>
                </div>
                <div style={{ background: "rgba(0,0,0,0.85)", padding: "6px 12px", "border-radius": "8px", "text-align": "center" }}>
                  <div style={{ "font-size": "10px", color: "#888" }}>Direção</div>
                  <div style={{ "font-weight": "600" }}>{interpolatedPoint()?.bearing?.toFixed(0)}°</div>
                </div>
              </div>
            </Show>
            
            {/* Loading state */}
            <Show when={!mapLoaded()}>
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
          </div>

          {/* Events Panel */}
          <div class="card" style={{ width: "260px", "min-width": "260px" }}>
            <div class="card-header" style={{ padding: "12px 16px" }}>
              <h3 style={{ "font-size": "14px", "font-weight": "600" }}>Eventos</h3>
              <span class="badge">{events().length}</span>
            </div>
            <div style={{ overflow: "auto", "max-height": "380px" }}>
              <Show when={events().length > 0} fallback={
                <div class="p-4 text-center text-muted" style={{ "font-size": "13px" }}>Nenhum evento</div>
              }>
                <For each={events()}>
                  {(event) => (
                    <div 
                      onClick={() => jumpToEvent(event.index)}
                      style={{ 
                        padding: "8px 12px",
                        "border-bottom": "1px solid var(--color-border-primary)",
                        cursor: "pointer",
                        background: currentIndex() === event.index ? "var(--color-bg-hover)" : "transparent",
                        display: "flex",
                        "align-items": "center",
                        gap: "8px"
                      }}
                    >
                      <div style={{
                        width: "6px", height: "6px", "border-radius": "50%",
                        background: event.type === "impact" ? "#ef4444" : event.type === "speed" ? "#f59e0b" : "#3b82f6"
                      }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ "font-size": "12px" }}>{event.message}</div>
                        <div style={{ "font-size": "10px", color: "#888" }}>{event.time}</div>
                      </div>
                    </div>
                  )}
                </For>
              </Show>
            </div>
          </div>
        </div>

        {/* Timeline & Controls */}
        <div class="card">
          <div style={{ padding: "16px" }}>
            <div style={{ "margin-bottom": "12px" }}>
              <div class="flex items-center gap-4">
                <span style={{ width: "70px", "font-size": "12px" }}>{formatTime(replayData()?.data?.[currentIndex()])}</span>
                <input 
                  type="range" 
                  min="0" 
                  max={Math.max(1, (replayData()?.data?.length || 1) - 1)}
                  value={currentIndex()}
                  onInput={(e) => handleSeek(parseInt(e.target.value))}
                  style={{ flex: 1, height: "6px", "accent-color": "#f59e0b", cursor: "pointer" }}
                />
                <span style={{ width: "70px", "font-size": "12px", color: "#888" }}>
                  {replayData()?.data?.length ? formatTime(replayData()!.data[replayData()!.data.length - 1]) : "--:--:--"}
                </span>
              </div>
            </div>

            <div class="flex items-center justify-center gap-4">
              <button class="btn btn-ghost" style={{ width: "40px", height: "40px" }} onClick={() => handleSeek(Math.max(0, currentIndex() - 30))}>⏮</button>
              <button class="btn btn-primary" style={{ width: "56px", height: "56px", "border-radius": "50%", "font-size": "24px" }} onClick={handlePlay} disabled={!replayData()?.data?.length}>
                {isPlaying() ? "⏸" : "▶"}
              </button>
              <button class="btn btn-ghost" style={{ width: "40px", height: "40px" }} onClick={() => handleSeek(Math.min((replayData()?.data?.length || 1) - 1, currentIndex() + 30))}>⏭</button>

              <div class="flex items-center gap-1 ml-4" style={{ background: "var(--color-bg-tertiary)", padding: "4px", "border-radius": "8px" }}>
                <For each={[0.5, 1, 2, 4, 8, 16]}>
                  {(speed) => (
                    <button class={playbackSpeed() === speed ? "btn btn-primary" : "btn btn-ghost"} style={{ "min-width": "40px", height: "32px", "font-size": "12px" }} onClick={() => setPlaybackSpeed(speed)}>{speed}x</button>
                  )}
                </For>
              </div>

              <div style={{ "margin-left": "16px", "font-size": "13px" }}>
                <span style={{ color: "#f59e0b", "font-weight": "600" }}>{(currentIndex() + 1).toLocaleString()}</span>
                <span style={{ color: "#888" }}> / {(replayData()?.data?.length || 0).toLocaleString()}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </AppLayout>
  );
}
