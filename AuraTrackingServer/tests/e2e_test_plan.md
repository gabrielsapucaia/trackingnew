# 🔥 PLANO DE TESTE END-TO-END - AuraTracking Server Stack

## Arquitetura Testada

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Moto G34   │ ──▶  │   EMQX      │ ──▶  │   Ingest    │ ──▶  │ TimescaleDB │ ──▶  │  Grafana    │
│  (Android)  │      │   Broker    │      │   Worker    │      │             │      │             │
│  App        │ MQTT │   :1883     │ Sub  │   Python    │ SQL  │   :5432     │ Viz  │   :3000     │
└─────────────┘      └─────────────┘      └─────────────┘      └─────────────┘      └─────────────┘
```

## Configuração do Ambiente

| Componente | Host | Porta | Credenciais |
|------------|------|-------|-------------|
| MQTT (EMQX) | localhost / 192.168.0.50 | 1883 | - |
| EMQX Dashboard | localhost / 192.168.0.50 | 18083 | admin / AuraTrack@2024! |
| TimescaleDB | localhost / 192.168.0.50 | 5432 | aura / AuraTrack@DB2024! |
| Ingest Health | localhost / 192.168.0.50 | 8080 | - |
| Grafana | localhost / 192.168.0.50 | 3000 | admin / AuraTrack@2024! |

---

# 📋 20 TESTES AUTOMATIZADOS

## 1️⃣ TESTES DE MQTT (EMQX) - Testes 1-5

### Teste 1: Conexão TCP ao Broker MQTT
```bash
# Testar porta MQTT
nc -zv localhost 1883

# Ou com timeout
timeout 5 bash -c 'cat < /dev/null > /dev/tcp/localhost/1883' && echo "✅ MQTT OK" || echo "❌ MQTT FAIL"
```

### Teste 2: Publish Manual em Tópico de Teste
```bash
mosquitto_pub -h localhost -p 1883 -t "aura/test/ping" -m '{"test": true, "timestamp": '$(date +%s)'}'
```

### Teste 3: Subscribe no Wildcard
```bash
# Em um terminal, subscribe
mosquitto_sub -h localhost -p 1883 -t "aura/tracking/#" -v &

# Em outro, publish
mosquitto_pub -h localhost -p 1883 -t "aura/tracking/test/telemetry" -m '{"deviceId":"test"}'

# Deve aparecer a mensagem no subscriber
```

### Teste 4: Testar QoS1 com Confirmação
```bash
# QoS 1 - At least once delivery
mosquitto_pub -h localhost -p 1883 -t "aura/tracking/qos_test/telemetry" -q 1 -m '{"qos":1}' -d
# Deve mostrar PUBACK no debug
```

### Teste 5: Verificar Clientes Conectados no EMQX
```bash
docker exec aura_emqx emqx_ctl clients list
```

---

## 2️⃣ TESTES CELULAR → MQTT - Testes 6-9

### Teste 6: Simular Envio Idêntico ao App Android
```bash
# Payload exatamente como o app envia
mosquitto_pub -h localhost -p 1883 -t "aura/tracking/ZF524XRLK3/telemetry" -q 1 -m '{
  "deviceId": "ZF524XRLK3",
  "operatorId": "OP_TESTE",
  "timestamp": '$(date +%s%3N)',
  "gps": {
    "latitude": -11.563234,
    "longitude": -47.170456,
    "altitude": 285.5,
    "speed": 12.5,
    "bearing": 180.0,
    "accuracy": 4.5
  },
  "imu": {
    "accelX": 0.15,
    "accelY": -0.23,
    "accelZ": 9.78,
    "gyroX": 0.012,
    "gyroY": -0.008,
    "gyroZ": 0.003
  }
}'
```

### Teste 7: Envio em Lote (Simular 1Hz por 10 segundos)
```bash
for i in {1..10}; do
  ts=$(date +%s%3N)
  lat=$(echo "-11.563 + 0.0001 * $i" | bc)
  mosquitto_pub -h localhost -p 1883 -t "aura/tracking/ZF524XRLK3/telemetry" -q 1 -m \
    "{\"deviceId\":\"ZF524XRLK3\",\"operatorId\":\"OP_TESTE\",\"timestamp\":$ts,\"gps\":{\"latitude\":$lat,\"longitude\":-47.170,\"altitude\":285.5,\"speed\":15.$i,\"bearing\":180.0,\"accuracy\":5.0},\"imu\":{\"accelX\":0.1,\"accelY\":0.2,\"accelZ\":9.8,\"gyroX\":0.01,\"gyroY\":0.02,\"gyroZ\":0.01}}"
  sleep 1
