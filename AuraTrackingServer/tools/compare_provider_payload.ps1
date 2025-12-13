# Script para comparar campos capturados pelos providers com campos enviados no payload
param(
    [int]$Samples = 5
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Comparação Provider vs Payload"
Write-Host "=========================================="
Write-Host "Amostras: $Samples"
Write-Host ""

# Extrair payloads reais do banco
$query = @"
SELECT 
    raw_payload::json as payload
FROM telemetry
WHERE time > NOW() - INTERVAL '10 minutes'
ORDER BY time DESC
LIMIT $Samples;
"@

$payloads = docker compose exec -T timescaledb psql -U aura -d auratracking -t -c $query

if (-not $payloads -or $payloads.Count -eq 0) {
    Write-Host "Nenhum payload encontrado nos últimos 10 minutos" -ForegroundColor Yellow
    exit 0
}

# Analisar estrutura de um payload de exemplo
$payloadJson = $payloads[0] | ConvertFrom-Json

$comparison = @{
    timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    samples = $Samples
    sections = @{}
}

Write-Host "Analisando estrutura do payload..." -ForegroundColor Cyan
Write-Host ""

# GPS
if ($payloadJson.gps) {
    Write-Host "GPS:" -ForegroundColor Green
    $gpsFields = @{}
    $expectedGps = @('satellites', 'hAcc', 'vAcc', 'sAcc', 'hdop', 'vdop', 'pdop', 'gpsTimestamp')
    foreach ($field in $expectedGps) {
        $hasField = $null -ne $payloadJson.gps.$field
        $gpsFields[$field] = $hasField
        $status = if ($hasField) { "✅" } else { "❌" }
        Write-Host "  $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
    }
    $comparison.sections['gps'] = $gpsFields
} else {
    Write-Host "GPS: ❌ Seção não encontrada" -ForegroundColor Red
    $comparison.sections['gps'] = @{}
}

Write-Host ""

# IMU
if ($payloadJson.imu) {
    Write-Host "IMU:" -ForegroundColor Green
    $imuFields = @{}
    $expectedImu = @('magX', 'magY', 'magZ', 'magMagnitude', 'linearAccelX', 'linearAccelY', 'linearAccelZ', 'linearAccelMagnitude', 'gravityX', 'gravityY', 'gravityZ', 'rotationVectorX', 'rotationVectorY', 'rotationVectorZ', 'rotationVectorW')
    foreach ($field in $expectedImu) {
        $hasField = $null -ne $payloadJson.imu.$field
        $imuFields[$field] = $hasField
        $status = if ($hasField) { "✅" } else { "❌" }
        Write-Host "  $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
    }
    $comparison.sections['imu'] = $imuFields
} else {
    Write-Host "IMU: ❌ Seção não encontrada" -ForegroundColor Red
    $comparison.sections['imu'] = @{}
}

Write-Host ""

# Orientation
if ($payloadJson.orientation) {
    Write-Host "Orientation:" -ForegroundColor Green
    $orientationFields = @{}
    $expectedOrientation = @('pitch', 'roll')
    foreach ($field in $expectedOrientation) {
        $hasField = $null -ne $payloadJson.orientation.$field
        $orientationFields[$field] = $hasField
        $status = if ($hasField) { "✅" } else { "❌" }
        Write-Host "  $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
    }
    $comparison.sections['orientation'] = $orientationFields
} else {
    Write-Host "Orientation: ❌ Seção não encontrada" -ForegroundColor Red
    $comparison.sections['orientation'] = @{}
}

Write-Host ""

# System
if ($payloadJson.system) {
    Write-Host "System:" -ForegroundColor Green
    
    # Battery
    if ($payloadJson.system.battery) {
        Write-Host "  Battery:" -ForegroundColor Cyan
        $batteryFields = @{}
        $expectedBattery = @('level', 'temperature', 'status', 'voltage', 'health', 'technology')
        foreach ($field in $expectedBattery) {
            $hasField = $null -ne $payloadJson.system.battery.$field
            $batteryFields[$field] = $hasField
            $status = if ($hasField) { "✅" } else { "❌" }
            Write-Host "    $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
        }
        $comparison.sections['system_battery'] = $batteryFields
    }
    
    # WiFi
    if ($payloadJson.system.connectivity.wifi) {
        Write-Host "  WiFi:" -ForegroundColor Cyan
        $wifiFields = @{}
        $expectedWifi = @('rssi', 'ssid', 'channel')
        foreach ($field in $expectedWifi) {
            $hasField = $null -ne $payloadJson.system.connectivity.wifi.$field
            $wifiFields[$field] = $hasField
            $status = if ($hasField) { "✅" } else { "❌" }
            Write-Host "    $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
        }
        $comparison.sections['system_wifi'] = $wifiFields
    }
    
    # Cellular
    if ($payloadJson.system.connectivity.cellular) {
        Write-Host "  Cellular:" -ForegroundColor Cyan
        $cellularFields = @{}
        $expectedCellular = @('networkType', 'operator', 'rsrp', 'rsrq', 'rssnr', 'tac', 'earfcn', 'band', 'bandwidth')
        
        # Verificar campos diretos
        foreach ($field in @('networkType', 'operator')) {
            $hasField = $null -ne $payloadJson.system.connectivity.cellular.$field
            $cellularFields[$field] = $hasField
            $status = if ($hasField) { "✅" } else { "❌" }
            Write-Host "    $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
        }
        
        # Verificar signalStrength
        if ($payloadJson.system.connectivity.cellular.signalStrength) {
            foreach ($field in @('rsrp', 'rsrq', 'rssnr')) {
                $hasField = $null -ne $payloadJson.system.connectivity.cellular.signalStrength.$field
                $cellularFields[$field] = $hasField
                $status = if ($hasField) { "✅" } else { "❌" }
                Write-Host "    $status signalStrength.$field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
            }
        }
        
        # Verificar cellInfo
        if ($payloadJson.system.connectivity.cellular.cellInfo) {
            foreach ($field in @('tac', 'earfcn', 'band', 'bandwidth')) {
                $hasField = $null -ne $payloadJson.system.connectivity.cellular.cellInfo.$field
                $cellularFields[$field] = $hasField
                $status = if ($hasField) { "✅" } else { "❌" }
                Write-Host "    $status cellInfo.$field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
            }
        }
        
        $comparison.sections['system_cellular'] = $cellularFields
    }
}

Write-Host ""

# Motion
if ($payloadJson.motion) {
    Write-Host "Motion:" -ForegroundColor Green
    $motionFields = @{}
    $expectedMotion = @('significantMotion', 'stationaryDetect', 'motionDetect', 'flatUp', 'flatDown', 'stowed', 'displayRotate')
    foreach ($field in $expectedMotion) {
        $hasField = $null -ne $payloadJson.motion.$field
        $motionFields[$field] = $hasField
        $status = if ($hasField) { "✅" } else { "❌" }
        Write-Host "  $status $field" -ForegroundColor $(if ($hasField) { "Green" } else { "Red" })
    }
    $comparison.sections['motion'] = $motionFields
} else {
    Write-Host "Motion: ❌ Seção não encontrada" -ForegroundColor Red
    $comparison.sections['motion'] = @{}
}

# Salvar relatório
$reportFile = "provider_payload_comparison_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
$comparison | ConvertTo-Json -Depth 5 | Out-File $reportFile -Encoding UTF8

Write-Host ""
Write-Host "Relatório salvo em: $reportFile" -ForegroundColor Cyan



