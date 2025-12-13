-- Migration: Adicionar campos de Sistema (Bateria, WiFi, Celular básico)
-- Data: 2024-12-11
-- Descrição: Adiciona campos de sistema que estavam no schema mas não foram aplicados no banco existente

-- Sistema - Bateria
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS battery_level INTEGER;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS battery_temperature DOUBLE PRECISION;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS battery_status VARCHAR(20);
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS battery_voltage INTEGER;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS battery_health VARCHAR(20);
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS battery_technology VARCHAR(20);

-- Sistema - WiFi básico
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS wifi_rssi INTEGER;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS wifi_ssid VARCHAR(100);

-- Sistema - Celular básico
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS cellular_network_type VARCHAR(20);
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS cellular_operator VARCHAR(50);
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS cellular_rsrp INTEGER;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS cellular_rsrq INTEGER;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS cellular_rssnr INTEGER;

-- Flag de transmissão
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS transmission_mode VARCHAR(10) DEFAULT 'online';



