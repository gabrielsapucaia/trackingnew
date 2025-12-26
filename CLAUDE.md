# CLAUDE.md

Este arquivo fornece orientações ao Claude Code (claude.ai/code) para trabalhar com o código deste repositório.

## Visão Geral do Projeto

AuraTracking é uma plataforma de telemetria industrial para rastreamento GPS/IMU de equipamentos de frota de mineração. O sistema coleta dados de dispositivos Android, ingere via MQTT, armazena em TimescaleDB e fornece dashboards de visualização.

## Estrutura do Repositório

Este é um monorepo contendo quatro componentes principais:

```
trackingnew/
├── AuraTracking/          # App Android (Kotlin) - coleta de dados GPS/IMU
├── AuraTrackingServer/    # Stack Docker - EMQX, TimescaleDB, Ingest Worker, Grafana
├── AuraTrackingDash/      # Dashboard Next.js 16 - interface web principal (consolidado)
└── BackTest/              # Ferramentas de análise Python - detecção de ciclos, processamento
```

## Arquitetura

```
App Android (AuraTracking)
    │ MQTT (QoS1, porta 1883)
    ▼
Broker EMQX (Docker)
    │
    ▼
Ingest Worker (Python/FastAPI)
    │
    ▼
TimescaleDB (PostgreSQL 15)
    │
    ├──▶ Dashboards Grafana
    └──▶ Dashboards Next.js (conexão Supabase)
```

## Comandos de Desenvolvimento

### AuraTrackingDash (Dashboard Principal)
```bash
cd AuraTrackingDash
npm install
npm run dev          # Inicia em http://localhost:3000
npm run build        # Build de produção
npm run lint         # ESLint
```

### AuraTrackingServer (Stack Docker)
```bash
cd AuraTrackingServer
docker compose up -d      # Inicia todos os serviços
docker compose logs -f    # Ver logs
docker compose down       # Para serviços
./deploy.sh               # Script de deploy completo
./test.sh                 # Executar testes MQTT
```

### AuraTracking (App Android)
```bash
cd AuraTracking
./gradlew assembleDebug   # Build APK debug
./gradlew installDebug    # Instalar no dispositivo conectado
```

### BackTest (Ferramentas de Análise)
```bash
cd BackTest
python 0_exportador/exportar_telemetria.py     # Exportar dados de telemetria
python 2_deteccao/detect_carregamento.py       # Detectar eventos de carregamento
python 3_processamento/gerar_extrato_ciclos.py # Gerar relatórios de ciclos
python 4_servidor/server.py                     # Executar servidor de análise
```

## Tecnologias Principais

- **Android**: Kotlin, Room, Ktor, Play Services Location, MQTT (Paho)
- **Stack Servidor**: EMQX 5.8.3, TimescaleDB (PostgreSQL 15), Grafana 11.3
- **Ingest Worker**: Python 3.12, FastAPI, paho-mqtt, asyncpg, Pydantic
- **Dashboard**: Next.js 16, React 19, TypeScript, Tailwind CSS v4, deck.gl, MapLibre GL
- **Banco de Dados**: Supabase (operadores, equipamentos), TimescaleDB (hypertable telemetria)

## Portas dos Serviços

| Serviço     | Porta | Descrição              |
|-------------|-------|------------------------|
| EMQX        | 1883  | MQTT TCP               |
| EMQX        | 8083  | MQTT WebSocket         |
| EMQX        | 18083 | Dashboard Web          |
| TimescaleDB | 5432  | PostgreSQL             |
| Ingest      | 8080  | API REST/SSE           |
| Grafana     | 3000  | Dashboards             |

## Configuração de Ambiente

- **AuraTrackingDash**: Copiar `.env.example` para `.env.local` e configurar credenciais Supabase
- **AuraTrackingServer**: Credenciais em `.env` (padrão: admin/aura2025)
- **AuraTracking**: Credenciais Supabase em `gradle.properties`

---

## API Endpoints

### Ingest Worker (porta 8080)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/health` | GET | Status e métricas do serviço |
| `/stats` | GET | Estatísticas detalhadas (mensagens, latência, erros) |
| `/ready` | GET | Readiness probe para Kubernetes/Docker |
| `/api/events/stream` | GET | Stream SSE tempo real (throttle 5s/device) |
| `/api/devices` | GET | Dispositivos ativos (últimos 5 minutos) |
| `/api/history` | GET | Telemetria histórica (params: device_id, start, end, limit=20000) |
| `/api/telemetry` | GET | Histórico com granularidade (raw, 1min, 1hour) |
| `/api/events` | GET | Busca de eventos (device, type, date range) |
| `/api/summary` | GET | Resumo do sistema últimas 24h |

