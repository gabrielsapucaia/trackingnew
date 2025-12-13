# Script PowerShell para capturar amostra de payload MQTT e salvar em arquivo
# Uso: .\test_capture_mqtt_sample.ps1 [MQTT_HOST] [MQTT_PORT] [NUM_SAMPLES] [OUTPUT_FILE]

param(
    [string]$MQTT_HOST = "10.10.10.10",
    [int]$MQTT_PORT = 1883,
    [int]$NUM_SAMPLES = 5,
    [string]$OUTPUT_FILE = "mqtt_sample_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
)

Write-Host "=========================================="
Write-Host "Captura de Amostra MQTT"
Write-Host "=========================================="
Write-Host "Host: $MQTT_HOST"
Write-Host "Port: $MQTT_PORT"
Write-Host "Amostras: $NUM_SAMPLES"
Write-Host "Arquivo: $OUTPUT_FILE"
Write-Host "=========================================="
Write-Host ""

# Verifica se mosquitto_sub está instalado
$mosquittoSub = Get-Command mosquitto_sub -ErrorAction SilentlyContinue
if (-not $mosquittoSub) {
    Write-Host "ERRO: mosquitto_sub não encontrado!" -ForegroundColor Red
    Write-Host "Instale com: sudo apt-get install mosquitto-clients (Linux) ou use Docker"
    exit 1
}

# Array para armazenar amostras
$samples = @()

# Captura amostras
Write-Host "Capturando amostras..."
& mosquitto_sub -h $MQTT_HOST -p $MQTT_PORT -t "aura/tracking/#" -C $NUM_SAMPLES | ForEach-Object {
    $line = $_
    $parts = $line -split ' ', 2
    $topic = $parts[0]
    $payload = if ($parts.Length -gt 1) { $parts[1] } else { "" }
    
    try {
        $jsonObj = $payload | ConvertFrom-Json
        $sample = @{
            topic = $topic
            payload = $jsonObj
            timestamp = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')
        }
        $samples += $sample
        Write-Host "Capturado: $($samples.Count)/$NUM_SAMPLES"
    } catch {
        Write-Host "ERRO ao processar payload: $_" -ForegroundColor Red
    }
}

# Salva em arquivo JSON
$samples | ConvertTo-Json -Depth 10 | Out-File -FilePath $OUTPUT_FILE -Encoding UTF8

Write-Host ""
Write-Host "✓ Amostras capturadas em: $OUTPUT_FILE" -ForegroundColor Green
Write-Host ""
Write-Host "Validando payloads..."
Write-Host ""

# Valida cada payload
$valid = 0
$invalid = 0
foreach ($sample in $samples) {
    try {
        $sample.payload | ConvertTo-Json | Out-Null
        $valid++
        Write-Host "✓ Payload válido" -ForegroundColor Green
    } catch {
        $invalid++
        Write-Host "✗ Payload inválido" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Resumo: $valid válidos, $invalid inválidos"
Write-Host ""
Write-Host "Use: .\test_validate_payload.ps1 '$OUTPUT_FILE' para validar detalhadamente"

