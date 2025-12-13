-- Migration: Adicionar novos campos de WiFi, CellInfo, Bateria e Motion Detection
-- Data: 2024-12-11
-- Descrição: Adiciona campos que o app Android está enviando mas não estavam no schema

-- WiFi adicional
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS wifi_bssid VARCHAR(20);
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS wifi_frequency INTEGER;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS wifi_channel INTEGER;

-- CellInfo detalhado
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS cellular_ci BIGINT;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS cellular_pci INTEGER;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS cellular_tac INTEGER;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS cellular_earfcn INTEGER;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS cellular_band INTEGER[];
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS cellular_bandwidth INTEGER;

-- Bateria adicional
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS battery_charge_counter BIGINT;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS battery_full_capacity BIGINT;

-- Motion Detection
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS motion_significant_motion BOOLEAN;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS motion_stationary_detect BOOLEAN;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS motion_motion_detect BOOLEAN;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS motion_flat_up BOOLEAN;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS motion_flat_down BOOLEAN;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS motion_stowed BOOLEAN;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS motion_display_rotate INTEGER;