### Dashboard API Routes (Next.js)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/offline/positions` | POST | Proxy para histórico do Ingest (converte timezone UTC-3) |
| `/api/profiles` | GET | Perfis de usuário (admin) |
| `/api/material-types` | POST | CRUD tipos de materiais |
| `/api/liberacoes` | POST | CRUD liberações |

---

## Tópicos MQTT

### Estrutura de Tópicos
```
aura/tracking/{deviceId}/telemetry  - Dados de telemetria (1Hz)
aura/tracking/{deviceId}/events     - Eventos discretos (login, impactos)
aura/tracking/{deviceId}/geofence   - Eventos de entrada/saída de zonas
```

### Payload Telemetria (exemplo)
```json
{
  "messageId": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-12-26T10:30:00Z",
  "deviceId": "samsung_a52_001",
  "operatorId": "op_12345",
  "gps": {
    "latitude": -11.695,
    "longitude": -47.159,
    "altitude": 280.5,
    "speed": 25.3,
    "bearing": 180.0,
    "accuracy": 3.5,
    "satellites": 12,
    "hdop": 0.8
  },
  "imu": {
    "accel": {"x": 0.1, "y": -0.2, "z": 9.8, "magnitude": 9.81},
    "gyro": {"x": 0.01, "y": -0.02, "z": 0.005, "magnitude": 0.023}
  },
  "system": {
    "battery": {"level": 85, "temp": 28.5, "status": "charging"},
    "wifi": {"rssi": -45, "ssid": "AuraMine"}
  }
}
```

### Configuração MQTT
- **Broker**: EMQX 5.8.3
- **QoS**: 1 (at least once)
- **Clean Session**: false (persistência de sessão)
- **Keepalive**: 30 segundos

---

## Schema do Banco de Dados

### TimescaleDB (Telemetria)

#### Tabela `telemetry` (Hypertable - chunks de 1 dia)

| Categoria | Campos |
|-----------|--------|
| **Metadados** | time, device_id, operator_id, message_id, topic, transmission_mode, received_at |
| **GPS Básico** | latitude, longitude, altitude, speed, bearing, gps_accuracy |
| **GPS Detalhado** | satellites, h_accuracy, v_accuracy, speed_accuracy, hdop, vdop, pdop |
| **IMU Básico** | accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z |
| **IMU Magnitude** | accel_magnitude, gyro_magnitude |
| **Magnetômetro** | mag_x, mag_y, mag_z, mag_magnitude, mag_accuracy |
| **Aceleração Linear** | linear_accel_x, linear_accel_y, linear_accel_z |
| **Gravidade** | gravity_x, gravity_y, gravity_z |
| **Rotation Vector** | rotation_x, rotation_y, rotation_z, rotation_w, rotation_heading_accuracy |
| **Orientação** | azimuth, pitch, roll |
| **Bateria** | battery_level, battery_temp, battery_status, battery_voltage, battery_health, battery_technology, charge_counter, full_capacity |
| **WiFi** | wifi_rssi, wifi_ssid, wifi_bssid, wifi_frequency, wifi_channel |
| **Celular** | network_type, operator_name, signal_strength, rsrp, rsrq, rssnr, cell_id, pci, tac, earfcn, bands |
| **Raw** | raw_payload (JSONB) |

#### Tabela `events` (Hypertable)
- time, device_id, operator_id, event_type, event_data (JSONB), topic, received_at

#### Continuous Aggregates
- `telemetry_1min` - Médias por minuto
- `telemetry_1hour` - Médias por hora

#### Políticas
- **Compressão**: após 3 dias (segmentação por device_id, ~90% economia)
- **Retenção**: telemetry 180 dias, events 365 dias, ingest_stats 30 dias

#### Índices Otimizados
- `device_time` - Busca por dispositivo e período
- `operator_time` - Busca por operador
- `location` - Busca geográfica (GIST)
- `high_speed` - Alertas de velocidade (>80 km/h)
- `high_accel` - Alertas de aceleração (>15 m/s²)

### Supabase (Dados de Configuração)

| Tabela | Descrição | Colunas Principais |
|--------|-----------|-------------------|
| `operators` | Cadastro de operadores | id, name, registration, pin, status |
| `equipment` | Cadastro de equipamentos | id, tag, type_id, status, fleet |
| `equipment_types` | Tipos de equipamentos | id, name, description |
| `geofences` | Zonas geográficas | id, name, zone_type, polygon_json, color, is_active |
| `profiles` | Usuários do dashboard | id, email, status, role, permission |
| `material_types` | Tipos de materiais | id, name |
| `liberacoes` | Liberações | id, tipo, responsavel |

**Valores de zone_type (geofences):** `loading`, `unloading`, `parking`, `maintenance`, `fuel`, `restricted`, `custom`

