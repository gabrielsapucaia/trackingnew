import { createSignal, createResource, createEffect, For, Show, onMount } from "solid-js";
import AppLayout from "~/layouts/AppLayout";
import { api, type Device, type TelemetryPoint } from "~/lib/api/client";

export default function ChartsPage() {
  const [selectedDevice, setSelectedDevice] = createSignal<string>("");
  const [timeRange, setTimeRange] = createSignal("1h");
  
  // Fetch devices
  const [devicesData] = createResource(() => api.getDevices());
  
  // Calculate time range
  const getTimeRange = () => {
    const now = new Date();
    const range = timeRange();
    let start = new Date();
    
    switch (range) {
      case "15m": start = new Date(now.getTime() - 15 * 60 * 1000); break;
      case "1h": start = new Date(now.getTime() - 60 * 60 * 1000); break;
      case "6h": start = new Date(now.getTime() - 6 * 60 * 60 * 1000); break;
      case "24h": start = new Date(now.getTime() - 24 * 60 * 60 * 1000); break;
    }
    
    return { start: start.toISOString(), end: now.toISOString() };
  };
  
  // Fetch telemetry for selected device
  const [telemetryData, { refetch }] = createResource(
    () => ({ device: selectedDevice(), range: timeRange() }),
    async ({ device }) => {
      if (!device) return null;
      const { start, end } = getTimeRange();
      return api.getTelemetry({ 
        device_id: device, 
        start, 
        end, 
        limit: 500,
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

  // Calculate stats from telemetry
  const stats = () => {
    const data = telemetryData()?.data || [];
    if (data.length === 0) return null;
    
    const speeds = data.map(d => d.speed_kmh).filter(s => s != null);
    const accels = data.map(d => d.accel_magnitude).filter(a => a != null);
    
    return {
      currentSpeed: data[data.length - 1]?.speed_kmh || 0,
      avgSpeed: speeds.length ? speeds.reduce((a, b) => a + b, 0) / speeds.length : 0,
      maxSpeed: speeds.length ? Math.max(...speeds) : 0,
      currentAccel: data[data.length - 1]?.accel_magnitude || 0,
      maxAccel: accels.length ? Math.max(...accels) : 0,
      pointCount: data.length
    };
  };

  // Simple sparkline component
  const Sparkline = (props: { data: number[]; color: string; height?: number }) => {
    const height = props.height || 60;
    const width = 100;
    
    if (props.data.length < 2) return null;
    
    const min = Math.min(...props.data);
    const max = Math.max(...props.data);
    const range = max - min || 1;
    
    const points = props.data.map((val, i) => {
      const x = (i / (props.data.length - 1)) * width;
      const y = height - ((val - min) / range) * height;
      return `${x},${y}`;
    }).join(" ");
    
    return (
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <polyline
          fill="none"
          stroke={props.color}
          stroke-width="2"
          points={points}
        />
      </svg>
    );
  };

  // Chart component with bars
  const BarChart = (props: { 
    data: { time: string; value: number }[]; 
    color: string; 
    label: string;
    unit: string;
  }) => {
    if (props.data.length === 0) {
      return (
        <div class="flex items-center justify-center h-full text-muted">
          Sem dados disponíveis
        </div>
      );
    }
    
    const maxVal = Math.max(...props.data.map(d => d.value), 1);
    const displayData = props.data.slice(-50); // Show last 50 points
    
    return (
      <div style={{ height: "200px", position: "relative" }}>
        {/* Y-axis labels */}
        <div style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: "20px",
          width: "50px",
          display: "flex",
          "flex-direction": "column",
          "justify-content": "space-between",
          "font-size": "var(--text-xs)",
          color: "var(--color-text-tertiary)"
        }}>
          <span>{maxVal.toFixed(1)}</span>
          <span>{(maxVal / 2).toFixed(1)}</span>
          <span>0</span>
        </div>
        
        {/* Chart area */}
        <div style={{
          position: "absolute",
          left: "55px",
          right: "10px",
          top: 0,
          bottom: "20px",
          display: "flex",
          "align-items": "flex-end",
          gap: "2px",
          background: "var(--color-bg-tertiary)",
          "border-radius": "var(--radius-md)",
          padding: "8px"
        }}>
          <For each={displayData}>
            {(point) => {
              const height = (point.value / maxVal) * 100;
              return (
                <div 
                  style={{
                    flex: 1,
                    height: `${Math.max(height, 2)}%`,
                    background: props.color,
                    "border-radius": "2px 2px 0 0",
                    "min-width": "3px",
                    opacity: 0.8,
                    transition: "height 0.3s ease"
                  }}
                  title={`${point.value.toFixed(2)} ${props.unit}`}
                />
              );
            }}
          </For>
        </div>
        
        {/* X-axis */}
        <div style={{
          position: "absolute",
          left: "55px",
          right: "10px",
          bottom: 0,
          height: "20px",
          display: "flex",
          "justify-content": "space-between",
          "font-size": "var(--text-xs)",
          color: "var(--color-text-tertiary)"
        }}>
          <span>{displayData[0] ? new Date(displayData[0].time).toLocaleTimeString() : ""}</span>
          <span>{displayData[displayData.length - 1] ? new Date(displayData[displayData.length - 1].time).toLocaleTimeString() : ""}</span>
        </div>
      </div>
    );
  };

  const speedData = () => {
    const data = telemetryData()?.data || [];
    return data.map(d => ({ time: d.time, value: d.speed_kmh || 0 }));
  };

  const accelData = () => {
    const data = telemetryData()?.data || [];
    return data.map(d => ({ time: d.time, value: d.accel_magnitude || 0 }));
  };

  return (
    <AppLayout>
      <div class="flex flex-col gap-4">
        {/* Controls */}
        <div class="flex items-center justify-between">
          <div class="flex gap-3">
            <select 
              class="btn btn-secondary"
              value={selectedDevice()}
              onChange={(e) => setSelectedDevice(e.target.value)}
              style={{ 
                background: "var(--color-bg-tertiary)",
                border: "1px solid var(--color-border-primary)",
                color: "var(--color-text-primary)",
                padding: "var(--space-2) var(--space-4)",
                "border-radius": "var(--radius-lg)",
                cursor: "pointer",
                "min-width": "200px"
              }}
            >
              <option value="">Selecionar dispositivo</option>
              <For each={devicesData()?.devices || []}>
                {(device) => (
                  <option value={device.device_id}>{device.device_id}</option>
                )}
              </For>
            </select>

            <div class="flex" style={{ 
              background: "var(--color-bg-tertiary)", 
              "border-radius": "var(--radius-lg)",
              border: "1px solid var(--color-border-primary)",
              overflow: "hidden"
            }}>
              <For each={["15m", "1h", "6h", "24h"]}>
                {(range) => (
                  <button
                    class={`btn ${timeRange() === range ? "btn-primary" : "btn-ghost"}`}
                    style={{ 
                      "border-radius": "0",
                      "border-right": range !== "24h" ? "1px solid var(--color-border-primary)" : "none"
                    }}
                    onClick={() => setTimeRange(range)}
                  >
                    {range}
                  </button>
                )}
              </For>
            </div>
          </div>

          <div class="flex gap-2 items-center">
            <Show when={stats()}>
              <div class="badge">
                {stats()!.pointCount} pontos
              </div>
            </Show>
            <button class="btn btn-ghost btn-icon" title="Atualizar" onClick={() => refetch()}>
              <RefreshIcon />
            </button>
          </div>
        </div>

        {/* Stats Cards */}
        <Show when={stats()}>
          <div class="grid grid-cols-4 gap-4">
            <div class="stat-card">
              <span class="stat-label">Velocidade Atual</span>
              <div class="stat-value accent">{stats()!.currentSpeed.toFixed(1)} km/h</div>
            </div>
            <div class="stat-card">
              <span class="stat-label">Velocidade Média</span>
              <div class="stat-value">{stats()!.avgSpeed.toFixed(1)} km/h</div>
            </div>
            <div class="stat-card">
              <span class="stat-label">Velocidade Máxima</span>
              <div class="stat-value">{stats()!.maxSpeed.toFixed(1)} km/h</div>
            </div>
            <div class="stat-card">
              <span class="stat-label">Aceleração Máxima</span>
              <div class="stat-value">{stats()!.maxAccel.toFixed(1)} m/s²</div>
            </div>
          </div>
        </Show>

        {/* Speed Chart */}
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Velocidade (km/h)</h3>
            <Show when={stats()}>
              <div class="flex items-center gap-4 text-sm">
                <span>
                  <span class="text-muted">Atual: </span>
                  <span style={{ color: "var(--color-accent-primary)", "font-weight": "600" }}>
                    {stats()!.currentSpeed.toFixed(1)}
                  </span>
                </span>
                <span>
                  <span class="text-muted">Média: </span>
                  <span>{stats()!.avgSpeed.toFixed(1)}</span>
                </span>
                <span>
                  <span class="text-muted">Máx: </span>
                  <span style={{ color: "var(--color-warning)" }}>{stats()!.maxSpeed.toFixed(1)}</span>
                </span>
              </div>
            </Show>
          </div>
          <div class="card-body">
            <Show when={!telemetryData.loading} fallback={
              <div class="flex items-center justify-center" style={{ height: "200px" }}>
                <span class="text-muted">Carregando dados...</span>
              </div>
            }>
              <BarChart 
                data={speedData()} 
                color="var(--color-accent-primary)" 
                label="Velocidade"
                unit="km/h"
              />
            </Show>
          </div>
        </div>

        {/* Acceleration Chart */}
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Aceleração (m/s²)</h3>
            <Show when={stats()}>
              <div class="badge" style={{ 
                background: stats()!.maxAccel > 12 ? "var(--color-error)" : "var(--color-bg-tertiary)"
              }}>
                Pico: {stats()!.maxAccel.toFixed(1)}
              </div>
            </Show>
          </div>
          <div class="card-body">
            <Show when={!telemetryData.loading} fallback={
              <div class="flex items-center justify-center" style={{ height: "200px" }}>
                <span class="text-muted">Carregando dados...</span>
              </div>
            }>
              <BarChart 
                data={accelData()} 
                color="var(--color-warning)" 
                label="Aceleração"
                unit="m/s²"
              />
            </Show>
          </div>
        </div>

        {/* GPS Accuracy */}
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Precisão GPS</h3>
          </div>
          <div class="card-body">
            <Show when={telemetryData()?.data?.length} fallback={
              <div class="flex items-center justify-center" style={{ height: "100px" }}>
                <span class="text-muted">Selecione um dispositivo</span>
              </div>
            }>
              <div class="grid grid-cols-3 gap-4">
                <div class="text-center p-4" style={{ background: "var(--color-bg-tertiary)", "border-radius": "var(--radius-lg)" }}>
                  <div class="text-muted text-sm mb-1">Precisão Média</div>
                  <div style={{ "font-size": "var(--text-xl)", "font-weight": "600" }}>
                    {(telemetryData()!.data.reduce((a, b) => a + (b.gps_accuracy || 0), 0) / telemetryData()!.data.length).toFixed(1)}m
                  </div>
                </div>
                <div class="text-center p-4" style={{ background: "var(--color-bg-tertiary)", "border-radius": "var(--radius-lg)" }}>
                  <div class="text-muted text-sm mb-1">Altitude Média</div>
                  <div style={{ "font-size": "var(--text-xl)", "font-weight": "600" }}>
                    {(telemetryData()!.data.reduce((a, b) => a + (b.altitude || 0), 0) / telemetryData()!.data.length).toFixed(0)}m
                  </div>
                </div>
                <div class="text-center p-4" style={{ background: "var(--color-bg-tertiary)", "border-radius": "var(--radius-lg)" }}>
                  <div class="text-muted text-sm mb-1">Bearing Atual</div>
                  <div style={{ "font-size": "var(--text-xl)", "font-weight": "600" }}>
                    {telemetryData()!.data[telemetryData()!.data.length - 1]?.bearing?.toFixed(0) || 0}°
                  </div>
                </div>
              </div>
            </Show>
          </div>
        </div>
      </div>
    </AppLayout>
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
