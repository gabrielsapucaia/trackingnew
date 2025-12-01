import { createSignal, For, createResource } from "solid-js";
import AppLayout from "~/layouts/AppLayout";
import { api } from "~/lib/api/client";
import { enrichDevicesWithMetadata } from "~/lib/utils/device";

// Fallback mock data (will be replaced by real data when available)
const fallbackKPIs = [
  { label: "Distância Total", value: "1,234.5 km", change: 8.2, positive: true },
  { label: "Tempo Operação", value: "156.3 h", change: 5.1, positive: true },
  { label: "Velocidade Média", value: "28.5 km/h", change: -2.3, positive: false },
  { label: "Consumo Est.", value: "892 L", change: 3.4, positive: false },
  { label: "Eventos/Dia", value: "23.4", change: -15.2, positive: true },
  { label: "Disponibilidade", value: "94.2%", change: 1.8, positive: true },
];

const fallbackTopDrivers = [
  { name: "João Silva", trips: 45, avgSpeed: 32.1, score: 92 },
  { name: "Maria Santos", trips: 38, avgSpeed: 28.5, score: 88 },
  { name: "Pedro Costa", trips: 42, avgSpeed: 35.2, score: 85 },
  { name: "Ana Oliveira", trips: 35, avgSpeed: 26.8, score: 82 },
];

const alertsSummary = [
  { type: "Velocidade Alta", count: 23, color: "var(--color-warning)" },
  { type: "Impactos", count: 5, color: "var(--color-error)" },
  { type: "Frenagem Brusca", count: 12, color: "var(--color-warning)" },
  { type: "Aceleração Brusca", count: 8, color: "var(--color-info)" },
];

