# 🔍 Guia de Diagnóstico - AuraTracking Flow

Este guia ajuda a verificar se o fluxo de dados está funcionando corretamente:
**Celular → Mosquitto → TimescaleDB**

## 📋 Pré-requisitos

1. **Docker Services Rodando:**
   ```bash
   cd AuraTrackingServer
   docker compose ps
   ```
   Deve mostrar: `aura_emqx`, `aura_timescaledb`, `aura_ingest`, `aura_grafana`

2. **Ferramentas Necessárias:**
   ```bash
   # macOS
   brew install mosquitto

   # Ubuntu/Debian
   sudo apt install mosquitto-clients postgresql-client
   ```

## 🧪 Método 1: Script de Diagnóstico Completo (Recomendado)

Execute o script de diagnóstico abrangente:

```bash
cd /Users/sapucaia/tracking
python3 diagnostic_script.py
```

Este script testa:
- ✅ Status dos containers Docker
- ✅ Conectividade MQTT
- ✅ Publicação/Assinatura MQTT
- ✅ Conectividade TimescaleDB
- ✅ Health do Ingest Worker
- ✅ Dados recentes no banco
- ✅ Fluxo end-to-end completo

## 📊 Método 2: Monitoramento em Tempo Real

Para verificar o fluxo enquanto o app Android está rodando:

```bash
cd /Users/sapucaia/tracking
python3 monitor_flow.py --duration 300 --interval 10
```

Parâmetros:
- `--duration`: Tempo de monitoramento em segundos (padrão: 60)
- `--interval`: Intervalo entre verificações (padrão: 5)

## 🔧 Método 3: Testes Manuais Passo-a-Passo

### 1. Verificar Serviços Docker

```bash
cd AuraTrackingServer
docker compose ps
```

### 2. Testar MQTT Broker

```bash
# Publicar mensagem de teste
cd AuraTrackingServer
./test.sh
# Escolher opção 1 (uma telemetria de teste)
```

### 3. Verificar se Ingest Worker Recebeu

```bash
# Health check do ingest
curl -s http://10.10.10.30:8080/health | python3 -m json.tool

# Ver estatísticas
curl -s http://10.10.10.30:8080/stats | python3 -m json.tool
```

### 4. Verificar Dados no Banco

```bash
# Conectar ao TimescaleDB
docker compose exec timescaledb psql -U aura -d auratracking

# Verificar dados recentes
SELECT time, device_id, latitude, longitude, speed_kmh
FROM telemetry
ORDER BY time DESC
LIMIT 10;
```

## 📱 Verificando o Lado do Celular

### 1. Verificar Logs do App Android

```bash
# Logs ficam em:
tail -f AuraTracking/mqtt_monitoring.log
tail -f AuraTracking/mqtt_final_test.log
```

### 2. Verificar Configuração MQTT no App

No app Android, verificar se a configuração aponta para:
- **Host:** 192.168.0.113 (ou IP correto da rede)
- **Port:** 1883
- **Topic:** aura/tracking/[SERIAL_NUMBER]/telemetry

### 3. Testar com App em Modo Debug

1. Abrir app no Android Studio
2. Usar matrícula "TEST" para modo teste
3. Verificar logs no Logcat por mensagens MQTT

## 🚨 Problemas Comuns e Soluções

### ❌ Problema: Nenhuma mensagem MQTT recebida

**Possíveis causas:**
- App Android não está enviando dados
- IP do broker incorreto no app
- Firewall bloqueando porta 1883
- Broker MQTT não está rodando

**Soluções:**
```bash
# Verificar se broker está ouvindo
telnet 10.10.10.10 1883

# Verificar logs do EMQX
docker compose logs emqx | tail -20
```

### ❌ Problema: Mensagens MQTT chegam mas não no banco

**Possíveis causas:**
- Ingest Worker não está rodando
- Conexão do Ingest com banco falhou
- Fila offline cheia

**Soluções:**
```bash
# Verificar health do ingest
curl http://10.10.10.30:8080/health

# Verificar logs do ingest
docker compose logs ingest | tail -30

# Verificar conectividade do banco
docker compose exec ingest nc -zv 10.10.10.20 5432
```

### ❌ Problema: Dados chegam no banco mas com delay

**Possíveis causas:**
- Fila offline sendo processada lentamente
- Batch size muito grande
- Problemas de performance

**Soluções:**
```bash
# Verificar tamanho da fila offline
curl http://10.10.10.30:8080/health | grep offline_queue_size

# Verificar métricas de performance
curl http://10.10.10.30:8080/stats
```

## 📈 Métricas de Monitoramento

### Ingest Worker Metrics
- `messages_received`: Total de mensagens MQTT recebidas
- `messages_inserted`: Total inserido no banco
- `offline_queue_size`: Tamanho da fila offline
- `mqtt_connected`: Status da conexão MQTT
- `db_connected`: Status da conexão com banco

### Database Metrics
```sql
-- Dados por hora
SELECT
    date_trunc('hour', time) as hour,
    device_id,
    COUNT(*) as points,
    AVG(speed_kmh) as avg_speed,
    MAX(speed_kmh) as max_speed
FROM telemetry
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY hour, device_id
ORDER BY hour DESC;

-- Status dos dispositivos
SELECT * FROM device_status;
```

## 🎯 Verificação Final

Para confirmar que tudo está funcionando:

1. **App Android ativo** → Deve publicar dados a cada 1 segundo
2. **Mosquitto recebe** → Logs mostram mensagens chegando
3. **Ingest processa** → Health check mostra `messages_received` > 0
4. **Banco armazena** → Query mostra novos registros aparecendo

**Comando de verificação rápida:**
```bash
cd AuraTrackingServer

# 1. Status dos serviços
docker compose ps

# 2. Verificar dados recentes
docker compose exec timescaledb psql -U aura -d auratracking -c "
SELECT COUNT(*) as total_telemetries,
       COUNT(DISTINCT device_id) as active_devices,
       MAX(time) as last_data_time
FROM telemetry
WHERE time > NOW() - INTERVAL '1 minute';"

# 3. Health do ingest
curl -s http://10.10.10.30:8080/health | python3 -m json.tool
```

## 📞 Suporte

Se os problemas persistirem:

1. Execute o `diagnostic_script.py` completo
2. Colete os logs de todos os serviços:
   ```bash
   docker compose logs > diagnostic_logs.txt
   ```
3. Verifique conectividade de rede entre dispositivos
4. Confirme que o app Android tem as permissões de localização
