#!/bin/bash
# Script para validar que todas as novas colunas existem

docker compose exec -T timescaledb psql -U aura -d auratracking -c "
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'telemetry' 
AND column_name IN (
    'wifi_bssid', 'wifi_frequency', 'wifi_channel',
    'cellular_ci', 'cellular_pci', 'cellular_tac', 'cellular_earfcn', 'cellular_band', 'cellular_bandwidth',
    'battery_charge_counter', 'battery_full_capacity',
    'motion_significant_motion', 'motion_stationary_detect', 'motion_motion_detect',
    'motion_flat_up', 'motion_flat_down', 'motion_stowed', 'motion_display_rotate'
)
ORDER BY column_name;
"



