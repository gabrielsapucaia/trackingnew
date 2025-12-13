# Script PowerShell para validar estrutura JSON dos payloads MQTT
# Uso: .\test_validate_payload.ps1 [arquivo_json] ou pipe JSON

param(
    [Parameter(Mandatory=$true)]
    [string]$InputFile
)

$EXPECTED_STRUCTURE_FILE = Join-Path (Split-Path $PSCommandPath) "ESTRUTURA_MQTT_PROPOSTA.json"

Write-Host "=========================================="
Write-Host "Validador de Payload MQTT"
Write-Host "=========================================="

# Lê payload
if (Test-Path $InputFile) {
    $content = Get-Content $InputFile -Raw
    try {
        $PAYLOAD = $content | ConvertFrom-Json
    } catch {
        Write-Host "ERRO: JSON inválido!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "ERRO: Arquivo não encontrado: $InputFile" -ForegroundColor Red
    exit 1
}

Write-Host "✓ JSON válido" -ForegroundColor Green
Write-Host ""

# Campos obrigatórios
$REQUIRED_FIELDS = @("messageId", "deviceId", "timestamp", "gps")
$MISSING_FIELDS = @()

foreach ($field in $REQUIRED_FIELDS) {
    if (-not $PAYLOAD.PSObject.Properties.Name -contains $field) {
        $MISSING_FIELDS += $field
    }
}

if ($MISSING_FIELDS.Count -eq 0) {
    Write-Host "✓ Todos os campos obrigatórios presentes" -ForegroundColor Green
} else {
    Write-Host "✗ Campos obrigatórios faltando: $($MISSING_FIELDS -join ', ')" -ForegroundColor Red
}

# Verifica campos expandidos
Write-Host ""
Write-Host "Campos Expandidos:"

# GPS detalhado
$GPS_FIELDS = @("satellites", "hAcc", "vAcc", "sAcc")
Write-Host "  GPS Detalhado:"
foreach ($field in $GPS_FIELDS) {
    if ($PAYLOAD.gps -and $PAYLOAD.gps.PSObject.Properties.Name -contains $field) {
        $value = $PAYLOAD.gps.$field
        Write-Host "    ✓ $field : $value" -ForegroundColor Green
    } else {
        Write-Host "    ✗ $field : ausente" -ForegroundColor Yellow
    }
}

# IMU expandido
$IMU_FIELDS = @("accelMagnitude", "gyroMagnitude", "magX", "magY", "magZ", "magMagnitude", "linearAccelX", "linearAccelY", "linearAccelZ", "linearAccelMagnitude")
Write-Host "  IMU Expandido:"
foreach ($field in $IMU_FIELDS) {
    if ($PAYLOAD.imu -and $PAYLOAD.imu.PSObject.Properties.Name -contains $field) {
        $value = $PAYLOAD.imu.$field
        Write-Host "    ✓ $field : $value" -ForegroundColor Green
    } else {
        Write-Host "    ✗ $field : ausente" -ForegroundColor Yellow
    }
}

# Orientação
$ORIENTATION_FIELDS = @("azimuth", "pitch", "roll")
Write-Host "  Orientação:"
if ($PAYLOAD.orientation) {
    foreach ($field in $ORIENTATION_FIELDS) {
        if ($PAYLOAD.orientation.PSObject.Properties.Name -contains $field) {
            $value = $PAYLOAD.orientation.$field
            Write-Host "    ✓ $field : $value" -ForegroundColor Green
        } else {
            Write-Host "    ✗ $field : ausente" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "    ✗ orientation : ausente" -ForegroundColor Yellow
}

# Sistema
Write-Host "  Sistema:"
if ($PAYLOAD.system) {
    if ($PAYLOAD.system.battery) {
        $battery_level = $PAYLOAD.system.battery.level
        Write-Host "    ✓ battery.level : $battery_level" -ForegroundColor Green
    }
    if ($PAYLOAD.system.connectivity -and $PAYLOAD.system.connectivity.cellular) {
        $network_type = $PAYLOAD.system.connectivity.cellular.networkType
        Write-Host "    ✓ connectivity.cellular.networkType : $network_type" -ForegroundColor Green
    }
} else {
    Write-Host "    ✗ system : ausente" -ForegroundColor Yellow
}

# Flag de transmissão
Write-Host "  Transmissão:"
if ($PAYLOAD.PSObject.Properties.Name -contains "transmissionMode") {
    $transmission_mode = $PAYLOAD.transmissionMode
    Write-Host "    ✓ transmissionMode : $transmission_mode" -ForegroundColor Green
} else {
    Write-Host "    ✗ transmissionMode : ausente" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=========================================="

