import { useParams, A } from "@solidjs/router";
import { createSignal, Show } from "solid-js";
import AppLayout from "~/layouts/AppLayout";

// Mock device data (would come from API in real app)
const getDevice = (id: string) => ({
  id,
  name: id === "ZF524XRLK3" ? "Caminhão 001" : `Device ${id.slice(0, 6)}`,
  model: "Moto G34 5G",
  operator: "João Silva",
  operatorId: "OP_001",
  status: "online" as const,
  speed: 32.5,
  latitude: -11.563234,
  longitude: -47.170456,
  altitude: 285.5,
  bearing: 180,
  gpsAccuracy: 4.5,
  accelMagnitude: 9.82,
  lastSeen: new Date(),
  firstSeen: new Date(Date.now() - 30 * 24 * 3600000),
  totalKm: 1234.5,
  todayKm: 45.2,
  totalHours: 156.3,
  todayHours: 4.2,
  alerts: [
    { id: 1, type: "speed", message: "Velocidade alta: 72 km/h", time: new Date(Date.now() - 300000) },
    { id: 2, type: "impact", message: "Impacto detectado", time: new Date(Date.now() - 3600000) },
  ],
  metadata: {
    appVersion: "1.2.0",
    osVersion: "Android 14",
    batteryLevel: 78,
    signalStrength: -65,
  },
});

