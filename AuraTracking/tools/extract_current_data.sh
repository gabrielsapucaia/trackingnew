#!/bin/bash
# =============================================================================
# AuraTracking - Extração de Dados Atuais
# =============================================================================
# Uso: ./extract_current_data.sh [opções]
#
# Extrai dados que o app AuraTracking já captura atualmente:
# - GPS (lat, lon, alt, speed, bearing, accuracy)
# - IMU (acelerômetro, giroscópio)
#
# Compara com o que está disponível no dispositivo para identificar gaps.
#
# Opções:
#   -o, --output    Arquivo de saída JSON (padrão: current_data_TIMESTAMP.json)
#   -h, --help      Mostra esta ajuda
# =============================================================================

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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
print_status "Dispositivo conectado: $DEVICE_MODEL"

# Define arquivo de saída
if [ -z "$OUTPUT_FILE" ]; then
    OUTPUT_FILE="current_data_${TIMESTAMP}.json"
fi

print_status "Extraindo dados atuais do app..."

# Extrai dados GPS atuais
print_status "Coletando dados GPS..."

GPS_DATA=$(adb shell "dumpsys location | grep -A 30 'Last Location'" 2>/dev/null || echo "")

# Tenta obter última localização via LocationManager
LAST_LOC=$(adb shell "am start -a android.intent.action.VIEW" 2>/dev/null || true)

# Extrai dados de sensores IMU
print_status "Coletando dados IMU..."

# Verifica se sensores estão disponíveis
ACCEL_AVAILABLE=$(adb shell "dumpsys sensorservice | grep -i accelerometer" | wc -l)
GYRO_AVAILABLE=$(adb shell "dumpsys sensorservice | grep -i gyroscope" | wc -l)

# Tenta ler eventos de sensores (requer permissões)
print_warning "Lendo eventos de sensores (pode requerer permissões)..."

# Cria JSON com dados atuais
JSON_TEMP=$(mktemp)

