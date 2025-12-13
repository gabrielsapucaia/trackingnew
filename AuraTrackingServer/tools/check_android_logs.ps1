# Script para verificar logs do app Android
param(
    [int]$DurationSeconds = 30
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Verificação de Logs do App Android"
Write-Host "=========================================="
Write-Host "Capturando logs por $DurationSeconds segundos..."
Write-Host ""

# Verificar se dispositivo está conectado
$devices = adb devices
$deviceConnected = $devices | Select-String -Pattern "device$" | Where-Object { $_ -notmatch "List of devices" }

if (-not $deviceConnected) {
    Write-Host "AVISO: Nenhum dispositivo Android conectado!" -ForegroundColor Yellow
    Write-Host "Pulando captura de logs..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Para conectar um dispositivo:" -ForegroundColor Cyan
    Write-Host "1. Conecte o dispositivo via USB"
    Write-Host "2. Ative 'Depuração USB' nas opções de desenvolvedor"
    Write-Host "3. Execute: adb devices"
    exit 0
}

Write-Host "Dispositivo conectado: $deviceConnected" -ForegroundColor Green
Write-Host ""

# Capturar logs relevantes
$logFile = "android_logs_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
Write-Host "Capturando logs em: $logFile" -ForegroundColor Cyan
Write-Host ""

# Limpar logs anteriores
adb logcat -c | Out-Null

# Capturar logs com timeout
$job = Start-Job -ScriptBlock {
    param($duration)
    adb logcat | Select-String -Pattern "TelemetryAggregator|ImuSensorProvider|GpsLocationProvider|SystemDataProvider|OrientationProvider|MotionDetectorProvider|AuraLog"
} -ArgumentList $DurationSeconds

Start-Sleep -Seconds $DurationSeconds
Stop-Job $job | Out-Null
Remove-Job $job | Out-Null

# Capturar logs de forma síncrona
Write-Host "Capturando logs relevantes..." -ForegroundColor Yellow
$logs = adb logcat -d | Select-String -Pattern "TelemetryAggregator|ImuSensorProvider|GpsLocationProvider|SystemDataProvider|OrientationProvider|MotionDetectorProvider|AuraLog" | Select-Object -Last 200

if ($logs) {
    $logs | Out-File $logFile -Encoding UTF8
    Write-Host ""
    Write-Host "Logs capturados:" -ForegroundColor Green
    Write-Host ""
    
    # Analisar padrões importantes
    $patterns = @{
        'TelemetryAggregator' = $logs | Select-String -Pattern "TelemetryAggregator"
        'ImuSensorProvider' = $logs | Select-String -Pattern "ImuSensorProvider"
        'GpsLocationProvider' = $logs | Select-String -Pattern "GpsLocationProvider"
        'SystemDataProvider' = $logs | Select-String -Pattern "SystemDataProvider"
        'OrientationProvider' = $logs | Select-String -Pattern "OrientationProvider"
        'MotionDetectorProvider' = $logs | Select-String -Pattern "MotionDetectorProvider"
        'Errors' = $logs | Select-String -Pattern "ERROR|Error|Exception|Crash"
        'Warnings' = $logs | Select-String -Pattern "WARN|Warning"
    }
    
    foreach ($pattern in $patterns.GetEnumerator()) {
        $count = ($pattern.Value | Measure-Object).Count
        if ($count -gt 0) {
            Write-Host "  $($pattern.Key): $count ocorrências" -ForegroundColor Cyan
        }
    }
    
    Write-Host ""
    Write-Host "Últimas 10 linhas relevantes:" -ForegroundColor Yellow
    $logs | Select-Object -Last 10 | ForEach-Object {
        Write-Host "  $_"
    }
    
    Write-Host ""
    Write-Host "Logs completos salvos em: $logFile" -ForegroundColor Cyan
} else {
    Write-Host "Nenhum log relevante encontrado" -ForegroundColor Yellow
    Write-Host "Verifique se o app está rodando e enviando dados" -ForegroundColor Yellow
}



