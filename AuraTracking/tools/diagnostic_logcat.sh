#!/bin/bash
# =============================================================================
# AuraTracking - Script de Diagnóstico de Campo
# =============================================================================
# Uso: ./diagnostic_logcat.sh [opções]
#
# Opções:
#   -f, --full      Captura log completo (todas as tags)
#   -g, --gps       Apenas logs de GPS
#   -m, --mqtt      Apenas logs de MQTT
#   -s, --service   Apenas logs do serviço
#   -w, --watchdog  Apenas logs do watchdog
#   -q, --queue     Apenas logs da fila
#   -c, --clear     Limpa buffer de log antes de capturar
#   -o, --output    Arquivo de saída (padrão: aura_diag_TIMESTAMP.log)
#   -h, --help      Mostra esta ajuda
# =============================================================================

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PACKAGE="com.aura.tracking"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE=""
CLEAR_LOG=false
FILTER_MODE="full"

# Tags do AuraTracking
TAGS_ALL="AuraLog:V GpsLocationProvider:V ImuSensorProvider:V MqttClientManager:V TrackingService:V QueueFlushWorker:V ServiceWatchdogWorker:V TelemetryAggregator:V"
TAGS_GPS="AuraLog:V GpsLocationProvider:V *:S"
TAGS_MQTT="AuraLog:V MqttClientManager:V *:S"
TAGS_SERVICE="AuraLog:V TrackingService:V *:S"
TAGS_WATCHDOG="AuraLog:V ServiceWatchdogWorker:V *:S"
TAGS_QUEUE="AuraLog:V QueueFlushWorker:V TelemetryAggregator:V *:S"

print_help() {
    head -24 "$0" | tail -20
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
        -f|--full)
            FILTER_MODE="full"
            shift
            ;;
        -g|--gps)
            FILTER_MODE="gps"
            shift
            ;;
        -m|--mqtt)
            FILTER_MODE="mqtt"
            shift
            ;;
        -s|--service)
            FILTER_MODE="service"
            shift
            ;;
        -w|--watchdog)
            FILTER_MODE="watchdog"
            shift
            ;;
        -q|--queue)
            FILTER_MODE="queue"
            shift
            ;;
        -c|--clear)
            CLEAR_LOG=true
            shift
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

DEVICE_INFO=$(adb shell getprop ro.product.model 2>/dev/null || echo "Unknown")
print_status "Dispositivo conectado: $DEVICE_INFO"

# Define arquivo de saída
if [ -z "$OUTPUT_FILE" ]; then
    OUTPUT_FILE="aura_diag_${FILTER_MODE}_${TIMESTAMP}.log"
fi

# Limpa buffer se solicitado
if [ "$CLEAR_LOG" = true ]; then
    print_status "Limpando buffer de log..."
    adb logcat -c
fi

# Seleciona tags baseado no modo
case $FILTER_MODE in
    full)
        TAGS="$TAGS_ALL"
        print_status "Modo: Log completo"
        ;;
    gps)
        TAGS="$TAGS_GPS"
        print_status "Modo: Apenas GPS"
        ;;
    mqtt)
        TAGS="$TAGS_MQTT"
        print_status "Modo: Apenas MQTT"
        ;;
    service)
        TAGS="$TAGS_SERVICE"
        print_status "Modo: Apenas Serviço"
        ;;
    watchdog)
        TAGS="$TAGS_WATCHDOG"
        print_status "Modo: Apenas Watchdog"
        ;;
    queue)
        TAGS="$TAGS_QUEUE"
        print_status "Modo: Apenas Fila"
        ;;
esac

print_status "Salvando em: $OUTPUT_FILE"
print_status "Pressione Ctrl+C para parar..."
echo ""
echo "=========================================="
echo " AuraTracking Diagnostic Log"
echo " Device: $DEVICE_INFO"
echo " Started: $(date)"
echo " Mode: $FILTER_MODE"
echo "=========================================="
echo ""

# Captura logs
if [ "$FILTER_MODE" = "full" ]; then
    # Log completo do app
    adb logcat -v time $TAGS 2>&1 | tee "$OUTPUT_FILE"
else
    # Log filtrado
    adb logcat -v time $TAGS 2>&1 | tee "$OUTPUT_FILE"
fi

print_status "Log salvo em: $OUTPUT_FILE"
