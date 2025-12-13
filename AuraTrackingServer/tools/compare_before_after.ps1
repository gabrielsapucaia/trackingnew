# Script para comparar análise antes vs depois das correções
param(
    [string]$BeforeFile = "null_analysis_final.json",
    [string]$AfterFile = "null_analysis_after_fix.json"
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Comparação Antes vs Depois"
Write-Host "=========================================="
Write-Host ""

if (-not (Test-Path $BeforeFile)) {
    Write-Host "Arquivo 'antes' não encontrado: $BeforeFile" -ForegroundColor Yellow
    Write-Host "Usando dados atuais do banco..." -ForegroundColor Yellow
    $beforeData = @{ fields = @{} }
} else {
    $beforeData = Get-Content $BeforeFile | ConvertFrom-Json
}

if (-not (Test-Path $AfterFile)) {
    Write-Host "Arquivo 'depois' não encontrado: $AfterFile" -ForegroundColor Red
    Write-Host "Execute analyze_nulls.ps1 primeiro!" -ForegroundColor Red
    exit 1
}

$afterData = Get-Content $AfterFile | ConvertFrom-Json

$comparison = @{
    timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    before = $beforeData
    after = $afterData
    improvements = @{}
    regressions = @{}
    unchanged = @{}
}

Write-Host "Analisando campos..." -ForegroundColor Cyan

foreach ($field in $afterData.fields.PSObject.Properties) {
    $fieldName = $field.Name
    $afterValue = $field.Value
    
    $beforeValue = $null
    if ($beforeData.fields.$fieldName) {
        $beforeValue = $beforeData.fields.$fieldName
    }
    
    $beforeCount = if ($beforeValue) { $beforeValue.count } else { 0 }
    $afterCount = $afterValue.count
    
    $beforePercent = if ($beforeValue) { $beforeValue.percent } else { 0 }
    $afterPercent = $afterValue.percent
    
    $improvement = $afterPercent - $beforePercent
    
    if ($improvement -gt 0) {
        $comparison.improvements[$fieldName] = @{
            before = $beforePercent
            after = $afterPercent
            improvement = [math]::Round($improvement, 2)
        }
    } elseif ($improvement -lt 0) {
        $comparison.regressions[$fieldName] = @{
            before = $beforePercent
            after = $afterPercent
            regression = [math]::Round($improvement, 2)
        }
    } else {
        $comparison.unchanged[$fieldName] = @{
            percent = $afterPercent
        }
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "Resumo da Comparação"
Write-Host "=========================================="
Write-Host ""

Write-Host "Campos que Melhoraram: $($comparison.improvements.Count)" -ForegroundColor Green
if ($comparison.improvements.Count -gt 0) {
    Write-Host ""
    $comparison.improvements.GetEnumerator() | Sort-Object { $_.Value.improvement } -Descending | Select-Object -First 10 | ForEach-Object {
        Write-Host "  ✅ $($_.Key): $($_.Value.before)% → $($_.Value.after)% (+$($_.Value.improvement)%)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Campos que Pioraram: $($comparison.regressions.Count)" -ForegroundColor $(if ($comparison.regressions.Count -gt 0) { "Red" } else { "Green" })
if ($comparison.regressions.Count -gt 0) {
    Write-Host ""
    $comparison.regressions.GetEnumerator() | ForEach-Object {
        Write-Host "  ❌ $($_.Key): $($_.Value.before)% → $($_.Value.after)% ($($_.Value.regression)%)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Campos Sem Mudança: $($comparison.unchanged.Count)" -ForegroundColor Yellow

# Campos críticos esperados
Write-Host ""
Write-Host "=========================================="
Write-Host "Campos Críticos Esperados"
Write-Host "=========================================="
Write-Host ""

$criticalFields = @{
    'cellular_network_type' = 'Tipo de rede celular'
    'cellular_operator' = 'Operadora celular'
    'cellular_rsrp' = 'RSRP celular'
    'cellular_rsrq' = 'RSRQ celular'
    'cellular_rssnr' = 'RSSNR celular'
    'battery_level' = 'Nível de bateria'
}

foreach ($critical in $criticalFields.GetEnumerator()) {
    $fieldName = $critical.Key
    $fieldDesc = $critical.Value
    
    $afterValue = $afterData.fields.$fieldName
    $beforeValue = if ($beforeData.fields.$fieldName) { $beforeData.fields.$fieldName } else { $null }
    
    $beforePercent = if ($beforeValue) { $beforeValue.percent } else { 0 }
    $afterPercent = if ($afterValue) { $afterValue.percent } else { 0 }
    $improvement = $afterPercent - $beforePercent
    
    $status = if ($afterPercent > 0) { "✅" } else { "❌" }
    $color = if ($improvement > 0) { "Green" } elseif ($improvement -eq 0 -and $afterPercent > 0) { "Green" } else { "Red" }
    
    Write-Host "  $status $fieldDesc ($fieldName): $beforePercent% → $afterPercent%" -ForegroundColor $color
    if ($improvement -ne 0) {
        Write-Host "    Mudança: $([math]::Round($improvement, 2))%" -ForegroundColor $(if ($improvement > 0) { "Green" } else { "Red" })
    }
}

# Salvar comparação
$outputFile = "comparison_before_after_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
$comparison | ConvertTo-Json -Depth 5 | Out-File $outputFile -Encoding UTF8

Write-Host ""
Write-Host "Comparação salva em: $outputFile" -ForegroundColor Cyan

