#!/bin/bash
# ============================================================
# AuraTracking End-to-End Test Suite
# ============================================================
# Script automatizado para validar toda a cadeia de telemetria
# Moto G34 → MQTT → Ingest → TimescaleDB → Grafana
# ============================================================

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Contadores
PASSED=0
FAILED=0
WARNINGS=0

# Configuração
MQTT_HOST="${MQTT_HOST:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-aura}"
DB_PASS="${DB_PASS:-AuraTrack@DB2024!}"
DB_NAME="${DB_NAME:-auratracking}"
GRAFANA_HOST="${GRAFANA_HOST:-localhost}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASS="${GRAFANA_PASS:-AuraTrack@2024!}"
INGEST_HEALTH="${INGEST_HEALTH:-http://localhost:8080/health}"

# Funções de utilidade
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[✅ PASS]${NC} $1"
    ((PASSED++))
}

log_fail() {
    echo -e "${RED}[❌ FAIL]${NC} $1"
    ((FAILED++))
}

log_warn() {
    echo -e "${YELLOW}[⚠️ WARN]${NC} $1"
    ((WARNINGS++))
}

log_section() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
}

# Função para executar SQL
run_sql() {
    docker exec aura_timescaledb psql -U "$DB_USER" -d "$DB_NAME" -t -c "$1" 2>/dev/null
}

# ============================================================
# TESTE 1: Verificar Containers Docker
# ============================================================
test_docker_containers() {
    log_section "TESTE 1: Containers Docker"
    
    local containers=("aura_emqx" "aura_timescaledb" "aura_ingest" "aura_grafana")
    
    for container in "${containers[@]}"; do
        if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            local status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "no-healthcheck")
            if [[ "$status" == "healthy" ]] || [[ "$status" == "no-healthcheck" ]]; then
                log_pass "$container está rodando (status: $status)"
            else
                log_warn "$container rodando mas status: $status"
            fi
        else
            log_fail "$container NÃO está rodando"
        fi
    done
}

# ============================================================
# TESTE 2: Conexão MQTT
# ============================================================
test_mqtt_connection() {
    log_section "TESTE 2: Conexão MQTT (EMQX)"
    
    # Teste de porta
    if nc -zv "$MQTT_HOST" "$MQTT_PORT" 2>&1 | grep -q "succeeded"; then
        log_pass "Porta MQTT $MQTT_PORT acessível"
    else
        log_fail "Porta MQTT $MQTT_PORT NÃO acessível"
        return
    fi
    
    # Teste de publish
    if mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "aura/test/e2e" -m '{"test":true}' 2>&1; then
        log_pass "Publish MQTT funcionando"
    else
        log_fail "Publish MQTT falhou"
    fi
    
    # Verificar clientes conectados
    local clients=$(docker exec aura_emqx emqx_ctl clients list 2>/dev/null | wc -l)
    if [[ $clients -gt 0 ]]; then
        log_pass "EMQX tem $clients cliente(s) conectado(s)"
    else
        log_warn "Nenhum cliente MQTT conectado"
    fi
    
    # Verificar ingest worker conectado
    if docker exec aura_emqx emqx_ctl clients list 2>/dev/null | grep -q "ingest"; then
        log_pass "Ingest worker conectado ao MQTT"
    else
        log_fail "Ingest worker NÃO conectado ao MQTT"
    fi
}

# ============================================================
# TESTE 3: Ingest Worker Health
# ============================================================
test_ingest_health() {
    log_section "TESTE 3: Ingest Worker Health"
    
    local health_response=$(curl -s "$INGEST_HEALTH" 2>/dev/null)
    
    if [[ -n "$health_response" ]]; then
        log_pass "Ingest health endpoint respondendo"
        
        # Parsear resposta
        if echo "$health_response" | grep -q '"status".*"healthy"'; then
            log_pass "Ingest status: healthy"
        elif echo "$health_response" | grep -q '"mqtt_connected".*true'; then
            log_pass "Ingest MQTT connected: true"
        fi
        
        if echo "$health_response" | grep -q '"db_connected".*true'; then
            log_pass "Ingest DB connected: true"
        fi
    else
        log_fail "Ingest health endpoint não respondeu"
    fi
    
    # Verificar logs recentes
    local recent_errors=$(docker logs aura_ingest 2>&1 | tail -50 | grep -c "error\|ERROR\|failed" || true)
    if [[ $recent_errors -eq 0 ]]; then
        log_pass "Nenhum erro recente nos logs do ingest"
    else
        log_warn "$recent_errors erros recentes nos logs do ingest"
    fi
}

