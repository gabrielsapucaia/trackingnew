# Script para comparar payload MQTT com dados extraídos no banco
param(
    [int]$Samples = 10
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Comparação Payload MQTT vs Banco"
Write-Host "=========================================="
Write-Host "Amostras: $Samples"
Write-Host ""

$query = @"
SELECT 
    time,
    device_id,
    raw_payload::json->'system'->'battery'->>'chargeCounter' as payload_battery_charge_counter,
    raw_payload::json->'system'->'battery'->>'fullCapacity' as payload_battery_full_capacity,
    raw_payload::json->'system'->'connectivity'->'wifi'->>'bssid' as payload_wifi_bssid,
    raw_payload::json->'system'->'connectivity'->'wifi'->>'frequency' as payload_wifi_frequency,
    raw_payload::json->'system'->'connectivity'->'cellular'->'cellInfo'->>'ci' as payload_cellular_ci,
    raw_payload::json->'system'->'connectivity'->'cellular'->'cellInfo'->>'pci' as payload_cellular_pci,
    raw_payload::json->'imu'->>'accelMagnitude' as payload_accel_magnitude,
    raw_payload::json->'imu'->>'gyroMagnitude' as payload_gyro_magnitude,
    battery_charge_counter,
    battery_full_capacity,
    wifi_bssid,
    wifi_frequency,
    cellular_ci,
    cellular_pci,
    accel_magnitude,
    gyro_magnitude
FROM telemetry
WHERE time > NOW() - INTERVAL '10 minutes'
ORDER BY time DESC
LIMIT $Samples;
"@

docker compose exec timescaledb psql -U aura -d auratracking -c $query

Write-Host ""
Write-Host "Análise:" -ForegroundColor Cyan
Write-Host "- Se payload tem valor mas coluna está NULL: problema no mapeamento Python"
Write-Host "- Se payload está NULL: app Android não está enviando o campo"
Write-Host "- Se ambos NULL: normal (dado não disponível)"



