import { createSignal, For, createMemo } from "solid-js";
import { A } from "@solidjs/router";
import AppLayout from "~/layouts/AppLayout";

// Mock device data
const mockDevices = [
  { 
    id: "ZF524XRLK3", 
    name: "Caminhão 001", 
    model: "Moto G34 5G",
    operator: "João Silva",
    status: "online" as const, 
    speed: 32.5, 
    lastSeen: new Date(),
    totalKm: 1234.5,
    todayKm: 45.2,
    alerts: 2
  },
  { 
    id: "AB123DEF45", 
    name: "Caminhão 002", 
    model: "Moto G34 5G",
    operator: "Maria Santos",
    status: "online" as const, 
    speed: 0, 
    lastSeen: new Date(),
    totalKm: 892.3,
    todayKm: 23.1,
    alerts: 0
  },
  { 
    id: "CD789GHI01", 
    name: "Escavadeira 001", 
    model: "Samsung A54",
    operator: "Pedro Costa",
    status: "idle" as const, 
    speed: 0, 
    lastSeen: new Date(Date.now() - 120000),
    totalKm: 567.8,
    todayKm: 12.4,
    alerts: 1
  },
  { 
    id: "EF456JKL23", 
    name: "Caminhão 003", 
    model: "Moto G34 5G",
    operator: "Ana Oliveira",
    status: "online" as const, 
    speed: 45.2, 
    lastSeen: new Date(),
    totalKm: 2341.2,
    todayKm: 67.8,
    alerts: 5
  },
  { 
    id: "GH012MNO45", 
    name: "Caminhão 004", 
    model: "Moto G34 5G",
    operator: "Carlos Lima",
    status: "offline" as const, 
    speed: 0, 
    lastSeen: new Date(Date.now() - 3600000),
    totalKm: 1567.9,
    todayKm: 0,
    alerts: 0
  },
];

type StatusFilter = "all" | "online" | "idle" | "offline";

