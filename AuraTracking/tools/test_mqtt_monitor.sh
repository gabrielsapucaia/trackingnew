#!/bin/bash

# Script para monitorar tópicos MQTT e exibir payloads
# Uso: ./test_mqtt_monitor.sh [MQTT_HOST] [MQTT_PORT] [TOPIC]

MQTT_HOST="${1:-10.10.10.10}"
MQTT_PORT="${2:-1883}"
TOPIC="${3:-aura/tracking/#}"

echo "=========================================="
echo "MQTT Monitor - AuraTracking"
echo "=========================================="
echo "Host: $MQTT_HOST"
echo "Port: $MQTT_PORT"
echo "Topic: $TOPIC"
echo "=========================================="
echo ""

# Verifica se mosquitto_sub está instalado
if ! command -v mosquitto_sub &> /dev/null; then
    echo "ERRO: mosquitto_sub não encontrado!"
    echo "Instale com: sudo apt-get install mosquitto-clients"
    exit 1
fi

# Monitora tópicos e exibe payloads formatados
mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "$TOPIC" -v | while read -r line; do
    topic=$(echo "$line" | cut -d' ' -f1)
    payload=$(echo "$line" | cut -d' ' -f2-)
    
    echo "----------------------------------------"
    echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Topic: $topic"
    echo "Payload:"
    
    # Tenta formatar JSON se válido
    if echo "$payload" | jq . > /dev/null 2>&1; then
        echo "$payload" | jq .
        
        # Extrai campos importantes
        echo ""
        echo "Campos Extraídos:"
        echo "  - messageId: $(echo "$payload" | jq -r '.messageId // "N/A"')"
        echo "  - deviceId: $(echo "$payload" | jq -r '.deviceId // "N/A"')"
        echo "  - transmissionMode: $(echo "$payload" | jq -r '.transmissionMode // "N/A"')"
        echo "  - timestamp: $(echo "$payload" | jq -r '.timestamp // "N/A"')"
        
        # GPS
        if echo "$payload" | jq -e '.gps' > /dev/null 2>&1; then
            echo "  - GPS lat: $(echo "$payload" | jq -r '.gps.lat // "N/A"')"
            echo "  - GPS lon: $(echo "$payload" | jq -r '.gps.lon // "N/A"')"
            echo "  - GPS satellites: $(echo "$payload" | jq -r '.gps.satellites // "N/A"')"
            echo "  - GPS hAcc: $(echo "$payload" | jq -r '.gps.hAcc // "N/A"')"
        fi
        
        # IMU
        if echo "$payload" | jq -e '.imu' > /dev/null 2>&1; then
            echo "  - IMU accelMagnitude: $(echo "$payload" | jq -r '.imu.accelMagnitude // "N/A"')"
            echo "  - IMU magX: $(echo "$payload" | jq -r '.imu.magX // "N/A"')"
            echo "  - IMU linearAccelMagnitude: $(echo "$payload" | jq -r '.imu.linearAccelMagnitude // "N/A"')"
        fi
        
        # Orientation
        if echo "$payload" | jq -e '.orientation' > /dev/null 2>&1; then
            echo "  - Orientation azimuth: $(echo "$payload" | jq -r '.orientation.azimuth // "N/A"')"
            echo "  - Orientation pitch: $(echo "$payload" | jq -r '.orientation.pitch // "N/A"')"
            echo "  - Orientation roll: $(echo "$payload" | jq -r '.orientation.roll // "N/A"')"
        fi
        
        # System
        if echo "$payload" | jq -e '.system' > /dev/null 2>&1; then
            echo "  - Battery level: $(echo "$payload" | jq -r '.system.battery.level // "N/A"')"
            echo "  - Battery status: $(echo "$payload" | jq -r '.system.battery.status // "N/A"')"
            echo "  - Network type: $(echo "$payload" | jq -r '.system.connectivity.cellular.networkType // "N/A"')"
        fi
    else
        echo "$payload"
    fi
    
    echo ""
done

