# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AuraTracking is an industrial telemetry platform for GPS/IMU tracking of mining fleet equipment. The system collects data from Android devices, ingests it via MQTT, stores in TimescaleDB, and provides visualization dashboards.

## Repository Structure

This is a monorepo containing five main components:

```
trackingnew/
├── AuraTracking/          # Android app (Kotlin) - GPS/IMU data collection
├── AuraTrackingServer/    # Docker stack - EMQX, TimescaleDB, Ingest Worker, Grafana
├── AuraTrackingDash/      # Next.js 16 dashboard - main web interface
├── AuraTrackingFrontend/  # Next.js 14 frontend - map visualization
└── BackTest/              # Python analysis tools - cycle detection, data processing
```

## Architecture

```
Android App (AuraTracking)
    │ MQTT (QoS1, port 1883)
    ▼
EMQX Broker (Docker)
    │
    ▼
Ingest Worker (Python/FastAPI)
    │
    ▼
TimescaleDB (PostgreSQL 15)
    │
    ├──▶ Grafana Dashboards
    └──▶ Next.js Dashboards (Supabase connection)
```

## Development Commands

### AuraTrackingDash (Main Dashboard)
```bash
cd AuraTrackingDash
npm install
npm run dev          # Starts on http://localhost:3000
npm run build        # Production build
npm run lint         # ESLint
```

### AuraTrackingFrontend (Map Visualization)
```bash
cd AuraTrackingFrontend
npm install
npm run dev          # Starts on http://localhost:3001
npm run build
npm run lint
```

### AuraTrackingServer (Docker Stack)
```bash
cd AuraTrackingServer
docker compose up -d      # Start all services
docker compose logs -f    # View logs
docker compose down       # Stop services
./deploy.sh               # Full deployment script
./test.sh                 # Run MQTT tests
```

### AuraTracking (Android App)
```bash
cd AuraTracking
./gradlew assembleDebug   # Build debug APK
./gradlew installDebug    # Install on connected device
```

### BackTest (Analysis Tools)
```bash
cd BackTest
python 0_exportador/exportar_telemetria.py     # Export telemetry data
python 2_deteccao/detect_carregamento.py       # Detect loading events
python 3_processamento/gerar_extrato_ciclos.py # Generate cycle reports
python 4_servidor/server.py                     # Run analysis server
```

## Key Technologies

- **Android**: Kotlin, Room, Ktor, Play Services Location, MQTT (Paho)
- **Server Stack**: EMQX 5.x, TimescaleDB (PostgreSQL 15), Grafana 11.x
- **Ingest Worker**: Python 3.12, FastAPI, paho-mqtt, asyncpg, Pydantic
- **Dashboards**: Next.js (16 and 14), React, TypeScript, Tailwind CSS, deck.gl, MapLibre GL
- **Database**: Supabase (operators, equipment), TimescaleDB (telemetry hypertable)

## Server Stack Ports

| Service     | Port  | Description          |
|-------------|-------|----------------------|
| EMQX        | 1883  | MQTT TCP             |
| EMQX        | 18083 | Dashboard Web        |
| TimescaleDB | 5432  | PostgreSQL           |
| Ingest      | 8080  | Health API           |
| Grafana     | 3000  | Dashboards           |

## Environment Configuration

- **AuraTrackingDash**: Copy `.env.example` to `.env.local` and set Supabase credentials
- **AuraTrackingServer**: Credentials in `.env` file (default: admin/aura2025)
- **AuraTracking**: Supabase credentials in `gradle.properties`

## Database Schema

### TimescaleDB (Telemetry)
- `telemetry` (hypertable): device_id, operator_id, latitude, longitude, altitude, speed, bearing, gps_accuracy, accel_x/y/z, gyro_x/y/z, time
- Compression policy: data > 3 days compressed (~90% savings)
- Retention policy: data > 180 days removed

### Supabase (Configuration Data)
| Table | Description | Key Columns |
|-------|-------------|-------------|
| `operators` | Operator registry | id, name, registration, pin, status |
| `equipment` | Equipment registry | id, tag, type_id, status, fleet |
| `geofence` | Geographic zones | id, name, zone_type, polygon_json, color, is_active |

**Geofence zone_type values:** `loading`, `unloading`, `parking`, `maintenance`, `fuel`, `restricted`, `custom`

**Geofence polygon_json format:** `[[lat, lng], [lat, lng], ...]` (closed polygon)

## Android App Architecture (AuraTracking)

### Room Database (v6)
| Table | Purpose |
|-------|---------|
| `config` | Device configuration (equipment_name, tracking_enabled) |
| `operators` | Cached operators from Supabase |
| `telemetry_queue` | Offline telemetry queue (up to 30 days, ~3M records) |
| `zones` | Cached geofences from Supabase |
| `geofence_events` | Entry/exit events pending upload |
| `sync_state` | Sync status per data type |

### SyncOrchestrator (sync/)
Unified sync system with guardrails for intermittent connectivity (truck in rural areas).

**Architecture:**
```
UnifiedSyncWorker (every 15 min)
    │
    ▼
SyncOrchestrator
    │
    ├── FASE 1: DOWNLOAD (Supabase → App)
    │   ├── Fetch operators, geofences
    │   ├── Validate (SyncValidator guardrails)
    │   └── Atomic commit (Room withTransaction)
    │
    └── FASE 2: UPLOAD (App → MQTT)
        ├── Flush telemetry queue (batches of 50)
        └── Flush geofence events (batches of 50)
```

**Guardrails (SyncValidator):**
- Operators: minimum 1 active, valid IDs, non-blank names
- Geofences: polygon >= 3 points, valid JSON structure
- Retry: 3 attempts with exponential backoff
- Timeout: 30s per fetch operation
- Mutex: prevents concurrent sync executions

**Key files:**
- `sync/SyncOrchestrator.kt` - Main orchestrator logic
- `sync/SyncValidator.kt` - Data validation guardrails
- `sync/UnifiedSyncWorker.kt` - WorkManager wrapper
- `sync/SyncStateEntity.kt` - Persistent sync state

### Logging (AuraLog)
Persistent file logging with components: GPS, IMU, MQTT, Service, Queue, Watchdog, Analytics, Geofence, Sync

Logs saved to: `/storage/emulated/0/Android/data/com.aura.tracking/files/logs/`

### Geofencing
- `GeofenceManager`: Point-in-polygon detection for loading/unloading zones
- `ZoneSyncWorker`: (deprecated) Replaced by UnifiedSyncWorker
- `GeofenceEventFlushWorker`: (deprecated) Replaced by UnifiedSyncWorker

## Supabase Project
- **Project ID:** `nucqowewuqeveocmsdnq`
- **Region:** us-east-1
- **API:** REST via Ktor HTTP Client in Android app
