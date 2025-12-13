# Script master para executar todos os testes de diagnóstico de NULLs
param(
    [int]$Hours = 1,
    [int]$Samples = 10,
    [int]$DurationMinutes = 5,
    [int]$IntervalSeconds = 30,
    [switch]$SkipContinuous = $false
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Execução Completa de Diagnóstico de NULLs"
Write-Host "=========================================="
Write-Host ""

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputDir = Join-Path $scriptPath "null_diagnostics_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

Write-Host "Diretório de saída: $outputDir" -ForegroundColor Cyan
Write-Host ""

# 1. Análise inicial
Write-Host "=========================================="
Write-Host "1. Executando análise inicial de NULLs..."
Write-Host "=========================================="
$analysisFile = Join-Path $outputDir "null_analysis.json"
& "$scriptPath\analyze_nulls.ps1" -Hours $Hours -OutputFile $analysisFile
Write-Host ""

# 2. Comparação payload vs banco
Write-Host "=========================================="
Write-Host "2. Comparando payload MQTT com banco..."
Write-Host "=========================================="
$compareOutput = & "$scriptPath\compare_payload_db.ps1" -Samples $Samples
$compareOutput | Out-File (Join-Path $outputDir "payload_comparison.txt") -Encoding UTF8
Write-Host ""

# 3. Diagnóstico detalhado
Write-Host "=========================================="
Write-Host "3. Executando diagnóstico detalhado..."
Write-Host "=========================================="
$diagnoseOutput = & "$scriptPath\diagnose_nulls.ps1" -Samples $Samples
$diagnoseOutput | Out-File (Join-Path $outputDir "detailed_diagnosis.txt") -Encoding UTF8
Write-Host ""

# 4. Monitoramento contínuo (opcional)
if (-not $SkipContinuous) {
    Write-Host "=========================================="
    Write-Host "4. Monitoramento contínuo de NULLs..."
    Write-Host "=========================================="
    Write-Host "Pressione Ctrl+C para interromper antes do tempo"
    Write-Host ""
    $continuousOutput = & "$scriptPath\test_nulls_continuous.ps1" -DurationMinutes $DurationMinutes -IntervalSeconds $IntervalSeconds
    $continuousOutput | Out-File (Join-Path $outputDir "continuous_monitoring.txt") -Encoding UTF8
    Write-Host ""
}

Write-Host "=========================================="
Write-Host "Diagnóstico Completo Concluído!" -ForegroundColor Green
Write-Host "=========================================="
Write-Host ""
Write-Host "Resultados salvos em: $outputDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "Próximos passos:" -ForegroundColor Yellow
Write-Host "1. Revisar null_analysis.json para identificar campos sempre NULL"
Write-Host "2. Revisar payload_comparison.txt para verificar mapeamento"
Write-Host "3. Revisar detailed_diagnosis.txt para diagnóstico completo"
if (-not $SkipContinuous) {
    Write-Host "4. Revisar continuous_monitoring.txt para padrões temporais"
}



