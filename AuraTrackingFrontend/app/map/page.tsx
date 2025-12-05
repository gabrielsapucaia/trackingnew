"use client";

import { useDevices } from "./useDevices";
import MapView from "./MapView";

export default function MapPage() {
  const { devices, isLoading, error } = useDevices(5000);

  return (
    <main style={{ minHeight: "100vh", padding: "1rem" }}>
      <header style={{ marginBottom: "1rem" }}>
        <h1 style={{ margin: 0 }}>Aura Tracking Map</h1>
        <p style={{ margin: 0, opacity: 0.8 }}>
          Devices: {devices.length} {isLoading && "(loading...)"}
        </p>
        {error && (
          <p style={{ color: "#f87171", margin: "0.5rem 0 0 0" }}>Error: {error}</p>
        )}
      </header>
      <MapView devices={devices} isLoading={isLoading} error={error} />
    </main>
  );
}
