# Script para analisar código Android e identificar campos não enviados
param(
    [string]$AndroidProjectPath = "D:\tracking\AuraTracking"
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Análise de Código Android"
Write-Host "=========================================="
Write-Host ""

# Campos esperados vs encontrados
$expectedFields = @{
    'gps' = @('satellites', 'hAcc', 'vAcc', 'sAcc', 'hdop', 'vdop', 'pdop', 'gpsTimestamp')
    'imu' = @('magX', 'magY', 'magZ', 'magMagnitude', 'linearAccelX', 'linearAccelY', 'linearAccelZ', 'linearAccelMagnitude', 'gravityX', 'gravityY', 'gravityZ', 'rotationVectorX', 'rotationVectorY', 'rotationVectorZ', 'rotationVectorW')
    'orientation' = @('pitch', 'roll')
    'system_battery' = @('level', 'temperature', 'status', 'voltage', 'health', 'technology')
    'system_wifi' = @('rssi', 'ssid', 'channel')
    'system_cellular' = @('networkType', 'operator', 'rsrp', 'rsrq', 'rssnr', 'tac', 'earfcn', 'band', 'bandwidth')
    'motion' = @('significantMotion', 'stationaryDetect', 'motionDetect', 'flatUp', 'flatDown', 'stowed', 'displayRotate')
}

# Verificar arquivos
$files = @{
    'GpsLocationProvider' = "$AndroidProjectPath\app\src\main\java\com\aura\tracking\sensors\gps\GpsLocationProvider.kt"
    'GpsData' = "$AndroidProjectPath\app\src\main\java\com\aura\tracking\sensors\gps\GpsData.kt"
    'ImuSensorProvider' = "$AndroidProjectPath\app\src\main\java\com\aura\tracking\sensors\imu\ImuSensorProvider.kt"
    'ImuData' = "$AndroidProjectPath\app\src\main\java\com\aura\tracking\sensors\imu\ImuData.kt"
    'OrientationProvider' = "$AndroidProjectPath\app\src\main\java\com\aura\tracking\sensors\orientation\OrientationProvider.kt"
    'OrientationData' = "$AndroidProjectPath\app\src\main\java\com\aura\tracking\sensors\orientation\OrientationData.kt"
    'SystemDataProvider' = "$AndroidProjectPath\app\src\main\java\com\aura\tracking\sensors\system\SystemDataProvider.kt"
    'SystemData' = "$AndroidProjectPath\app\src\main\java\com\aura\tracking\sensors\system\SystemData.kt"
    'MotionDetectorProvider' = "$AndroidProjectPath\app\src\main\java\com\aura\tracking\sensors\motion\MotionDetectorProvider.kt"
    'MotionDetectionData' = "$AndroidProjectPath\app\src\main\java\com\aura\tracking\sensors\motion\MotionDetectionData.kt"
    'TelemetryAggregator' = "$AndroidProjectPath\app\src\main\java\com\aura\tracking\background\TelemetryAggregator.kt"
}

$analysis = @{
    timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    files = @{}
    findings = @{}
}

# Analisar cada arquivo
foreach ($file in $files.GetEnumerator()) {
    $fileName = $file.Key
    $filePath = $file.Value
    
    Write-Host "Verificando: $fileName" -ForegroundColor Cyan
    
    if (-not (Test-Path $filePath)) {
        Write-Host "  ❌ Arquivo não encontrado: $filePath" -ForegroundColor Red
        $analysis.files[$fileName] = @{
            found = $false
            path = $filePath
        }
        continue
    }
    
    $content = Get-Content $filePath -Raw
    $analysis.files[$fileName] = @{
        found = $true
        path = $filePath
        size = $content.Length
    }
    
    # Análise específica por tipo de arquivo
    if ($fileName -eq 'GpsData') {
        Write-Host "  Analisando campos GPS..." -ForegroundColor Yellow
        foreach ($field in $expectedFields['gps']) {
            $found = $content -match "\b$field\b"
            $status = if ($found) { "✅" } else { "❌" }
            Write-Host "    $status $field" -ForegroundColor $(if ($found) { "Green" } else { "Red" })
        }
    }
    elseif ($fileName -eq 'ImuData') {
        Write-Host "  Analisando campos IMU..." -ForegroundColor Yellow
        foreach ($field in $expectedFields['imu']) {
            $found = $content -match "\b$field\b"
            $status = if ($found) { "✅" } else { "❌" }
            Write-Host "    $status $field" -ForegroundColor $(if ($found) { "Green" } else { "Red" })
        }
    }
    elseif ($fileName -eq 'OrientationData') {
        Write-Host "  Analisando campos de orientação..." -ForegroundColor Yellow
        foreach ($field in $expectedFields['orientation']) {
            $found = $content -match "\b$field\b"
            $status = if ($found) { "✅" } else { "❌" }
            Write-Host "    $status $field" -ForegroundColor $(if ($found) { "Green" } else { "Red" })
        }
    }
    elseif ($fileName -eq 'SystemData') {
        Write-Host "  Analisando campos de sistema..." -ForegroundColor Yellow
        # Verificar bateria
        foreach ($field in $expectedFields['system_battery']) {
            $found = $content -match "\b$field\b"
            $status = if ($found) { "✅" } else { "❌" }
            Write-Host "    $status battery.$field" -ForegroundColor $(if ($found) { "Green" } else { "Red" })
        }
    }
    elseif ($fileName -eq 'TelemetryAggregator') {
        Write-Host "  Analisando inclusão de campos no payload..." -ForegroundColor Yellow
        
        # Verificar se campos GPS estão sendo incluídos
        $gpsFieldsIncluded = @()
        foreach ($field in $expectedFields['gps']) {
            $found = $content -match "\b$field\s*="
            if ($found) {
                $gpsFieldsIncluded += $field
            }
        }
        Write-Host "    GPS detalhado incluído: $($gpsFieldsIncluded.Count)/$($expectedFields['gps'].Count)" -ForegroundColor $(if ($gpsFieldsIncluded.Count -eq $expectedFields['gps'].Count) { "Green" } else { "Yellow" })
        
        # Verificar se campos IMU estão sendo incluídos
        $imuFieldsIncluded = @()
        foreach ($field in $expectedFields['imu']) {
            $found = $content -match "\b$field\s*="
            if ($found) {
                $imuFieldsIncluded += $field
            }
        }
        Write-Host "    IMU detalhado incluído: $($imuFieldsIncluded.Count)/$($expectedFields['imu'].Count)" -ForegroundColor $(if ($imuFieldsIncluded.Count -eq $expectedFields['imu'].Count) { "Green" } else { "Yellow" })
        
        # Verificar se pitch e roll estão sendo incluídos
        $orientationFieldsIncluded = @()
        foreach ($field in $expectedFields['orientation']) {
            $found = $content -match "\b$field\s*="
            if ($found) {
                $orientationFieldsIncluded += $field
            }
        }
        Write-Host "    Orientação incluída: $($orientationFieldsIncluded.Count)/$($expectedFields['orientation'].Count)" -ForegroundColor $(if ($orientationFieldsIncluded.Count -eq $expectedFields['orientation'].Count) { "Green" } else { "Yellow" })
    }
    
    Write-Host ""
}

# Salvar relatório
$reportFile = "android_code_analysis_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
$analysis | ConvertTo-Json -Depth 5 | Out-File $reportFile -Encoding UTF8

Write-Host "Relatório salvo em: $reportFile" -ForegroundColor Cyan



