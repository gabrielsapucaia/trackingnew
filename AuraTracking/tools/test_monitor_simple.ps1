# Monitor simples e rápido de mensagens e performance
# Uso: .\test_monitor_simple.ps1 [MQTT_HOST] [MQTT_PORT]

param(
    [string]$MQTT_HOST = "10.10.10.10",
    [int]$MQTT_PORT = 1883
)

$PACKAGE = "com.aura.tracking"

Write-Host "=========================================="
Write-Host "Monitor Simples - AuraTracking"
Write-Host "=========================================="
Write-Host "Pressione Ctrl+C para parar"
Write-Host ""

# Limpa logcat
adb logcat -c

# Contadores
$mqttCount = 0
$queueCount = 0
$lastMemoryCheck = Get-Date

Write-Host "Monitorando..." -ForegroundColor Cyan
Write-Host ""

try {
    while ($true) {
        Start-Sleep -Seconds 5
        
        # Verifica mensagens MQTT no logcat
        $logs = adb logcat -d -t 50 | Select-String -Pattern "Published to|Queuing message|Publish latency"
        
        $newMqtt = ($logs | Select-String -Pattern "Published to").Count
        $newQueue = ($logs | Select-String -Pattern "Queuing").Count
        
        if ($newMqtt -gt 0) {
            $mqttCount += $newMqtt
        }
        if ($newQueue -gt 0) {
            $queueCount += $newQueue
        }
        
        # Verifica memória a cada 15 segundos
        if (((Get-Date) - $lastMemoryCheck).TotalSeconds -ge 15) {
            $meminfo = adb shell dumpsys meminfo $PACKAGE
            $totalPss = ($meminfo | Select-String -Pattern "TOTAL PSS:\s+(\d+)").Matches.Groups[1].Value
            $totalMB = if ($totalPss) { [math]::Round([int]$totalPss / 1024, 2) } else { "N/A" }
            
            Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Memória: $totalMB MB | MQTT: $mqttCount | Fila: $queueCount" -ForegroundColor Green
            
            $lastMemoryCheck = Get-Date
        }
        
        # Mostra latência se disponível
        $latency = $logs | Select-String -Pattern "Publish latency:\s+(\d+)ms" | Select-Object -Last 1
        if ($latency) {
            $latencyMs = $latency.Matches.Groups[1].Value
            if ([int]$latencyMs -gt 500) {
                Write-Host "  ⚠ Latência alta: ${latencyMs}ms" -ForegroundColor Yellow
            }
        }
    }
} catch {
    Write-Host ""
    Write-Host "Monitoramento interrompido" -ForegroundColor Yellow
}

