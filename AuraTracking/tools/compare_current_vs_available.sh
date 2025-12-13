#!/bin/bash
# =============================================================================
# AuraTracking - Comparação: Dados Atuais vs Disponíveis
# =============================================================================
# Uso: ./compare_current_vs_available.sh [opções]
#
# Compara o que o app captura atualmente com o que está disponível
# no dispositivo. Gera relatório de gaps e oportunidades.
#
# Opções:
#   -o, --output    Arquivo de saída JSON (padrão: comparison_TIMESTAMP.json)
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
    OUTPUT_FILE="comparison_${TIMESTAMP}.json"
fi

print_status "Analisando gaps e oportunidades..."

# Verifica disponibilidade de sensores
SENSORS_DUMP=$(adb shell dumpsys sensorservice 2>/dev/null)

check_sensor() {
    SENSOR_NAME=$1
    echo "$SENSORS_DUMP" | grep -qi "$SENSOR_NAME" && echo "true" || echo "false"
}

ACCEL_AVAILABLE=$(check_sensor "accelerometer")
GYRO_AVAILABLE=$(check_sensor "gyroscope")
MAG_AVAILABLE=$(check_sensor "magnetometer")
PRESSURE_AVAILABLE=$(check_sensor "pressure")
GRAVITY_AVAILABLE=$(check_sensor "gravity")
LINEAR_ACCEL_AVAILABLE=$(check_sensor "linear.*acceleration")
ROTATION_VECTOR_AVAILABLE=$(check_sensor "rotation.*vector")

# Cria JSON de comparação
JSON_TEMP=$(mktemp)