export default function DeviceDetailPage() {
  const params = useParams();
  const device = () => getDevice(params.id);
  const [activeTab, setActiveTab] = createSignal<"overview" | "history" | "settings">("overview");

  const formatDate = (date: Date) => {
    return date.toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  return (
    <AppLayout>
      <div class="flex flex-col gap-4">
        {/* Header */}
        <div class="flex items-center gap-4 mb-2">
          <A href="/devices" class="btn btn-ghost btn-icon">
            <BackIcon />
          </A>
          <div class="flex-1">
            <div class="flex items-center gap-3">
              <h2 style={{ "font-size": "var(--text-2xl)", "font-weight": "600" }}>
                {device().name}
              </h2>
              <StatusBadge status={device().status} />
            </div>
            <p class="text-muted">{device().id} · {device().model}</p>
          </div>
          <div class="flex gap-2">
            <A href={`/replay?device=${device().id}`} class="btn btn-secondary">
              <ReplayIcon />
              Replay
            </A>
            <A href={`/map?device=${device().id}`} class="btn btn-primary">
              <MapIcon />
              Ver no Mapa
            </A>
          </div>
        </div>

        {/* Tabs */}
        <div class="flex gap-1" style={{ 
          background: "var(--color-bg-tertiary)", 
          "border-radius": "var(--radius-lg)",
          padding: "var(--space-1)",
          border: "1px solid var(--color-border-primary)",
          width: "fit-content"
        }}>
          <button
            class={`btn ${activeTab() === "overview" ? "btn-primary" : "btn-ghost"}`}
            onClick={() => setActiveTab("overview")}
          >
            Visão Geral
          </button>
          <button
            class={`btn ${activeTab() === "history" ? "btn-primary" : "btn-ghost"}`}
            onClick={() => setActiveTab("history")}
          >
            Histórico
          </button>
          <button
            class={`btn ${activeTab() === "settings" ? "btn-primary" : "btn-ghost"}`}
            onClick={() => setActiveTab("settings")}
          >
            Configurações
          </button>
        </div>

        <Show when={activeTab() === "overview"}>
          {/* Live Status */}
          <div class="grid gap-4" style={{ "grid-template-columns": "1fr 1fr 1fr" }}>
            {/* Current Position Card */}
            <div class="card">
              <div class="card-header">
                <h3 class="card-title">Posição Atual</h3>
                <span class="badge badge-success">Ao vivo</span>
              </div>
              <div class="card-body">
                <div class="grid grid-cols-2 gap-4">
                  <div>
                    <div class="text-xs text-muted">Latitude</div>
                    <div style={{ "font-weight": "600", "font-family": "var(--font-sans)" }}>
                      {device().latitude.toFixed(6)}°
                    </div>
                  </div>
                  <div>
                    <div class="text-xs text-muted">Longitude</div>
                    <div style={{ "font-weight": "600", "font-family": "var(--font-sans)" }}>
                      {device().longitude.toFixed(6)}°
                    </div>
                  </div>
                  <div>
                    <div class="text-xs text-muted">Altitude</div>
                    <div style={{ "font-weight": "600" }}>{device().altitude.toFixed(1)} m</div>
                  </div>
                  <div>
                    <div class="text-xs text-muted">Precisão GPS</div>
                    <div style={{ "font-weight": "600" }}>{device().gpsAccuracy.toFixed(1)} m</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Movement Card */}
            <div class="card">
              <div class="card-header">
                <h3 class="card-title">Movimento</h3>
              </div>
              <div class="card-body">
                <div class="grid grid-cols-2 gap-4">
                  <div>
                    <div class="text-xs text-muted">Velocidade</div>
                    <div style={{ 
                      "font-weight": "700",
                      "font-size": "var(--text-2xl)",
                      color: device().speed > 0 ? "var(--color-accent-primary)" : "var(--color-text-tertiary)"
                    }}>
                      {device().speed.toFixed(1)}
                      <span style={{ "font-size": "var(--text-sm)", "font-weight": "400", "margin-left": "4px" }}>
                        km/h
                      </span>
                    </div>
                  </div>
                  <div>
                    <div class="text-xs text-muted">Direção</div>
                    <div style={{ "font-weight": "600" }}>
                      {device().bearing}° {getCardinalDirection(device().bearing)}
                    </div>
                  </div>
                  <div>
                    <div class="text-xs text-muted">Aceleração</div>
                    <div style={{ "font-weight": "600" }}>{device().accelMagnitude.toFixed(2)} m/s²</div>
                  </div>
                  <div>
                    <div class="text-xs text-muted">Última Atualização</div>
                    <div style={{ "font-weight": "600" }}>agora</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Operator Card */}
            <div class="card">
              <div class="card-header">
                <h3 class="card-title">Operador</h3>
              </div>
              <div class="card-body">
                <div class="flex items-center gap-4 mb-4">
                  <div style={{
                    width: "48px",
                    height: "48px",
                    background: "var(--color-accent-glow)",
                    "border-radius": "var(--radius-full)",
                    display: "flex",
                    "align-items": "center",
                    "justify-content": "center",
                    "font-weight": "600",
                    color: "var(--color-accent-primary)"
                  }}>
                    JS
                  </div>
                  <div>
                    <div style={{ "font-weight": "600" }}>{device().operator}</div>
                    <div class="text-sm text-muted">{device().operatorId}</div>
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-4">
                  <div>
                    <div class="text-xs text-muted">Turno</div>
                    <div style={{ "font-weight": "600" }}>06:00 - 14:00</div>
                  </div>
                  <div>
                    <div class="text-xs text-muted">Tempo Ativo</div>
                    <div style={{ "font-weight": "600" }}>{device().todayHours}h</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Stats Row */}
          <div class="grid grid-cols-4 gap-4">
            <div class="stat-card">
              <span class="stat-label">Distância Hoje</span>
              <span class="stat-value accent">{device().todayKm} km</span>
            </div>
            <div class="stat-card">
              <span class="stat-label">Distância Total</span>
              <span class="stat-value">{device().totalKm.toLocaleString()} km</span>
            </div>
            <div class="stat-card">
              <span class="stat-label">Horas Hoje</span>
              <span class="stat-value">{device().todayHours}h</span>
            </div>
            <div class="stat-card">
              <span class="stat-label">Horas Totais</span>
              <span class="stat-value">{device().totalHours}h</span>
            </div>
          </div>

          {/* Alerts & Device Info */}
          <div class="grid grid-cols-2 gap-4">
            {/* Recent Alerts */}
            <div class="card">
              <div class="card-header">
                <h3 class="card-title">Alertas Recentes</h3>
                <span class="badge badge-warning">{device().alerts.length}</span>
              </div>
              <div class="card-body" style={{ padding: "0" }}>
                {device().alerts.map((alert, index) => (
                  <div 
                    class="flex items-center gap-3 p-4"
                    style={{ 
                      "border-bottom": index < device().alerts.length - 1 ? "1px solid var(--color-border-primary)" : "none"
                    }}
                  >
                    <div style={{
                      width: "8px",
                      height: "8px",
                      background: alert.type === "impact" ? "var(--color-error)" : "var(--color-warning)",
                      "border-radius": "50%"
                    }} />
                    <div class="flex-1">
                      <div class="text-sm">{alert.message}</div>
                      <div class="text-xs text-muted">{formatDate(alert.time)}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Device Info */}
            <div class="card">
              <div class="card-header">
                <h3 class="card-title">Informações do Dispositivo</h3>
              </div>
              <div class="card-body">
                <div class="grid grid-cols-2 gap-4">
                  <div>
                    <div class="text-xs text-muted">Modelo</div>
                    <div style={{ "font-weight": "600" }}>{device().model}</div>
                  </div>
                  <div>
                    <div class="text-xs text-muted">Versão do App</div>
                    <div style={{ "font-weight": "600" }}>{device().metadata.appVersion}</div>
                  </div>
                  <div>
                    <div class="text-xs text-muted">Sistema</div>
                    <div style={{ "font-weight": "600" }}>{device().metadata.osVersion}</div>
                  </div>
                  <div>
                    <div class="text-xs text-muted">Bateria</div>
                    <div style={{ 
                      "font-weight": "600",
                      color: device().metadata.batteryLevel < 20 ? "var(--color-error)" : "inherit"
                    }}>
                      {device().metadata.batteryLevel}%
                    </div>
                  </div>
                  <div>
                    <div class="text-xs text-muted">Sinal</div>
                    <div style={{ "font-weight": "600" }}>{device().metadata.signalStrength} dBm</div>
                  </div>
                  <div>
                    <div class="text-xs text-muted">Primeiro Registro</div>
                    <div style={{ "font-weight": "600" }}>
                      {device().firstSeen.toLocaleDateString("pt-BR")}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Show>

        <Show when={activeTab() === "history"}>
          <div class="card">
            <div class="card-body text-center" style={{ padding: "var(--space-12)" }}>
              <HistoryIcon style={{ 
                width: "48px", 
                height: "48px", 
                color: "var(--color-text-tertiary)",
                margin: "0 auto var(--space-4)"
              }} />
              <h3 style={{ "margin-bottom": "var(--space-2)" }}>Histórico de Atividades</h3>
              <p class="text-muted">
                Visualização de trilhas e eventos históricos será implementada com o sistema de replay
              </p>
              <A href={`/replay?device=${device().id}`} class="btn btn-primary mt-4">
                Ir para Replay
              </A>
            </div>
          </div>
        </Show>

        <Show when={activeTab() === "settings"}>
          <div class="card">
            <div class="card-body text-center" style={{ padding: "var(--space-12)" }}>
              <SettingsIcon style={{ 
                width: "48px", 
                height: "48px", 
                color: "var(--color-text-tertiary)",
                margin: "0 auto var(--space-4)"
              }} />
              <h3 style={{ "margin-bottom": "var(--space-2)" }}>Configurações do Dispositivo</h3>
              <p class="text-muted">
                Configurações de alertas, limites de velocidade e outras opções serão implementadas em versões futuras
              </p>
            </div>
          </div>
        </Show>
      </div>
    </AppLayout>
  );
}

function getCardinalDirection(degrees: number): string {
  const directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return directions[Math.round(degrees / 45) % 8];
}

function StatusBadge(props: { status: "online" | "idle" | "offline" }) {
  const config = {
    online: { class: "badge-success", label: "Online" },
    idle: { class: "badge-warning", label: "Parado" },
    offline: { class: "badge-error", label: "Offline" },
  };

  return (
    <span class={`badge ${config[props.status].class}`}>
      {config[props.status].label}
    </span>
  );
}

// Icons
function BackIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

function MapIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
      <line x1="8" y1="2" x2="8" y2="18" />
      <line x1="16" y1="6" x2="16" y2="22" />
    </svg>
  );
}

function ReplayIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  );
}

function HistoryIcon(props: { style?: any }) {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style={props.style}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function SettingsIcon(props: { style?: any }) {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style={props.style}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

