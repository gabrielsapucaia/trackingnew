"use client";

import { useState, useEffect } from "react";
import { useDevices } from "./useDevices";
import MapView from "./MapView";

// Threshold for "fresh" data (10 seconds)
const FRESH_THRESHOLD_MS = 10000;

/**
 * Formats a date as time string (HH:MM:SS)
 */
function formatTime(date: Date): string {
  return date.toLocaleTimeString('pt-BR', { 
    hour: '2-digit', 
    minute: '2-digit', 
    second: '2-digit' 
  });
}

/**
 * Checks if the last update is within the fresh threshold
 */
function isDataFresh(lastUpdated: Date | null): boolean {
  if (!lastUpdated) return false;
  const now = new Date();
  return (now.getTime() - lastUpdated.getTime()) < FRESH_THRESHOLD_MS;
}

export default function MapPage() {
  const { 
    devices, 
    activeDevices,
    isInitialLoading, 
    isRefreshing,
    error, 
    lastUpdated, 
    retryCount
  } = useDevices(5000);

  // State to force re-render for freshness indicator
  const [, setTick] = useState(0);
  
  // Update freshness indicator every second
  useEffect(() => {
    const interval = setInterval(() => {
      setTick(t => t + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const isLoading = isInitialLoading;
  const isFresh = isDataFresh(lastUpdated);
  
  // Green when fresh (<10s), red when stale
  const indicatorColor = isFresh ? '#22c55e' : '#ef4444';
  const indicatorLabel = isFresh ? 'Atualizado' : 'Desatualizado';
  
  // Smooth transition style to prevent flickering
  const smoothTransition = 'color 0.3s ease-out, background-color 0.3s ease-out, box-shadow 0.3s ease-out';

  return (
    <main style={{ minHeight: "100vh", padding: "1rem" }}>
      <header style={{ marginBottom: "1rem" }}>
        <h1 style={{ margin: 0 }}>Aura Tracking Map</h1>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
          <p style={{ margin: 0, opacity: 0.8 }}>
            Dispositivos ativos: {activeDevices.length} {isRefreshing && "(atualizando...)"}
          </p>
          
          {/* Last updated time */}
          {lastUpdated && (
            <p 
              style={{ 
                margin: 0, 
                fontSize: "0.85rem",
                color: "#94a3b8",
                display: "flex",
                alignItems: "center",
                gap: "0.35rem",
                transition: smoothTransition
              }}
            >
              Última atualização: {formatTime(lastUpdated)}
            </p>
          )}
          
          {/* Connection freshness indicator */}
          {!isInitialLoading && lastUpdated && (
            <div 
              style={{ 
                display: "flex", 
                alignItems: "center", 
                gap: "0.35rem",
                fontSize: "0.85rem",
                color: indicatorColor,
                transition: smoothTransition
              }}
              title={`${indicatorLabel}${retryCount > 0 ? ` (${retryCount} erros consecutivos)` : ''}`}
            >
              <span
                style={{
                  display: "inline-block",
                  width: "10px",
                  height: "10px",
                  borderRadius: "50%",
                  backgroundColor: indicatorColor,
                  boxShadow: isFresh ? '0 0 6px rgba(34, 197, 94, 0.5)' : '0 0 6px rgba(239, 68, 68, 0.5)',
                  transition: smoothTransition
                }}
              />
              <span style={{ fontSize: "0.75rem", transition: smoothTransition }}>
                {indicatorLabel}
              </span>
            </div>
          )}
        </div>
        
        {/* Error message with guidance */}
        {error && (
          <div 
            style={{ 
              color: "#f87171", 
              margin: "0.5rem 0 0 0",
              padding: "0.5rem 0.75rem",
              backgroundColor: "rgba(248, 113, 113, 0.1)",
              borderRadius: "6px",
              fontSize: "0.9rem"
            }}
          >
            <p style={{ margin: 0 }}>
              <strong>Erro:</strong> {error}
              {devices.length > 0 && (
                <span style={{ opacity: 0.8, marginLeft: "0.5rem" }}>
                  (mostrando últimos dados conhecidos)
                </span>
              )}
            </p>
            {retryCount > 0 && (
              <p style={{ margin: "0.25rem 0 0 0", fontSize: "0.8rem", opacity: 0.8 }}>
                Tentando novamente automaticamente...
              </p>
            )}
          </div>
        )}
        
        {/* Empty state */}
        {!isInitialLoading && !error && devices.length === 0 && (
          <p style={{ color: "#94a3b8", margin: "0.5rem 0 0 0", fontSize: "0.9rem" }}>
            Nenhum dispositivo encontrado. Os dispositivos aparecerão quando começarem a reportar.
          </p>
        )}
      </header>
      <MapView devices={activeDevices} isLoading={isLoading} error={error} />
    </main>
  );
}
