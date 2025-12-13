# Script PowerShell para monitorar tópicos MQTT e exibir payloads
# Uso: .\test_mqtt_monitor.ps1 [MQTT_HOST] [MQTT_PORT] [TOPIC]

param(
    [string]$MQTT_HOST = "10.10.10.10",
    [int]$MQTT_PORT = 1883,
    [string]$TOPIC = "aura/tracking/#"
)

Write-Host "=========================================="
Write-Host "MQTT Monitor - AuraTracking"
Write-Host "=========================================="
Write-Host "Host: $MQTT_HOST"
Write-Host "Port: $MQTT_PORT"
Write-Host "Topic: $TOPIC"
Write-Host "=========================================="
Write-Host ""

# Verifica se mosquitto_sub está instalado
$mosquittoSub = Get-Command mosquitto_sub -ErrorAction SilentlyContinue
if (-not $mosquittoSub) {
    Write-Host "ERRO: mosquitto_sub não encontrado!" -ForegroundColor Red
    Write-Host "Instale com: sudo apt-get install mosquitto-clients (Linux) ou use Docker"
    exit 1
}

# Monitora tópicos e exibe payloads formatados
& mosquitto_sub -h $MQTT_HOST -p $MQTT_PORT -t $TOPIC -v | ForEach-Object {
    $line = $_
    $parts = $line -split ' ', 2
    $topic = $parts[0]
    $payload = if ($parts.Length -gt 1) { $parts[1] } else { "" }
    
    Write-Host "----------------------------------------"
    Write-Host "Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Host "Topic: $topic"
    Write-Host "Payload:"
    
    # Tenta formatar JSON se válido
    try {
        $jsonObj = $payload | ConvertFrom-Json
        
        $payload | ConvertFrom-Json | ConvertTo-Json -Depth 10 | Write-Host
        
        Write-Host ""
        Write-Host "Campos Extraídos:"
        Write-Host "  - messageId: $($jsonObj.messageId)"
        Write-Host "  - deviceId: $($jsonObj.deviceId)"
        Write-Host "  - transmissionMode: $($jsonObj.transmissionMode)"
        Write-Host "  - timestamp: $($jsonObj.timestamp)"
        
        # GPS
        if ($jsonObj.gps) {
            Write-Host "  - GPS lat: $($jsonObj.gps.lat)"
            Write-Host "  - GPS lon: $($jsonObj.gps.lon)"
            Write-Host "  - GPS satellites: $($jsonObj.gps.satellites)"
            Write-Host "  - GPS hAcc: $($jsonObj.gps.hAcc)"
        }
        
        # IMU
        if ($jsonObj.imu) {
            Write-Host "  - IMU accelMagnitude: $($jsonObj.imu.accelMagnitude)"
            Write-Host "  - IMU magX: $($jsonObj.imu.magX)"
            Write-Host "  - IMU linearAccelMagnitude: $($jsonObj.imu.linearAccelMagnitude)"
        }
        
        # Orientation
        if ($jsonObj.orientation) {
            Write-Host "  - Orientation azimuth: $($jsonObj.orientation.azimuth)"
            Write-Host "  - Orientation pitch: $($jsonObj.orientation.pitch)"
            Write-Host "  - Orientation roll: $($jsonObj.orientation.roll)"
        }
        
        # System
        if ($jsonObj.system) {
            Write-Host "  - Battery level: $($jsonObj.system.battery.level)"
            Write-Host "  - Battery status: $($jsonObj.system.battery.status)"
            Write-Host "  - Network type: $($jsonObj.system.connectivity.cellular.networkType)"
        }
    } catch {
        Write-Host $payload
    }
    
    Write-Host ""
}