# ============================================================
# TESTE 4: TimescaleDB Connection
# ============================================================
test_timescaledb() {
    log_section "TESTE 4: TimescaleDB"
    
    # Testar conexão
    if docker exec aura_timescaledb pg_isready -U "$DB_USER" -d "$DB_NAME" 2>/dev/null | grep -q "accepting"; then
        log_pass "TimescaleDB aceitando conexões"
    else
        log_fail "TimescaleDB NÃO está aceitando conexões"
        return
    fi
    
    # Verificar tabela telemetry
    if run_sql "SELECT 1 FROM telemetry LIMIT 1;" 2>/dev/null | grep -q "1"; then
        log_pass "Tabela telemetry existe e acessível"
    else
        log_warn "Tabela telemetry vazia ou não existe"
    fi
    
    # Verificar hypertable
    local is_hypertable=$(run_sql "SELECT COUNT(*) FROM timescaledb_information.hypertables WHERE hypertable_name = 'telemetry';")
    if [[ $(echo "$is_hypertable" | tr -d ' ') -gt 0 ]]; then
        log_pass "Telemetry é uma hypertable"
    else
        log_fail "Telemetry NÃO é uma hypertable"
    fi
    
    # Contagem de registros
    local count=$(run_sql "SELECT COUNT(*) FROM telemetry;")
    count=$(echo "$count" | tr -d ' ')
    log_info "Total de registros na telemetry: $count"
    
    if [[ $count -gt 0 ]]; then
        log_pass "Existem dados na tabela telemetry"
    else
        log_warn "Tabela telemetry está vazia"
    fi
}

