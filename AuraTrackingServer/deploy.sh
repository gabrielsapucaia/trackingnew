#!/bin/bash
# ============================================================
# AuraTracking Server - Deploy Script
# ============================================================
# Script para deploy em Ubuntu Server
# ============================================================

set -e

echo "=============================================="
echo "  AuraTracking Server - Deploy"
echo "=============================================="

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não encontrado. Instalando...${NC}"
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo -e "${GREEN}✅ Docker instalado${NC}"
fi

# Verificar Docker Compose
if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose não encontrado.${NC}"
    echo "Por favor, instale o Docker Compose v2+"
    exit 1
fi

echo -e "${GREEN}✅ Docker e Docker Compose disponíveis${NC}"

# Diretório do projeto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Criar diretórios necessários
echo "📁 Criando diretórios..."
mkdir -p emqx/config
mkdir -p timescale/init
mkdir -p ingest/src
mkdir -p grafana/provisioning/datasources
mkdir -p grafana/provisioning/dashboards
mkdir -p grafana/dashboards

# Verificar arquivos
echo "📋 Verificando arquivos..."
REQUIRED_FILES=(
    "docker-compose.yml"
    "emqx/config/acl.conf"
    "timescale/init/01_schema.sql"
    "ingest/Dockerfile"
    "ingest/requirements.txt"
    "ingest/src/main.py"
    "grafana/provisioning/datasources/datasources.yml"
    "grafana/provisioning/dashboards/dashboards.yml"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file - FALTANDO!"
        exit 1
    fi
done

# Parar containers existentes
echo "🛑 Parando containers existentes..."
docker compose down 2>/dev/null || true

# Build das imagens
echo "🔨 Construindo imagens..."
docker compose build --no-cache

# Iniciar serviços
echo "🚀 Iniciando serviços..."
docker compose up -d

# Aguardar inicialização
echo "⏳ Aguardando serviços iniciarem..."
sleep 30

# Verificar status
echo ""
echo "=============================================="
echo "  Status dos Serviços"
echo "=============================================="
docker compose ps

# Verificar saúde
echo ""
echo "=============================================="
echo "  Health Checks"
echo "=============================================="

# EMQX
if curl -s http://localhost:18083/status > /dev/null 2>&1; then
    echo -e "${GREEN}✅ EMQX Dashboard: http://localhost:18083 (admin/aura2025)${NC}"
else
    echo -e "${YELLOW}⏳ EMQX ainda iniciando...${NC}"
fi

# TimescaleDB
if docker compose exec -T timescaledb pg_isready -U aura -d auratracking > /dev/null 2>&1; then
    echo -e "${GREEN}✅ TimescaleDB: localhost:5432${NC}"
else
    echo -e "${YELLOW}⏳ TimescaleDB ainda iniciando...${NC}"
fi

# Ingest
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ingest Worker: http://localhost:8080/health${NC}"
else
    echo -e "${YELLOW}⏳ Ingest Worker ainda iniciando...${NC}"
fi

# Grafana
if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Grafana: http://localhost:3000 (admin/aura2025)${NC}"
else
    echo -e "${YELLOW}⏳ Grafana ainda iniciando...${NC}"
fi

echo ""
echo "=============================================="
echo "  Configuração do App Android"
echo "=============================================="
echo ""
echo "Configure o app AuraTracking com:"
echo ""
echo "  MQTT Host:  $(hostname -I | awk '{print $1}')"
echo "  MQTT Port:  1883"
echo "  TLS:        false"
echo "  Topic Base: aura/tracking"
echo ""
echo "=============================================="
echo "  Deploy Concluído!"
echo "=============================================="