cat > "$JSON_TEMP" <<EOF
{
  "device": {
    "model": "$DEVICE_MODEL",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  },
  "comparison": {
    "gps": {
      "currentlyCaptured": [
        "latitude", "longitude", "altitude", "speed", "bearing", "accuracy",
        "timestamp", "ageMs", "intervalSinceLastFixMs", "temporalQuality"
      ],
      "availableButNotCaptured": [
        {
          "field": "satellites",
          "priority": "HIGH",
          "reason": "Qualidade do fix GPS, confiabilidade da posição"
        },
        {
          "field": "hdop",
          "priority": "HIGH",
          "reason": "Precisão horizontal, filtrar dados ruins"
        },
        {
          "field": "vdop",
          "priority": "HIGH",
          "reason": "Precisão vertical, importante para altitude"
        },
        {
          "field": "pdop",
          "priority": "MEDIUM",
          "reason": "Precisão geral da posição"
        },
        {
          "field": "gpsTimestamp",
          "priority": "MEDIUM",
          "reason": "Timestamp do fix GPS (não do app)"
        }
      ]
    },
    "imu": {
      "currentlyCaptured": [
        "accelX", "accelY", "accelZ", "gyroX", "gyroY", "gyroZ"
      ],
      "availableButNotCaptured": [
        {
          "field": "magX",
          "sensorAvailable": $MAG_AVAILABLE,
          "priority": "CRITICAL",
          "reason": "Detectar direção real (mão vs contramão), calcular bearing preciso"
        },
        {
          "field": "magY",
          "sensorAvailable": $MAG_AVAILABLE,
          "priority": "CRITICAL",
          "reason": "Detectar direção real (mão vs contramão), calcular bearing preciso"
        },
        {
          "field": "magZ",
          "sensorAvailable": $MAG_AVAILABLE,
          "priority": "CRITICAL",
          "reason": "Detectar direção real (mão vs contramão), calcular bearing preciso"
        },
        {
          "field": "pressure",
          "sensorAvailable": $PRESSURE_AVAILABLE,
          "priority": "CRITICAL",
          "reason": "Altitude precisa (~1m vs ~10m GPS), detectar rampas, calcular inclinação"
        },
        {
          "field": "linearAccelX",
          "sensorAvailable": $LINEAR_ACCEL_AVAILABLE,
          "priority": "CRITICAL",
          "reason": "Aceleração real do veículo, detectar frenagens/acelerações bruscas"
        },
        {
          "field": "linearAccelY",
          "sensorAvailable": $LINEAR_ACCEL_AVAILABLE,
          "priority": "CRITICAL",
          "reason": "Aceleração real do veículo, detectar frenagens/acelerações bruscas"
        },
        {
          "field": "linearAccelZ",
          "sensorAvailable": $LINEAR_ACCEL_AVAILABLE,
          "priority": "CRITICAL",
          "reason": "Aceleração real do veículo, detectar frenagens/acelerações bruscas"
        },
        {
          "field": "gravityX",
          "sensorAvailable": $GRAVITY_AVAILABLE,
          "priority": "MEDIUM",
          "reason": "Detectar inclinação do veículo (redundante com barômetro)"
        },
        {
          "field": "gravityY",
          "sensorAvailable": $GRAVITY_AVAILABLE,
          "priority": "MEDIUM",
          "reason": "Detectar inclinação do veículo (redundante com barômetro)"
        },
        {
          "field": "gravityZ",
          "sensorAvailable": $GRAVITY_AVAILABLE,
          "priority": "MEDIUM",
          "reason": "Detectar inclinação do veículo (redundante com barômetro)"
        }
      ]
    },
    "orientation": {
      "currentlyCaptured": [],
      "availableButNotCaptured": [
        {
          "field": "azimuth",
          "canCalculate": true,
          "requires": ["accelerometer", "magnetometer"],
          "priority": "CRITICAL",
          "reason": "Direção do movimento, separar mão vs contramão"
        },
        {
          "field": "pitch",
          "canCalculate": true,
          "requires": ["accelerometer", "magnetometer"],
          "priority": "CRITICAL",
          "reason": "Inclinação frontal, detectar rampas"
        },
        {
          "field": "roll",
          "canCalculate": true,
          "requires": ["accelerometer", "magnetometer"],
          "priority": "CRITICAL",
          "reason": "Inclinação lateral, análise de curvas"
        }
      ]
    },
    "system": {
      "currentlyCaptured": [],
      "availableButNotCaptured": [
        {
          "field": "batteryLevel",
          "priority": "HIGH",
          "reason": "Detectar quando carregando (pode estar parado)"
        },
        {
          "field": "batteryStatus",
          "priority": "HIGH",
          "reason": "Filtrar dados quando dispositivo está carregando"
        },
        {
          "field": "batteryTemperature",
          "priority": "MEDIUM",
          "reason": "Monitorar saúde do dispositivo"
        },
        {
          "field": "networkType",
          "priority": "LOW",
          "reason": "Contexto de conectividade (debugging)"
        },
        {
          "field": "signalStrength",
          "priority": "LOW",
          "reason": "Qualidade de transmissão (debugging)"
        }
      ]
    }
  },
  "recommendations": {
    "critical": [
      {
        "sensor": "Magnetômetro",
        "available": $MAG_AVAILABLE,
        "fields": ["magX", "magY", "magZ"],
        "useCase": "Detectar direção real do movimento, separar mão vs contramão em rampas"
      },
      {
        "sensor": "Barômetro",
        "available": $PRESSURE_AVAILABLE,
        "fields": ["pressure"],
        "useCase": "Altitude precisa, detectar subidas/descidas, calcular inclinação"
      },
      {
        "sensor": "Aceleração Linear",
        "available": $LINEAR_ACCEL_AVAILABLE,
        "fields": ["linearAccelX", "linearAccelY", "linearAccelZ"],
        "useCase": "Aceleração real do veículo, detectar frenagens/acelerações bruscas"
      },
      {
        "calculation": "Orientação",
        "requires": ["accelerometer", "magnetometer"],
        "available": $([ "$ACCEL_AVAILABLE" = "true" ] && [ "$MAG_AVAILABLE" = "true" ] && echo "true" || echo "false"),
        "fields": ["azimuth", "pitch", "roll"],
        "useCase": "Direção e inclinação do veículo, análise de comportamento"
      },
      {
        "data": "GPS Detalhado",
        "fields": ["satellites", "hdop", "vdop"],
        "useCase": "Qualidade do fix GPS, filtrar dados ruins"
      },
      {
        "data": "Bateria",
        "fields": ["level", "status"],
        "useCase": "Filtrar dados quando dispositivo está carregando"
      }
    ],
    "optional": [
      {
        "sensor": "Gravidade Isolada",
        "available": $GRAVITY_AVAILABLE,
        "fields": ["gravityX", "gravityY", "gravityZ"],
        "useCase": "Backup para cálculo de inclinação (redundante com barômetro)"
      },
      {
        "sensor": "Rotação Vetorial",
        "available": $ROTATION_VECTOR_AVAILABLE,
        "fields": ["rotationVector"],
        "useCase": "Orientação 3D precisa (pode ser calculada)"
      },
      {
        "data": "Conectividade",
        "fields": ["networkType", "signalStrength"],
        "useCase": "Debugging e análise de qualidade de transmissão"
      }
    ],
    "notRecommended": [
      {
        "data": "Umidade Relativa",
        "reason": "Não afeta análise de movimento"
      },
      {
        "data": "Luminosidade",
        "reason": "Não afeta análise de movimento"
      },
      {
        "data": "CPU/Memória",
        "reason": "Dados de sistema não relevantes"
      },
      {
        "data": "Temperatura Ambiente",
        "reason": "Não afeta análise de movimento diretamente"
      }
    ]
  },
  "summary": {
    "totalFieldsCurrentlyCaptured": 16,
    "totalFieldsAvailableButNotCaptured": 25,
    "criticalFieldsMissing": 15,
    "sensorsAvailable": {
      "accelerometer": $ACCEL_AVAILABLE,
      "gyroscope": $GYRO_AVAILABLE,
      "magnetometer": $MAG_AVAILABLE,
      "pressure": $PRESSURE_AVAILABLE,
      "gravity": $GRAVITY_AVAILABLE,
      "linearAcceleration": $LINEAR_ACCEL_AVAILABLE,
      "rotationVector": $ROTATION_VECTOR_AVAILABLE
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

print_status "Comparação salva em: $OUTPUT_FILE"
echo ""
echo "=== RESUMO ==="
echo "Campos atualmente capturados: 16"
echo "Campos disponíveis mas não capturados: 25"
echo "Campos críticos faltando: 15"
echo ""
echo "Sensores disponíveis:"
echo "  Acelerômetro: $ACCEL_AVAILABLE"
echo "  Giroscópio: $GYRO_AVAILABLE"
echo "  Magnetômetro: $MAG_AVAILABLE"
echo "  Barômetro: $PRESSURE_AVAILABLE"
echo "  Gravidade: $GRAVITY_AVAILABLE"
echo "  Aceleração Linear: $LINEAR_ACCEL_AVAILABLE"
echo "  Rotação Vetorial: $ROTATION_VECTOR_AVAILABLE"
echo ""
echo "Para visualizar: cat $OUTPUT_FILE | jq '.'"
echo ""

