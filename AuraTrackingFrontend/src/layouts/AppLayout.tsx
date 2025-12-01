import { A, useLocation } from "@solidjs/router";
import { ParentProps, Show, createMemo, createSignal, onMount, onCleanup } from "solid-js";
import { isServer } from "solid-js/web";

// Icons as simple SVG components
const DashboardIcon = () => (
  <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <rect x="3" y="3" width="7" height="7" rx="1" />
    <rect x="14" y="3" width="7" height="7" rx="1" />
    <rect x="3" y="14" width="7" height="7" rx="1" />
    <rect x="14" y="14" width="7" height="7" rx="1" />
  </svg>
);

const MapIcon = () => (
  <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
    <line x1="8" y1="2" x2="8" y2="18" />
    <line x1="16" y1="6" x2="16" y2="22" />
  </svg>
);

const ChartIcon = () => (
  <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);

const AnalyticsIcon = () => (
  <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M21.21 15.89A10 10 0 1 1 8 2.83" />
    <path d="M22 12A10 10 0 0 0 12 2v10z" />
  </svg>
);

const ReplayIcon = () => (
  <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polygon points="5 3 19 12 5 21 5 3" />
  </svg>
);

const DevicesIcon = () => (
  <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
    <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
  </svg>
);

const SettingsIcon = () => (
  <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

interface NavItemProps {
  href: string;
  icon: () => any;
  label: string;
}

function NavItem(props: NavItemProps) {
  const location = useLocation();
  const isActive = () => {
    if (props.href === "/") {
      return location.pathname === "/";
    }
    return location.pathname.startsWith(props.href);
  };

  return (
    <A href={props.href} class={`nav-item ${isActive() ? "active" : ""}`}>
      {props.icon()}
      <span>{props.label}</span>
    </A>
  );
}

export default function AppLayout(props: ParentProps) {
  const location = useLocation();
  
  // Default signals for SSR
  const [connectionState, setConnectionState] = createSignal<string>('DISCONNECTED');
  const [messagesReceived, setMessagesReceived] = createSignal(0);
  const [reconnectAttempts, setReconnectAttempts] = createSignal(0);
  const [isWorkerReady, setIsWorkerReady] = createSignal(false);

  // Listen for MQTT status events on client
  onMount(() => {
    if (isServer || typeof window === 'undefined') return;

    // Listen for telemetry events to count messages
    const handleTelemetry = () => {
      setMessagesReceived((prev) => prev + 1);
      setConnectionState('CONNECTED');
    };

    // Listen for MQTT connection status
    const handleMqttStatus = (e: CustomEvent<{ state: string; attempts?: number }>) => {
      setConnectionState(e.detail.state);
      if (e.detail.attempts !== undefined) {
        setReconnectAttempts(e.detail.attempts);
      }
    };

    // Listen for worker status
    const handleWorkerStatus = (e: CustomEvent<{ ready: boolean }>) => {
      setIsWorkerReady(e.detail.ready);
    };

    window.addEventListener('telemetry', handleTelemetry);
    window.addEventListener('mqtt-status', handleMqttStatus as EventListener);
    window.addEventListener('worker-status', handleWorkerStatus as EventListener);

    onCleanup(() => {
      window.removeEventListener('telemetry', handleTelemetry);
      window.removeEventListener('mqtt-status', handleMqttStatus as EventListener);
      window.removeEventListener('worker-status', handleWorkerStatus as EventListener);
    });
  });

  // Map MQTT connection state to UI state
  const uiConnectionState = createMemo(() => {
    const state = connectionState();
    switch (state) {
      case 'CONNECTED':
        return 'connected';
      case 'CONNECTING':
      case 'RECONNECTING':
        return 'connecting';
      default:
        return 'disconnected';
    }
  });

  const getPageTitle = () => {
    const path = location.pathname;
    switch (path) {
      case "/":
        return "Dashboard";
      case "/map":
        return "Mapa em Tempo Real";
      case "/charts":
        return "Gráficos";
      case "/analytics":
        return "Analytics";
      case "/replay":
        return "Replay";
      case "/devices":
        return "Dispositivos";
      default:
        if (path.startsWith("/devices/")) {
          return "Detalhes do Dispositivo";
        }
        return "AuraTracking";
    }
  };

  const getConnectionLabel = () => {
    const state = connectionState();
    const msgCount = messagesReceived();
    
    switch (state) {
      case "CONNECTED":
        return msgCount > 0 ? `${msgCount} msgs` : "Conectado";
      case "CONNECTING":
        return "Conectando...";
      case "RECONNECTING":
        return `Reconectando (${reconnectAttempts()})...`;
      case "FAILED":
        return "Falhou";
      default:
        return "Desconectado";
    }
  };

  return (
    <div class="app-layout">
      {/* Sidebar */}
      <aside class="sidebar">
        <div class="sidebar-header">
          <div class="sidebar-logo">A</div>
          <span class="sidebar-title">AuraTracking</span>
        </div>

        <nav class="sidebar-nav">
          <div class="nav-section">
            <div class="nav-section-title">Principal</div>
            <NavItem href="/" icon={DashboardIcon} label="Dashboard" />
            <NavItem href="/map" icon={MapIcon} label="Mapa" />
            <NavItem href="/charts" icon={ChartIcon} label="Gráficos" />
          </div>

          <div class="nav-section">
            <div class="nav-section-title">Análise</div>
            <NavItem href="/analytics" icon={AnalyticsIcon} label="Analytics" />
            <NavItem href="/replay" icon={ReplayIcon} label="Replay" />
          </div>

          <div class="nav-section">
            <div class="nav-section-title">Gestão</div>
            <NavItem href="/devices" icon={DevicesIcon} label="Dispositivos" />
          </div>
        </nav>

        <div class="sidebar-footer">
          <div class="connection-status">
            <div class={`status-dot ${uiConnectionState()}`} />
            <span>{getConnectionLabel()}</span>
          </div>
          <Show when={isWorkerReady()}>
            <div class="worker-status" title="Worker ativo">
              <span class="worker-badge">⚡ Worker</span>
            </div>
          </Show>
        </div>
      </aside>

      {/* Main Content */}
      <main class="main-content">
        <header class="main-header">
          <h1 class="page-title">{getPageTitle()}</h1>
          <div class="header-actions">
            <button class="btn btn-ghost btn-icon" title="Configurações">
              <SettingsIcon />
            </button>
          </div>
        </header>

        <div class="page-content">
          {props.children}
        </div>
      </main>
    </div>
  );
}