export default function DevicesPage() {
  const [searchQuery, setSearchQuery] = createSignal("");
  const [statusFilter, setStatusFilter] = createSignal<StatusFilter>("all");
  const [sortBy, setSortBy] = createSignal<"name" | "status" | "speed">("name");

  const filteredDevices = createMemo(() => {
    let result = [...mockDevices];

    // Apply search filter
    if (searchQuery()) {
      const query = searchQuery().toLowerCase();
      result = result.filter(d => 
        d.name.toLowerCase().includes(query) ||
        d.id.toLowerCase().includes(query) ||
        d.operator.toLowerCase().includes(query)
      );
    }

    // Apply status filter
    if (statusFilter() !== "all") {
      result = result.filter(d => d.status === statusFilter());
    }

    // Apply sorting
    result.sort((a, b) => {
      switch (sortBy()) {
        case "status":
          const statusOrder = { online: 0, idle: 1, offline: 2 };
          return statusOrder[a.status] - statusOrder[b.status];
        case "speed":
          return b.speed - a.speed;
        default:
          return a.name.localeCompare(b.name);
      }
    });

    return result;
  });

  const statusCounts = createMemo(() => ({
    all: mockDevices.length,
    online: mockDevices.filter(d => d.status === "online").length,
    idle: mockDevices.filter(d => d.status === "idle").length,
    offline: mockDevices.filter(d => d.status === "offline").length,
  }));

  const formatLastSeen = (date: Date) => {
    const diff = Date.now() - date.getTime();
    if (diff < 60000) return "agora";
    if (diff < 3600000) return `${Math.floor(diff / 60000)} min`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} h`;
    return `${Math.floor(diff / 86400000)} d`;
  };

  return (
    <AppLayout>
      <div class="flex flex-col gap-4">
        {/* Header */}
        <div class="flex items-center justify-between">
          <div>
            <h2 style={{ "font-size": "var(--text-2xl)", "font-weight": "600" }}>
              Dispositivos
            </h2>
            <p class="text-muted">Gerenciamento e monitoramento da frota</p>
          </div>
          <button class="btn btn-primary">
            <PlusIcon />
            Adicionar Dispositivo
          </button>
        </div>

        {/* Filters & Search */}
        <div class="flex items-center justify-between gap-4">
          {/* Status Tabs */}
          <div class="flex gap-1" style={{ 
            background: "var(--color-bg-tertiary)", 
            "border-radius": "var(--radius-lg)",
            padding: "var(--space-1)",
            border: "1px solid var(--color-border-primary)"
          }}>
            <For each={[
              { value: "all" as StatusFilter, label: "Todos" },
              { value: "online" as StatusFilter, label: "Online" },
              { value: "idle" as StatusFilter, label: "Parado" },
              { value: "offline" as StatusFilter, label: "Offline" },
            ]}>
              {(tab) => (
                <button
                  class={`btn ${statusFilter() === tab.value ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setStatusFilter(tab.value)}
                >
                  {tab.label}
                  <span class="badge" style={{ 
                    "margin-left": "var(--space-2)",
                    background: statusFilter() === tab.value ? "rgba(0,0,0,0.2)" : "var(--color-bg-secondary)"
                  }}>
                    {statusCounts()[tab.value]}
                  </span>
                </button>
              )}
            </For>
          </div>

          {/* Search & Sort */}
          <div class="flex gap-3">
            <div style={{ position: "relative" }}>
              <SearchIcon />
              <input 
                type="text"
                placeholder="Buscar dispositivo..."
                value={searchQuery()}
                onInput={(e) => setSearchQuery(e.target.value)}
                style={{
                  background: "var(--color-bg-tertiary)",
                  border: "1px solid var(--color-border-primary)",
                  color: "var(--color-text-primary)",
                  padding: "var(--space-2) var(--space-4) var(--space-2) var(--space-10)",
                  "border-radius": "var(--radius-lg)",
                  width: "250px"
                }}
              />
            </div>

            <select 
              value={sortBy()}
              onChange={(e) => setSortBy(e.target.value as any)}
              style={{
                background: "var(--color-bg-tertiary)",
                border: "1px solid var(--color-border-primary)",
                color: "var(--color-text-primary)",
                padding: "var(--space-2) var(--space-4)",
                "border-radius": "var(--radius-lg)",
                cursor: "pointer"
              }}
            >
              <option value="name">Ordenar por Nome</option>
              <option value="status">Ordenar por Status</option>
              <option value="speed">Ordenar por Velocidade</option>
            </select>
          </div>
        </div>

        {/* Devices Grid */}
        <div class="grid grid-cols-2 gap-4">
          <For each={filteredDevices()}>
            {(device) => (
              <A 
                href={`/devices/${device.id}`}
                class="card"
                style={{ 
                  "text-decoration": "none",
                  transition: "all var(--transition-fast)",
                  cursor: "pointer"
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "var(--color-border-secondary)";
                  e.currentTarget.style.transform = "translateY(-2px)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--color-border-primary)";
                  e.currentTarget.style.transform = "translateY(0)";
                }}
              >
                <div class="card-body">
                  <div class="flex items-start justify-between mb-4">
                    <div class="flex items-center gap-3">
                      <div style={{
                        width: "48px",
                        height: "48px",
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
                        <div style={{ "font-weight": "600", "font-size": "var(--text-lg)" }}>
                          {device.name}
                        </div>
                        <div class="text-sm text-muted">{device.id}</div>
                      </div>
                    </div>
                    <StatusBadge status={device.status} />
                  </div>

                  <div class="grid grid-cols-3 gap-4 mb-4">
                    <div>
                      <div class="text-xs text-muted">Velocidade</div>
                      <div style={{ 
                        "font-weight": "600",
                        color: device.speed > 0 ? "var(--color-accent-primary)" : "var(--color-text-tertiary)"
                      }}>
                        {device.speed > 0 ? `${device.speed} km/h` : "Parado"}
                      </div>
                    </div>
                    <div>
                      <div class="text-xs text-muted">Hoje</div>
                      <div style={{ "font-weight": "600" }}>{device.todayKm} km</div>
                    </div>
                    <div>
                      <div class="text-xs text-muted">Total</div>
                      <div style={{ "font-weight": "600" }}>{device.totalKm.toLocaleString()} km</div>
                    </div>
                  </div>

                  <div class="flex items-center justify-between pt-3" style={{ 
                    "border-top": "1px solid var(--color-border-primary)"
                  }}>
                    <div class="flex items-center gap-2">
                      <div style={{
                        width: "24px",
                        height: "24px",
                        background: "var(--color-bg-tertiary)",
                        "border-radius": "var(--radius-full)",
                        display: "flex",
                        "align-items": "center",
                        "justify-content": "center",
                        "font-size": "var(--text-xs)",
                        color: "var(--color-text-secondary)"
                      }}>
                        {device.operator.split(" ").map(n => n[0]).join("")}
                      </div>
                      <span class="text-sm">{device.operator}</span>
                    </div>
                    <div class="flex items-center gap-3">
                      {device.alerts > 0 && (
                        <span class="badge badge-warning">
                          {device.alerts} alertas
                        </span>
                      )}
                      <span class="text-xs text-muted">
                        {formatLastSeen(device.lastSeen)}
                      </span>
                    </div>
                  </div>
                </div>
              </A>
            )}
          </For>
        </div>

        {filteredDevices().length === 0 && (
          <div class="card">
            <div class="card-body text-center" style={{ padding: "var(--space-12)" }}>
              <SearchIcon style={{ 
                width: "48px", 
                height: "48px", 
                color: "var(--color-text-tertiary)",
                margin: "0 auto var(--space-4)"
              }} />
              <h3 style={{ "margin-bottom": "var(--space-2)" }}>Nenhum dispositivo encontrado</h3>
              <p class="text-muted">Tente ajustar os filtros ou termos de busca</p>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
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
function TruckIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M1 3h15v13H1z" />
      <path d="M16 8h4l3 3v5h-7V8z" />
      <circle cx="5.5" cy="18.5" r="2.5" />
      <circle cx="18.5" cy="18.5" r="2.5" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function SearchIcon(props: { style?: any }) {
  return (
    <svg 
      width="20" 
      height="20" 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      stroke-width="2"
      style={{ 
        position: "absolute", 
        left: "12px", 
        top: "50%", 
        transform: "translateY(-50%)",
        color: "var(--color-text-tertiary)",
        ...props.style
      }}
    >
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