done
```

### Teste 8: Validar Logs do App via ADB/Logcat
```bash
# Filtrar logs do AuraTracking
adb logcat -s AuraTracking:D MqttManager:D TelemetryService:D | grep -E "(MQTT|publish|connect)"
```

### Teste 9: Verificar MQTT Client do App Conectado
```bash
# Listar clientes no EMQX e procurar o device ID do Moto G34
docker exec aura_emqx emqx_ctl clients list | grep -i "moto\|ZF524"
```

---

## 3️⃣ TESTES DO INGEST WORKER - Testes 10-14

### Teste 10: Health Check do Ingest
```bash
curl -s http://localhost:8080/health | jq .

# Deve retornar algo como:
# {"status": "healthy", "mqtt_connected": true, "db_connected": true}
```

### Teste 11: Verificar Conexão do Ingest ao MQTT
```bash
docker exec aura_emqx emqx_ctl clients list | grep ingest
# Deve mostrar: aura_ingest_worker
```

### Teste 12: Ver Logs do Ingest em Tempo Real
```bash
docker logs -f aura_ingest --tail 50
```

### Teste 13: Injetar Mensagem e Verificar Inserção
```bash
# 1. Capturar count atual
COUNT_BEFORE=$(docker exec aura_timescaledb psql -U aura -d auratracking -t -c "SELECT COUNT(*) FROM telemetry;")

# 2. Enviar mensagem
mosquitto_pub -h localhost -p 1883 -t "aura/tracking/ingest_test/telemetry" -m \
  '{"deviceId":"ingest_test","operatorId":"TEST","timestamp":'$(date +%s%3N)',"gps":{"latitude":-11.5,"longitude":-47.1,"altitude":280,"speed":10,"bearing":90,"accuracy":5},"imu":{"accelX":0.1,"accelY":0.2,"accelZ":9.8,"gyroX":0.01,"gyroY":0.02,"gyroZ":0.01}}'

# 3. Aguardar flush (max 5s)
sleep 6

# 4. Verificar novo count
COUNT_AFTER=$(docker exec aura_timescaledb psql -U aura -d auratracking -t -c "SELECT COUNT(*) FROM telemetry;")

echo "Before: $COUNT_BEFORE | After: $COUNT_AFTER"
```

### Teste 14: Testar Fila Offline (Derrubar DB Temporariamente)
```bash
# Este é um teste destrutivo - usar com cuidado!
# 1. Parar TimescaleDB
# docker stop aura_timescaledb

# 2. Enviar mensagem (deve ir para fila offline)
# mosquitto_pub -h localhost -p 1883 -t "aura/tracking/offline_test/telemetry" -m '...'

# 3. Ver logs do ingest - deve mostrar "queued_offline"
# docker logs aura_ingest | grep offline

# 4. Reiniciar TimescaleDB
# docker start aura_timescaledb

# 5. Ver logs - deve mostrar processamento da fila offline
# docker logs aura_ingest | grep "processing_offline_queue"
```

---

## 4️⃣ TESTES DO TIMESCALEDB - Testes 15-18

### Teste 15: Validar Últimas Inserções
```sql
-- Executar via:
-- docker exec aura_timescaledb psql -U aura -d auratracking -c "..."

SELECT 
    time,
    device_id,
    operator_id,
    latitude,
    longitude,
    round(speed_kmh::numeric, 2) as speed_kmh,
    round(accel_magnitude::numeric, 2) as accel_g
FROM telemetry 
ORDER BY time DESC 
LIMIT 20;
```

### Teste 16: Contagem e Estatísticas
```sql
-- Contagem total
SELECT COUNT(*) as total_records FROM telemetry;

