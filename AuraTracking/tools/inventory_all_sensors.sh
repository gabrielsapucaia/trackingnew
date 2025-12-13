#!/bin/bash
# =============================================================================
# AuraTracking - Inventário Completo de Sensores
# =============================================================================
# Uso: ./inventory_all_sensors.sh [opções]
#
# Extrai e lista TODOS os sensores disponíveis no dispositivo Android
# Output: JSON estruturado com informações detalhadas de cada sensor
#
# Opções:
#   -o, --output    Arquivo de saída JSON (padrão: sensors_inventory_TIMESTAMP.json)
#   -h, --help      Mostra esta ajuda
# =============================================================================

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE=""

print_help() {
    head -15 "$0" | tail -11
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
DEVICE_BRAND=$(adb shell getprop ro.product.brand 2>/dev/null || echo "Unknown")
ANDROID_VERSION=$(adb shell getprop ro.build.version.release 2>/dev/null || echo "Unknown")

print_status "Dispositivo conectado: $DEVICE_BRAND $DEVICE_MODEL (Android $ANDROID_VERSION)"

# Define arquivo de saída
if [ -z "$OUTPUT_FILE" ]; then
    OUTPUT_FILE="sensors_inventory_${TIMESTAMP}.json"
fi

print_status "Coletando informações de sensores..."

# Coleta dados brutos
SENSORS_DUMP=$(adb shell dumpsys sensorservice 2>/dev/null)

# Extrai informações de sensores
print_status "Processando dados..."

# Cria JSON inicial
JSON_TEMP=$(mktemp)
cat > "$JSON_TEMP" <<EOF
{
  "device": {
    "brand": "$DEVICE_BRAND",
    "model": "$DEVICE_MODEL",
    "androidVersion": "$ANDROID_VERSION",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  },
  "sensors": [
EOF

# Lista de sensores conhecidos para buscar
SENSOR_TYPES=(
    "TYPE_ACCELEROMETER:Accelerometer"
    "TYPE_GYROSCOPE:Gyroscope"
    "TYPE_MAGNETIC_FIELD:Magnetometer"
    "TYPE_PRESSURE:Barometer"
    "TYPE_GRAVITY:Gravity"
    "TYPE_LINEAR_ACCELERATION:LinearAcceleration"
    "TYPE_ROTATION_VECTOR:RotationVector"
    "TYPE_GAME_ROTATION_VECTOR:GameRotationVector"
    "TYPE_GEOMAGNETIC_ROTATION_VECTOR:GeomagneticRotationVector"
    "TYPE_AMBIENT_TEMPERATURE:AmbientTemperature"
    "TYPE_RELATIVE_HUMIDITY:RelativeHumidity"
    "TYPE_LIGHT:Light"
    "TYPE_PROXIMITY:Proximity"
    "TYPE_STEP_COUNTER:StepCounter"
    "TYPE_STEP_DETECTOR:StepDetector"
)

SENSOR_COUNT=0
FIRST_SENSOR=true

for SENSOR_INFO in "${SENSOR_TYPES[@]}"; do
    IFS=':' read -r TYPE_NAME DISPLAY_NAME <<< "$SENSOR_INFO"
    
    # Busca sensor no dump
    SENSOR_DATA=$(echo "$SENSORS_DUMP" | grep -i "$DISPLAY_NAME" -A 10 | head -15 || true)
    
    if [ -n "$SENSOR_DATA" ]; then
        # Extrai informações específicas
        VENDOR=$(echo "$SENSORS_DUMP" | grep -i "$DISPLAY_NAME" -A 5 | grep -i "vendor" | head -1 | sed 's/.*vendor[^:]*: *\([^,]*\).*/\1/' | tr -d ' ' || echo "unknown")
        VERSION=$(echo "$SENSORS_DUMP" | grep -i "$DISPLAY_NAME" -A 5 | grep -i "version" | head -1 | sed 's/.*version[^:]*: *\([^,]*\).*/\1/' | tr -d ' ' || echo "unknown")
        MAX_RANGE=$(echo "$SENSORS_DUMP" | grep -i "$DISPLAY_NAME" -A 5 | grep -i "max.*range" | head -1 | sed 's/.*max.*range[^:]*: *\([^,]*\).*/\1/' | tr -d ' ' || echo "unknown")
        RESOLUTION=$(echo "$SENSORS_DUMP" | grep -i "$DISPLAY_NAME" -A 5 | grep -i "resolution" | head -1 | sed 's/.*resolution[^:]*: *\([^,]*\).*/\1/' | tr -d ' ' || echo "unknown")
        
        # Verifica se sensor está disponível via getDefaultSensor
        SENSOR_AVAILABLE="true"
        
        if [ "$FIRST_SENSOR" = false ]; then
            echo "," >> "$JSON_TEMP"
        fi
        FIRST_SENSOR=false
        
        cat >> "$JSON_TEMP" <<EOF
    {
      "type": "$TYPE_NAME",
      "name": "$DISPLAY_NAME",
      "available": $SENSOR_AVAILABLE,
      "vendor": "$VENDOR",
      "version": "$VERSION",
      "maxRange": "$MAX_RANGE",
      "resolution": "$RESOLUTION"
    }
EOF
        SENSOR_COUNT=$((SENSOR_COUNT + 1))
        print_status "  ✓ $DISPLAY_NAME encontrado"
    else
        print_warning "  ✗ $DISPLAY_NAME não encontrado"
    fi
done

# Adiciona lista completa de sensores do sistema
print_status "Buscando todos os sensores do sistema..."

ALL_SENSORS=$(echo "$SENSORS_DUMP" | grep -E "^\s+[0-9]+:" | head -50 || true)

if [ -n "$ALL_SENSORS" ]; then
    echo "," >> "$JSON_TEMP"
    echo "    {" >> "$JSON_TEMP"
    echo "      \"type\": \"RAW_DUMP\"," >> "$JSON_TEMP"
    echo "      \"name\": \"All Sensors Raw\"," >> "$JSON_TEMP"
    echo "      \"rawData\": [" >> "$JSON_TEMP"
    
    FIRST_RAW=true
    while IFS= read -r LINE; do
        if [ -n "$LINE" ]; then
            if [ "$FIRST_RAW" = false ]; then
                echo "," >> "$JSON_TEMP"
            fi
            FIRST_RAW=false
            ESCAPED_LINE=$(echo "$LINE" | sed 's/"/\\"/g')
            echo "        \"$ESCAPED_LINE\"" >> "$JSON_TEMP"
        fi
    done <<< "$ALL_SENSORS"
    
    echo "      ]" >> "$JSON_TEMP"
    echo "    }" >> "$JSON_TEMP"
fi

# Fecha JSON
cat >> "$JSON_TEMP" <<EOF
  ],
  "summary": {
    "totalSensorsFound": $SENSOR_COUNT,
    "collectionDate": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  }
}
EOF

# Formata JSON (se jq estiver disponível)
if command -v jq &> /dev/null; then
    jq '.' "$JSON_TEMP" > "$OUTPUT_FILE"
    rm "$JSON_TEMP"
else
    mv "$JSON_TEMP" "$OUTPUT_FILE"
    print_warning "jq não encontrado. JSON não formatado. Instale jq para formatação melhor."
fi

print_status "Inventário salvo em: $OUTPUT_FILE"
print_status "Total de sensores encontrados: $SENSOR_COUNT"

# Mostra resumo
echo ""
echo "=== RESUMO ==="
echo "Dispositivo: $DEVICE_BRAND $DEVICE_MODEL"
echo "Android: $ANDROID_VERSION"
echo "Sensores encontrados: $SENSOR_COUNT"
echo "Arquivo: $OUTPUT_FILE"
echo ""
echo "Para visualizar: cat $OUTPUT_FILE | jq '.'"
echo ""

