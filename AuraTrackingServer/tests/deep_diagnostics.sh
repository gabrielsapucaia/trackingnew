#!/bin/bash
# ============================================================
# AuraTracking Deep Diagnostics
# ============================================================
# Diagnóstico profundo de cada camada
# ============================================================

echo "🔍 AuraTracking Deep Diagnostics"
echo "================================"
echo ""

# ============================================================
# 1. CAMADA MQTT (EMQX)
# ============================================================
echo "📡 [1/5] MQTT BROKER (EMQX)"
echo "----------------------------"

# Status do container
echo "Container status:"
docker ps --filter "name=aura_emqx" --format "  Name: {{.Names}}\n  Status: {{.Status}}\n  Ports: {{.Ports}}"

# Broker status
echo ""
echo "Broker info:"
docker exec aura_emqx emqx_ctl broker 2>/dev/null || echo "  ❌ Não foi possível obter info do broker"

# Clientes conectados
echo ""
echo "Clientes conectados:"
docker exec aura_emqx emqx_ctl clients list 2>/dev/null || echo "  Nenhum cliente"

# Subscriptions
echo ""
echo "Subscriptions ativas:"
docker exec aura_emqx emqx_ctl subscriptions list 2>/dev/null || echo "  Nenhuma subscription"

# Métricas
echo ""
echo "Métricas (últimas):"
docker exec aura_emqx emqx_ctl metrics | grep -E "messages\.(received|sent|publish)" | head -10

echo ""

# ============================================================
# 2. CAMADA INGEST WORKER
# ============================================================
echo "🐍 [2/5] INGEST WORKER"
echo "----------------------"

# Status do container
echo "Container status:"
docker ps --filter "name=aura_ingest" --format "  Name: {{.Names}}\n  Status: {{.Status}}"

# Health check
echo ""
echo "Health check:"
curl -s http://localhost:8080/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  ❌ Health endpoint não disponível"

# Stats
echo ""
echo "Stats:"
curl -s http://localhost:8080/stats 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  Stats endpoint não disponível"

# Últimos logs
echo ""
echo "Últimos 10 logs:"
docker logs aura_ingest 2>&1 | tail -10

# Erros recentes
echo ""
echo "Erros recentes:"
docker logs aura_ingest 2>&1 | grep -i "error\|fail\|exception" | tail -5 || echo "  Nenhum erro recente"

echo ""

# ============================================================
# 3. CAMADA TIMESCALEDB
# ============================================================
echo "🗄️ [3/5] TIMESCALEDB"
echo "--------------------"

# Status do container
echo "Container status:"
docker ps --filter "name=aura_timescaledb" --format "  Name: {{.Names}}\n  Status: {{.Status}}"

# Conexão
echo ""
echo "Teste de conexão:"
docker exec aura_timescaledb pg_isready -U aura -d auratracking 2>&1

# Versão
echo ""
echo "Versões:"
docker exec aura_timescaledb psql -U aura -d auratracking -c "SELECT version();" 2>/dev/null | head -3
docker exec aura_timescaledb psql -U aura -d auratracking -c "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';" 2>/dev/null

# Tabelas
echo ""
echo "Tabelas:"
docker exec aura_timescaledb psql -U aura -d auratracking -c "\dt" 2>/dev/null

# Contagens
echo ""
echo "Contagens:"
docker exec aura_timescaledb psql -U aura -d auratracking -c "
SELECT 
    'telemetry' as table_name, COUNT(*) as rows FROM telemetry
UNION ALL
SELECT 'devices', COUNT(*) FROM devices
UNION ALL
SELECT 'events', COUNT(*) FROM events;
" 2>/dev/null

# Últimos registros
echo ""
echo "Últimos 5 registros de telemetry:"
docker exec aura_timescaledb psql -U aura -d auratracking -c "
SELECT 
    time,
    device_id,
    operator_id,
    ROUND(latitude::numeric, 4) as lat,
    ROUND(longitude::numeric, 4) as lon,
    ROUND(speed_kmh::numeric, 1) as kmh