-- Por dispositivo
SELECT 
    device_id,
    COUNT(*) as records,
    MIN(time) as first_record,
    MAX(time) as last_record,
    round(AVG(speed_kmh)::numeric, 2) as avg_speed
FROM telemetry
GROUP BY device_id
ORDER BY records DESC;

-- Últimas 24h
SELECT 
    date_trunc('hour', time) as hour,
    COUNT(*) as records
FROM telemetry
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;
```

### Teste 17: Validação de Qualidade dos Dados
```sql
-- Verificar dados inválidos
SELECT 
    'Latitude inválida' as issue, COUNT(*) 
FROM telemetry 
WHERE latitude IS NULL OR latitude < -90 OR latitude > 90

UNION ALL

SELECT 
    'Longitude inválida', COUNT(*) 
FROM telemetry 
WHERE longitude IS NULL OR longitude < -180 OR longitude > 180

UNION ALL

SELECT 
    'Velocidade negativa', COUNT(*) 
FROM telemetry 
WHERE speed < 0

UNION ALL

SELECT 
    'Aceleração impossível (>50 m/s²)', COUNT(*) 
FROM telemetry 
WHERE accel_magnitude > 50

UNION ALL

SELECT 
    'Timestamp futuro', COUNT(*) 
FROM telemetry 
WHERE time > NOW() + INTERVAL '1 minute';
```

### Teste 18: Integridade da Hypertable
```sql
-- Verificar hypertables
SELECT 
    hypertable_name,
    num_chunks,
    compression_enabled,
    total_bytes::bigint / 1024 / 1024 as size_mb
FROM timescaledb_information.hypertables
WHERE hypertable_name = 'telemetry';

-- Verificar chunks
SELECT 
    chunk_name,
    range_start,
    range_end,
    is_compressed
FROM timescaledb_information.chunks
WHERE hypertable_name = 'telemetry'
ORDER BY range_start DESC
LIMIT 10;

-- Verificar políticas
SELECT 
    application_name,
    schedule_interval,
    config
FROM timescaledb_information.jobs
WHERE application_name LIKE '%telemetry%';
```

---

## 5️⃣ TESTES DO GRAFANA - Testes 19-20

### Teste 19: Validar Datasource PostgreSQL
```bash
# Via API do Grafana
curl -s -u admin:AuraTrack@2024! \
  http://localhost:3000/api/datasources | jq '.[] | {name, type, url, isDefault}'
```

### Teste 20: Testar Query no Datasource
```bash
# Teste de query via API
curl -s -u admin:AuraTrack@2024! \
  -X POST http://localhost:3000/api/ds/query \
  -H "Content-Type: application/json" \
  -d '{
    "queries": [{
      "datasourceId": 1,
      "rawSql": "SELECT time, speed_kmh FROM telemetry ORDER BY time DESC LIMIT 5",
      "format": "table"
    }]
  }' | jq .
```

---

# ✅ CHECKLIST COMPLETO END-TO-END

## Fase 1: Infraestrutura
- [ ] Todos os containers rodando (`docker ps`)
- [ ] EMQX respondendo na porta 1883
- [ ] TimescaleDB respondendo na porta 5432
- [ ] Ingest health OK na porta 8080
- [ ] Grafana acessível na porta 3000

## Fase 2: MQTT Broker
- [ ] Consegue publicar mensagem de teste
- [ ] Consegue subscribar em aura/tracking/#
- [ ] Cliente ingest_worker conectado
- [ ] QoS 1 funcionando (PUBACK)

## Fase 3: Celular Android
- [ ] App AuraTracking instalado
- [ ] Login realizado (TEST mode ou Supabase)
- [ ] Foreground Service ativo (ícone na barra)
- [ ] GPS funcionando (check em Settings > Location)
- [ ] Logs mostrando MQTT publish (adb logcat)

## Fase 4: Ingest Worker
- [ ] Conectado ao MQTT (logs mostram mqtt_connected)
- [ ] Conectado ao DB (logs mostram database_connected)
- [ ] Recebendo mensagens (batch_inserted nos logs)
- [ ] Sem erros de validação (invalid_telemetry)

## Fase 5: TimescaleDB
- [ ] Tabela telemetry existe
- [ ] Hypertable configurada
- [ ] Dados sendo inseridos (COUNT(*) crescendo)
- [ ] Timestamps corretos (não no futuro)
- [ ] Coordenadas válidas

## Fase 6: Grafana
- [ ] Datasource TimescaleDB configurado
- [ ] Dashboard AuraTracking Overview carregado
- [ ] Painéis mostrando dados
- [ ] Atualização em tempo real (auto-refresh)

---

# 🔧 DIAGNÓSTICO DE FALHAS

## Se MQTT não conecta:
```bash
# Verificar se EMQX está rodando
docker logs aura_emqx | tail -50

