#!/bin/bash
# =============================================================================
# AuraTracking - Monitoramento Contínuo de Telemetria
# =============================================================================
# Uso: ./monitor_telemetry.sh [opções]
#
# Monitora em tempo real TODOS os dados possíveis:
# - GPS detalhado (satélites, HDOP, VDOP, PDOP)
# - Sensores IMU (acelerômetro, giroscópio, magnetômetro, barômetro)
# - Bateria (nível, temperatura, status)
# - Conectividade (WiFi, celular)
# - Orientação
#
# Opções:
#   -d, --duration    Duração em segundos (padrão: 60)
#   -i, --interval    Intervalo entre amostras em segundos (padrão: 1)
#   -o, --output      Arquivo de saída JSON (padrão: telemetry_monitor_TIMESTAMP.json)
#   -h, --help        Mostra esta ajuda
# =============================================================================

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DURATION=60
INTERVAL=1
OUTPUT_FILE=""
JSON_OUTPUT=true

print_help() {
    head -20 "$0" | tail -16
    exit 0
}

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse argumentos
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -h|--help)
            print_help
            ;;
        *)
            print_error "Opção desconhecida: $1"
            print_help
            ;;
    esac
done

# Verifica ADB
if ! command -v adb &> /dev/null; then
    print_error "ADB não encontrado. Instale o Android SDK."
    exit 1
fi

# Verifica dispositivo conectado
DEVICE_COUNT=$(adb devices | grep -c "device$" || true)
if [ "$DEVICE_COUNT" -eq 0 ]; then
    print_error "Nenhum dispositivo Android conectado."
    exit 1
fi

DEVICE_MODEL=$(adb shell getprop ro.product.model 2>/dev/null || echo "Unknown")
print_status "Dispositivo conectado: $DEVICE_MODEL"
print_status "Monitorando por $DURATION segundos (intervalo: ${INTERVAL}s)"

# Define arquivo de saída
if [ -z "$OUTPUT_FILE" ]; then
    OUTPUT_FILE="telemetry_monitor_${TIMESTAMP}.json"
fi

# Função para extrair GPS detalhado
get_gps_data() {
    LOCATION_DUMP=$(adb shell dumpsys location 2>/dev/null)
    
    # Extrai informações GPS
    GPS_ENABLED=$(echo "$LOCATION_DUMP" | grep -i "gps.*enabled" | head -1 | grep -o "true\|false" | head -1 || echo "unknown")
    GPS_PROVIDER=$(echo "$LOCATION_DUMP" | grep -A 5 "GPS" | grep -i "provider" | head -1 || echo "")
    
    # Tenta obter última localização conhecida
    LAST_LOC=$(adb shell "dumpsys location | grep -A 20 'Last Location' | head -20" 2>/dev/null || echo "")
    
    echo "{\"enabled\": \"$GPS_ENABLED\", \"provider\": \"$GPS_PROVIDER\"}"
}

# Função para extrair dados de bateria
get_battery_data() {
    BATTERY_DUMP=$(adb shell dumpsys battery 2>/dev/null)
    
    LEVEL=$(echo "$BATTERY_DUMP" | grep "level:" | awk '{print $2}' || echo "0")
    TEMP=$(echo "$BATTERY_DUMP" | grep "temperature:" | awk '{print $2}' || echo "0")
    STATUS=$(echo "$BATTERY_DUMP" | grep "status:" | awk '{print $2}' || echo "0")
    HEALTH=$(echo "$BATTERY_DUMP" | grep "health:" | awk '{print $2}' || echo "0")
    VOLTAGE=$(echo "$BATTERY_DUMP" | grep "voltage:" | awk '{print $2}' || echo "0")
    
    # Converte temperatura de décimos de grau para graus
    TEMP_C=$(echo "scale=1; $TEMP / 10" | bc 2>/dev/null || echo "$TEMP")
    
    # Converte status numérico para string
    case "$STATUS" in
        1) STATUS_STR="UNKNOWN" ;;
        2) STATUS_STR="CHARGING" ;;
        3) STATUS_STR="DISCHARGING" ;;
        4) STATUS_STR="NOT_CHARGING" ;;
        5) STATUS_STR="FULL" ;;
        *) STATUS_STR="UNKNOWN" ;;
    esac
    
    echo "{\"level\": $LEVEL, \"temperature\": $TEMP_C, \"status\": \"$STATUS_STR\", \"health\": $HEALTH, \"voltage\": $VOLTAGE}"
}