export default function AnalyticsPage() {
  const [period, setPeriod] = createSignal("7d");

  // Fetch real data
  const [devicesData] = createResource(() => api.getDevices());
  const [supabaseDevices] = createResource(() => api.getDevicesFromSupabase());
  const [summary] = createResource(() => api.getSummary(7)); // 7 days summary

  // Enrich devices with metadata
  const enrichedDevices = () => {
    const telemetryDevices = devicesData()?.devices || [];
    const supabaseDevicesList = supabaseDevices()?.devices || [];
    return enrichDevicesWithMetadata(telemetryDevices, supabaseDevicesList);
  };

  // Calculate real KPIs from enriched devices
  const realKPIs = () => {
    const devices = enrichedDevices();
    const summaryData = summary();

    if (!devices.length || !summaryData) return [];

    const totalDistance = devices.reduce((sum, d) => sum + (d.total_points_24h || 0) * 0.01, 0); // Estimate
    const activeDevices = devices.filter(d => d.status === 'online').length;
    const avgSpeed = summaryData.avg_speed_kmh || 0;

    return [
      {
        label: "Distância Total",
        value: `${totalDistance.toFixed(1)} km`,
        change: 8.2,
        positive: true
      },
      {
        label: "Tempo Operação",
        value: `${(summaryData.total_telemetries / 3600).toFixed(1)} h`, // Estimate hours
        change: 5.1,
        positive: true
      },
      {
        label: "Velocidade Média",
        value: `${avgSpeed.toFixed(1)} km/h`,
        change: -2.3,
        positive: false
      },
      {
        label: "Consumo Est.",
        value: `${(totalDistance * 0.08).toFixed(0)} L`, // Estimate consumption
        change: 3.4,
        positive: false
      },
      {
        label: "Eventos/Dia",
        value: `${(summaryData.total_telemetries / 7).toFixed(1)}`,
        change: -15.2,
        positive: true
      },
      {
        label: "Disponibilidade",
        value: `${((activeDevices / devices.length) * 100).toFixed(1)}%`,
        change: 1.8,
        positive: true
      }
    ];
  };

  // Generate real top drivers from enriched devices
  const realTopDrivers = () => {
    const devices = enrichedDevices();
    if (!devices.length) return [];

    // Group by operator and calculate metrics
    const operatorStats = new Map();

    devices.forEach(device => {
      const operator = device.displayOperator;
      if (!operatorStats.has(operator)) {
        operatorStats.set(operator, {
          name: operator,
          trips: 0,
          avgSpeed: 0,
          score: 85 + Math.random() * 15, // Mock score
          devices: []
        });
      }

      const stats = operatorStats.get(operator);
      stats.trips += Math.floor(Math.random() * 5) + 1; // Mock trips
      stats.avgSpeed = (stats.avgSpeed + (device.speed_kmh || 0)) / 2;
      stats.devices.push(device);
    });

    return Array.from(operatorStats.values())
      .sort((a, b) => b.score - a.score)
      .slice(0, 4);
  };

  return (
    <AppLayout>
      <div class="flex flex-col gap-4">
        {/* Period Selector */}
        <div class="flex items-center justify-between">
          <div>
            <h2 style={{ "font-size": "var(--text-2xl)", "font-weight": "600" }}>
              Análise de Performance
            </h2>
            <p class="text-muted">Métricas agregadas da frota</p>
          </div>
          <div class="flex gap-2" style={{ 
            background: "var(--color-bg-tertiary)", 
            "border-radius": "var(--radius-lg)",
            padding: "var(--space-1)",
            border: "1px solid var(--color-border-primary)"
          }}>
            <For each={["24h", "7d", "30d", "90d"]}>
              {(p) => (
                <button
                  class={`btn ${period() === p ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setPeriod(p)}
                >
                  {p === "24h" ? "Hoje" : p === "7d" ? "Semana" : p === "30d" ? "Mês" : "Trimestre"}
                </button>
              )}
            </For>
          </div>
        </div>

        {/* KPIs Grid */}
        <div class="grid gap-4" style={{ "grid-template-columns": "repeat(6, 1fr)" }}>
          <For each={kpis}>
            {(kpi, index) => (
              <div 
                class="stat-card animate-slideUp" 
                style={{ "animation-delay": `${index() * 50}ms` }}
              >
                <span class="stat-label">{kpi.label}</span>
                <span class="stat-value">{kpi.value}</span>
                <div class={`stat-change ${kpi.positive ? "positive" : "negative"}`}>
                  {kpi.positive ? "↑" : "↓"} {Math.abs(kpi.change)}%
                </div>
              </div>
            )}
          </For>
        </div>

        {/* Charts Row */}
        <div class="grid grid-cols-2 gap-4">
          {/* Usage Chart */}
          <div class="card">
            <div class="card-header">
              <h3 class="card-title">Utilização por Hora</h3>
              <span class="badge">Últimos 7 dias</span>
            </div>
            <div class="card-body">
              <AnalyticsChartPlaceholder 
                title="Heatmap de Atividade"
                subtitle="Hora x Dia da Semana"
                height={250}
              />
            </div>
          </div>

          {/* Distance Chart */}
          <div class="card">
            <div class="card-header">
              <h3 class="card-title">Distância Percorrida</h3>
              <span class="badge badge-success">+8.2%</span>
            </div>
            <div class="card-body">
              <AnalyticsChartPlaceholder 
                title="Distância por Dia"
                subtitle="Comparativo com período anterior"
                height={250}
              />
            </div>
          </div>
        </div>

        {/* Bottom Row */}
        <div class="grid gap-4" style={{ "grid-template-columns": "1fr 1fr 1fr" }}>
          {/* Top Drivers */}
          <div class="card">
            <div class="card-header">
              <h3 class="card-title">Top Operadores</h3>
              <a href="/devices" class="btn btn-ghost text-sm">Ver todos</a>
            </div>
            <div class="card-body" style={{ padding: "0" }}>
              <For each={topDrivers}>
                {(driver, index) => (
                  <div 
                    class="flex items-center justify-between p-4"
                    style={{ 
                      "border-bottom": index() < topDrivers.length - 1 ? "1px solid var(--color-border-primary)" : "none"
                    }}
                  >
                    <div class="flex items-center gap-3">
                      <div style={{
                        width: "32px",
                        height: "32px",
                        background: "var(--color-bg-tertiary)",
                        "border-radius": "var(--radius-full)",
                        display: "flex",
                        "align-items": "center",
                        "justify-content": "center",
                        "font-weight": "600",
                        "font-size": "var(--text-sm)",
                        color: "var(--color-accent-primary)"
                      }}>
                        {index() + 1}
                      </div>
                      <div>
                        <div style={{ "font-weight": "500" }}>{driver.name}</div>
                        <div class="text-xs text-muted">{driver.trips} viagens</div>
                      </div>
                    </div>
                    <div class="text-right">
                      <div style={{ 
                        "font-weight": "600",
                        color: driver.score >= 90 ? "var(--color-success)" : 
                               driver.score >= 80 ? "var(--color-warning)" : "var(--color-error)"
                      }}>
                        {driver.score}
                      </div>
                      <div class="text-xs text-muted">Score</div>
                    </div>
                  </div>
                )}
              </For>
            </div>
          </div>

          {/* Alerts Summary */}
          <div class="card">
            <div class="card-header">
              <h3 class="card-title">Resumo de Alertas</h3>
              <span class="badge badge-warning">48 total</span>
            </div>
            <div class="card-body">
              <For each={alertsSummary}>
                {(alert) => (
                  <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center gap-3">
                      <div style={{
                        width: "8px",
                        height: "8px",
                        background: alert.color,
                        "border-radius": "var(--radius-full)"
                      }} />
                      <span>{alert.type}</span>
                    </div>
                    <div class="flex items-center gap-2">
                      <span style={{ "font-weight": "600" }}>{alert.count}</span>
                      <div style={{
                        width: `${(alert.count / 30) * 100}px`,
                        height: "4px",
                        background: alert.color,
                        "border-radius": "2px",
                        opacity: 0.5
                      }} />
                    </div>
                  </div>
                )}
              </For>
              <div style={{ 
                "margin-top": "var(--space-4)",
                "padding-top": "var(--space-4)",
                "border-top": "1px solid var(--color-border-primary)"
              }}>
                <a href="#" class="btn btn-secondary w-full">
                  Ver Detalhes
                </a>
              </div>
            </div>
          </div>

          {/* Vehicle Status */}
          <div class="card">
            <div class="card-header">
              <h3 class="card-title">Status da Frota</h3>
            </div>
            <div class="card-body">
              <div class="flex items-center justify-center" style={{ height: "200px" }}>
                <div style={{ position: "relative", width: "160px", height: "160px" }}>
                  {/* Donut chart placeholder */}
                  <svg viewBox="0 0 100 100" style={{ transform: "rotate(-90deg)" }}>
                    <circle cx="50" cy="50" r="40" fill="none" stroke="var(--color-bg-tertiary)" stroke-width="12" />
                    <circle 
                      cx="50" cy="50" r="40" fill="none" 
                      stroke="var(--color-success)" stroke-width="12"
                      stroke-dasharray="175.93" stroke-dashoffset="35.19"
                    />
                    <circle 
                      cx="50" cy="50" r="40" fill="none" 
                      stroke="var(--color-warning)" stroke-width="12"
                      stroke-dasharray="175.93" stroke-dashoffset="150"
                    />
                    <circle 
                      cx="50" cy="50" r="40" fill="none" 
                      stroke="var(--color-error)" stroke-width="12"
                      stroke-dasharray="175.93" stroke-dashoffset="165"
                    />
                  </svg>
                  <div style={{
                    position: "absolute",
                    top: "50%",
                    left: "50%",
                    transform: "translate(-50%, -50%)",
                    "text-align": "center"
                  }}>
                    <div style={{ "font-size": "var(--text-2xl)", "font-weight": "700" }}>15</div>
                    <div class="text-xs text-muted">Veículos</div>
                  </div>
                </div>
              </div>
              <div class="flex justify-center gap-4 mt-4">
                <div class="flex items-center gap-2">
                  <span style={{ width: "8px", height: "8px", background: "var(--color-success)", "border-radius": "50%" }} />
                  <span class="text-sm">Ativos (12)</span>
                </div>
                <div class="flex items-center gap-2">
                  <span style={{ width: "8px", height: "8px", background: "var(--color-warning)", "border-radius": "50%" }} />
                  <span class="text-sm">Parados (2)</span>
                </div>
                <div class="flex items-center gap-2">
                  <span style={{ width: "8px", height: "8px", background: "var(--color-error)", "border-radius": "50%" }} />
                  <span class="text-sm">Offline (1)</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

function AnalyticsChartPlaceholder(props: { title: string; subtitle: string; height: number }) {
  return (
    <div style={{
      height: `${props.height}px`,
      background: "linear-gradient(180deg, var(--color-bg-tertiary) 0%, var(--color-bg-secondary) 100%)",
      "border-radius": "var(--radius-lg)",
      border: "1px dashed var(--color-border-secondary)",
      display: "flex",
      "align-items": "center",
      "justify-content": "center",
      "flex-direction": "column",
      gap: "var(--space-2)"
    }}>
      <BarChartIcon />
      <div class="text-center">
        <div style={{ "font-weight": "500", color: "var(--color-text-secondary)" }}>
          {props.title}
        </div>
        <div class="text-xs text-muted">{props.subtitle}</div>
      </div>
    </div>
  );
}

function BarChartIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style={{ color: "var(--color-text-tertiary)" }}>
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}

