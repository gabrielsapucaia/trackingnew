# AuraTracking Frontend

Sistema de rastreamento de telemetria em tempo real para frota de mineração.

## 🎯 Visão Geral

AuraTracking Frontend é uma aplicação web de alta performance construída com:

- **SolidStart** - Framework web com SSR
- **Web Workers** - Processamento em background
- **SharedArrayBuffer** - Memória compartilhada para dados de telemetria
- **deck.gl** - Visualização de mapas WebGL
- **uPlot** - Gráficos de alta performance
- **MapLibre GL** - Renderização de mapas

## 📋 Requisitos

- Node.js 22+
- Navegador com suporte a SharedArrayBuffer (Chrome 92+, Firefox 79+, Safari 16.4+)

## 🚀 Quick Start

```bash
# Instalar dependências
npm install

# Desenvolvimento
npm run dev

# Build de produção
npm run build

# Preview do build
npm start
```

O servidor de desenvolvimento estará disponível em `http://localhost:3000`.

## 📁 Estrutura do Projeto

```
AuraTrackingFrontend/
├── src/
│   ├── routes/                 # Páginas (file-based routing)
│   │   ├── index.tsx          # Dashboard principal
│   │   ├── map.tsx            # Mapa em tempo real
│   │   ├── charts.tsx         # Gráficos 1Hz
│   │   ├── analytics.tsx      # Painéis de analytics
│   │   ├── replay.tsx         # Replay de trajetos
│   │   └── devices/
│   │       ├── index.tsx      # Lista de dispositivos
│   │       └── [id].tsx       # Detalhes do dispositivo
│   │
│   ├── layouts/
│   │   └── AppLayout.tsx      # Layout persistente
│   │
│   ├── components/
│   │   ├── map/               # Componentes deck.gl
│   │   ├── charts/            # Componentes uPlot
│   │   ├── replay/            # Controles de replay
│   │   └── ui/                # Componentes base
│   │
│   ├── lib/
│   │   ├── websocket/         # Cliente WebSocket
│   │   ├── workers/           # Web Workers e SAB
│   │   ├── stores/            # Estado SolidJS
│   │   └── utils/             # Utilitários
│   │
│   └── providers/
│       ├── TelemetryProvider.tsx
│       └── WebSocketProvider.tsx
│
└── public/                    # Assets estáticos
```

## 🔧 Configuração

### Headers COOP/COEP

Para SharedArrayBuffer funcionar, os seguintes headers são necessários:

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

Estes já estão configurados em `app.config.ts`.

### Variáveis de Ambiente

```env
VITE_API_URL=http://localhost:8080
VITE_WS_URL=ws://localhost:8083/mqtt
```

## 🗺️ Funcionalidades

### Dashboard
- Estatísticas em tempo real
- Lista de dispositivos ativos
- Alertas recentes
- Acesso rápido às funcionalidades

### Mapa em Tempo Real
- Marcadores de dispositivos
- Trilhas coloridas por velocidade
- Heatmap de densidade
- Zoom/pan com WebGL

### Gráficos 1Hz
- Velocidade em tempo real
- Aceleração (magnitude e eixos)
- Downsample automático (LTTB)
- Zoom e pan interativos

### Analytics
- KPIs agregados
- Ranking de operadores
- Resumo de alertas
- Status da frota

### Replay
- Reprodução de trajetos históricos
- Velocidade variável (0.5x - 8x)
- Timeline com seek
- Interpolação suave

### Gestão de Dispositivos
- Lista com filtros
- Busca textual
- Status em tempo real
- Detalhes completos

## 🏗️ Arquitetura

### Web Workers

```
┌─────────────────────────────────────────┐
│              MAIN THREAD                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │SolidJS  │  │ deck.gl │  │  uPlot  │ │
│  │   UI    │  │   Map   │  │ Charts  │ │
│  └────┬────┘  └────┬────┘  └────┬────┘ │
│       └────────────┼───────────-┘      │
│                    │                    │
│              ┌─────▼─────┐             │
│              │SAB Reader │             │
│              └─────┬─────┘             │
└────────────────────┼────────────────────┘
                     │ SharedArrayBuffer
┌────────────────────┼────────────────────┐
│    WORKER THREADS  │                    │
│              ┌─────▼─────┐             │
│              │    SAB    │             │
│              └─────┬─────┘             │
│        ┌───────────┼───────────┐       │
│  ┌─────▼─────┐  ┌──▼──────┐          │
│  │ Telemetry │  │Analytics│          │
│  │  Worker   │  │ Worker  │          │
│  └───────────┘  └─────────┘          │
└─────────────────────────────────────────┘
```

### SharedArrayBuffer Layout

```
HEADER (256 bytes):
┌────────────────────────────────────────┐
│ Magic (4B) | Version (4B) | Count (4B) │
│ WriteIdx (4B) | MaxRecords (4B) | ...  │
└────────────────────────────────────────┘

RECORD (64 bytes):
┌────────────────────────────────────────┐
│ Timestamp (8B) | DeviceHash (2B) | ... │
│ Lat (8B) | Lon (8B) | Speed (4B) | ... │
└────────────────────────────────────────┘
```

## 📊 Performance

| Métrica | Alvo | Implementado |
|---------|------|--------------|
| Mensagens/s | 200 | ✅ Via SAB |
| Frame time | <16ms | ✅ Workers |
| Memória (1h) | <500MB | ✅ ~11.5MB SAB |
| FCP | <1.5s | ✅ SSR |

## 🔌 Integração com Backend

O frontend espera dois endpoints do backend:

1. **WebSocket** para telemetria em tempo real
   - Porta 8083 (EMQX WebSocket) ou endpoint customizado
   - Formato: JSON com `type: "telemetry"` e array de packets

2. **REST API** para dados históricos
   - `GET /api/telemetry?device={id}&start={ts}&end={ts}`
   - `GET /api/devices`
   - `GET /api/events`

## 🧪 Testes

```bash
# Typecheck
npm run typecheck

# Lint
npm run lint
```

## 📜 Licença

Proprietário - AuraTracking

