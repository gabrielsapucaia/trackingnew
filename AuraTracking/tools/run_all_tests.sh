#!/bin/bash
# =============================================================================
# AuraTracking - Executa Todos os Testes de Sensores
# =============================================================================
# Uso: ./run_all_tests.sh
#
# Executa todos os scripts de teste em sequência:
# 1. Inventário de sensores
# 2. Monitoramento de telemetria (60s)
# 3. Extração de dados atuais
# 4. Comparação e recomendações
#
# Todos os resultados são salvos em arquivos timestamped.
# =============================================================================

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="sensor_tests_${TIMESTAMP}"

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Verifica se scripts existem
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$SCRIPT_DIR/inventory_all_sensors.sh" ]; then
    print_error "Script inventory_all_sensors.sh não encontrado em $SCRIPT_DIR"
    exit 1
fi

# Cria diretório para resultados
mkdir -p "$RESULTS_DIR"
print_status "Resultados serão salvos em: $RESULTS_DIR"

# 1. Inventário de Sensores
print_section "1. INVENTÁRIO DE SENSORES"
"$SCRIPT_DIR/inventory_all_sensors.sh" -o "$RESULTS_DIR/inventory.json"
print_status "✓ Inventário completo"

# 2. Monitoramento de Telemetria
print_section "2. MONITORAMENTO DE TELEMETRIA"
print_warning "Isso levará 60 segundos. Coloque o dispositivo em movimento se possível."
"$SCRIPT_DIR/monitor_telemetry.sh" -d 60 -i 1 -o "$RESULTS_DIR/monitor.json"
print_status "✓ Monitoramento completo"

# 3. Extração de Dados Atuais
print_section "3. EXTRAÇÃO DE DADOS ATUAIS"
"$SCRIPT_DIR/extract_current_data.sh" -o "$RESULTS_DIR/current_data.json"
print_status "✓ Extração completa"

# 4. Comparação e Recomendações
print_section "4. COMPARAÇÃO E RECOMENDAÇÕES"
"$SCRIPT_DIR/compare_current_vs_available.sh" -o "$RESULTS_DIR/comparison.json"
print_status "✓ Comparação completa"

# Resumo
print_section "RESUMO"
echo "Todos os testes foram concluídos!"
echo ""
echo "Arquivos gerados em: $RESULTS_DIR/"
echo "  - inventory.json       - Lista de sensores disponíveis"
echo "  - monitor.json         - Dados coletados em tempo real"
echo "  - current_data.json    - Dados atualmente capturados"
echo "  - comparison.json      - Comparação e recomendações"
echo ""
echo "Para visualizar recomendações:"
echo "  cat $RESULTS_DIR/comparison.json | jq '.recommendations.critical'"
echo ""
echo "Para visualizar sensores disponíveis:"
echo "  cat $RESULTS_DIR/inventory.json | jq '.sensors[] | select(.available == true)'"
echo ""

