import { createResource, onMount, For, Show, onCleanup, createSignal, createEffect } from "solid-js";
import AppLayout from "~/layouts/AppLayout";
import { api, type Device, type SystemSummary } from "~/lib/api/client";
import { realtimeManager } from "~/lib/supabase";
import { enrichDevicesWithMetadata, type EnrichedDevice } from "~/lib/utils/device";

// Icons
const TruckIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M1 3h15v13H1z" />
    <path d="M16 8h4l3 3v5h-7V8z" />
    <circle cx="5.5" cy="18.5" r="2.5" />
    <circle cx="18.5" cy="18.5" r="2.5" />
  </svg>
);

const SpeedIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M12 2a10 10 0 1 0 10 10" />
    <path d="M12 12l4-4" />
    <circle cx="12" cy="12" r="2" />
  </svg>
);

const ActivityIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </svg>
);

const DatabaseIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
  </svg>
);

const RefreshIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M23 4v6h-6" />
    <path d="M1 20v-6h6" />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
);

function StatCard(props: {
  label: string;
  value: string | number;
  icon: () => any;
  accent?: boolean;
  loading?: boolean;
}) {
  return (
    <div class="stat-card animate-slideUp">
      <div class="flex items-center justify-between">
        <span class="stat-label">{props.label}</span>
        <div style={{ color: "var(--color-text-tertiary)" }}>{props.icon()}</div>
      </div>
      <Show when={!props.loading} fallback={
        <div class="stat-value" style={{ color: "var(--color-text-tertiary)" }}>...</div>
      }>
        <div class={`stat-value ${props.accent ? "accent" : ""}`}>
          {props.value}
        </div>
      </Show>
    </div>
  );
}

function DeviceRow(props: { device: EnrichedDevice }) {
  const getStatusBadge = () => {
    switch (props.device.status) {
      case "online":
        return <span class="badge badge-success">Online</span>;
      case "offline":
        return <span class="badge badge-error">Offline</span>;
      default:
        return <span class="badge">Desconhecido</span>;
    }
  };

  const formatLastSeen = (lastSeen: string) => {
    const date = new Date(lastSeen);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);

    if (diffSec < 60) return "agora";
    if (diffMin < 60) return `${diffMin} min`;
    if (diffHour < 24) return `${diffHour}h`;
    return date.toLocaleDateString();
  };

  return (
    <div class="flex items-center justify-between p-4 border-b" style={{ "border-color": "var(--color-border-primary)" }}>
      <div class="flex items-center gap-3">
        <div style={{
          width: "40px",
          height: "40px",
          background: "var(--color-bg-tertiary)",
          "border-radius": "var(--radius-lg)",
          display: "flex",
          "align-items": "center",
          "justify-content": "center",
          color: "var(--color-text-tertiary)"
        }}>
          <TruckIcon />
        </div>
        <div>
          <div style={{ "font-weight": "500", color: "var(--color-text-primary)" }}>
            {props.device.supabaseData?.name || `Dispositivo ${props.device.device_id}`}
          </div>
          <div class="text-xs text-muted">
            <span style={{ "font-weight": "500" }}>Tag:</span> {props.device.device_id}
            {props.device.supabaseData?.operator_id && (
              <span> • <span style={{ "font-weight": "500" }}>Operador:</span> {props.device.supabaseData.operator_id}</span>
            )}
          </div>
        </div>
      </div>
      <div class="flex items-center gap-4">
        <div class="text-right">
          <div style={{ "font-weight": "600", color: props.device.speed_kmh && props.device.speed_kmh > 1 ? "var(--color-accent-primary)" : "var(--color-text-tertiary)" }}>
            {props.device.speed_kmh && props.device.speed_kmh > 1 ? `${props.device.speed_kmh.toFixed(1)} km/h` : "Parado"}
          </div>
          <div class="text-xs text-muted">{formatLastSeen(props.device.last_seen)}</div>
        </div>
        {getStatusBadge()}
      </div>
    </div>
  );
}

