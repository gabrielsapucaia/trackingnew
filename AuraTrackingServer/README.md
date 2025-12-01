# ============================================================
# AuraTracking Server Stack
# ============================================================
# Infraestrutura completa para ingestão de telemetria GPS/IMU
# ============================================================

## 📋 Visão Geral

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INTRANET DA MINA                             │
│                                                                     │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐   │
│  │   Moto G34  │     │   Moto G34  │     │   Moto G34          │   │
│  │ AuraTracking│     │ AuraTracking│     │ AuraTracking        │   │
│  │   GPS/IMU   │     │   GPS/IMU   │     │   GPS/IMU           │   │
│  └──────┬──────┘     └──────┬──────┘     └──────────┬──────────┘   │
│         │                   │                        │              │
│         └───────────────────┴────────────────────────┘              │
│                             │ MQTT (QoS1)                           │
│                             ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    SERVIDOR (Docker)                          │   │
│  │  ┌────────────────────────────────────────────────────────┐   │   │
│  │  │  EMQX 5.x        │  Ingest Worker  │   TimescaleDB    │   │   │
│  │  │  Broker MQTT     │  Python 3.12    │   PostgreSQL 15  │   │   │
│  │  │  :1883 :18083    │  :8080          │   :5432          │   │   │
│  │  │  10.10.10.10     │  10.10.10.30    │   10.10.10.20    │   │   │
│  │  └────────────────────────────────────────────────────────┘   │   │
│  │                             │                                 │   │
│  │                             ▼                                 │   │
│  │  ┌────────────────────────────────────────────────────────┐   │   │
│  │  │              Grafana 11.x                              │   │   │
│  │  │              Dashboards                                │   │   │
│  │  │              :3000  (10.10.10.40)                      │   │   │
│  │  └────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

```bash
# Clone ou copie os arquivos para o servidor
cd AuraTrackingServer

# Dar permissão aos scripts
chmod +x deploy.sh test.sh

# Deploy completo
./deploy.sh

# Ou manualmente:
docker compose up -d
```

## 📡 Serviços e Portas

| Serviço      | IP (interno)  | Porta(s)     | Descrição                    |
|--------------|---------------|--------------|------------------------------|
| EMQX         | 10.10.10.10   | 1883, 18083  | Broker MQTT + Dashboard      |
| TimescaleDB  | 10.10.10.20   | 5432         | Banco de séries temporais    |
| Ingest       | 10.10.10.30   | 8080         | Worker de ingestão           |
| Grafana      | 10.10.10.40   | 3000         | Dashboards                   |
| Autoheal     | 10.10.10.50   | -            | Watchdog de containers       |

## 🔐 Credenciais Padrão

| Serviço      | Usuário       | Senha        |
|--------------|---------------|--------------|
| EMQX         | admin         | aura2025     |
| TimescaleDB  | aura          | aura2025     |
| Grafana      | admin         | aura2025     |

## 📱 Configuração do App Android

No app **AuraTracking**, configure:

```
MQTT Host:  [IP do servidor na intranet]
MQTT Port:  1883
TLS:        Desabilitado
Topic Base: aura/tracking
```

## 🧪 Testes

### Testar MQTT com mosquitto

```bash
# Instalar mosquitto-clients
# macOS: brew install mosquitto
# Ubuntu: apt install mosquitto-clients

# Subscriber (terminal 1)
mosquitto_sub -h localhost -p 1883 -t "aura/tracking/#" -v

# Publisher (terminal 2)
mosquitto_pub -h localhost -p 1883 -t "aura/tracking/test/telemetry" \
  -m '{"deviceId":"test","timestamp":1732876800000,"gps":{"lat":-11.56,"lon":-47.17}}'
```

### Script de teste

```bash
./test.sh
```

## 📊 Grafana

Acesse: http://[IP_SERVIDOR]:3000

- **Login:** admin / aura2025
- **Dashboard:** AuraTracking - Visão Geral

Recursos:
- Dispositivos ativos
- Velocidade por dispositivo
- Aceleração (detecção de impactos)
- Mapa de veículos
- Status em tempo real

## 🗄️ Schema do Banco

### Tabela `telemetry` (Hypertable)

