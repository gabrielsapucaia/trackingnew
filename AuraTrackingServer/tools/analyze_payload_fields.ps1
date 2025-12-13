# Script para analisar campos presentes nos payloads MQTT
param(
    [int]$Samples = 10
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Análise de Campos nos Payloads MQTT"
Write-Host "=========================================="
Write-Host "Amostras: $Samples"
Write-Host ""

# Extrair um payload de exemplo
$query = @"
SELECT 
    raw_payload::json as payload
FROM telemetry
WHERE time > NOW() - INTERVAL '10 minutes'
ORDER BY time DESC
LIMIT 1;
"@

$payloadJson = docker compose exec -T timescaledb psql -U aura -d auratracking -t -c $query | ConvertFrom-Json

if (-not $payloadJson) {
    Write-Host "Nenhum payload encontrado nos últimos 10 minutos" -ForegroundColor Yellow
    exit 0
}

Write-Host "Estrutura do Payload:" -ForegroundColor Cyan
Write-Host ""

# Analisar cada seção
$sections = @{
    'gps' = @('lat', 'lon', 'alt', 'speed', 'bearing', 'accuracy', 'satellites', 'hAcc', 'vAcc', 'sAcc', 'hdop', 'vdop', 'pdop', 'gpsTimestamp')
    'imu' = @('accelX', 'accelY', 'accelZ', 'accelMagnitude', 'gyroX', 'gyroY', 'gyroZ', 'gyroMagnitude', 'magX', 'magY', 'magZ', 'magMagnitude', 'linearAccelX', 'linearAccelY', 'linearAccelZ', 'linearAccelMagnitude', 'gravityX', 'gravityY', 'gravityZ', 'rotationVectorX', 'rotationVectorY', 'rotationVectorZ', 'rotationVectorW')
    'orientation' = @('azimuth', 'pitch', 'roll')
    'system' = @{
        'battery' = @('level', 'temperature', 'status', 'voltage', 'health', 'technology', 'chargeCounter', 'fullCapacity')
        'connectivity' = @{
            'wifi' = @('rssi', 'ssid', 'bssid', 'frequency', 'channel')
            'cellular' = @{
                'signalStrength' = @('rsrp', 'rsrq', 'rssnr', 'rssi', 'level')
                'cellInfo' = @('ci', 'pci', 'tac', 'earfcn', 'band', 'bandwidth')
            }
        }
    }
    'motion' = @('significantMotion', 'stationaryDetect', 'motionDetect', 'flatUp', 'flatDown', 'stowed', 'displayRotate')
}

$report = @{
    timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    samples = $Samples
    sections = @{}
}

# GPS
if ($payloadJson.gps) {
    Write-Host "GPS:" -ForegroundColor Green
    $gpsFields = @{}
    foreach ($field in $sections['gps']) {
        $hasField = $null -ne $payloadJson.gps.$field
        $gpsFields[$field] = $hasField
        $status = if ($hasField) { "✅" } else { "❌" }
        Write-Host "  $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
    }
    $report.sections['gps'] = $gpsFields
} else {
    Write-Host "GPS: ❌ Seção não encontrada" -ForegroundColor Red
    $report.sections['gps'] = @{}
}

Write-Host ""

# IMU
if ($payloadJson.imu) {
    Write-Host "IMU:" -ForegroundColor Green
    $imuFields = @{}
    foreach ($field in $sections['imu']) {
        $hasField = $null -ne $payloadJson.imu.$field
        $imuFields[$field] = $hasField
        $status = if ($hasField) { "✅" } else { "❌" }
        Write-Host "  $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
    }
    $report.sections['imu'] = $imuFields
} else {
    Write-Host "IMU: ❌ Seção não encontrada" -ForegroundColor Red
    $report.sections['imu'] = @{}
}

Write-Host ""

# Orientation
if ($payloadJson.orientation) {
    Write-Host "Orientation:" -ForegroundColor Green
    $orientationFields = @{}
    foreach ($field in $sections['orientation']) {
        $hasField = $null -ne $payloadJson.orientation.$field
        $orientationFields[$field] = $hasField
        $status = if ($hasField) { "✅" } else { "❌" }
        Write-Host "  $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
    }
    $report.sections['orientation'] = $orientationFields
} else {
    Write-Host "Orientation: ❌ Seção não encontrada" -ForegroundColor Red
    $report.sections['orientation'] = @{}
}

Write-Host ""

# System
if ($payloadJson.system) {
    Write-Host "System:" -ForegroundColor Green
    
    # Battery
    if ($payloadJson.system.battery) {
        Write-Host "  Battery:" -ForegroundColor Cyan
        $batteryFields = @{}
        foreach ($field in $sections['system']['battery']) {
            $hasField = $null -ne $payloadJson.system.battery.$field
            $batteryFields[$field] = $hasField
            $status = if ($hasField) { "✅" } else { "❌" }
            Write-Host "    $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
        }
        $report.sections['system_battery'] = $batteryFields
    } else {
        Write-Host "  Battery: ❌ Seção não encontrada" -ForegroundColor Red
        $report.sections['system_battery'] = @{}
    }
    
    # Connectivity
    if ($payloadJson.system.connectivity) {
        Write-Host "  Connectivity:" -ForegroundColor Cyan
        
        # WiFi
        if ($payloadJson.system.connectivity.wifi) {
            Write-Host "    WiFi:" -ForegroundColor Yellow
            $wifiFields = @{}
            foreach ($field in $sections['system']['connectivity']['wifi']) {
                $hasField = $null -ne $payloadJson.system.connectivity.wifi.$field
                $wifiFields[$field] = $hasField
                $status = if ($hasField) { "✅" } else { "❌" }
                Write-Host "      $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
            }
            $report.sections['system_wifi'] = $wifiFields
        } else {
            Write-Host "    WiFi: ❌ Seção não encontrada" -ForegroundColor Red
            $report.sections['system_wifi'] = @{}
        }
        
        # Cellular
        if ($payloadJson.system.connectivity.cellular) {
            Write-Host "    Cellular:" -ForegroundColor Yellow
            
            # Signal Strength
            if ($payloadJson.system.connectivity.cellular.signalStrength) {
                Write-Host "      Signal Strength:" -ForegroundColor Gray
                $signalFields = @{}
                foreach ($field in $sections['system']['connectivity']['cellular']['signalStrength']) {
                    $hasField = $null -ne $payloadJson.system.connectivity.cellular.signalStrength.$field
                    $signalFields[$field] = $hasField
                    $status = if ($hasField) { "✅" } else { "❌" }
                    Write-Host "        $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
                }
                $report.sections['system_cellular_signal'] = $signalFields
            }
            
            # Cell Info
            if ($payloadJson.system.connectivity.cellular.cellInfo) {
                Write-Host "      Cell Info:" -ForegroundColor Gray
                $cellInfoFields = @{}
                foreach ($field in $sections['system']['connectivity']['cellular']['cellInfo']) {
                    $hasField = $null -ne $payloadJson.system.connectivity.cellular.cellInfo.$field
                    $cellInfoFields[$field] = $hasField
                    $status = if ($hasField) { "✅" } else { "❌" }
                    Write-Host "        $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
                }
                $report.sections['system_cellular_cellinfo'] = $cellInfoFields
            }
        }
    }
} else {
    Write-Host "System: ❌ Seção não encontrada" -ForegroundColor Red
    $report.sections['system'] = @{}
}

Write-Host ""

# Motion
if ($payloadJson.motion) {
    Write-Host "Motion:" -ForegroundColor Green
    $motionFields = @{}
    foreach ($field in $sections['motion']) {
        $hasField = $null -ne $payloadJson.motion.$field
        $motionFields[$field] = $hasField
        $status = if ($hasField) { "✅" } else { "❌" }
        Write-Host "  $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
    }
    $report.sections['motion'] = $motionFields
} else {
    Write-Host "Motion: ❌ Seção não encontrada" -ForegroundColor Red
    $report.sections['motion'] = @{}
}

# Salvar relatório
$reportFile = "payload_fields_analysis_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
$report | ConvertTo-Json -Depth 5 | Out-File $reportFile -Encoding UTF8

Write-Host ""
Write-Host "Relatório salvo em: $reportFile" -ForegroundColor Cyan



