#!/bin/bash
# Script para aplicar migration no TimescaleDB

set -e

echo "Aplicando migration 02_add_new_fields.sql..."

docker compose exec -T timescaledb psql -U aura -d auratracking < timescale/migrations/02_add_new_fields.sql

echo "Migration aplicada com sucesso!"



