# AuraTracking

Sistema de telemetria Android nativo para rastreamento contínuo de frotas com GPS + IMU.

## 📋 Visão Geral

AuraTracking é um aplicativo Android desenvolvido em Kotlin que coleta dados de telemetria (localização GPS e sensores IMU) e os envia para um broker MQTT. O sistema é integrado ao Supabase para autenticação e gerenciamento de frotas/equipamentos.

## 🏗️ Estrutura do Projeto

```
AuraTracking/
├── app/                          # Aplicativo Android
│   ├── src/main/
│   │   ├── java/com/aura/tracking/
│   │   │   ├── ui/               # Activities (Login, Pin, Dashboard, Admin)
│   │   │   ├── data/             # Room database + Supabase API
│   │   │   ├── sensors/          # GPS e IMU providers
│   │   │   ├── background/       # Foreground Service + Boot Receiver
│   │   │   ├── mqtt/             # MQTT client manager
│   │   │   └── util/             # Helpers (permissions, battery, service)
│   │   └── res/                  # Layouts, strings, colors, themes
│   └── build.gradle.kts          # Gradle do módulo app
├── docker/                       # Infraestrutura
│   └── mqtt/                     # Mosquitto MQTT Broker
│       ├── docker-compose.yml
│       ├── Dockerfile
│       └── mosquitto.conf
├── gradle/
│   └── libs.versions.toml        # Catálogo de versões
├── build.gradle.kts              # Gradle raiz
├── settings.gradle.kts
└── gradle.properties             # Credenciais Supabase
```

## 🚀 Como Começar

### Pré-requisitos

- Android Studio Hedgehog (2023.1.1) ou superior
- JDK 17
- Android SDK 34
- Docker e Docker Compose (para o broker MQTT)

### 1. Clone e Configure

```bash
# Clone o repositório
git clone <repository-url>
cd AuraTracking

# Verifique as credenciais Supabase em gradle.properties
# (já configuradas por padrão)
```

### 2. Inicie o Broker MQTT

```bash
cd docker/mqtt
docker-compose up -d
```

### 3. Compile o App

```bash
# Via terminal
./gradlew assembleDebug

# Ou abra no Android Studio e faça Build > Make Project
```

### 4. Instale no Dispositivo

```bash
./gradlew installDebug
```

## 📱 Fluxo do Aplicativo

1. **LoginActivity** - Operador informa sua matrícula
2. **PinActivity** - Operador informa PIN de 4 dígitos
3. **AdminConfigActivity** - Configuração inicial (MQTT + Frota + Equipamento)
4. **DashboardActivity** - Tela principal com controles de tracking

## 🔧 Tecnologias

| Componente | Tecnologia |
|------------|------------|
| Linguagem | Kotlin 1.9.22 |
| Build | Gradle 8.4 (Kotlin DSL) |
| UI | ViewBinding + Material 3 |
| Database Local | Room 2.6.1 |
| HTTP Client | Ktor 2.3.7 |
| Localização | Play Services Location 21.1.0 |
| Background | Foreground Service + WorkManager |
| MQTT | Eclipse Mosquitto 2 |
| Backend | Supabase (PostgREST) |

## 🔐 Permissões

O app requer as seguintes permissões:

- `ACCESS_FINE_LOCATION` - Localização precisa
- `ACCESS_COARSE_LOCATION` - Localização aproximada
- `ACCESS_BACKGROUND_LOCATION` - Localização em segundo plano
- `FOREGROUND_SERVICE` - Serviço em primeiro plano
- `FOREGROUND_SERVICE_LOCATION` - Serviço de localização
- `POST_NOTIFICATIONS` - Notificações (Android 13+)
- `RECEIVE_BOOT_COMPLETED` - Reiniciar após boot

## 📊 Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                         UI Layer                             │
│  LoginActivity │ PinActivity │ DashboardActivity │ AdminConfig│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Data Layer                             │
│    SupabaseApi (Remote)    │    Room Database (Local)        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Background Layer                          │
│  TrackingForegroundService │ BootCompletedReceiver           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Sensors Layer                            │
│     GpsLocationProvider    │    ImuSensorProvider            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      MQTT Layer                              │
│                  MqttClientManager                           │
│                         │                                    │
│                         ▼                                    │
│              Mosquitto Broker (Docker)                       │
└─────────────────────────────────────────────────────────────┘
```

## 📝 Fase 2 (TODO)

A lógica completa de telemetria será implementada na Fase 2:

- [ ] Loop de coleta de GPS contínuo
- [ ] Processamento de dados IMU
- [ ] Implementação completa do cliente MQTT (Paho)
- [ ] Fila offline com WorkManager
- [ ] Retry automático de mensagens
- [ ] Compressão de dados
- [ ] Batching de telemetria
- [ ] Monitoramento de bateria

## 🐳 Docker MQTT

O broker Mosquitto está configurado com:

- **Porta 1883** - MQTT padrão
- **Porta 9001** - MQTT sobre WebSocket
- **Persistência** - Ativada
- **Anonymous** - Permitido (desenvolvimento)
- **Tópico base** - `aura/tracking/#`

### Comandos úteis

```bash
# Ver logs
docker-compose logs -f

# Parar
docker-compose down

# Testar conexão
mosquitto_sub -h localhost -p 1883 -t "aura/tracking/#" -v
```

## 📄 Licença

Proprietary - AuraTracking Team