# Verificar porta
netstat -tlnp | grep 1883

# Testar conexão
mosquitto_pub -h localhost -p 1883 -t test -m test -d
```

## Se Ingest não processa:
```bash
# Ver logs em tempo real
docker logs -f aura_ingest

# Verificar subscriptions
docker exec aura_emqx emqx_ctl subscriptions list

# Reiniciar ingest
docker restart aura_ingest
```

## Se TimescaleDB não recebe:
```bash
# Verificar conexão
docker exec aura_timescaledb pg_isready -U aura -d auratracking

# Ver logs
docker logs aura_timescaledb | tail -50

# Testar insert manual
docker exec aura_timescaledb psql -U aura -d auratracking -c \
  "INSERT INTO telemetry (time, device_id, latitude, longitude, speed) VALUES (NOW(), 'manual_test', -11.5, -47.1, 10);"
```

## Se Grafana não mostra dados:
```bash
# Verificar datasource
curl -s -u admin:AuraTrack@2024! http://localhost:3000/api/datasources

# Testar query direto no banco
docker exec aura_timescaledb psql -U aura -d auratracking -c \
  "SELECT * FROM telemetry ORDER BY time DESC LIMIT 1;"

# Ver logs do Grafana
docker logs aura_grafana | grep -i error
```

## Se App não envia:
```bash
# Verificar logs do app
adb logcat -s AuraTracking MqttManager TelemetryService

# Verificar IP do servidor configurado no app
adb shell "run-as com.aura.tracking cat shared_prefs/aura_prefs.xml"

# Verificar conectividade do celular
adb shell ping -c 3 192.168.0.50
```

---

# 📊 QUERIES ÚTEIS PARA DIAGNÓSTICO

## Ver fluxo de dados por minuto
```sql
SELECT 
    date_trunc('minute', time) as minute,
    device_id,
    COUNT(*) as records
FROM telemetry
WHERE time > NOW() - INTERVAL '30 minutes'
GROUP BY minute, device_id
ORDER BY minute DESC, device_id;
```

## Detectar gaps de dados
```sql
WITH data AS (
    SELECT 
        time,
        device_id,
        LAG(time) OVER (PARTITION BY device_id ORDER BY time) as prev_time
    FROM telemetry
    WHERE time > NOW() - INTERVAL '1 hour'
)
SELECT 
    device_id,
    prev_time as gap_start,
    time as gap_end,
    EXTRACT(EPOCH FROM (time - prev_time)) as gap_seconds
FROM data
WHERE time - prev_time > INTERVAL '5 seconds'
ORDER BY gap_seconds DESC
LIMIT 20;
```

## Verificar latência de ingestão
```sql
SELECT 
    device_id,
    COUNT(*) as records,
    AVG(EXTRACT(EPOCH FROM (received_at - time))) as avg_latency_seconds,
    MAX(EXTRACT(EPOCH FROM (received_at - time))) as max_latency_seconds
FROM telemetry
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY device_id;
```

## Health check geral
```sql
SELECT 
    (SELECT COUNT(*) FROM telemetry WHERE time > NOW() - INTERVAL '5 minutes') as last_5min,
    (SELECT COUNT(*) FROM telemetry WHERE time > NOW() - INTERVAL '1 hour') as last_hour,
    (SELECT COUNT(DISTINCT device_id) FROM telemetry WHERE time > NOW() - INTERVAL '5 minutes') as active_devices,
    (SELECT MAX(time) FROM telemetry) as last_record;
```
