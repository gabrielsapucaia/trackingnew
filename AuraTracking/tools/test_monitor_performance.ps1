# Script para monitorar performance, memória e mensagens MQTT
# Uso: .\test_monitor_performance.ps1 [MQTT_HOST] [MQTT_PORT] [DURATION_SECONDS]

param(
    [string]$MQTT_HOST = "10.10.10.10",
    [int]$MQTT_PORT = 1883,
    [int]$DURATION_SECONDS = 60
)

$PACKAGE = "com.aura.tracking"
$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Monitor de Performance - AuraTracking"
Write-Host "=========================================="
Write-Host "Duração: $DURATION_SECONDS segundos"
Write-Host ""

# Verifica se app está rodando
$process = adb shell "ps -A | grep $PACKAGE"
if (-not $process) {
    Write-Host "⚠ App não está rodando!" -ForegroundColor Yellow
    Write-Host "Inicie o app manualmente no dispositivo"
    exit 1
}

Write-Host "✓ App está rodando" -ForegroundColor Green
Write-Host ""

# Limpa logcat
adb logcat -c

# Estatísticas
$stats = @{
    mqttMessages = 0
    queuedMessages = 0
    memorySamples = @()
    cpuSamples = @()
    startTime = Get-Date
}

# Função para capturar estatísticas de memória
function Get-MemoryStats {
    $meminfo = adb shell dumpsys meminfo $PACKAGE
    $total = ($meminfo | Select-String -Pattern "TOTAL PSS:\s+(\d+)").Matches.Groups[1].Value
    $native = ($meminfo | Select-String -Pattern "Native Heap:\s+(\d+)").Matches.Groups[1].Value
    $dalvik = ($meminfo | Select-String -Pattern "Dalvik Heap:\s+(\d+)").Matches.Groups[1].Value
    
    return @{
        TotalMB = if ($total) { [math]::Round([int]$total / 1024, 2) } else { 0 }
        NativeMB = if ($native) { [math]::Round([int]$native / 1024, 2) } else { 0 }
        DalvikMB = if ($dalvik) { [math]::Round([int]$dalvik / 1024, 2) } else { 0 }
        Timestamp = Get-Date
    }
}

# Função para capturar CPU
function Get-CpuStats {
    $top = adb shell "top -n 1 -d 1 | grep $PACKAGE"
    if ($top) {
        $parts = $top -split '\s+'
        $cpu = $parts[8] -replace '%', ''
        return [double]$cpu
    }
    return 0
}

# Monitora MQTT em background (se disponível)
$mosquittoSub = Get-Command mosquitto_sub -ErrorAction SilentlyContinue
$mqttJob = $null
if ($mosquittoSub) {
    $mqttJob = Start-Job -ScriptBlock {
        param($host, $port)
        & mosquitto_sub -h $host -p $port -t "aura/tracking/#" -C 1000 2>&1 | ForEach-Object {
            Write-Output $_
        }
    } -ArgumentList $MQTT_HOST, $MQTT_PORT
    
    Write-Host "✓ Monitor MQTT iniciado" -ForegroundColor Green
} else {
    Write-Host "⚠ mosquitto_sub não disponível - pulando monitoramento MQTT" -ForegroundColor Yellow
}

# Monitora logcat em background
$logcatJob = Start-Job -ScriptBlock {
    adb logcat -v time TelemetryAggregator:* MQTT:* Service:* *:S 2>&1 | ForEach-Object {
        Write-Output $_
    }
}

Write-Host "✓ Monitor logcat iniciado" -ForegroundColor Green
Write-Host ""
Write-Host "Coletando dados..." -ForegroundColor Cyan
Write-Host ""

$endTime = (Get-Date).AddSeconds($DURATION_SECONDS)
$lastMemoryCheck = Get-Date
$lastCpuCheck = Get-Date
$lastStatsDisplay = Get-Date