# ============================================================
# TESTE 5: Fluxo End-to-End
# ============================================================
test_e2e_flow() {
    log_section "TESTE 5: Fluxo End-to-End"
    
    local test_device="e2e_test_$(date +%s)"
    local timestamp=$(date +%s%3N)
    
    # Capturar count antes
    local count_before=$(run_sql "SELECT COUNT(*) FROM telemetry;" | tr -d ' ')
    
    log_info "Enviando mensagem de teste..."
    
    # Enviar mensagem MQTT
    mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" -q 1 \
        -t "aura/tracking/${test_device}/telemetry" \
        -m "{\"deviceId\":\"${test_device}\",\"operatorId\":\"E2E_TEST\",\"timestamp\":${timestamp},\"gps\":{\"latitude\":-11.563,\"longitude\":-47.170,\"altitude\":280,\"speed\":15,\"bearing\":180,\"accuracy\":5},\"imu\":{\"accelX\":0.1,\"accelY\":0.2,\"accelZ\":9.8,\"gyroX\":0.01,\"gyroY\":0.02,\"gyroZ\":0.01}}"
    
    log_info "Aguardando processamento (6 segundos)..."
    sleep 6
    
    # Capturar count depois
    local count_after=$(run_sql "SELECT COUNT(*) FROM telemetry;" | tr -d ' ')
    
    log_info "Registros antes: $count_before | depois: $count_after"
    
    if [[ $count_after -gt $count_before ]]; then
        log_pass "Mensagem MQTT → Ingest → TimescaleDB funcionando!"
        
        # Verificar se é o nosso registro
        local found=$(run_sql "SELECT device_id FROM telemetry WHERE device_id = '${test_device}' LIMIT 1;")
        if echo "$found" | grep -q "$test_device"; then
            log_pass "Registro encontrado no banco: $test_device"
        fi
    else
        log_fail "Mensagem NÃO foi inserida no banco"
        
        # Debug
        log_info "Verificando logs do ingest..."
        docker logs aura_ingest 2>&1 | tail -10
    fi
}

# ============================================================
# TESTE 6: Qualidade dos Dados
# ============================================================
test_data_quality() {
    log_section "TESTE 6: Qualidade dos Dados"
    
    # Verificar dados inválidos
    local invalid_lat=$(run_sql "SELECT COUNT(*) FROM telemetry WHERE latitude IS NULL OR latitude < -90 OR latitude > 90;" | tr -d ' ')
    local invalid_lon=$(run_sql "SELECT COUNT(*) FROM telemetry WHERE longitude IS NULL OR longitude < -180 OR longitude > 180;" | tr -d ' ')
    local invalid_speed=$(run_sql "SELECT COUNT(*) FROM telemetry WHERE speed < 0;" | tr -d ' ')
    local future_ts=$(run_sql "SELECT COUNT(*) FROM telemetry WHERE time > NOW() + INTERVAL '1 minute';" | tr -d ' ')
    
    if [[ $invalid_lat -eq 0 ]]; then
        log_pass "Todas latitudes válidas"
    else
        log_warn "$invalid_lat registros com latitude inválida"
    fi
    
    if [[ $invalid_lon -eq 0 ]]; then
        log_pass "Todas longitudes válidas"
    else
        log_warn "$invalid_lon registros com longitude inválida"
    fi
    
    if [[ $invalid_speed -eq 0 ]]; then
        log_pass "Todas velocidades >= 0"
    else
        log_warn "$invalid_speed registros com velocidade negativa"
    fi
    
    if [[ $future_ts -eq 0 ]]; then
        log_pass "Nenhum timestamp no futuro"
    else
        log_warn "$future_ts registros com timestamp no futuro"
    fi
}

# ============================================================
# TESTE 7: Grafana
# ============================================================
test_grafana() {
    log_section "TESTE 7: Grafana"
    
    # Testar acesso
    local grafana_status=$(curl -s -o /dev/null -w "%{http_code}" "http://${GRAFANA_HOST}:${GRAFANA_PORT}/api/health")
    
    if [[ "$grafana_status" == "200" ]]; then
        log_pass "Grafana respondendo (HTTP 200)"
    else
        log_fail "Grafana não respondendo (HTTP $grafana_status)"
        return
    fi
    
    # Verificar datasources
    local datasources=$(curl -s -u "${GRAFANA_USER}:${GRAFANA_PASS}" \
        "http://${GRAFANA_HOST}:${GRAFANA_PORT}/api/datasources" 2>/dev/null)
    
    if echo "$datasources" | grep -q "TimescaleDB\|PostgreSQL\|postgres"; then
        log_pass "Datasource TimescaleDB/PostgreSQL configurado"
    else
        log_warn "Datasource TimescaleDB não encontrado"
    fi
    
    # Verificar dashboards
    local dashboards=$(curl -s -u "${GRAFANA_USER}:${GRAFANA_PASS}" \
        "http://${GRAFANA_HOST}:${GRAFANA_PORT}/api/search?query=aura" 2>/dev/null)
    
    if echo "$dashboards" | grep -q "AuraTracking\|aura"; then
        log_pass "Dashboard AuraTracking encontrado"
    else
        log_warn "Dashboard AuraTracking não encontrado"
    fi
}

# ============================================================
# TESTE 8: Latência de Ingestão
# ============================================================
test_ingestion_latency() {
    log_section "TESTE 8: Latência de Ingestão"
    
    local latency=$(run_sql "
        SELECT 
            ROUND(AVG(EXTRACT(EPOCH FROM (received_at - time)))::numeric, 3) as avg_latency
        FROM telemetry
        WHERE time > NOW() - INTERVAL '1 hour'
        AND received_at IS NOT NULL;
    " | tr -d ' ')
    
    if [[ -n "$latency" ]] && [[ "$latency" != "" ]]; then
        log_info "Latência média de ingestão: ${latency}s"
        
        # Converter para comparação
        local lat_int=$(echo "$latency" | cut -d'.' -f1)
        if [[ ${lat_int:-0} -lt 5 ]]; then
            log_pass "Latência aceitável (<5s)"
        elif [[ ${lat_int:-0} -lt 30 ]]; then
            log_warn "Latência alta (${latency}s)"
        else
            log_fail "Latência muito alta (${latency}s)"
        fi
    else
        log_warn "Sem dados suficientes para calcular latência"
    fi
}

# ============================================================
# TESTE 9: Dispositivos Ativos
# ============================================================
test_active_devices() {
    log_section "TESTE 9: Dispositivos Ativos"
    
    local devices=$(run_sql "
        SELECT device_id, COUNT(*) as records, MAX(time) as last_seen
        FROM telemetry
        WHERE time > NOW() - INTERVAL '1 hour'
        GROUP BY device_id
        ORDER BY last_seen DESC;
    ")
    
    if [[ -n "$devices" ]]; then
        log_info "Dispositivos ativos na última hora:"
        echo "$devices"
        
        local device_count=$(run_sql "
            SELECT COUNT(DISTINCT device_id) 
            FROM telemetry 
            WHERE time > NOW() - INTERVAL '1 hour';
        " | tr -d ' ')
        
        log_pass "$device_count dispositivo(s) ativo(s) na última hora"
    else
        log_warn "Nenhum dispositivo ativo na última hora"
    fi
}

# ============================================================
# TESTE 10: Taxa de Mensagens
# ============================================================
test_message_rate() {
    log_section "TESTE 10: Taxa de Mensagens"
    
    local rate=$(run_sql "
        SELECT 
            COUNT(*) as total,
            COUNT(*) / GREATEST(EXTRACT(EPOCH FROM (MAX(time) - MIN(time))), 1) as msgs_per_sec
        FROM telemetry
        WHERE time > NOW() - INTERVAL '10 minutes';
    ")
    
    log_info "Taxa de mensagens (últimos 10 min):"
    echo "$rate"
    
    local total=$(run_sql "SELECT COUNT(*) FROM telemetry WHERE time > NOW() - INTERVAL '10 minutes';" | tr -d ' ')
    
    if [[ ${total:-0} -gt 0 ]]; then
        log_pass "$total mensagens nos últimos 10 minutos"
    else
        log_warn "Nenhuma mensagem nos últimos 10 minutos"
    fi
}

# ============================================================
# RESUMO FINAL
# ============================================================
print_summary() {
    log_section "RESUMO DOS TESTES"
    
    echo ""
    echo -e "${GREEN}✅ Passou: $PASSED${NC}"
    echo -e "${YELLOW}⚠️  Warnings: $WARNINGS${NC}"
    echo -e "${RED}❌ Falhou: $FAILED${NC}"
    echo ""
    
    local total=$((PASSED + FAILED))
    local percentage=$((PASSED * 100 / total))
    
    if [[ $FAILED -eq 0 ]]; then
        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}  🎉 TODOS OS TESTES PASSARAM! Stack funcionando 100%${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    elif [[ $percentage -ge 80 ]]; then
        echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
        echo -e "${YELLOW}  ⚠️  Stack funcionando parcialmente (${percentage}%)${NC}"
        echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
    else
        echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
        echo -e "${RED}  ❌ Stack com problemas (${percentage}% dos testes passaram)${NC}"
        echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
    fi
    
    echo ""
    echo "Timestamp: $(date)"
    echo ""
}

# ============================================================
# MAIN
# ============================================================
main() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}║   🔥 AuraTracking End-to-End Test Suite v1.0              ║${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}║   Moto G34 → MQTT → Ingest → TimescaleDB → Grafana        ║${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Executar todos os testes
    test_docker_containers
    test_mqtt_connection
    test_ingest_health
    test_timescaledb
    test_e2e_flow
    test_data_quality
    test_grafana
    test_ingestion_latency
    test_active_devices
    test_message_rate
    
    print_summary
    
    # Exit code
    if [[ $FAILED -gt 0 ]]; then
        exit 1
    else
        exit 0
    fi
}

# Executar
main "$@"
