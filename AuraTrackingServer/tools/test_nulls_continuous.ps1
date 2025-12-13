# Script para monitorar campos NULL continuamente
param(
    [int]$DurationMinutes = 5,
    [int]$IntervalSeconds = 30
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Monitoramento Contínuo de NULLs"
Write-Host "=========================================="
Write-Host "Duração: $DurationMinutes minutos"
Write-Host "Intervalo: $IntervalSeconds segundos"
Write-Host ""

$endTime = (Get-Date).AddMinutes($DurationMinutes)
$iteration = 0

while ((Get-Date) -lt $endTime) {
    $iteration++
    $now = Get-Date -Format 'HH:mm:ss'
    
    Write-Host "[$now] Iteração $iteration" -ForegroundColor Cyan
    
    $query = @"
SELECT 
    COUNT(*) as total,
    COUNT(battery_charge_counter) as battery_counter,
    COUNT(wifi_bssid) as wifi_bssid,
    COUNT(cellular_ci) as cellular_ci,
    COUNT(gyro_magnitude) as gyro_magnitude,
    COUNT(azimuth) as azimuth
FROM telemetry
WHERE time > NOW() - INTERVAL '2 minutes';
"@
    
    $result = docker compose exec -T timescaledb psql -U aura -d auratracking -c $query | ConvertFrom-Csv -Delimiter '|' | Select-Object -Skip 2 | Select-Object -First 1
    
    $total = [int]$result.total
    if ($total -gt 0) {
        $batteryPct = ([int]$result.battery_counter / $total) * 100
        $wifiPct = ([int]$result.wifi_bssid / $total) * 100
        $cellularPct = ([int]$result.cellular_ci / $total) * 100
        $gyroPct = ([int]$result.gyro_magnitude / $total) * 100
        $azimuthPct = ([int]$result.azimuth / $total) * 100
        
        Write-Host "  Total: $total | Battery: $([math]::Round($batteryPct, 1))% | WiFi: $([math]::Round($wifiPct, 1))% | Cellular: $([math]::Round($cellularPct, 1))% | Gyro: $([math]::Round($gyroPct, 1))% | Azimuth: $([math]::Round($azimuthPct, 1))%"
    } else {
        Write-Host "  Nenhum registro encontrado"
    }
    
    Start-Sleep -Seconds $IntervalSeconds
}

Write-Host ""
Write-Host "Monitoramento concluído!" -ForegroundColor Green



