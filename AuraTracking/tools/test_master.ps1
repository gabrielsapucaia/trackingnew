# Script Master para Teste e Monitoramento Completo
# Uso: .\test_master.ps1 [MQTT_HOST] [MQTT_PORT]

param(
    [string]$MQTT_HOST = "10.10.10.10",
    [int]$MQTT_PORT = 1883
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "TESTE COMPLETO - AuraTracking"
Write-Host "=========================================="
Write-Host ""

# FASE 1: Preparação do Ambiente
Write-Host "FASE 1: Preparação do Ambiente" -ForegroundColor Cyan
Write-Host "----------------------------------------"

# 1.1 Verificar Conexão ADB
Write-Host "1.1 Verificando conexão ADB..."
$devices = adb devices | Select-String -Pattern "device$"
if ($devices) {
    $deviceId = ($devices[0] -split '\s+')[0]
    Write-Host "✓ Dispositivo conectado: $deviceId" -ForegroundColor Green
    
    $model = adb shell getprop ro.product.model
    $androidVersion = adb shell getprop ro.build.version.release
    Write-Host "  Modelo: $model"
    Write-Host "  Android: $androidVersion"
} else {
    Write-Host "✗ Nenhum dispositivo conectado!" -ForegroundColor Red
    exit 1
}

# 1.2 Verificar App Instalado
Write-Host ""
Write-Host "1.2 Verificando app instalado..."
$appInstalled = adb shell pm list packages | Select-String -Pattern "com.aura.tracking"
if ($appInstalled) {
    Write-Host "✓ App instalado: com.aura.tracking" -ForegroundColor Green
    
    $version = adb shell dumpsys package com.aura.tracking | Select-String -Pattern "versionName" | Select-Object -First 1
    Write-Host "  Versão: $($version.ToString().Trim())"
    
    # Verifica serviço
    $serviceRunning = adb shell dumpsys activity services | Select-String -Pattern "TrackingForegroundService"
    if ($serviceRunning) {
        Write-Host "✓ Serviço de tracking está rodando" -ForegroundColor Green
    } else {
        Write-Host "⚠ Serviço NÃO está rodando - pode precisar iniciar o app" -ForegroundColor Yellow
    }
} else {
    Write-Host "✗ App NÃO instalado!" -ForegroundColor Red
    Write-Host "  Execute: cd ..\.. && .\gradlew installDebug"
    exit 1
}

# 1.3 Verificar MQTT Broker
Write-Host ""
Write-Host "1.3 Verificando MQTT Broker..."
$mosquittoSub = Get-Command mosquitto_sub -ErrorAction SilentlyContinue
if (-not $mosquittoSub) {
    Write-Host "⚠ mosquitto_sub não encontrado - usando Docker ou instale mosquitto-clients" -ForegroundColor Yellow
    Write-Host "  Para usar Docker: docker run -it --rm eclipse-mosquitto mosquitto_sub -h $MQTT_HOST -p $MQTT_PORT -t 'aura/tracking/#'"
} else {
    Write-Host "✓ mosquitto_sub disponível" -ForegroundColor Green
}

Write-Host ""
Write-Host "=========================================="
Write-Host "FASE 2: Monitoramento de Dados" -ForegroundColor Cyan
Write-Host "=========================================="
Write-Host ""
Write-Host "Iniciando monitoramento em 3 segundos..."
Write-Host "Pressione Ctrl+C para parar"
Start-Sleep -Seconds 3

# Cria diretório para logs
$logDir = "test_logs_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
Write-Host "Logs serão salvos em: $logDir"
Write-Host ""

# Limpa logcat anterior
adb logcat -c

# Inicia monitoramento de logcat em background
$logcatJob = Start-Job -ScriptBlock {
    param($logFile)
    adb logcat -v time GPS:* IMU:* OrientationProvider:* SystemDataProvider:* MotionDetectorProvider:* TelemetryAggregator:* TrackingService:* *:S | 
        Tee-Object -FilePath $logFile | 
        Select-String -Pattern "(GPS|IMU|Orientation|System|Motion|Telemetry|Tracking)"
} -ArgumentList "$logDir\logcat.txt"

Write-Host "✓ Logcat monitor iniciado (Job ID: $($logcatJob.Id))" -ForegroundColor Green

# Inicia monitoramento MQTT em background (se disponível)
$mqttJob = $null
if ($mosquittoSub) {
    $mqttJob = Start-Job -ScriptBlock {
        param($host, $port, $logFile)
        & mosquitto_sub -h $host -p $port -t "aura/tracking/#" -v | 
            Tee-Object -FilePath $logFile | 
            ForEach-Object {
                $line = $_
                $parts = $line -split ' ', 2
                $topic = $parts[0]
                $payload = if ($parts.Length -gt 1) { $parts[1] } else { "" }
                
                Write-Host "[MQTT] $(Get-Date -Format 'HH:mm:ss') - $topic"
                try {
                    $json = $payload | ConvertFrom-Json
                    Write-Host "  messageId: $($json.messageId)"
                    Write-Host "  transmissionMode: $($json.transmissionMode)"
                    if ($json.gps) { Write-Host "  GPS satellites: $($json.gps.satellites)" }
                    if ($json.imu) { Write-Host "  IMU accelMagnitude: $($json.imu.accelMagnitude)" }
                    if ($json.orientation) { Write-Host "  Orientation azimuth: $($json.orientation.azimuth)" }
                    if ($json.system) { Write-Host "  Battery: $($json.system.battery.level)%" }
                } catch {
                    Write-Host "  Payload: $payload"
                }
            }
    } -ArgumentList $MQTT_HOST, $MQTT_PORT, "$logDir\mqtt.txt"
    
    Write-Host "✓ MQTT monitor iniciado (Job ID: $($mqttJob.Id))" -ForegroundColor Green
} else {
    Write-Host "⚠ MQTT monitor não iniciado (mosquitto_sub não disponível)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=========================================="
Write-Host "Monitoramento Ativo" -ForegroundColor Green
Write-Host "=========================================="
Write-Host ""
Write-Host "Aguardando dados..."
Write-Host "Pressione Ctrl+C para parar e gerar relatório"
Write-Host ""

# Aguarda e monitora jobs
try {
    $startTime = Get-Date
    $sampleCount = 0
    
    while ($true) {
        Start-Sleep -Seconds 5
        
        # Verifica logcat
        $logcatOutput = Receive-Job -Job $logcatJob -ErrorAction SilentlyContinue
        if ($logcatOutput) {
            $logcatOutput | ForEach-Object {
                if ($_ -match "GPS|IMU|Orientation|System|Motion|Telemetry") {
                    Write-Host "[LOGCAT] $_" -ForegroundColor Cyan
                }
            }
        }
        
        # Verifica MQTT
        if ($mqttJob) {
            $mqttOutput = Receive-Job -Job $mqttJob -ErrorAction SilentlyContinue
            if ($mqttOutput) {
                $mqttOutput | ForEach-Object {
                    Write-Host "[MQTT] $_" -ForegroundColor Green
                    $sampleCount++
                }
            }
        }
        
        # Mostra estatísticas a cada 30 segundos
        $elapsed = (Get-Date) - $startTime
        if ($elapsed.TotalSeconds % 30 -lt 5) {
            Write-Host ""
            Write-Host "--- Estatísticas (Tempo: $([math]::Floor($elapsed.TotalSeconds))s, Amostras MQTT: $sampleCount) ---" -ForegroundColor Yellow
            Write-Host ""
        }
    }
} catch {
    Write-Host ""
    Write-Host "Parando monitoramento..." -ForegroundColor Yellow
} finally {
    # Para jobs
    if ($logcatJob) { Stop-Job -Job $logcatJob; Remove-Job -Job $logcatJob }
    if ($mqttJob) { Stop-Job -Job $mqttJob; Remove-Job -Job $mqttJob }
    
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "Relatório Final" -ForegroundColor Cyan
    Write-Host "=========================================="
    Write-Host ""
    Write-Host "Logs salvos em: $logDir"
    Write-Host "  - logcat.txt: Logs do Android"
    Write-Host "  - mqtt.txt: Mensagens MQTT capturadas"
    Write-Host ""
    Write-Host "Total de amostras MQTT capturadas: $sampleCount"
    Write-Host ""
    Write-Host "Para validar payloads:"
    Write-Host "  .\test_validate_payload.ps1 '$logDir\mqtt_sample.json'"
    Write-Host ""
}

