# Script para comparar payload esperado vs real
param(
    [int]$Samples = 5
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Comparação Payload Esperado vs Real"
Write-Host "=========================================="
Write-Host "Amostras: $Samples"
Write-Host ""

# Campos esperados (baseado na estrutura definida)
$expectedFields = @{
    'gps' = @('lat', 'lon', 'alt', 'speed', 'bearing', 'accuracy', 'satellites', 'hAcc', 'vAcc', 'sAcc', 'hdop', 'vdop', 'pdop', 'gpsTimestamp')
    'imu' = @('accelX', 'accelY', 'accelZ', 'accelMagnitude', 'gyroX', 'gyroY', 'gyroZ', 'gyroMagnitude', 'magX', 'magY', 'magZ', 'magMagnitude', 'linearAccelX', 'linearAccelY', 'linearAccelZ', 'linearAccelMagnitude', 'gravityX', 'gravityY', 'gravityZ', 'rotationVectorX', 'rotationVectorY', 'rotationVectorZ', 'rotationVectorW')
    'orientation' = @('azimuth', 'pitch', 'roll')
    'system_battery' = @('level', 'temperature', 'status', 'voltage', 'health', 'technology', 'chargeCounter', 'fullCapacity')
    'system_wifi' = @('rssi', 'ssid', 'bssid', 'frequency', 'channel')
    'system_cellular_signal' = @('rsrp', 'rsrq', 'rssnr', 'rssi', 'level')
    'system_cellular_cellinfo' = @('ci', 'pci', 'tac', 'earfcn', 'band', 'bandwidth')
    'motion' = @('significantMotion', 'stationaryDetect', 'motionDetect', 'flatUp', 'flatDown', 'stowed', 'displayRotate')
}

# Extrair payloads reais
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

$comparison = @{
    timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    samples = $Samples
    sections = @{}
}

# Analisar cada seção
foreach ($section in $expectedFields.GetEnumerator()) {
    $sectionName = $section.Key
    $expected = $section.Value
    $found = @()
    $missing = @()
    
    Write-Host "Seção: $sectionName" -ForegroundColor Cyan
    
    # Extrair caminho JSON baseado no nome da seção
    $jsonPath = $sectionName -replace 'system_', 'system.' -replace '_', '.'
    
    foreach ($field in $expected) {
        # Construir query JSON para verificar campo
        $fieldPath = if ($jsonPath -eq 'gps' -or $jsonPath -eq 'imu' -or $jsonPath -eq 'orientation' -or $jsonPath -eq 'motion') {
            "'$jsonPath'->>'$field'"
        } else {
            "'system'->'$($jsonPath -replace 'system\.', '')'->>'$field'"
        }
        
        $checkQuery = "SELECT COUNT(*) FROM telemetry WHERE time > NOW() - INTERVAL '10 minutes' AND raw_payload::json->$fieldPath IS NOT NULL LIMIT $Samples;"
        $count = docker compose exec -T timescaledb psql -U aura -d auratracking -t -c $checkQuery
        
        if ([int]$count -gt 0) {
            $found += $field
            Write-Host "  ✅ $field" -ForegroundColor Green
        } else {
            $missing += $field
            Write-Host "  ❌ $field" -ForegroundColor Red
        }
    }
    
    $comparison.sections[$sectionName] = @{
        expected = $expected.Count
        found = $found.Count
        missing = $missing.Count
        found_fields = $found
        missing_fields = $missing
        coverage = if ($expected.Count -gt 0) { [math]::Round(($found.Count / $expected.Count) * 100, 2) } else { 0 }
    }
    
    Write-Host "  Cobertura: $($comparison.sections[$sectionName].coverage)% ($($found.Count)/$($expected.Count))" -ForegroundColor $(if ($comparison.sections[$sectionName].coverage -ge 80) { "Green" } elseif ($comparison.sections[$sectionName].coverage -ge 50) { "Yellow" } else { "Red" })
    Write-Host ""
}

# Resumo geral
Write-Host "=========================================="
Write-Host "Resumo Geral" -ForegroundColor Cyan
Write-Host "=========================================="

$totalExpected = ($expectedFields.Values | Measure-Object -Sum).Sum
$totalFound = ($comparison.sections.Values | ForEach-Object { $_.found } | Measure-Object -Sum).Sum
$totalCoverage = if ($totalExpected -gt 0) { [math]::Round(($totalFound / $totalExpected) * 100, 2) } else { 0 }

Write-Host "Total de campos esperados: $totalExpected"
Write-Host "Total de campos encontrados: $totalFound"
Write-Host "Cobertura geral: $totalCoverage%" -ForegroundColor $(if ($totalCoverage -ge 80) { "Green" } elseif ($totalCoverage -ge 50) { "Yellow" } else { "Red" })
Write-Host ""

# Seções com baixa cobertura
Write-Host "Seções com baixa cobertura (< 50%):" -ForegroundColor Yellow
foreach ($section in $comparison.sections.GetEnumerator()) {
    if ($section.Value.coverage -lt 50) {
        Write-Host "  - $($section.Key): $($section.Value.coverage)% ($($section.Value.missing) campos faltando)" -ForegroundColor Red
    }
}

# Salvar relatório
$reportFile = "payload_comparison_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
$comparison | ConvertTo-Json -Depth 5 | Out-File $reportFile -Encoding UTF8

Write-Host ""
Write-Host "Relatório salvo em: $reportFile" -ForegroundColor Cyan



