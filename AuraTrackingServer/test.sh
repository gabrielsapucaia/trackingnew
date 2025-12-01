#!/bin/bash
# ============================================================
# AuraTracking Server - Test Script
# ============================================================
# Scripts para testar a infraestrutura
# ============================================================

set -e

MQTT_HOST="${MQTT_HOST:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"

echo "=============================================="
echo "  AuraTracking Server - Testes"
echo "=============================================="
echo ""

# Verificar ferramentas
if ! command -v mosquitto_pub &> /dev/null; then
    echo "⚠️  mosquitto-clients não encontrado."
    echo "   Instalando: brew install mosquitto (macOS) ou apt install mosquitto-clients (Ubuntu)"
    exit 1
fi

# Função para publicar telemetria de teste
publish_test_telemetry() {
    local device_id="$1"
    local timestamp=$(date +%s)000
    local lat=$(echo "scale=6; -11.5636 + ($RANDOM / 100000)" | bc)
    local lon=$(echo "scale=6; -47.1706 + ($RANDOM / 100000)" | bc)
    local speed=$(echo "scale=2; $RANDOM / 3276" | bc)
    local accel_x=$(echo "scale=2; ($RANDOM - 16383) / 16383" | bc)
    local accel_y=$(echo "scale=2; ($RANDOM - 16383) / 16383" | bc)
    local accel_z=$(echo "scale=2; 9.8 + ($RANDOM - 16383) / 163830" | bc)
    
    local payload=$(cat <<EOF
{
    "deviceId": "$device_id",
    "operatorId": "test-operator-001",
    "timestamp": $timestamp,
    "gps": {
        "lat": $lat,
        "lon": $lon,
        "alt": 760.5,
        "speed": $speed,
        "bearing": $((RANDOM % 360)),
        "accuracy": $((RANDOM % 20 + 5))
    },
    "imu": {
        "accelX": $accel_x,
        "accelY": $accel_y,
        "accelZ": $accel_z,
        "gyroX": 0.01,
        "gyroY": 0.02,
        "gyroZ": 0.01
    }
}
EOF
)
    
    echo "📤 Publicando para aura/tracking/$device_id/telemetry"
    mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" \
        -t "aura/tracking/$device_id/telemetry" \
        -m "$payload" \
        -q 1
}

# Função para publicar evento de teste
publish_test_event() {
    local device_id="$1"
    local event_type="$2"
    local timestamp=$(date +%s)000
    
    local payload=$(cat <<EOF
{
    "deviceId": "$device_id",
    "operatorId": "test-operator-001",
    "timestamp": $timestamp,
    "eventType": "$event_type",
    "data": {
        "test": true,
        "source": "test_script"
    }
}
EOF
)
    
    echo "📤 Publicando evento $event_type para aura/tracking/$device_id/events"
    mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" \
        -t "aura/tracking/$device_id/events" \
        -m "$payload" \
        -q 1
}

# Menu de opções
echo "Opções de teste:"
echo "  1) Publicar uma telemetria de teste"
echo "  2) Publicar 10 telemetrias em sequência"
echo "  3) Simular 3 dispositivos por 1 minuto"
echo "  4) Publicar evento de login"
echo "  5) Monitorar tópico MQTT (subscriber)"
echo "  6) Verificar banco de dados"
echo "  7) Verificar health do ingest"
echo ""
read -p "Escolha uma opção (1-7): " option

case $option in
    1)
        publish_test_telemetry "test_device_001"
        echo "✅ Telemetria publicada!"
        ;;
    2)
        echo "Publicando 10 telemetrias..."
        for i in {1..10}; do
            publish_test_telemetry "test_device_001"
            sleep 1
        done
        echo "✅ 10 telemetrias publicadas!"
        ;;
    3)
        echo "Simulando 3 dispositivos por 1 minuto..."
        end_time=$(($(date +%s) + 60))
        while [ $(date +%s) -lt $end_time ]; do
            for device in "caminhao_001" "caminhao_002" "caminhao_003"; do
                publish_test_telemetry "$device" &
            done
            wait
            sleep 1
        done
        echo "✅ Simulação concluída!"
        ;;
    4)
        publish_test_event "test_device_001" "login"
        echo "✅ Evento publicado!"
        ;;
    5)
        echo "Monitorando aura/tracking/# (Ctrl+C para sair)..."
        mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" \
            -t "aura/tracking/#" \
            -v
        ;;
    6)
        echo "Verificando banco de dados..."
        docker compose exec timescaledb psql -U aura -d auratracking -c "
            SELECT 'Telemetrias' as tabela, COUNT(*) as total FROM telemetry
            UNION ALL
            SELECT 'Eventos', COUNT(*) FROM events
            UNION ALL
            SELECT 'Dispositivos', COUNT(*) FROM devices;
        "
        echo ""
        echo "Últimas 5 telemetrias:"
        docker compose exec timescaledb psql -U aura -d auratracking -c "
            SELECT time, device_id, latitude, longitude, speed_kmh, accel_magnitude
            FROM telemetry
            ORDER BY time DESC
            LIMIT 5;
        "
        ;;
    7)
        echo "Health do Ingest Worker:"
        curl -s http://localhost:8080/health | python3 -m json.tool || echo "Ingest não disponível"
        echo ""
        echo "Stats do Ingest Worker:"
        curl -s http://localhost:8080/stats | python3 -m json.tool || echo "Ingest não disponível"
        ;;
    *)
        echo "Opção inválida"
        exit 1
        ;;
esac