| Coluna           | Tipo             | Descrição                    |
|------------------|------------------|------------------------------|
| time             | TIMESTAMPTZ      | Timestamp do evento          |
| device_id        | VARCHAR(100)     | ID do dispositivo            |
| operator_id      | VARCHAR(100)     | ID do operador               |
| latitude         | DOUBLE PRECISION | Latitude GPS                 |
| longitude        | DOUBLE PRECISION | Longitude GPS                |
| altitude         | DOUBLE PRECISION | Altitude GPS                 |
| speed            | DOUBLE PRECISION | Velocidade (m/s)             |
| speed_kmh        | DOUBLE PRECISION | Velocidade (km/h) [calculado]|
| bearing          | DOUBLE PRECISION | Direção (graus)              |
| gps_accuracy     | DOUBLE PRECISION | Precisão GPS (metros)        |
| accel_x/y/z      | DOUBLE PRECISION | Aceleração (m/s²)            |
| accel_magnitude  | DOUBLE PRECISION | Magnitude [calculado]        |
| gyro_x/y/z       | DOUBLE PRECISION | Giroscópio (rad/s)           |

### Políticas

- **Compressão:** Dados > 3 dias são comprimidos (~90% economia)
- **Retenção:** Dados > 180 dias são removidos automaticamente
- **Agregações:** Views materializadas para 1min e 1hour

## 📈 Monitoramento

### Health Check do Ingest

```bash
curl http://localhost:8080/health
curl http://localhost:8080/stats
```

### Logs

```bash
# Todos os serviços
docker compose logs -f

# Serviço específico
docker compose logs -f ingest
docker compose logs -f emqx
```

### Estatísticas do Banco

```bash
docker compose exec timescaledb psql -U aura -d auratracking -c "
  SELECT 
    hypertable_name,
    total_chunks,
    pg_size_pretty(total_bytes) as total_size,
    pg_size_pretty(compressed_total_size) as compressed_size
  FROM timescaledb_information.hypertables;
"
```

## 🔧 Manutenção

### Backup do banco

```bash
docker compose exec timescaledb pg_dump -U aura auratracking > backup_$(date +%Y%m%d).sql
```

### Reiniciar serviços

```bash
docker compose restart
```

### Atualizar imagens

```bash
docker compose pull
docker compose up -d
```

### Limpar dados antigos manualmente

```bash
docker compose exec timescaledb psql -U aura -d auratracking -c "
  SELECT drop_chunks('telemetry', older_than => INTERVAL '30 days');
"
```

## 🐛 Troubleshooting

### EMQX não inicia

```bash
docker compose logs emqx
# Verificar se porta 1883 não está em uso
lsof -i :1883
```

### Ingest não conecta ao MQTT

```bash
docker compose logs ingest
# Verificar se EMQX está healthy
docker compose ps
```

### Grafana sem dados

1. Verificar se Ingest está inserindo dados:
   ```bash
   curl http://localhost:8080/stats
   ```
2. Verificar conexão do datasource no Grafana
3. Verificar se há dados no banco:
   ```bash
   docker compose exec timescaledb psql -U aura -d auratracking -c "SELECT COUNT(*) FROM telemetry;"
   ```

## 📁 Estrutura de Arquivos

```
AuraTrackingServer/
├── docker-compose.yml          # Orquestração de containers
├── deploy.sh                   # Script de deploy
├── test.sh                     # Script de testes
├── README.md                   # Esta documentação
├── emqx/
│   └── config/
│       └── acl.conf           # Configuração ACL do MQTT
├── timescale/
│   └── init/
│       └── 01_schema.sql      # Schema do banco
├── ingest/
│   ├── Dockerfile             # Imagem do ingest worker
│   ├── requirements.txt       # Dependências Python
│   └── src/
│       └── main.py           # Código do ingest worker
└── grafana/
    ├── provisioning/
    │   ├── datasources/
    │   │   └── datasources.yml
    │   └── dashboards/
    │       └── dashboards.yml
    └── dashboards/
        └── overview.json      # Dashboard principal
```

## ✅ Checklist de Produção

- [ ] Alterar senhas padrão
- [ ] Configurar TLS/SSL no MQTT
- [ ] Configurar backup automático do TimescaleDB
- [ ] Configurar alertas no Grafana
- [ ] Configurar firewall (apenas portas necessárias)
- [ ] Monitorar espaço em disco
- [ ] Testar recuperação de desastres
