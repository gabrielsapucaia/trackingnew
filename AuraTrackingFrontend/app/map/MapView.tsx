"use client";

import { useMemo, useRef, useState, useEffect, useCallback } from "react";
import { DeckGL } from "@deck.gl/react";
import { ScatterplotLayer } from "@deck.gl/layers";
import maplibregl from "maplibre-gl";
import Map from "react-map-gl/maplibre";
import type { DeviceSummary } from "../../types/devices";
import type { ViewStateChangeEvent } from "react-map-gl/maplibre";

type MapViewProps = {
  devices: DeviceSummary[];
  isLoading: boolean;
  error: string | null;
};

const INITIAL_VIEW_STATE = {
  latitude: -11.57,
  longitude: -47.18,
  zoom: 12,
  bearing: 0,
  pitch: 0
};

const SATELLITE_STYLE = "/satellite-ortho-style.json";

export default function MapView({ devices, isLoading, error }: MapViewProps) {
  const mapRef = useRef<any>(null);
  const [isMapLoaded, setIsMapLoaded] = useState(false);
  const [webglSupported, setWebglSupported] = useState(false);
  const [deckGLReady, setDeckGLReady] = useState(false);
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);

  // Verifica suporte a WebGL no cliente
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const canvas = document.createElement("canvas");
        const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl") as WebGLRenderingContext | null;
        if (gl && gl instanceof WebGLRenderingContext) {
          // Verifica se contexto tem propriedades necessárias
          try {
            gl.getParameter(gl.VERSION);
            setWebglSupported(true);
            // NÃO define deckGLReady aqui - será definido após Map carregar
          } catch {
            setWebglSupported(false);
          }
        } else {
          setWebglSupported(false);
        }
      } catch (e) {
        console.warn("WebGL not supported:", e);
        setWebglSupported(false);
      }
    }
  }, []);

  const validDevices = useMemo(
    () => devices.filter((d) => d.latitude !== null && d.longitude !== null),
    [devices]
  );

  const layers = useMemo(() => {
    if (!webglSupported) return [];
    
    return [
      new ScatterplotLayer<DeviceSummary>({
        id: "devices-layer",
        data: validDevices,
        getPosition: (d) => [d.longitude as number, d.latitude as number],
        getRadius: 50,
        radiusUnits: "meters",
        radiusMinPixels: 3,
        radiusMaxPixels: 30,
        getFillColor: (d) =>
          d.status === "online" ? [56, 189, 248, 200] : [148, 163, 184, 180],
        pickable: true,
        autoHighlight: false,
        updateTriggers: {
          getPosition: [validDevices.length],
          getFillColor: [validDevices.map(d => d.status).join(',')]
        }
      })
    ];
  }, [validDevices, webglSupported]);

  const onMapLoad = useCallback(() => {
    setIsMapLoaded(true);
    // Aguarda um pouco mais para garantir que contexto WebGL do Map está totalmente inicializado
    setTimeout(() => {
      if (mapRef.current) {
        try {
          const map = mapRef.current.getMap();
          const center = map.getCenter();
          setViewState({
            latitude: center.lat,
            longitude: center.lng,
            zoom: map.getZoom(),
            bearing: map.getBearing(),
            pitch: map.getPitch()
          });
        } catch {}
      }
      setDeckGLReady(true);
    }, 300);
  }, []);

  // Atualiza viewState diretamente do evento - sem debounce/throttle para máxima fluidez
  const onMapMove = useCallback((evt: ViewStateChangeEvent) => {
    if (evt?.viewState) {
      setViewState(evt.viewState);
    }
  }, []);

  return (
    <section
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
      {/* Map primeiro - recebe todos os eventos de interação */}
      <Map
        ref={mapRef}
        mapLib={maplibregl}
        mapStyle={SATELLITE_STYLE}
        initialViewState={INITIAL_VIEW_STATE}
        onLoad={onMapLoad}
        onMove={onMapMove}
        style={{ width: "100%", height: "100%", position: "relative", zIndex: 1 }}
      />

      {/* DeckGL como overlay - layers dos dispositivos */}
      {/* Renderiza apenas quando WebGL está disponível, Map está carregado e DeckGL está pronto */}
      {webglSupported && deckGLReady && isMapLoaded && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
            zIndex: 2
          }}
        >
          <DeckGL
            initialViewState={INITIAL_VIEW_STATE}
            viewState={viewState}
            layers={layers}
            controller={false}
            style={{ width: "100%", height: "100%" }}
          />
        </div>
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
            zIndex: 1000
          }}
        >
          Loading devices…
        </div>
      )}

      {error && (
        <div
          style={{
            position: "absolute",
            top: 12,
            right: 12,
            padding: "6px 10px",
            borderRadius: 8,
            background: "rgba(248,113,113,0.8)",
            color: "#111",
            fontSize: 12,
            zIndex: 1000
          }}
        >
          Error: {error}
        </div>
      )}
    </section>
  );
}