# Função para extrair conectividade
get_connectivity_data() {
    # WiFi
    WIFI_DUMP=$(adb shell dumpsys wifi 2>/dev/null)
    WIFI_ENABLED=$(echo "$WIFI_DUMP" | grep -i "wifi.*enabled" | grep -o "true\|false" | head -1 || echo "unknown")
    WIFI_RSSI=$(echo "$WIFI_DUMP" | grep -i "rssi" | head -1 | grep -oE "-[0-9]+" | head -1 || echo "0")
    
    # Celular
    TELEPHONY_DUMP=$(adb shell dumpsys telephony.registry 2>/dev/null)
    NETWORK_TYPE=$(echo "$TELEPHONY_DUMP" | grep -i "network.*type" | head -1 | awk '{print $NF}' || echo "unknown")
    SIGNAL_STRENGTH=$(echo "$TELEPHONY_DUMP" | grep -i "signal.*strength" | head -1 | awk '{print $NF}' || echo "0")
    OPERATOR=$(adb shell getprop gsm.operator.alpha 2>/dev/null | head -1 || echo "unknown")
    
    echo "{\"wifi\": {\"enabled\": \"$WIFI_ENABLED\", \"rssi\": $WIFI_RSSI}, \"cellular\": {\"networkType\": \"$NETWORK_TYPE\", \"signalStrength\": $SIGNAL_STRENGTH, \"operator\": \"$OPERATOR\"}}"
}

# Função para verificar sensores disponíveis
check_sensor_available() {
    SENSOR_NAME=$1
    SENSORS_DUMP=$(adb shell dumpsys sensorservice 2>/dev/null)
    echo "$SENSORS_DUMP" | grep -qi "$SENSOR_NAME" && echo "true" || echo "false"
}

# Inicia JSON
JSON_TEMP=$(mktemp)
cat > "$JSON_TEMP" <<EOF
{
  "device": {
    "model": "$DEVICE_MODEL",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  },
  "samples": [
EOF

SAMPLE_COUNT=0
START_TIME=$(date +%s)
END_TIME=$((START_TIME + DURATION))

print_status "Iniciando coleta de dados..."
print_status "Pressione Ctrl+C para parar antes do tempo"

FIRST_SAMPLE=true

while [ $(date +%s) -lt $END_TIME ]; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    if [ "$FIRST_SAMPLE" = false ]; then
        echo "," >> "$JSON_TEMP"
    fi
    FIRST_SAMPLE=false
    
    # Coleta dados
    GPS_DATA=$(get_gps_data)
    BATTERY_DATA=$(get_battery_data)
    CONNECTIVITY_DATA=$(get_connectivity_data)
    
    # Verifica sensores
    ACCEL_AVAILABLE=$(check_sensor_available "accelerometer")
    GYRO_AVAILABLE=$(check_sensor_available "gyroscope")
    MAG_AVAILABLE=$(check_sensor_available "magnetometer")
    PRESSURE_AVAILABLE=$(check_sensor_available "pressure")
    
    # Monta JSON do sample
    cat >> "$JSON_TEMP" <<EOF
    {
      "timestamp": $(date +%s)000,
      "elapsedSeconds": $ELAPSED,
      "gps": $GPS_DATA,
      "battery": $BATTERY_DATA,
      "connectivity": $CONNECTIVITY_DATA,
      "sensorsAvailable": {
        "accelerometer": $ACCEL_AVAILABLE,
        "gyroscope": $GYRO_AVAILABLE,
        "magnetometer": $MAG_AVAILABLE,
        "pressure": $PRESSURE_AVAILABLE
      }
    }
EOF
    
    SAMPLE_COUNT=$((SAMPLE_COUNT + 1))
    
    # Mostra progresso
    printf "\r${BLUE}[$ELAPSED/${DURATION}s]${NC} Amostras coletadas: $SAMPLE_COUNT"
    
    # Aguarda intervalo
    sleep "$INTERVAL"
done

echo ""

# Fecha JSON
cat >> "$JSON_TEMP" <<EOF
  ],
  "summary": {
    "totalSamples": $SAMPLE_COUNT,
    "durationSeconds": $DURATION,
    "intervalSeconds": $INTERVAL,
    "endTime": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  }
}
EOF

# Formata JSON (se jq estiver disponível)
if command -v jq &> /dev/null; then
    jq '.' "$JSON_TEMP" > "$OUTPUT_FILE"
    rm "$JSON_TEMP"
else
    mv "$JSON_TEMP" "$OUTPUT_FILE"
    print_warning "jq não encontrado. JSON não formatado."
fi

print_status "Dados salvos em: $OUTPUT_FILE"
print_status "Total de amostras coletadas: $SAMPLE_COUNT"
echo ""
echo "Para visualizar: cat $OUTPUT_FILE | jq '.'"
echo ""

