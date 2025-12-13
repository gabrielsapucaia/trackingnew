#!/bin/bash

# Script para validar estrutura JSON dos payloads MQTT
# Uso: ./test_validate_payload.sh [arquivo_json] ou pipe JSON

if [ -z "$1" ]; then
    echo "Uso: $0 <arquivo_json>"
    echo "   ou: echo '{\"json\":\"aqui\"}' | $0"
    exit 1
fi

PAYLOAD_FILE="$1"
EXPECTED_STRUCTURE_FILE="$(dirname "$0")/ESTRUTURA_MQTT_PROPOSTA.json"

echo "=========================================="
echo "Validador de Payload MQTT"
echo "=========================================="

# Lê payload
if [ -f "$PAYLOAD_FILE" ]; then
    PAYLOAD=$(cat "$PAYLOAD_FILE")
else
    PAYLOAD="$PAYLOAD_FILE"
fi

# Valida JSON
if ! echo "$PAYLOAD" | jq . > /dev/null 2>&1; then
    echo "ERRO: JSON inválido!"
    exit 1
fi

echo "✓ JSON válido"
echo ""

# Campos obrigatórios
REQUIRED_FIELDS=("messageId" "deviceId" "timestamp" "gps")
MISSING_FIELDS=()

for field in "${REQUIRED_FIELDS[@]}"; do
    if ! echo "$PAYLOAD" | jq -e ".$field" > /dev/null 2>&1; then
        MISSING_FIELDS+=("$field")
    fi
done

if [ ${#MISSING_FIELDS[@]} -eq 0 ]; then
    echo "✓ Todos os campos obrigatórios presentes"
else
    echo "✗ Campos obrigatórios faltando: ${MISSING_FIELDS[*]}"
fi

# Verifica campos expandidos
echo ""
echo "Campos Expandidos:"

# GPS detalhado
GPS_FIELDS=("satellites" "hAcc" "vAcc" "sAcc")
echo "  GPS Detalhado:"
for field in "${GPS_FIELDS[@]}"; do
    if echo "$PAYLOAD" | jq -e ".gps.$field" > /dev/null 2>&1; then
        value=$(echo "$PAYLOAD" | jq -r ".gps.$field")
        echo "    ✓ $field: $value"
    else
        echo "    ✗ $field: ausente"
    fi
done

# IMU expandido
IMU_FIELDS=("accelMagnitude" "gyroMagnitude" "magX" "magY" "magZ" "magMagnitude" "linearAccelX" "linearAccelY" "linearAccelZ" "linearAccelMagnitude")
echo "  IMU Expandido:"
for field in "${IMU_FIELDS[@]}"; do
    if echo "$PAYLOAD" | jq -e ".imu.$field" > /dev/null 2>&1; then
        value=$(echo "$PAYLOAD" | jq -r ".imu.$field")
        echo "    ✓ $field: $value"
    else
        echo "    ✗ $field: ausente"
    fi
done

# Orientação
ORIENTATION_FIELDS=("azimuth" "pitch" "roll")
echo "  Orientação:"
if echo "$PAYLOAD" | jq -e ".orientation" > /dev/null 2>&1; then
    for field in "${ORIENTATION_FIELDS[@]}"; do
        if echo "$PAYLOAD" | jq -e ".orientation.$field" > /dev/null 2>&1; then
            value=$(echo "$PAYLOAD" | jq -r ".orientation.$field")
            echo "    ✓ $field: $value"
        else
            echo "    ✗ $field: ausente"
        fi
    done
else
    echo "    ✗ orientation: ausente"
fi

# Sistema
echo "  Sistema:"
if echo "$PAYLOAD" | jq -e ".system" > /dev/null 2>&1; then
    if echo "$PAYLOAD" | jq -e ".system.battery" > /dev/null 2>&1; then
        battery_level=$(echo "$PAYLOAD" | jq -r ".system.battery.level // \"ausente\"")
        echo "    ✓ battery.level: $battery_level"
    fi
    if echo "$PAYLOAD" | jq -e ".system.connectivity" > /dev/null 2>&1; then
        network_type=$(echo "$PAYLOAD" | jq -r ".system.connectivity.cellular.networkType // \"ausente\"")
        echo "    ✓ connectivity.cellular.networkType: $network_type"
    fi
else
    echo "    ✗ system: ausente"
fi

# Flag de transmissão
echo "  Transmissão:"
transmission_mode=$(echo "$PAYLOAD" | jq -r ".transmissionMode // \"ausente\"")
if [ "$transmission_mode" != "ausente" ]; then
    echo "    ✓ transmissionMode: $transmission_mode"
else
    echo "    ✗ transmissionMode: ausente"
fi

echo ""
echo "=========================================="

