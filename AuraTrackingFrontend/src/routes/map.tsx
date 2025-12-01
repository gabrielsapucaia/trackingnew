import { createSignal, createResource, onMount, onCleanup, Show, For, createEffect } from "solid-js";
import AppLayout from "~/layouts/AppLayout";
import { api, type Device, type TelemetryPoint } from "~/lib/api/client";
import type { TelemetryPacket } from "~/lib/mqtt/types";
import { convertDatum, type Datum, applyCoordinateOffset, getRecommendedOffset } from "~/lib/utils/geo";

// Declare maplibregl as any for dynamic import
let maplibregl: any = null;

export default function MapPage() {
  const [selectedDevice, setSelectedDevice] = createSignal<string | null>(null);
  const [showTrail, setShowTrail] = createSignal(true);
  const [mapLoaded, setMapLoaded] = createSignal(false);
  const [mapStyle, setMapStyle] = createSignal<'google-satellite' | 'esri-satellite' | 'osm'>('esri-satellite');
  const [datum, setDatum] = createSignal<'WGS84' | 'SIRGAS2000'>('WGS84');
  const [coordinateOffset, setCoordinateOffset] = createSignal({ lat: 0, lon: 0 });
  const [showOffsetPanel, setShowOffsetPanel] = createSignal(false);
  const [manualOffset, setManualOffset] = createSignal({ lat: 0, lon: 0 });
  
  // Real-time device data from MQTT
  const [realtimePosition, setRealtimePosition] = createSignal<{
    latitude: number;
    longitude: number;
    speed: number;
    bearing: number;
    timestamp: number;
  } | null>(null);
  
  let mapContainer: HTMLDivElement | undefined;
  let map: any = null;
  let deviceMarker: any = null;
  let trailSource: any = null;
  
  // Fetch devices once on load (no polling!)
  const [devicesData, { refetch: refetchDevices }] = createResource(() => api.getDevices());
  
  // Fetch trail for selected device
  const [trailData, { refetch: refetchTrail }] = createResource(
    () => selectedDevice(),
    async (deviceId) => {
      if (!deviceId) return null;
      return api.getTelemetry({ device_id: deviceId, limit: 100 });
    }
  );

  // Auto-select first device
  const devices = () => devicesData()?.devices || [];
  
  onMount(() => {
    const checkDevices = setInterval(() => {
      if (devices().length > 0 && !selectedDevice()) {
        setSelectedDevice(devices()[0].device_id);
        // Wait a bit for device data to load, then center map
        setTimeout(() => {
          centerMapOnDevice();
        }, 1000);
        clearInterval(checkDevices);
      }
    }, 500);
    return () => clearInterval(checkDevices);
  });

  // Get current device (from API data, merged with realtime)
  const currentDevice = () => {
    const device = devices().find(d => d.device_id === selectedDevice());
    if (!device) return null;

    // Merge with realtime data if available
    const rt = realtimePosition();
    if (rt && rt.latitude && rt.longitude) {
      // Apply datum conversion if needed
      let convertedCoords = convertDatum(rt.latitude, rt.longitude, 'WGS84', datum() as Datum);
      // Apply coordinate offset for map alignment
      convertedCoords = applyCoordinateOffset(
        convertedCoords.lat,
        convertedCoords.lon,
        coordinateOffset().lat,
        coordinateOffset().lon
      );
      return {
        ...device,
        latitude: convertedCoords.lat,
        longitude: convertedCoords.lon,
        speed_kmh: rt.speed * 3.6, // m/s to km/h
        last_seen: new Date(rt.timestamp).toISOString()
      };
    }

    // Use API data if available, apply datum conversion and offset
    if (device.latitude && device.longitude) {
      let convertedCoords = convertDatum(device.latitude, device.longitude, 'WGS84', datum() as Datum);
      // Apply coordinate offset for map alignment
      convertedCoords = applyCoordinateOffset(
        convertedCoords.lat,
        convertedCoords.lon,
        coordinateOffset().lat,
        coordinateOffset().lon
      );
      return {
        ...device,
        latitude: convertedCoords.lat,
        longitude: convertedCoords.lon
      };
    }

    return {
      ...device,
      latitude: device.latitude || null,
      longitude: device.longitude || null
    };
  };

  // Listen to MQTT telemetry events for real-time updates
  onMount(() => {
    if (typeof window === "undefined") return;
    
    const handleTelemetry = (event: CustomEvent<{ topic: string; packet: TelemetryPacket }>) => {
      const { packet } = event.detail;
      const selected = selectedDevice();
      
      // Normalize device IDs for comparison (handle spaces, case, etc.)
      const normalizeId = (id: string) => id.toLowerCase().replace(/[^a-z0-9]/g, '');
      
      // Only process if this is the selected device
      if (selected && normalizeId(packet.deviceId) === normalizeId(selected)) {
        setRealtimePosition({
          latitude: packet.gps.latitude,
          longitude: packet.gps.longitude,
          speed: packet.gps.speed || 0,
          bearing: packet.gps.bearing || 0,
          timestamp: packet.timestamp
        });
      }
    };
    
    window.addEventListener("telemetry", handleTelemetry as EventListener);
    
    return () => {
      window.removeEventListener("telemetry", handleTelemetry as EventListener);
    };
  });
  
  // Refresh trail periodically (less frequently, every 30s)
  onMount(() => {
    const interval = setInterval(() => {
      if (selectedDevice()) {
        refetchTrail();
      }
    }, 30000);
    return () => clearInterval(interval);
  });

  // Initialize MapLibre GL
  onMount(async () => {
    if (typeof window === "undefined" || !mapContainer) return;
    
    try {
      const maplibre = await import("maplibre-gl");
      maplibregl = maplibre.default;
      
      // Add MapLibre CSS
      if (!document.getElementById("maplibre-css")) {
        const link = document.createElement("link");
        link.id = "maplibre-css";
        link.rel = "stylesheet";
        link.href = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css";
        document.head.appendChild(link);
      }
      
      // Initialize map based on selected style
      const createMapStyle = (style: string) => {
        if (style === 'osm') {
          return {
            version: 8,
            sources: {
              osm: {
                type: "raster",
                tiles: [
                  "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                ],
                tileSize: 256,
                attribution: "© OpenStreetMap contributors"
              }
            },
            layers: [
              {
                id: "osm-layer",
                type: "raster",
                source: "osm",
                minzoom: 0,
                maxzoom: 19
              }
            ]
          };
        } else if (style === 'esri-satellite') {
          // Esri World Imagery - more accurate for Brazil
          return {
            version: 8,
            sources: {
              esri: {
                type: "raster",
                tiles: [
                  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                ],
                tileSize: 256,
                attribution: "© Esri"
              }
            },
            layers: [
              {
                id: "esri-layer",
                type: "raster",
                source: "esri",
                minzoom: 0,
                maxzoom: 19
              }
            ]
          };
        } else {
          // Google satellite style
          return {
            version: 8,
            sources: {
              satellite: {
                type: "raster",
                tiles: [
                  "https://mt0.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
                  "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
                  "https://mt2.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
                  "https://mt3.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
                ],
                tileSize: 256,
                attribution: "© Google Maps"
              }
            },
            layers: [
              {
                id: "satellite-layer",
                type: "raster",
                source: "satellite",
                minzoom: 0,
                maxzoom: 22
              }
            ]
          };
        }
      };

      map = new maplibregl.Map({
        container: mapContainer,
        style: createMapStyle(mapStyle()),
        center: [-47.1706, -11.5637], // Default: Tocantins, Brazil
        zoom: 14,
        pitch: 0,
        bearing: 0,
        attributionControl: false
      });
      
      // Add navigation controls
      map.addControl(new maplibregl.NavigationControl({
        showCompass: true,
        showZoom: true,
        visualizePitch: true
      }), "bottom-right");
      
      // Add scale control
      map.addControl(new maplibregl.ScaleControl({
        maxWidth: 100,
        unit: "metric"
      }), "bottom-left");
      
      // Add fullscreen control
      map.addControl(new maplibregl.FullscreenControl(), "top-right");
      
      map.on("load", () => {
        setMapLoaded(true);
        
        // Add trail source
        map.addSource("trail", {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: []
          }
        });
        
        // Add trail line layer with gradient based on speed
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
            "line-width": 4,
            "line-opacity": 0.8
          }
        });
        
        // Add trail points layer
        map.addLayer({
          id: "trail-points",
          type: "circle",
          source: "trail",
          filter: ["==", "$type", "Point"],
          paint: {
            "circle-radius": 4,
            "circle-color": "#f59e0b",
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff"
          }
        });
      });
      
    } catch (err) {
      console.error("Failed to initialize map:", err);
    }
  });
  
  // Cleanup on unmount
  onCleanup(() => {
    if (map) {
      map.remove();
      map = null;
    }
  });
  
  // Update device marker smoothly when device data changes (from API or MQTT)
  createEffect(() => {
    const device = currentDevice();
    if (!map || !mapLoaded() || !device?.latitude || !device?.longitude) {
      if (deviceMarker) {
        deviceMarker.remove();
        deviceMarker = null;
      }
      return;
    }
    
    const lngLat: [number, number] = [device.longitude, device.latitude];
    const speed = device.speed_kmh?.toFixed(0) || 0;
    
    if (!deviceMarker) {
      // Create marker element
      const el = document.createElement("div");
      el.className = "device-marker";
      el.innerHTML = `
        <div class="marker-pulse"></div>
        <div class="marker-inner">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="white" stroke="none">
            <!-- Truck body -->
            <rect x="2" y="8" width="16" height="10" rx="2" fill="white"/>
            <!-- Truck cabin -->
            <rect x="18" y="6" width="6" height="12" rx="1" fill="white"/>
            <!-- Front wheel -->
            <circle cx="6" cy="20" r="3" fill="white"/>
            <circle cx="6" cy="20" r="1.5" fill="#1a1a2e"/>
            <!-- Rear wheels -->
            <circle cx="14" cy="20" r="3" fill="white"/>
            <circle cx="14" cy="20" r="1.5" fill="#1a1a2e"/>
            <circle cx="20" cy="20" r="3" fill="white"/>
            <circle cx="20" cy="20" r="1.5" fill="#1a1a2e"/>
            <!-- Windows -->
            <rect x="19" y="8" width="4" height="2" rx="0.5" fill="#1a1a2e"/>
            <rect x="19" y="12" width="4" height="2" rx="0.5" fill="#1a1a2e"/>
            <!-- Headlights -->
            <circle cx="24" cy="10" r="0.8" fill="#f59e0b"/>
          </svg>
        </div>
        <div class="marker-speed">${speed} km/h</div>
        <div class="marker-tag">${device.device_id}</div>
      `;
      
      deviceMarker = new maplibregl.Marker({
        element: el,
        anchor: "center"
      })
        .setLngLat(lngLat)
        .addTo(map);
      
      // Fly to device location
      map.flyTo({
        center: lngLat,
        zoom: 16,
        duration: 1500,
        essential: true
      });
    } else {
      // Smoothly animate marker to new position using easing
      const currentPos = deviceMarker.getLngLat();
      const startLng = currentPos.lng;
      const startLat = currentPos.lat;
      const endLng = lngLat[0];
      const endLat = lngLat[1];
      
      // Only animate if position changed significantly
      const distance = Math.sqrt(
        Math.pow(endLng - startLng, 2) + Math.pow(endLat - startLat, 2)
      );
      
      if (distance > 0.000001) {
        // Animate over 300ms
        const duration = 300;
        const startTime = performance.now();
        
        const animate = (currentTime: number) => {
          const elapsed = currentTime - startTime;
          const progress = Math.min(elapsed / duration, 1);
          
          // Ease-out cubic
          const eased = 1 - Math.pow(1 - progress, 3);
          
          const lng = startLng + (endLng - startLng) * eased;
          const lat = startLat + (endLat - startLat) * eased;
          
          deviceMarker.setLngLat([lng, lat]);
          
          if (progress < 1) {
            requestAnimationFrame(animate);
          }
        };
        
        requestAnimationFrame(animate);
      }
      
      // Update speed display
      const speedEl = deviceMarker.getElement().querySelector(".marker-speed");
      if (speedEl) {
        speedEl.textContent = `${speed} km/h`;
      }
    }
  });
  
  // Initialize offset on mount
  onMount(() => {
    const recommendedOffset = getRecommendedOffset(mapStyle());
    setCoordinateOffset({
      lat: recommendedOffset.lat + manualOffset().lat,
      lon: recommendedOffset.lon + manualOffset().lon
    });
  });

  // Update map style when style changes
  createEffect(() => {
    if (!map || !mapLoaded()) return;

    const createMapStyle = (style: string) => {
      if (style === 'osm') {
        return {
          version: 8,
          sources: {
            osm: {
              type: "raster",
              tiles: [
                "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
              ],
              tileSize: 256,
              attribution: "© OpenStreetMap contributors"
            }
          },
          layers: [
            {
              id: "osm-layer",
              type: "raster",
              source: "osm",
              minzoom: 0,
              maxzoom: 19
            }
          ]
        };
      } else if (style === 'esri-satellite') {
        return {
          version: 8,
          sources: {
            esri: {
              type: "raster",
              tiles: [
                "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              ],
              tileSize: 256,
              attribution: "© Esri"
            }
          },
          layers: [
            {
              id: "esri-layer",
              type: "raster",
              source: "esri",
              minzoom: 0,
              maxzoom: 19
            }
          ]
        };
      } else {
        return {
          version: 8,
          sources: {
            satellite: {
              type: "raster",
              tiles: [
                "https://mt0.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
                "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
                "https://mt2.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
                "https://mt3.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
              ],
              tileSize: 256,
              attribution: "© Google Maps"
            }
          },
          layers: [
            {
              id: "satellite-layer",
              type: "raster",
              source: "satellite",
              minzoom: 0,
              maxzoom: 22
            }
          ]
        };
      }
    };

    map.setStyle(createMapStyle(mapStyle()));
    
    // Apply recommended offset for the selected map provider
    const recommendedOffset = getRecommendedOffset(mapStyle());
    // Combine with manual offset
    setCoordinateOffset({
      lat: recommendedOffset.lat + manualOffset().lat,
      lon: recommendedOffset.lon + manualOffset().lon
    });
  });
  
  // Update coordinate offset when manual offset changes
  createEffect(() => {
    const recommendedOffset = getRecommendedOffset(mapStyle());
    setCoordinateOffset({
      lat: recommendedOffset.lat + manualOffset().lat,
      lon: recommendedOffset.lon + manualOffset().lon
    });
  });

  // Update trail when trail data or datum changes
  createEffect(() => {
    const trail = trailData()?.data || [];
    if (!map || !mapLoaded() || !showTrail()) {
      if (map && mapLoaded() && map.getSource("trail")) {
        map.getSource("trail").setData({
          type: "FeatureCollection",
          features: []
        });
      }
      return;
    }
    
    if (trail.length > 0 && map.getSource("trail")) {
      // Create line from trail points, applying datum conversion and offset
      const coordinates = trail
        .filter(p => p.latitude && p.longitude)
        .map(p => {
          let converted = convertDatum(p.latitude, p.longitude, 'WGS84', datum() as Datum);
          // Apply coordinate offset for map alignment
          converted = applyCoordinateOffset(
            converted.lat,
            converted.lon,
            coordinateOffset().lat,
            coordinateOffset().lon
          );
          return [converted.lon, converted.lat];
        });
      
      const geojsonData = {
        type: "FeatureCollection" as const,
        features: [
          {
            type: "Feature" as const,
            properties: {},
            geometry: {
              type: "LineString" as const,
              coordinates: coordinates
            }
          },
          // Add points at each trail position, applying datum conversion and offset
          ...trail
            .filter(p => p.latitude && p.longitude)
            .map((p, i) => {
              let converted = convertDatum(p.latitude, p.longitude, 'WGS84', datum() as Datum);
              // Apply coordinate offset for map alignment
              converted = applyCoordinateOffset(
                converted.lat,
                converted.lon,
                coordinateOffset().lat,
                coordinateOffset().lon
              );
              return {
                type: "Feature" as const,
                properties: {
                  speed: p.speed_kmh,
                  index: i
                },
                geometry: {
                  type: "Point" as const,
                  coordinates: [converted.lon, converted.lat]
                }
              };
            })
        ]
      };
      
      map.getSource("trail").setData(geojsonData);
    }
  });
  
  // Center on device
  const centerOnDevice = () => {
    const device = currentDevice();
    if (map && mapLoaded() && device?.latitude && device?.longitude) {
      map.flyTo({
        center: [device.longitude, device.latitude],
        zoom: 16,
        duration: 1000
      });
    }
  };

  // Center map on device when available (used for initial centering)
  const centerMapOnDevice = () => {
    const device = currentDevice();
    if (map && mapLoaded() && device?.latitude && device?.longitude) {
      map.flyTo({
        center: [device.longitude, device.latitude],
        zoom: 16,
        duration: 1500,
        essential: true
      });
    } else if (map && mapLoaded() && devices().length > 0) {
      // If device doesn't have coordinates yet, wait a bit and try again
      setTimeout(centerMapOnDevice, 2000);
    }
  };

  return (
    <AppLayout>
      <div class="flex flex-col gap-4 h-full" style={{ "min-height": "calc(100vh - 120px)" }}>
        {/* Map Controls */}
        <div class="flex items-center justify-between">
          <div class="flex gap-2">
            <select
              class="btn btn-secondary"
              style={{ "min-width": "200px", cursor: "pointer" }}
              value={selectedDevice() || ""}
              onChange={(e) => {
                setSelectedDevice(e.target.value || null);
                setRealtimePosition(null); // Reset realtime when changing device
                // Center map on newly selected device
                setTimeout(() => {
                  centerMapOnDevice();
                }, 500);
              }}
            >
              <option value="">Selecionar dispositivo</option>
              <For each={devices()}>
                {(device) => (
                  <option value={device.device_id}>
                    {device.device_id} ({device.status})
                  </option>
                )}
              </For>
            </select>
            <select
              class="btn btn-secondary"
              value={mapStyle()}
              onChange={(e) => setMapStyle(e.target.value as 'google-satellite' | 'esri-satellite' | 'osm')}
            >
              <option value="esri-satellite">Esri Satélite (Recomendado)</option>
              <option value="google-satellite">Google Satélite</option>
              <option value="osm">OpenStreetMap</option>
            </select>
            <select
              class="btn btn-secondary"
              value={datum()}
              onChange={(e) => setDatum(e.target.value as 'WGS84' | 'SIRGAS2000')}
            >
              <option value="WGS84">WGS84</option>
              <option value="SIRGAS2000">SIRGAS2000</option>
            </select>
            <button
              class={`btn ${showTrail() ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setShowTrail(!showTrail())}
            >
              <TrailIcon />
              Trilha
            </button>
          </div>
          <div class="flex gap-2 items-center">
            <Show when={currentDevice()}>
              <button 
                class="btn btn-ghost btn-icon" 
                title="Centralizar no dispositivo"
                onClick={centerOnDevice}
              >
                <CenterIcon />
              </button>
              <div class="badge badge-success">
                <span style={{ 
                  width: "8px", 
                  height: "8px", 
                  background: currentDevice()?.status === 'online' ? "var(--color-success)" : "var(--color-error)", 
                  "border-radius": "50%",
                  "margin-right": "6px"
                }} />
                {currentDevice()?.status === 'online' ? 'Online' : 'Offline'}
              </div>
            </Show>
            <button class="btn btn-ghost btn-icon" title="Atualizar dispositivos" onClick={() => refetchDevices()}>
              <RefreshIcon />
            </button>
          </div>
        </div>

        {/* Map Container */}
        <div class="card flex-1" style={{ 
          "min-height": "500px",
          position: "relative",
          overflow: "hidden",
          padding: 0
        }}>
          {/* MapLibre GL Container */}
          <div 
            ref={mapContainer}
            style={{
              width: "100%",
              height: "100%",
              "min-height": "500px"
            }}
          />
          
          {/* Loading overlay */}
          <Show when={!mapLoaded()}>
            <div style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: "var(--color-bg-primary)",
              display: "flex",
              "align-items": "center",
              "justify-content": "center",
              "z-index": 10
            }}>
              <div class="text-center">
                <div class="spinner" style={{ width: "40px", height: "40px", margin: "0 auto 16px" }} />
                <p class="text-muted">Carregando mapa...</p>
              </div>
            </div>
          </Show>

          {/* Map Legend (overlay) */}
          <div style={{
            position: "absolute",
            bottom: "40px",
            left: "16px",
            background: "rgba(26, 26, 46, 0.9)",
            "backdrop-filter": "blur(8px)",
            border: "1px solid var(--color-border-primary)",
            "border-radius": "var(--radius-lg)",
            padding: "var(--space-3)",
            "font-size": "var(--text-xs)",
            "z-index": 5
          }}>
            <div style={{ "font-weight": "600", "margin-bottom": "var(--space-2)" }}>
              Velocidade
            </div>
            <div class="flex flex-col gap-1">
              <div class="flex items-center gap-2">
                <span style={{ width: "12px", height: "3px", background: "var(--color-speed-low)", "border-radius": "2px" }} />
                <span class="text-muted">0-20 km/h</span>
              </div>
              <div class="flex items-center gap-2">
                <span style={{ width: "12px", height: "3px", background: "var(--color-speed-medium)", "border-radius": "2px" }} />
                <span class="text-muted">20-40 km/h</span>
              </div>
              <div class="flex items-center gap-2">
                <span style={{ width: "12px", height: "3px", background: "var(--color-speed-high)", "border-radius": "2px" }} />
                <span class="text-muted">40-60 km/h</span>
              </div>
              <div class="flex items-center gap-2">
                <span style={{ width: "12px", height: "3px", background: "var(--color-speed-danger)", "border-radius": "2px" }} />
                <span class="text-muted">60-80 km/h</span>
              </div>
              <div class="flex items-center gap-2">
                <span style={{ width: "12px", height: "3px", background: "var(--color-speed-critical)", "border-radius": "2px" }} />
                <span class="text-muted">&gt;80 km/h</span>
              </div>
            </div>
          </div>

          {/* Offset Adjustment Panel */}
          <div style={{
            position: "absolute",
            top: "16px",
            right: "16px",
            background: "rgba(26, 26, 46, 0.9)",
            "backdrop-filter": "blur(8px)",
            border: "1px solid var(--color-border-primary)",
            "border-radius": "var(--radius-lg)",
            padding: "var(--space-3)",
            width: "280px",
            "z-index": 5
          }}>
            <div class="flex items-center justify-between" style={{ "margin-bottom": "var(--space-2)" }}>
              <h4 style={{ "font-weight": "600", "font-size": "var(--text-sm)" }}>
                Ajuste de Alinhamento
              </h4>
              <button
                class="btn btn-ghost btn-icon"
                onClick={() => setShowOffsetPanel(!showOffsetPanel())}
                style={{ padding: "4px" }}
              >
                {showOffsetPanel() ? "−" : "+"}
              </button>
            </div>
            <Show when={showOffsetPanel()}>
              <div class="flex flex-col gap-2" style={{ "font-size": "var(--text-xs)" }}>
                <div>
                  <label class="text-muted" style={{ display: "block", "margin-bottom": "4px" }}>
                    Offset Norte/Sul (metros)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={manualOffset().lat * 111320}
                    onChange={(e) => {
                      const meters = parseFloat(e.target.value) || 0;
                      setManualOffset({ ...manualOffset(), lat: meters / 111320 });
                    }}
                    style={{
                      width: "100%",
                      padding: "6px",
                      background: "var(--color-bg-secondary)",
                      border: "1px solid var(--color-border-primary)",
                      "border-radius": "var(--radius-md)",
                      color: "white"
                    }}
                  />
                </div>
                <div>
                  <label class="text-muted" style={{ display: "block", "margin-bottom": "4px" }}>
                    Offset Leste/Oeste (metros)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={manualOffset().lon * 111320 * Math.cos(-11.5 * Math.PI / 180)}
                    onChange={(e) => {
                      const meters = parseFloat(e.target.value) || 0;
                      const latRad = -11.5 * Math.PI / 180; // Approximate Tocantins latitude
                      setManualOffset({ ...manualOffset(), lon: meters / (111320 * Math.cos(latRad)) });
                    }}
                    style={{
                      width: "100%",
                      padding: "6px",
                      background: "var(--color-bg-secondary)",
                      border: "1px solid var(--color-border-primary)",
                      "border-radius": "var(--radius-md)",
                      color: "white"
                    }}
                  />
                </div>
                <button
                  class="btn btn-secondary"
                  onClick={() => {
                    setManualOffset({ lat: 0, lon: 0 });
                  }}
                  style={{ "margin-top": "8px", padding: "6px" }}
                >
                  Resetar
                </button>
                <div class="text-muted" style={{ "font-size": "10px", "margin-top": "4px" }}>
                  Offset atual: {coordinateOffset().lat.toFixed(6)}°, {coordinateOffset().lon.toFixed(6)}°
                </div>
              </div>
            </Show>
          </div>

          {/* Device Info Panel */}
          <Show when={currentDevice()}>
            <div style={{
              position: "absolute",
              top: "16px",
              left: "16px",
              background: "rgba(26, 26, 46, 0.9)",
              "backdrop-filter": "blur(8px)",
              border: "1px solid var(--color-border-primary)",
              "border-radius": "var(--radius-lg)",
              padding: "var(--space-4)",
              width: "250px",
              "z-index": 5
            }}>
              <h4 style={{ "font-weight": "600", "margin-bottom": "var(--space-3)" }}>
                Informações
              </h4>
              <div class="flex flex-col gap-2" style={{ "font-size": "var(--text-sm)" }}>
                <div class="flex justify-between">
                  <span class="text-muted">Dispositivo:</span>
                  <span>{currentDevice()!.device_id}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-muted">Operador:</span>
                  <span>{currentDevice()!.operator_id}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-muted">Velocidade:</span>
                  <span style={{ color: "var(--color-accent-primary)", "font-weight": "600" }}>
                    {currentDevice()!.speed_kmh?.toFixed(1) || 0} km/h
                  </span>
                </div>
                <div class="flex justify-between">
                  <span class="text-muted">Coordenadas:</span>
                  <span style={{ "font-size": "var(--text-xs)", "font-family": "var(--font-mono)" }}>
                    {currentDevice()!.latitude ? currentDevice()!.latitude.toFixed(5) : "-"}, {currentDevice()!.longitude ? currentDevice()!.longitude.toFixed(5) : "-"}
                  </span>
                </div>
                <div class="flex justify-between">
                  <span class="text-muted">Pontos (24h):</span>
                  <span>{currentDevice()!.total_points_24h?.toLocaleString()}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-muted">Última atualização:</span>
                  <span style={{ "font-size": "var(--text-xs)" }}>
                    {new Date(currentDevice()!.last_seen).toLocaleTimeString()}
                  </span>
                </div>
              </div>
            </div>
          </Show>
          
          {/* Trail info */}
          <Show when={showTrail() && trailData()?.data?.length}>
            <div style={{
              position: "absolute",
              top: "16px",
              right: "60px",
              background: "rgba(26, 26, 46, 0.9)",
              "backdrop-filter": "blur(8px)",
              border: "1px solid var(--color-border-primary)",
              "border-radius": "var(--radius-md)",
              padding: "8px 16px",
              "font-size": "var(--text-xs)",
              "z-index": 5
            }}>
              <span class="text-muted">Trilha: </span>
              <span style={{ color: "var(--color-accent-primary)", "font-weight": "600" }}>
                {trailData()!.data.length} pontos
              </span>
            </div>
          </Show>
          
          {/* Realtime indicator */}
          <Show when={realtimePosition()}>
            <div style={{
              position: "absolute",
              bottom: "16px",
              right: "60px",
              background: "rgba(16, 185, 129, 0.9)",
              "backdrop-filter": "blur(8px)",
              border: "1px solid rgba(16, 185, 129, 0.5)",
              "border-radius": "var(--radius-md)",
              padding: "6px 12px",
              "font-size": "var(--text-xs)",
              "z-index": 5,
              display: "flex",
              "align-items": "center",
              gap: "6px"
            }}>
              <span style={{
                width: "6px",
                height: "6px",
                background: "white",
                "border-radius": "50%",
                animation: "pulse-dot 1s infinite"
              }} />
              <span style={{ color: "white", "font-weight": "500" }}>
                Tempo Real via MQTT
              </span>
            </div>
          </Show>
        </div>
      </div>

      <style>{`
        .device-marker {
          position: relative;
          width: 70px;
          height: 70px;
        }

        .marker-pulse {
          position: absolute;
          width: 70px;
          height: 70px;
          background: rgba(245, 158, 11, 0.25);
          border-radius: 50%;
          animation: marker-pulse 2s infinite;
        }

        .marker-inner {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          width: 48px;
          height: 48px;
          background: var(--color-accent-primary);
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 6px 24px rgba(245, 158, 11, 0.6);
          border: 3px solid white;
          transition: all 0.3s ease;
        }

        .marker-inner:hover {
          transform: translate(-50%, -50%) scale(1.05);
          box-shadow: 0 8px 32px rgba(245, 158, 11, 0.8);
        }
        
        .marker-speed {
          position: absolute;
          top: -32px;
          left: 50%;
          transform: translateX(-50%);
          background: rgba(26, 26, 46, 0.95);
          padding: 6px 12px;
          border-radius: 16px;
          font-size: 12px;
          font-weight: 700;
          white-space: nowrap;
          border: 2px solid var(--color-border-primary);
          color: white;
          backdrop-filter: blur(10px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }

        .marker-tag {
          position: absolute;
          bottom: -38px;
          left: 50%;
          transform: translateX(-50%);
          background: rgba(245, 158, 11, 0.95);
          padding: 6px 10px;
          border-radius: 12px;
          font-size: 11px;
          font-weight: 700;
          white-space: nowrap;
          border: 2px solid rgba(245, 158, 11, 0.6);
          color: white;
          max-width: 100px;
          overflow: hidden;
          text-overflow: ellipsis;
          backdrop-filter: blur(10px);
          box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        
        @keyframes marker-pulse {
          0% {
            transform: scale(1);
            opacity: 0.4;
          }
          50% {
            transform: scale(1.2);
            opacity: 0.1;
          }
          100% {
            transform: scale(1);
            opacity: 0.4;
          }
        }
        
        @keyframes pulse-dot {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.3;
          }
        }
        
        .maplibregl-ctrl-group {
          background: rgba(26, 26, 46, 0.9) !important;
          border: 1px solid var(--color-border-primary) !important;
          backdrop-filter: blur(8px);
        }
        
        .maplibregl-ctrl-group button {
          background: transparent !important;
          border: none !important;
        }
        
        .maplibregl-ctrl-group button:hover {
          background: rgba(255, 255, 255, 0.1) !important;
        }
        
        .maplibregl-ctrl-group button .maplibregl-ctrl-icon {
          filter: invert(1);
        }
        
        .maplibregl-ctrl-scale {
          background: rgba(26, 26, 46, 0.9) !important;
          border: 1px solid var(--color-border-primary) !important;
          color: white !important;
          backdrop-filter: blur(8px);
        }
        
        .spinner {
          border: 3px solid var(--color-border-primary);
          border-top: 3px solid var(--color-accent-primary);
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </AppLayout>
  );
}

// Icon components
function TrailIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12 2L2 7l10 5 10-5-10-5z" />
      <path d="M2 17l10 5 10-5" />
      <path d="M2 12l10 5 10-5" />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M23 4v6h-6" />
      <path d="M1 20v-6h6" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  );
}

function CenterIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v4" />
      <path d="M12 18v4" />
      <path d="M2 12h4" />
      <path d="M18 12h4" />
    </svg>
  );
}