FROM telemetry 
ORDER BY time DESC 
LIMIT 5;
" 2>/dev/null

# Hypertable info
echo ""
echo "Hypertable info:"
docker exec aura_timescaledb psql -U aura -d auratracking -c "
SELECT 
    hypertable_name,
    num_chunks,
    compression_enabled
FROM timescaledb_information.hypertables
WHERE hypertable_name = 'telemetry';
" 2>/dev/null

# Tamanho
echo ""
echo "Tamanho dos dados:"
docker exec aura_timescaledb psql -U aura -d auratracking -c "
SELECT 
    pg_size_pretty(pg_total_relation_size('telemetry')) as total_size,
    pg_size_pretty(pg_relation_size('telemetry')) as data_size,
    pg_size_pretty(pg_indexes_size('telemetry')) as index_size;
" 2>/dev/null

echo ""

# ============================================================
# 4. CAMADA GRAFANA
# ============================================================
echo "📊 [4/5] GRAFANA"
echo "----------------"

# Status do container
echo "Container status:"
docker ps --filter "name=aura_grafana" --format "  Name: {{.Names}}\n  Status: {{.Status}}\n  Ports: {{.Ports}}"

# Health
echo ""
echo "Health:"
curl -s http://localhost:3000/api/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  ❌ Não acessível"

# Datasources
echo ""
echo "Datasources:"
curl -s -u admin:AuraTrack@2024! http://localhost:3000/api/datasources 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for ds in data:
        print(f\"  - {ds.get('name', 'N/A')} ({ds.get('type', 'N/A')})\")
except:
    print('  Erro ao listar datasources')
" 2>/dev/null

# Dashboards
echo ""
echo "Dashboards:"
curl -s -u admin:AuraTrack@2024! http://localhost:3000/api/search 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for d in data[:10]:
        print(f\"  - {d.get('title', 'N/A')} (uid: {d.get('uid', 'N/A')})\")
except:
    print('  Erro ao listar dashboards')
" 2>/dev/null

echo ""

# ============================================================
# 5. FLUXO DE DADOS
# ============================================================
echo "🔄 [5/5] FLUXO DE DADOS"
echo "-----------------------"

# Taxa de mensagens por minuto
echo "Taxa de mensagens (último minuto):"
docker exec aura_timescaledb psql -U aura -d auratracking -t -c "
SELECT COUNT(*) || ' mensagens' 
FROM telemetry 
WHERE time > NOW() - INTERVAL '1 minute';
" 2>/dev/null

# Dispositivos ativos
echo ""
echo "Dispositivos ativos (última hora):"
docker exec aura_timescaledb psql -U aura -d auratracking -c "
SELECT 
    device_id,
    COUNT(*) as msgs,
    MAX(time) as last_seen,
    ROUND(AVG(speed_kmh)::numeric, 1) as avg_kmh
FROM telemetry
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY device_id
ORDER BY last_seen DESC
LIMIT 10;
" 2>/dev/null

# Gaps de dados
echo ""
echo "Gaps de dados (>30s, última hora):"
docker exec aura_timescaledb psql -U aura -d auratracking -c "
WITH data AS (
    SELECT 
        device_id,
        time,
        LAG(time) OVER (PARTITION BY device_id ORDER BY time) as prev_time
    FROM telemetry
    WHERE time > NOW() - INTERVAL '1 hour'
)
SELECT 
    device_id,
    COUNT(*) as gaps
FROM data
WHERE time - prev_time > INTERVAL '30 seconds'
GROUP BY device_id
ORDER BY gaps DESC
LIMIT 5;
" 2>/dev/null || echo "  Sem gaps significativos"

echo ""
echo "================================"
echo "🔍 Diagnóstico completo!"
echo "================================"