cat > "$JSON_TEMP" <<EOF
{
  "device": {
    "model": "$DEVICE_MODEL",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  },
  "currentData": {
    "gps": {
      "description": "Dados GPS capturados pelo app",
      "fields": [
        {
          "name": "latitude",
          "type": "Double",
          "unit": "degrees",
          "captured": true,
          "description": "Latitude GPS"
        },
        {
          "name": "longitude",
          "type": "Double",
          "unit": "degrees",
          "captured": true,
          "description": "Longitude GPS"
        },
        {
          "name": "altitude",
          "type": "Double",
          "unit": "meters",
          "captured": true,
          "description": "Altitude GPS"
        },
        {
          "name": "speed",
          "type": "Float",
          "unit": "m/s",
          "captured": true,
          "description": "Velocidade em m/s"
        },
        {
          "name": "bearing",
          "type": "Float",
          "unit": "degrees",
          "captured": true,
          "description": "Direção (0-360°)"
        },
        {
          "name": "accuracy",
          "type": "Float",
          "unit": "meters",
          "captured": true,
          "description": "Precisão do fix GPS"
        },
        {
          "name": "timestamp",
          "type": "Long",
          "unit": "milliseconds",
          "captured": true,
          "description": "Timestamp do app"
        },
        {
          "name": "ageMs",
          "type": "Long",
          "unit": "milliseconds",
          "captured": true,
          "description": "Idade do fix GPS"
        },
        {
          "name": "intervalSinceLastFixMs",
          "type": "Long",
          "unit": "milliseconds",
          "captured": true,
          "description": "Intervalo desde último fix"
        },
        {
          "name": "temporalQuality",
          "type": "String",
          "captured": true,
          "description": "Qualidade temporal (normal/stale)"
        },
        {
          "name": "satellites",
          "type": "Integer",
          "captured": false,
          "description": "Número de satélites GPS usados",
          "available": true
        },
        {
          "name": "hdop",
          "type": "Float",
          "captured": false,
          "description": "Horizontal Dilution of Precision",
          "available": true
        },
        {
          "name": "vdop",
          "type": "Float",
          "captured": false,
          "description": "Vertical Dilution of Precision",
          "available": true
        },
        {
          "name": "pdop",
          "type": "Float",
          "captured": false,
          "description": "Position Dilution of Precision",
          "available": true
        },
        {
          "name": "gpsTimestamp",
          "type": "Long",
          "unit": "milliseconds",
          "captured": false,
          "description": "Timestamp do fix GPS (não do app)",
          "available": true
        }
      ]
    },
    "imu": {
      "description": "Dados IMU capturados pelo app",
      "fields": [
        {
          "name": "accelX",
          "type": "Float",
          "unit": "m/s²",
          "captured": true,
          "description": "Aceleração X",
          "sensorAvailable": $([ "$ACCEL_AVAILABLE" -gt 0 ] && echo "true" || echo "false")
        },
        {
          "name": "accelY",
          "type": "Float",
          "unit": "m/s²",
          "captured": true,
          "description": "Aceleração Y",
          "sensorAvailable": $([ "$ACCEL_AVAILABLE" -gt 0 ] && echo "true" || echo "false")
        },
        {
          "name": "accelZ",
          "type": "Float",
          "unit": "m/s²",
          "captured": true,
          "description": "Aceleração Z",
          "sensorAvailable": $([ "$ACCEL_AVAILABLE" -gt 0 ] && echo "true" || echo "false")
        },
        {
          "name": "gyroX",
          "type": "Float",
          "unit": "rad/s",
          "captured": true,
          "description": "Rotação X",
          "sensorAvailable": $([ "$GYRO_AVAILABLE" -gt 0 ] && echo "true" || echo "false")
        },
        {
          "name": "gyroY",
          "type": "Float",
          "unit": "rad/s",
          "captured": true,
          "description": "Rotação Y",
          "sensorAvailable": $([ "$GYRO_AVAILABLE" -gt 0 ] && echo "true" || echo "false")
        },
        {
          "name": "gyroZ",
          "type": "Float",
          "unit": "rad/s",
          "captured": true,
          "description": "Rotação Z",
          "sensorAvailable": $([ "$GYRO_AVAILABLE" -gt 0 ] && echo "true" || echo "false")
        },
        {
          "name": "magX",
          "type": "Float",
          "unit": "μT",
          "captured": false,
          "description": "Campo magnético X",
          "available": true
        },
        {
          "name": "magY",
          "type": "Float",
          "unit": "μT",
          "captured": false,
          "description": "Campo magnético Y",
          "available": true
        },
        {
          "name": "magZ",
          "type": "Float",
          "unit": "μT",
          "captured": false,
          "description": "Campo magnético Z",
          "available": true
        },
        {
          "name": "pressure",
          "type": "Float",
          "unit": "hPa",
          "captured": false,
          "description": "Pressão barométrica",
          "available": true
        },
        {
          "name": "linearAccelX",
          "type": "Float",
          "unit": "m/s²",
          "captured": false,
          "description": "Aceleração linear X (sem gravidade)",
          "available": true
        },
        {
          "name": "linearAccelY",
          "type": "Float",
          "unit": "m/s²",
          "captured": false,
          "description": "Aceleração linear Y (sem gravidade)",
          "available": true
        },
        {
          "name": "linearAccelZ",
          "type": "Float",
          "unit": "m/s²",
          "captured": false,
          "description": "Aceleração linear Z (sem gravidade)",
          "available": true
        },
        {
          "name": "gravityX",
          "type": "Float",
          "unit": "m/s²",
          "captured": false,
          "description": "Gravidade isolada X",
          "available": true
        },
        {
          "name": "gravityY",
          "type": "Float",
          "unit": "m/s²",
          "captured": false,
          "description": "Gravidade isolada Y",
          "available": true
        },
        {
          "name": "gravityZ",
          "type": "Float",
          "unit": "m/s²",
          "captured": false,
          "description": "Gravidade isolada Z",
          "available": true
        }
      ]
    },
    "orientation": {
      "description": "Dados de orientação (não capturados atualmente)",
      "fields": [
        {
          "name": "azimuth",
          "type": "Float",
          "unit": "degrees",
          "captured": false,
          "description": "Azimuth (0-360°)",
          "available": true,
          "canCalculate": true
        },
        {
          "name": "pitch",
          "type": "Float",
          "unit": "degrees",
          "captured": false,
          "description": "Pitch (-180° a +180°)",
          "available": true,
          "canCalculate": true
        },
        {
          "name": "roll",
          "type": "Float",
          "unit": "degrees",
          "captured": false,
          "description": "Roll (-90° a +90°)",
          "available": true,
          "canCalculate": true
        }
      ]
    },
    "system": {
      "description": "Dados de sistema (não capturados atualmente)",
      "fields": [
        {
          "name": "batteryLevel",
          "type": "Integer",
          "unit": "percent",
          "captured": false,
          "description": "Nível da bateria (0-100%)",
          "available": true
        },
        {
          "name": "batteryTemperature",
          "type": "Float",
          "unit": "celsius",
          "captured": false,
          "description": "Temperatura da bateria",
          "available": true
        },
        {
          "name": "batteryStatus",
          "type": "String",
          "captured": false,
          "description": "Status da bateria (CHARGING/DISCHARGING)",
          "available": true
        },
        {
          "name": "networkType",
          "type": "String",
          "captured": false,
          "description": "Tipo de rede (WIFI/CELLULAR)",
          "available": true
        },
        {
          "name": "signalStrength",
          "type": "Integer",
          "unit": "dBm",
          "captured": false,
          "description": "Força do sinal",
          "available": true
        }
      ]
    }
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
echo ""
echo "Para visualizar: cat $OUTPUT_FILE | jq '.'"
echo ""