**Formato polygon_json:** `[[lat, lng], [lat, lng], ...]` (polígono fechado)

---

## Arquitetura do App Android (AuraTracking)

### Room Database (v6)
| Tabela | Propósito |
|--------|-----------|
| `config` | Configuração do dispositivo (equipment_name, tracking_enabled) |
| `operators` | Operadores cacheados do Supabase |
| `telemetry_queue` | Fila offline de telemetria (até 30 dias, ~3M registros) |
| `zones` | Geofences cacheadas do Supabase |
| `geofence_events` | Eventos de entrada/saída pendentes de upload |
| `sync_state` | Status de sincronização por tipo de dado |

### SyncOrchestrator (sync/)
Sistema de sincronização unificado com guardrails para conectividade intermitente (caminhão em área rural).

**Arquitetura:**
```
UnifiedSyncWorker (a cada 15 min)
    │
    ▼
SyncOrchestrator
    │
    ├── FASE 1: DOWNLOAD (Supabase → App)
    │   ├── Fetch operadores, geofences
    │   ├── Validar (SyncValidator guardrails)
    │   └── Commit atômico (Room withTransaction)
    │
    └── FASE 2: UPLOAD (App → MQTT)
        ├── Flush fila telemetria (lotes de 50)
        └── Flush eventos geofence (lotes de 50)
```

**Guardrails (SyncValidator):**
- Operadores: mínimo 1 ativo, IDs válidos, nomes não-vazios
- Geofences: polígono >= 3 pontos, estrutura JSON válida
- Retry: 3 tentativas com backoff exponencial (máx 120s)
- Timeout: 30s por operação de fetch
- Mutex: previne execuções concorrentes de sync

**Arquivos-chave:**
- `sync/SyncOrchestrator.kt` - Lógica principal do orquestrador
- `sync/SyncValidator.kt` - Guardrails de validação de dados
- `sync/UnifiedSyncWorker.kt` - Wrapper WorkManager
- `sync/SyncStateEntity.kt` - Estado persistente de sync

### Logging (AuraLog)
Logging persistente em arquivo com componentes: GPS, IMU, MQTT, Service, Queue, Watchdog, Analytics, Geofence, Sync

Logs salvos em: `/storage/emulated/0/Android/data/com.aura.tracking/files/logs/`

### Geofencing
- `GeofenceManager`: Detecção ponto-em-polígono para zonas de carga/descarga
- Hysteresis de 10m para evitar flapping
- Dwell time mínimo de 5s para confirmar entrada

### Sistema de Design UI/UX (Dez 2024)

**Tema Industrial/Corporativo** implementado com Material Design 3:

| Cor | Hex | Uso |
|-----|-----|-----|
| Primary (Azul Petróleo) | `#1A3A52` | Toolbar, textos principais |
| Secondary (Laranja Segurança) | `#E65100` | CTAs, botões primários |
| Accent (Âmbar) | `#FFC107` | Destaques, alertas |
| Background | `#F5F7FA` | Fundo das telas |
| Surface | `#FFFFFF` | Cards |

**Arquivos de estilo:**
- `res/values/colors.xml` - Paleta de cores completa
- `res/values/themes.xml` - Tema e estilos de componentes
- `res/drawable/` - Ícones vetoriais (ic_*.xml)

**Estilos de botões:**
- `AuraTracking.Button.Primary` - Laranja, CTAs principais
- `AuraTracking.Button.Secondary` - Azul petróleo
- `AuraTracking.Button.Outlined` - Borda azul, fundo transparente

**Padrão para botões:** Sempre usar `wrap_content` para altura (nunca altura fixa como 40dp/48dp) para evitar truncamento de texto em diferentes densidades de tela.

**Telas do app:**
| Activity | Descrição |
|----------|-----------|
| `LoginActivity` | Tela inicial com matrícula |
| `PinActivity` | Entrada de PIN com ícone de cadeado |
| `DashboardActivity` | Painel principal com telemetria |
| `AdminConfigActivity` | Configurações do dispositivo |
| `SupabasePinActivity` | PIN para acesso Supabase |
| `SupabaseConfigActivity` | Sync de tabelas Supabase |
| `DiagnosticsActivity` | Diagnósticos e logs |

---

## Projeto Supabase
- **Project ID:** `nucqowewuqeveocmsdnq`
- **Região:** us-east-1
- **API:** REST via Ktor HTTP Client no app Android

---

## Dashboard Web (AuraTrackingDash)

### Arquitetura de Dados

