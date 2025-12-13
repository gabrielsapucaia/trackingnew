# Script de diagnóstico completo de campos NULL
param(
    [int]$Samples = 5
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Diagnóstico Completo de NULLs"
Write-Host "=========================================="
Write-Host ""

# 1. Pegar amostras recentes
Write-Host "1. Coletando amostras recentes..." -ForegroundColor Yellow
$query = @"
SELECT 
    time,
    device_id,
    raw_payload::json as payload_json
FROM telemetry
WHERE time > NOW() - INTERVAL '10 minutes'
ORDER BY time DESC
LIMIT $Samples;
"@

$samples = docker compose exec -T timescaledb psql -U aura -d auratracking -t -c $query

# 2. Analisar cada campo crítico
Write-Host "2. Analisando campos críticos..." -ForegroundColor Yellow

$criticalFields = @{
    'battery_charge_counter' = 'system.battery.chargeCounter'
    'battery_full_capacity' = 'system.battery.fullCapacity'
    'wifi_bssid' = 'system.connectivity.wifi.bssid'
    'wifi_frequency' = 'system.connectivity.wifi.frequency'
    'cellular_ci' = 'system.connectivity.cellular.cellInfo.ci'
    'gyro_magnitude' = 'imu.gyroMagnitude'
    'azimuth' = 'orientation.azimuth'
}

foreach ($field in $criticalFields.GetEnumerator()) {
    $dbField = $field.Key
    $jsonPath = $field.Value
    
    Write-Host ""
    Write-Host "Campo: $dbField" -ForegroundColor Cyan
    Write-Host "  Path JSON: $jsonPath"
    
    # Verificar no banco
    $dbQuery = "SELECT COUNT(*) as total, COUNT($dbField) as has_value FROM telemetry WHERE time > NOW() - INTERVAL '10 minutes';"
    $dbResult = docker compose exec -T timescaledb psql -U aura -d auratracking -t -c $dbQuery
    
    Write-Host "  Banco: $dbResult"
}

# 3. Verificar logs do ingest para erros
Write-Host ""
Write-Host "3. Verificando logs do ingest..." -ForegroundColor Yellow
docker compose logs --tail=50 ingest | Select-String -Pattern "error|Error|ERROR|warning|Warning" | Select-Object -Last 10

Write-Host ""
Write-Host "Diagnóstico concluído!" -ForegroundColor Green



