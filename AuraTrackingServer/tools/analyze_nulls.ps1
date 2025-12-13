# Script para analisar campos NULL no banco de dados
param(
    [int]$Hours = 1,
    [string]$OutputFile = "null_analysis_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Análise de Campos NULL"
Write-Host "=========================================="
Write-Host "Período: últimas $Hours hora(s)"
Write-Host ""

$query = @"
SELECT 
    COUNT(*) as total_records,
    -- GPS Detalhado
    COUNT(satellites) as has_satellites,
    COUNT(h_acc) as has_h_acc,
    COUNT(v_acc) as has_v_acc,
    COUNT(s_acc) as has_s_acc,
    COUNT(hdop) as has_hdop,
    COUNT(vdop) as has_vdop,
    COUNT(pdop) as has_pdop,
    COUNT(gps_timestamp) as has_gps_timestamp,
    -- IMU Detalhado
    COUNT(gyro_magnitude) as has_gyro_magnitude,
    COUNT(mag_x) as has_mag_x,
    COUNT(mag_y) as has_mag_y,
    COUNT(mag_z) as has_mag_z,
    COUNT(mag_magnitude) as has_mag_magnitude,
    COUNT(linear_accel_x) as has_linear_accel_x,
    COUNT(linear_accel_magnitude) as has_linear_accel_magnitude,
    COUNT(gravity_x) as has_gravity_x,
    COUNT(rotation_vector_x) as has_rotation_vector_x,
    -- Orientação
    COUNT(azimuth) as has_azimuth,
    COUNT(pitch) as has_pitch,
    COUNT(roll) as has_roll,
    -- Sistema - Bateria
    COUNT(battery_level) as has_battery_level,
    COUNT(battery_temperature) as has_battery_temperature,
    COUNT(battery_status) as has_battery_status,
    COUNT(battery_voltage) as has_battery_voltage,
    COUNT(battery_health) as has_battery_health,
    COUNT(battery_technology) as has_battery_technology,
    COUNT(battery_charge_counter) as has_battery_charge_counter,
    COUNT(battery_full_capacity) as has_battery_full_capacity,
    -- Sistema - WiFi
    COUNT(wifi_rssi) as has_wifi_rssi,
    COUNT(wifi_ssid) as has_wifi_ssid,
    COUNT(wifi_bssid) as has_wifi_bssid,
    COUNT(wifi_frequency) as has_wifi_frequency,
    COUNT(wifi_channel) as has_wifi_channel,
    -- Sistema - Celular
    COUNT(cellular_network_type) as has_cellular_network_type,
    COUNT(cellular_operator) as has_cellular_operator,
    COUNT(cellular_rsrp) as has_cellular_rsrp,
    COUNT(cellular_rsrq) as has_cellular_rsrq,
    COUNT(cellular_rssnr) as has_cellular_rssnr,
    COUNT(cellular_ci) as has_cellular_ci,
    COUNT(cellular_pci) as has_cellular_pci,
    COUNT(cellular_tac) as has_cellular_tac,
    COUNT(cellular_earfcn) as has_cellular_earfcn,
    COUNT(cellular_band) as has_cellular_band,
    COUNT(cellular_bandwidth) as has_cellular_bandwidth,
    -- Motion Detection
    COUNT(motion_significant_motion) as has_motion_significant_motion,
    COUNT(motion_stationary_detect) as has_motion_stationary_detect,
    COUNT(motion_motion_detect) as has_motion_motion_detect,
    COUNT(motion_flat_up) as has_motion_flat_up,
    COUNT(motion_flat_down) as has_motion_flat_down,
    COUNT(motion_stowed) as has_motion_stowed,
    COUNT(motion_display_rotate) as has_motion_display_rotate
FROM telemetry
WHERE time > NOW() - INTERVAL '$Hours hours';
"@

$result = docker compose exec -T timescaledb psql -U aura -d auratracking -c $query | ConvertFrom-Csv -Delimiter '|' | Select-Object -Skip 2 | Select-Object -First 1

$analysis = @{
    period_hours = $Hours
    timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    total_records = [int]$result.total_records
    fields = @{}
}

$fields = @(
    'satellites', 'h_acc', 'v_acc', 's_acc', 'hdop', 'vdop', 'pdop', 'gps_timestamp',
    'gyro_magnitude', 'mag_x', 'mag_y', 'mag_z', 'mag_magnitude',
    'linear_accel_x', 'linear_accel_magnitude', 'gravity_x', 'rotation_vector_x',
    'azimuth', 'pitch', 'roll',
    'battery_level', 'battery_temperature', 'battery_status', 'battery_voltage',
    'battery_health', 'battery_technology', 'battery_charge_counter', 'battery_full_capacity',
    'wifi_rssi', 'wifi_ssid', 'wifi_bssid', 'wifi_frequency', 'wifi_channel',
    'cellular_network_type', 'cellular_operator', 'cellular_rsrp', 'cellular_rsrq',
    'cellular_rssnr', 'cellular_ci', 'cellular_pci', 'cellular_tac',
    'cellular_earfcn', 'cellular_band', 'cellular_bandwidth',
    'motion_significant_motion', 'motion_stationary_detect', 'motion_motion_detect',
    'motion_flat_up', 'motion_flat_down', 'motion_stowed', 'motion_display_rotate'
)

foreach ($field in $fields) {
    $hasField = "has_$field"
    $count = [int]$result.$hasField
    $percent = if ($analysis.total_records -gt 0) { ($count / $analysis.total_records) * 100 } else { 0 }
    
    $analysis.fields[$field] = @{
        count = $count
        percent = [math]::Round($percent, 2)
        is_null = $count -eq 0
    }
}

$fullPath = Join-Path (Get-Location) $OutputFile
$analysis | ConvertTo-Json -Depth 3 | Out-File $fullPath -Encoding UTF8

Write-Host "Análise concluída!" -ForegroundColor Green
Write-Host "Resultado salvo em: $fullPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "Campos sempre NULL:" -ForegroundColor Yellow
$analysis.fields.GetEnumerator() | Where-Object { $_.Value.is_null } | ForEach-Object {
    Write-Host "  - $($_.Key)" -ForegroundColor Red
}

Write-Host ""
Write-Host "Campos parcialmente NULL:" -ForegroundColor Yellow
$analysis.fields.GetEnumerator() | Where-Object { -not $_.Value.is_null -and $_.Value.percent -lt 100 } | ForEach-Object {
    Write-Host "  - $($_.Key): $($_.Value.percent)% preenchido" -ForegroundColor Yellow
}