function AlertItem(props: { alert: { type: string; message: string; time: string } }) {
  const getAlertStyle = () => {
    switch (props.alert.type) {
      case "warning":
        return {
          borderColor: "var(--color-warning)",
          iconColor: "var(--color-warning)"
        };
      case "error":
        return {
          borderColor: "var(--color-error)",
          iconColor: "var(--color-error)"
        };
      default:
        return {
          borderColor: "var(--color-info)",
          iconColor: "var(--color-info)"
        };
    }
  };

  const style = getAlertStyle();

  return (
    <div class="flex items-center gap-3 p-3" style={{
      "border-left": `3px solid ${style.borderColor}`,
      background: "var(--color-bg-tertiary)",
      "border-radius": "0 var(--radius-md) var(--radius-md) 0",
      "margin-bottom": "var(--space-2)"
    }}>
      <div style={{ color: style.iconColor }}>
        <ActivityIcon />
      </div>
      <div class="flex-1">
        <div class="text-sm" style={{ color: "var(--color-text-primary)" }}>{props.alert.message}</div>
        <div class="text-xs text-muted">{props.alert.time}</div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  // Fetch real data from API
  const [summary, { refetch: refetchSummary }] = createResource(() => api.getSummary(1));
  const [devicesData, { refetch: refetchDevices }] = createResource(() => api.getDevices());
  const [supabaseDevices, { refetch: refetchSupabaseDevices }] = createResource(() => api.getDevicesFromSupabase());

  // Local state to hold the latest valid data (Stale-While-Revalidate pattern)
  // This prevents the UI from flickering to empty/loading state during refetches
  const [latestSummary, setLatestSummary] = createSignal<SystemSummary | null>(null);
  const [latestTelemetry, setLatestTelemetry] = createSignal<Device[]>([]);
  const [latestSupabase, setLatestSupabase] = createSignal<any[]>([]); // Using any[] for SupabaseDevice to avoid import issues if not exported

  // Sync resources to local state only when data is available
  createEffect(() => {
    const s = summary();
    if (s) setLatestSummary(s);
  });

  createEffect(() => {
    const d = devicesData();
    if (d?.devices) setLatestTelemetry(d.devices);
  });

  createEffect(() => {
    const d = supabaseDevices();
    if (d?.devices) setLatestSupabase(d.devices);
  });

  // Setup Realtime and Polling
  onMount(() => {
    // 1. Subscribe to Realtime updates for 'devices' table
    const channelName = realtimeManager.subscribeToTable('devices', {
      onAny: () => {
        // When any change happens in Supabase 'devices' table, refresh the local data
        refetchSupabaseDevices();
      }
    });

    // 2. Poll only for non-Supabase data (Telemetry/Summary)
    const interval = setInterval(() => {
      refetchSummary();
      refetchDevices();
      // Note: refetchSupabaseDevices is now handled by Realtime!
    }, 5000);

    onCleanup(() => {
      clearInterval(interval);
      realtimeManager.unsubscribe(channelName);
    });
  });

  // Combine devices with Supabase metadata using stable local data
  const enrichedDevices = () => {
    return enrichDevicesWithMetadata(latestTelemetry(), latestSupabase());
  };

  // Loading states now only matter if we have NO data at all
  const isSummaryLoading = () => summary.loading && !latestSummary();
  const isDevicesLoading = () => (devicesData.loading || supabaseDevices.loading) && !latestTelemetry().length;

  // Generate alerts based on stable local data
  const alerts = () => {
    const alertList: { type: string; message: string; time: string }[] = [];
    const s = latestSummary();

    if (s) {
      if (s.max_speed_kmh > 60) {
        alertList.push({
          type: "warning",
          message: `Velocidade máxima: ${s.max_speed_kmh.toFixed(1)} km/h`,
          time: "última hora"
        });
      }
      if (s.max_acceleration > 12) {
        alertList.push({
          type: "error",
          message: `Aceleração alta detectada: ${s.max_acceleration.toFixed(1)} m/s²`,
          time: "última hora"
        });
      }
      if (s.ingest_stats.mqtt_connected) {
        alertList.push({
          type: "info",
          message: `Sistema operacional: ${s.ingest_stats.messages_per_second.toFixed(1)} msg/s`,
          time: "tempo real"
        });
      }
    }

    return alertList;
  };

  return (
    <AppLayout>
      {/* Stats Grid */}
      <div class="grid grid-cols-4 gap-4 mb-4">
        <StatCard
          label="Dispositivos Ativos"
          value={latestSummary()?.active_devices ?? "..."}
          icon={TruckIcon}
          accent
          loading={isSummaryLoading()}
        />
        <StatCard
          label="Telemetrias (1h)"
          value={latestSummary()?.total_telemetries?.toLocaleString() ?? "..."}
          icon={DatabaseIcon}
          loading={isSummaryLoading()}
        />
        <StatCard
          label="Velocidade Média"
          value={latestSummary() ? `${latestSummary()!.avg_speed_kmh.toFixed(1)} km/h` : "..."}
          icon={SpeedIcon}
          loading={isSummaryLoading()}
        />
        <StatCard
          label="Aceleração Máxima"
          value={latestSummary() ? `${latestSummary()!.max_acceleration.toFixed(1)} m/s²` : "..."}
          icon={ActivityIcon}
          loading={isSummaryLoading()}
        />
      </div>

      {/* Main Content Grid */}
      <div class="grid gap-4" style={{ "grid-template-columns": "2fr 1fr" }}>
        {/* Devices List */}
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Dispositivos</h3>
            <div class="flex items-center gap-2">
              <button
                class="btn btn-ghost btn-sm"
                onClick={() => {
                  refetchDevices();
                  refetchSupabaseDevices();
                }}
                title="Atualizar"
              >
                <RefreshIcon />
              </button>
              <a href="/devices" class="btn btn-ghost text-sm">Ver todos →</a>
            </div>
          </div>
          <div>
            {/* Optimized Show: Only show fallback if we have NO data AND are pending. 
                If we have data, keep showing it even if refreshing. */}
            <Show when={!(isDevicesLoading() && !enrichedDevices()?.length)} fallback={
              <div class="p-4 text-center text-muted">Carregando dispositivos...</div>
            }>
              <Show when={enrichedDevices()?.length} fallback={
                <div class="p-4 text-center text-muted">Nenhum dispositivo ativo</div>
              }>
                <For each={enrichedDevices()}>
                  {(device) => <DeviceRow device={device} />}
                </For>
              </Show>
            </Show>
          </div>
        </div>

        {/* Alerts */}
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Status do Sistema</h3>
            <Show when={latestSummary()?.ingest_stats.mqtt_connected}>
              <span class="badge badge-success">MQTT OK</span>
            </Show>
          </div>
          <div class="card-body">
            <Show when={alerts().length > 0} fallback={
              <div class="text-center text-muted p-4">
                Sistema operando normalmente
              </div>
            }>
              <For each={alerts()}>
                {(alert) => <AlertItem alert={alert} />}
              </For>
            </Show>

            {/* Ingest Stats */}
            <Show when={latestSummary()}>
              <div class="mt-4 p-3" style={{
                background: "var(--color-bg-tertiary)",
                "border-radius": "var(--radius-md)"
              }}>
                <div class="text-xs text-muted mb-2">Estatísticas do Ingest</div>
                <div class="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span class="text-muted">Recebidas:</span>
                    <span style={{ "margin-left": "4px", color: "var(--color-text-primary)" }}>
                      {latestSummary()!.ingest_stats.messages_received}
                    </span>
                  </div>
                  <div>
                    <span class="text-muted">Inseridas:</span>
                    <span style={{ "margin-left": "4px", color: "var(--color-text-primary)" }}>
                      {latestSummary()!.ingest_stats.messages_inserted}
                    </span>
                  </div>
                  <div>
                    <span class="text-muted">Uptime:</span>
                    <span style={{ "margin-left": "4px", color: "var(--color-text-primary)" }}>
                      {Math.floor(latestSummary()!.ingest_stats.uptime_seconds / 60)}min
                    </span>
                  </div>
                  <div>
                    <span class="text-muted">DB:</span>
                    <span style={{
                      "margin-left": "4px",
                      color: latestSummary()!.ingest_stats.db_connected ? "var(--color-success)" : "var(--color-error)"
                    }}>
                      {latestSummary()!.ingest_stats.db_connected ? "OK" : "OFF"}
                    </span>
                  </div>
                </div>
              </div>
            </Show>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div class="mt-4">
        <div class="card">
          <div class="card-body">
            <div class="flex items-center justify-between">
              <div>
                <h3 style={{ "font-size": "var(--text-lg)", "font-weight": "600", "margin-bottom": "var(--space-1)" }}>
                  Acesso Rápido
                </h3>
                <p class="text-muted">Navegue para as principais funcionalidades</p>
              </div>
              <div class="flex gap-3">
                <a href="/map" class="btn btn-primary">
                  <MapIcon />
                  Abrir Mapa
                </a>
                <a href="/charts" class="btn btn-secondary">
                  <ChartIcon />
                  Ver Gráficos
                </a>
                <a href="/replay" class="btn btn-secondary">
                  <ReplayIcon />
                  Replay
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

// Icon components for quick actions
function MapIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
      <line x1="8" y1="2" x2="8" y2="18" />
      <line x1="16" y1="6" x2="16" y2="22" />
    </svg>
  );
}

function ChartIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
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
