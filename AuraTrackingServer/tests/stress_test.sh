#!/bin/bash
# ============================================================
# AuraTracking Stress Test
# ============================================================
# Simula múltiplos dispositivos enviando telemetria
# ============================================================

set -e

# Configuração
MQTT_HOST="${MQTT_HOST:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"
NUM_DEVICES="${1:-5}"
DURATION_SECONDS="${2:-60}"
INTERVAL_MS="${3:-1000}"

echo "🔥 AuraTracking Stress Test"
echo "==========================="
echo "Dispositivos: $NUM_DEVICES"
echo "Duração: ${DURATION_SECONDS}s"
echo "Intervalo: ${INTERVAL_MS}ms"
echo ""

# Arrays para PIDs dos processos
declare -a PIDS

# Função para gerar telemetria de um dispositivo
generate_telemetry() {
    local device_id=$1
    local duration=$2
    local interval_sec=$(echo "scale=3; $INTERVAL_MS / 1000" | bc)
    
    local lat_base=$(echo "-11.56 + 0.001 * $device_id" | bc)
    local lon_base=$(echo "-47.17 + 0.001 * $device_id" | bc)
    
    local end_time=$(($(date +%s) + duration))
    local count=0
    
    while [[ $(date +%s) -lt $end_time ]]; do
        local ts=$(date +%s%3N)
        local lat=$(echo "$lat_base + 0.0001 * $count" | bc)
        local lon=$(echo "$lon_base + 0.0001 * $count" | bc)
        local speed=$(echo "10 + $RANDOM % 30" | bc)
        local accel_x=$(echo "scale=2; ($RANDOM % 100 - 50) / 100" | bc)
        local accel_y=$(echo "scale=2; ($RANDOM % 100 - 50) / 100" | bc)
        local accel_z=$(echo "scale=2; 9.8 + ($RANDOM % 20 - 10) / 100" | bc)
        
        mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" -q 1 \
            -t "aura/tracking/stress_${device_id}/telemetry" \
            -m "{\"deviceId\":\"stress_${device_id}\",\"operatorId\":\"OP_${device_id}\",\"timestamp\":${ts},\"gps\":{\"latitude\":${lat},\"longitude\":${lon},\"altitude\":280,\"speed\":${speed},\"bearing\":180,\"accuracy\":5},\"imu\":{\"accelX\":${accel_x},\"accelY\":${accel_y},\"accelZ\":${accel_z},\"gyroX\":0.01,\"gyroY\":0.02,\"gyroZ\":0.01}}" \
            2>/dev/null
        
        ((count++))
        sleep "$interval_sec"
    done
    
    echo "Device stress_${device_id}: $count mensagens enviadas"
}

# Capturar count inicial
COUNT_BEFORE=$(docker exec aura_timescaledb psql -U aura -d auratracking -t -c "SELECT COUNT(*) FROM telemetry;" | tr -d ' ')

echo "Registros antes: $COUNT_BEFORE"
echo ""
echo "Iniciando $NUM_DEVICES dispositivos simulados..."
echo ""

# Iniciar dispositivos em background
for i in $(seq 1 $NUM_DEVICES); do
    generate_telemetry "$i" "$DURATION_SECONDS" &
    PIDS+=($!)
    echo "Iniciado dispositivo stress_$i (PID: ${PIDS[-1]})"
done

echo ""
echo "Aguardando término (${DURATION_SECONDS}s)..."
echo ""

# Aguardar todos terminarem
for pid in "${PIDS[@]}"; do
    wait "$pid"
done

echo ""
echo "Todos os dispositivos finalizaram."
echo ""

# Aguardar flush do ingest
echo "Aguardando flush do ingest (10s)..."
sleep 10

# Capturar count final
COUNT_AFTER=$(docker exec aura_timescaledb psql -U aura -d auratracking -t -c "SELECT COUNT(*) FROM telemetry;" | tr -d ' ')

INSERTED=$((COUNT_AFTER - COUNT_BEFORE))
EXPECTED=$((NUM_DEVICES * DURATION_SECONDS * 1000 / INTERVAL_MS))

echo "==========================="
echo "📊 Resultados"
echo "==========================="
echo "Registros antes: $COUNT_BEFORE"
echo "Registros depois: $COUNT_AFTER"
echo "Inseridos: $INSERTED"
echo "Esperados: ~$EXPECTED"
echo ""

if [[ $INSERTED -ge $((EXPECTED * 90 / 100)) ]]; then
    echo "✅ Stress test passou! (>90% das mensagens inseridas)"
else
    echo "⚠️ Possível perda de dados ($(($INSERTED * 100 / EXPECTED))% inserido)"
fi

echo ""
echo "Taxa média: $(echo "scale=2; $INSERTED / $DURATION_SECONDS" | bc) msgs/s"
echo ""

# Estatísticas por dispositivo
echo "Por dispositivo:"
docker exec aura_timescaledb psql -U aura -d auratracking -c "
SELECT 
    device_id,
    COUNT(*) as msgs,
    MIN(time) as first,
    MAX(time) as last
FROM telemetry
WHERE device_id LIKE 'stress_%'
AND time > NOW() - INTERVAL '5 minutes'
GROUP BY device_id
ORDER BY device_id;
"
