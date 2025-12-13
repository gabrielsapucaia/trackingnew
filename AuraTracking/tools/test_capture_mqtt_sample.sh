#!/bin/bash

# Script para capturar amostra de payload MQTT e salvar em arquivo
# Uso: ./test_capture_mqtt_sample.sh [MQTT_HOST] [MQTT_PORT] [NUM_SAMPLES] [OUTPUT_FILE]

MQTT_HOST="${1:-10.10.10.10}"
MQTT_PORT="${2:-1883}"
NUM_SAMPLES="${3:-5}"
OUTPUT_FILE="${4:-mqtt_sample_$(date +%Y%m%d_%H%M%S).json}"

echo "=========================================="
echo "Captura de Amostra MQTT"
echo "=========================================="
echo "Host: $MQTT_HOST"
echo "Port: $MQTT_PORT"
echo "Amostras: $NUM_SAMPLES"
echo "Arquivo: $OUTPUT_FILE"
echo "=========================================="
echo ""

# Verifica se mosquitto_sub está instalado
if ! command -v mosquitto_sub &> /dev/null; then
    echo "ERRO: mosquitto_sub não encontrado!"
    echo "Instale com: sudo apt-get install mosquitto-clients"
    exit 1
fi

# Cria arquivo de saída
echo "[" > "$OUTPUT_FILE"

# Captura amostras
count=0
mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "aura/tracking/#" -C "$NUM_SAMPLES" | while read -r line; do
    topic=$(echo "$line" | cut -d' ' -f1)
    payload=$(echo "$line" | cut -d' ' -f2-)
    
    if [ $count -gt 0 ]; then
        echo "," >> "$OUTPUT_FILE"
    fi
    
    # Cria objeto com topic e payload
    echo "{\"topic\":\"$topic\",\"payload\":$payload,\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >> "$OUTPUT_FILE"
    
    count=$((count + 1))
    echo "Capturado: $count/$NUM_SAMPLES"
done

echo "]" >> "$OUTPUT_FILE"

echo ""
echo "✓ Amostras capturadas em: $OUTPUT_FILE"
echo ""
echo "Validando payloads..."
echo ""

# Valida cada payload
jq -r '.[].payload' "$OUTPUT_FILE" | while read -r payload; do
    if echo "$payload" | jq . > /dev/null 2>&1; then
        echo "✓ Payload válido"
    else
        echo "✗ Payload inválido"
    fi
done

echo ""
echo "Use: ./test_validate_payload.sh <arquivo_json> para validar detalhadamente"