```
┌──────────────────────────────────────────────┐
│           AuraTrackingDash                   │
├──────────────────────────────────────────────┤
│  Autenticação: Supabase                      │
│  Dados de Configuração: Supabase             │
│    • operators, equipment, geofences         │
│    • equipment_types, material_types         │
│    • profiles (usuários)                     │
├──────────────────────────────────────────────┤
│  Telemetria: Ingest Worker (porta 8080)      │
│    • SSE: /api/events/stream                 │
│    • REST: /api/devices                      │
│    • Histórico: /api/offline/positions       │
└──────────────────────────────────────────────┘
```

### Recursos do Dashboard

| Página | Rota | Descrição |
|--------|------|-----------|
| Login | `/login` | Autenticação com restrição de domínio (@auraminerals.com) |
| Tempo Real | `/monitoramento/tempo-real` | Mapa com posições ao vivo via SSE |
| Offline | `/monitoramento/offline*` | Análise histórica (heatmap, hex, scatter, etc.) |
| Cadastro | `/cadastro/*` | CRUD de operadores, equipamentos, tipos |
| Admin | `/admin/usuarios` | Gerenciamento de usuários |

### Melhorias Técnicas

- **SSE Connection**: Singleton global, idle timeout (30s), auto-reconnect com delay
- **DeviceTooltip**: Segue dispositivo em pan/zoom do mapa
- **Connection Status**: Indicador visual (LIVE/RECONNECTING/FALLBACK/OFFLINE)
- **API Client**: Timeout handling (10s), `combineAbortSignals()`, error handling

### Arquivos-Chave

```
AuraTrackingDash/src/
├── components/map/
│   ├── MapView.tsx           # Componente principal do mapa
│   ├── useDeviceStream.ts    # Hook SSE com reconnect
│   └── offlineLayers.ts      # Layers para análise offline
├── lib/map/
│   ├── config.ts             # Configuração API_BASE_URL
│   └── api-client/devices.ts # Fetch com timeout
├── services/                 # Camada de serviços Supabase
└── middleware.ts             # Auth middleware (não modificar)
```

### Variáveis de Ambiente

```bash
# .env.local
NEXT_PUBLIC_SUPABASE_URL=https://nucqowewuqeveocmsdnq.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080  # Ingest Worker
```

---

## BackTest (Análise Python)

### Estrutura
```
BackTest/
├── 0_exportador/           # Exportar telemetria do TimescaleDB
│   ├── exportar_telemetria.py
│   └── config_db.yaml
├── 1_configuracao/         # Configurações de análise
│   ├── config.yaml
│   └── areas_carregamento.json
├── 2_deteccao/             # Detecção de eventos
│   └── detect_carregamento.py
├── 3_processamento/        # Processamento de ciclos
│   └── gerar_extrato_ciclos.py
├── 4_servidor/             # Servidor web Flask
│   └── server.py
└── 5_visualizacao/         # Dashboards HTML/JS
    ├── index.html
    ├── visualizacao_ciclos.html
    ├── distribuicao_fases.html
    └── editor_poligonos.html
```

### Algoritmo de Detecção de Carregamento
- Velocidade < 0.5 km/h
- Duração: 90-320 segundos
- Variância de vibração: 0.012-0.04

### Comandos Úteis
```bash
# Exportar telemetria de um período
python 0_exportador/exportar_telemetria.py --device CAM01 --start 2024-12-01 --end 2024-12-07

# Detectar carregamentos
python 2_deteccao/detect_carregamento.py --input data/telemetria.csv

# Gerar extrato de ciclos
python 3_processamento/gerar_extrato_ciclos.py --input data/eventos.csv

# Iniciar servidor de visualização
python 4_servidor/server.py  # http://localhost:5000
```

---

## Troubleshooting

| Problema | Causa Provável | Solução |
|----------|----------------|---------|
| SSE não conecta | Ingest Worker offline | `docker compose logs ingest` |
| Mapa em branco | Falta ortho.webp | Verificar `public/ortho.webp` existe |
| Dados não aparecem | Filtro de tempo incorreto | Ajustar range de datas no seletor |
| Build falha com env | Variáveis faltando | Verificar `.env.local` com Supabase keys |
| MQTT desconecta | Keepalive timeout | Verificar logs EMQX: `docker compose logs emqx` |
| Android não sincroniza | Sem conectividade | Verificar `DiagnosticsActivity` no app |
| Queue crescendo | MQTT offline | Verificar conexão e fazer flush manual |
| GPS impreciso | Poucos satélites | Verificar céu aberto, hdop > 2.0 é ruim |
| Login falha | Domínio incorreto | Usar email @auraminerals.com |
| Página /aguardando | Perfil pendente | Admin aprovar em /admin/usuarios |
| Telemetria duplicada | message_id faltando | Verificar envio de UUID único |
| Compressão falha | Chunks muito novos | Aguardar 3 dias para compressão automática |