while ((Get-Date) -lt $endTime) {
    Start-Sleep -Seconds 2
    
    # Coleta memória a cada 5 segundos
    if (((Get-Date) - $lastMemoryCheck).TotalSeconds -ge 5) {
        $memStats = Get-MemoryStats
        $stats.memorySamples += $memStats
        $lastMemoryCheck = Get-Date
    }
    
    # Coleta CPU a cada 3 segundos
    if (((Get-Date) - $lastCpuCheck).TotalSeconds -ge 3) {
        $cpu = Get-CpuStats
        $stats.cpuSamples += @{ CPU = $cpu; Timestamp = Get-Date }
        $lastCpuCheck = Get-Date
    }
    
    # Processa logcat
    $logcatOutput = Receive-Job -Job $logcatJob -ErrorAction SilentlyContinue
    if ($logcatOutput) {
        foreach ($line in $logcatOutput) {
            if ($line -match "Publishing telemetry|Telemetry sent") {
                $stats.mqttMessages++
            }
            if ($line -match "Queuing|queued") {
                $stats.queuedMessages++
            }
        }
    }
    
    # Processa MQTT
    if ($mqttJob) {
        $mqttOutput = Receive-Job -Job $mqttJob -ErrorAction SilentlyContinue
        if ($mqttOutput) {
            $stats.mqttMessages += ($mqttOutput | Measure-Object).Count
        }
    }
    
    # Exibe estatísticas a cada 10 segundos
    if (((Get-Date) - $lastStatsDisplay).TotalSeconds -ge 10) {
        $elapsed = ((Get-Date) - $stats.startTime).TotalSeconds
        $avgMemory = if ($stats.memorySamples.Count -gt 0) {
            ($stats.memorySamples | Measure-Object -Property TotalMB -Average).Average
        } else { 0 }
        $maxMemory = if ($stats.memorySamples.Count -gt 0) {
            ($stats.memorySamples | Measure-Object -Property TotalMB -Maximum).Maximum
        } else { 0 }
        $avgCpu = if ($stats.cpuSamples.Count -gt 0) {
            ($stats.cpuSamples | Measure-Object -Property CPU -Average).Average
        } else { 0 }
        $maxCpu = if ($stats.cpuSamples.Count -gt 0) {
            ($stats.cpuSamples | Measure-Object -Property CPU -Maximum).Maximum
        } else { 0 }
        
        Write-Host "--- Estatísticas (${elapsed}s) ---" -ForegroundColor Yellow
        Write-Host "  Mensagens MQTT: $($stats.mqttMessages)"
        Write-Host "  Mensagens em Fila: $($stats.queuedMessages)"
        Write-Host "  Memória Média: $([math]::Round($avgMemory, 2)) MB"
        Write-Host "  Memória Máxima: $([math]::Round($maxMemory, 2)) MB"
        Write-Host "  CPU Média: $([math]::Round($avgCpu, 2))%"
        Write-Host "  CPU Máxima: $([math]::Round($maxCpu, 2))%"
        Write-Host ""
        
        $lastStatsDisplay = Get-Date
    }
}

# Para jobs
Stop-Job -Job $logcatJob -ErrorAction SilentlyContinue
Remove-Job -Job $logcatJob -ErrorAction SilentlyContinue
if ($mqttJob) {
    Stop-Job -Job $mqttJob -ErrorAction SilentlyContinue
    Remove-Job -Job $mqttJob -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "=========================================="
Write-Host "Relatório Final" -ForegroundColor Cyan
Write-Host "=========================================="
Write-Host ""

$totalTime = ((Get-Date) - $stats.startTime).TotalSeconds
$avgMemory = if ($stats.memorySamples.Count -gt 0) {
    ($stats.memorySamples | Measure-Object -Property TotalMB -Average).Average
} else { 0 }
$maxMemory = if ($stats.memorySamples.Count -gt 0) {
    ($stats.memorySamples | Measure-Object -Property TotalMB -Maximum).Maximum
} else { 0 }
$minMemory = if ($stats.memorySamples.Count -gt 0) {
    ($stats.memorySamples | Measure-Object -Property TotalMB -Minimum).Minimum
} else { 0 }
$avgCpu = if ($stats.cpuSamples.Count -gt 0) {
    ($stats.cpuSamples | Measure-Object -Property CPU -Average).Average
} else { 0 }
$maxCpu = if ($stats.cpuSamples.Count -gt 0) {
    ($stats.cpuSamples | Measure-Object -Property CPU -Maximum).Maximum
} else { 0 }

Write-Host "Tempo Total: $([math]::Round($totalTime, 1)) segundos"
Write-Host ""
Write-Host "Mensagens MQTT:"
Write-Host "  Total Enviadas: $($stats.mqttMessages)"
Write-Host "  Taxa: $([math]::Round($stats.mqttMessages / $totalTime, 2)) msg/s"
Write-Host "  Em Fila: $($stats.queuedMessages)"
Write-Host ""
Write-Host "Memória (MB):"
Write-Host "  Média: $([math]::Round($avgMemory, 2)) MB"
Write-Host "  Mínima: $([math]::Round($minMemory, 2)) MB"
Write-Host "  Máxima: $([math]::Round($maxMemory, 2)) MB"
Write-Host ""
Write-Host "CPU (%):"
Write-Host "  Média: $([math]::Round($avgCpu, 2))%"
Write-Host "  Máxima: $([math]::Round($maxCpu, 2))%"
Write-Host ""

# Análise
Write-Host "Análise:" -ForegroundColor Cyan
if ($maxMemory -gt 100) {
    Write-Host "  ⚠ Memória alta detectada (>100MB)" -ForegroundColor Yellow
} else {
    Write-Host "  ✓ Uso de memória dentro do esperado" -ForegroundColor Green
}

if ($maxCpu -gt 20) {
    Write-Host "  ⚠ CPU alta detectada (>20%)" -ForegroundColor Yellow
} else {
    Write-Host "  ✓ Uso de CPU dentro do esperado" -ForegroundColor Green
}

if ($stats.mqttMessages -eq 0) {
    Write-Host "  ⚠ Nenhuma mensagem MQTT detectada" -ForegroundColor Yellow
} elseif ($stats.mqttMessages / $totalTime -lt 0.5) {
    Write-Host "  ⚠ Taxa de envio baixa (<0.5 msg/s)" -ForegroundColor Yellow
} else {
    Write-Host "  ✓ Mensagens sendo enviadas corretamente" -ForegroundColor Green
}

if ($stats.queuedMessages -gt $stats.mqttMessages * 0.5) {
    Write-Host "  ⚠ Muitas mensagens em fila (>50%)" -ForegroundColor Yellow
} else {
    Write-Host "  ✓ Fila de mensagens normal" -ForegroundColor Green
}

Write-Host ""

