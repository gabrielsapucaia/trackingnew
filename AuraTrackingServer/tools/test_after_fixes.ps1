# Script de teste completo após correções
param(
    [int]$WaitMinutes = 2
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Teste Completo Após Correções"
Write-Host "=========================================="
Write-Host ""
Write-Host "Aguardando $WaitMinutes minutos para coletar novos dados..."
Write-Host ""

Start-Sleep -Seconds ($WaitMinutes * 60)

# 1. Verificar se accel_magnitude está sendo salvo
Write-Host "1. Verificando accel_magnitude..." -ForegroundColor Yellow
$accelCheck = docker compose exec -T timescaledb psql -U aura -d auratracking -c "SELECT COUNT(*) as total, COUNT(accel_magnitude) as has_accel_mag, COUNT(CASE WHEN accel_magnitude IS NOT NULL THEN 1 END) as not_null FROM telemetry WHERE time > NOW() - INTERVAL '5 minutes';"
Write-Host $accelCheck
Write-Host ""

# Extrair valores para análise
$accelStats = docker compose exec -T timescaledb psql -U aura -d auratracking -t -c "SELECT COUNT(*) as total, COUNT(accel_magnitude) as has_value FROM telemetry WHERE time > NOW() - INTERVAL '5 minutes';" | ConvertFrom-Csv -Delimiter '|' | Select-Object -Skip 2 | Select-Object -First 1

if ($accelStats) {
    $total = [int]$accelStats.total
    $hasValue = [int]$accelStats.has_value
    $percent = if ($total -gt 0) { ($hasValue / $total) * 100 } else { 0 }
    
    if ($percent -eq 100) {
        Write-Host "✅ accel_magnitude: 100% dos registros têm valor!" -ForegroundColor Green
    } elseif ($percent -gt 0) {
        Write-Host "⚠️ accel_magnitude: $([math]::Round($percent, 1))% dos registros têm valor ($hasValue/$total)" -ForegroundColor Yellow
    } else {
        Write-Host "❌ accel_magnitude: Ainda está NULL em todos os registros" -ForegroundColor Red
    }
}

# Verificar valores de exemplo
Write-Host ""
Write-Host "Valores de exemplo de accel_magnitude:" -ForegroundColor Cyan
$examples = docker compose exec -T timescaledb psql -U aura -d auratracking -c "SELECT accel_x, accel_y, accel_z, accel_magnitude, raw_payload::json->'imu'->>'accelMagnitude' as payload_accel FROM telemetry WHERE time > NOW() - INTERVAL '5 minutes' AND accel_magnitude IS NOT NULL ORDER BY time DESC LIMIT 3;"
Write-Host $examples
Write-Host ""

# 2. Re-executar análise de NULLs
Write-Host "2. Re-executando análise de NULLs..." -ForegroundColor Yellow
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$scriptPath\analyze_nulls.ps1" -Hours 0.1 -OutputFile "null_analysis_after_fix.json"
Write-Host ""

# 3. Comparar payload vs banco novamente
Write-Host "3. Comparando payload vs banco..." -ForegroundColor Yellow
& "$scriptPath\compare_payload_db.ps1" -Samples 10
Write-Host ""

# 4. Gerar relatório comparativo
Write-Host "4. Gerando relatório comparativo..." -ForegroundColor Yellow

# Comparar antes vs depois
$beforeFile = Get-ChildItem "$scriptPath\null_analysis_*.json" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 1 -First 1
$afterFile = Get-ChildItem "$scriptPath\null_analysis_after_fix.json" | Select-Object -First 1

if ($beforeFile -and $afterFile) {
    Write-Host "Comparando:" -ForegroundColor Cyan
    Write-Host "  Antes: $($beforeFile.Name)"
    Write-Host "  Depois: $($afterFile.Name)"
    
    $before = Get-Content $beforeFile.FullName | ConvertFrom-Json
    $after = Get-Content $afterFile.FullName | ConvertFrom-Json
    
    Write-Host ""
    Write-Host "Campos que melhoraram:" -ForegroundColor Green
    $improved = @()
    foreach ($field in $after.fields.GetEnumerator()) {
        $fieldName = $field.Key
        $afterPercent = $field.Value.percent
        $beforeField = $before.fields.$fieldName
        if ($beforeField) {
            $beforePercent = $beforeField.percent
            if ($afterPercent -gt $beforePercent) {
                $improved += @{
                    field = $fieldName
                    before = $beforePercent
                    after = $afterPercent
                    improvement = $afterPercent - $beforePercent
                }
            }
        }
    }
    
    if ($improved.Count -gt 0) {
        $improved | Sort-Object improvement -Descending | ForEach-Object {
            Write-Host "  ✅ $($_.field): $($_.before)% → $($_.after)% (+$($_.improvement)%)" -ForegroundColor Green
        }
    } else {
        Write-Host "  Nenhum campo melhorou ainda (pode precisar de mais tempo)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "Teste completo concluído!" -ForegroundColor Green
Write-Host "=========================================="
Write-Host ""
Write-Host "Próximos passos recomendados:" -ForegroundColor Cyan
Write-Host "1. Se accel_magnitude ainda está NULL: verificar logs do ingest"
Write-Host "2. Se accel_magnitude está funcionando: verificar outros campos NULL"
Write-Host "3. Executar analyze_payload_fields.ps1 para ver campos não enviados"
Write-Host "4. Executar compare_expected_payload.ps1 para análise completa"



