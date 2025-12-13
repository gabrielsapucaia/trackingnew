# Script para verificar sensores disponíveis no dispositivo Android
param(
    [int]$DurationSeconds = 10
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Verificação de Sensores Disponíveis"
Write-Host "=========================================="
Write-Host ""

# Verificar se dispositivo está conectado
$device = adb devices | Select-String -Pattern "device$"
if (-not $device) {
    Write-Host "AVISO: Nenhum dispositivo Android conectado!" -ForegroundColor Yellow
    Write-Host "Pulando verificação de sensores..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Para conectar um dispositivo:" -ForegroundColor Cyan
    Write-Host "1. Conecte o dispositivo via USB"
    Write-Host "2. Ative 'Depuração USB' nas opções de desenvolvedor"
    Write-Host "3. Execute: adb devices"
    exit 0
}

Write-Host "Dispositivo conectado: $device" -ForegroundColor Green
Write-Host ""

# Listar todos os sensores disponíveis
Write-Host "Listando sensores disponíveis..." -ForegroundColor Cyan
$sensorList = adb shell dumpsys sensorservice | Select-String -Pattern "Sensor List|^\s+\d+\s+\|" | Select-Object -First 100

if ($sensorList) {
    Write-Host ""
    Write-Host "Primeiros 30 sensores encontrados:" -ForegroundColor Yellow
    $sensorList | Select-Object -First 30 | ForEach-Object {
        Write-Host "  $_"
    }
} else {
    Write-Host "Não foi possível listar sensores" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Verificando sensores específicos necessários..." -ForegroundColor Cyan

# Verificar sensores específicos
$sensors = @{
    'TYPE_MAGNETIC_FIELD' = 'Magnetômetro'
    'TYPE_LINEAR_ACCELERATION' = 'Aceleração Linear'
    'TYPE_GRAVITY' = 'Gravidade'
    'TYPE_ROTATION_VECTOR' = 'Rotação Vetorial'
    'TYPE_SIGNIFICANT_MOTION' = 'Movimento Significativo'
    'TYPE_STATIONARY_DETECT' = 'Detecção Estacionária'
    'TYPE_MOTION_DETECT' = 'Detecção de Movimento'
    'TYPE_ACCELEROMETER' = 'Acelerômetro'
    'TYPE_GYROSCOPE' = 'Giroscópio'
}

$sensorReport = @{
    timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    device = $device.ToString()
    sensors = @{}
}

foreach ($sensor in $sensors.GetEnumerator()) {
    $sensorType = $sensor.Key
    $sensorName = $sensor.Value
    
    # Buscar por tipo numérico ou nome
    $result = adb shell dumpsys sensorservice | Select-String -Pattern $sensorType -CaseSensitive:$false
    
    if ($result) {
        Write-Host "  ✅ $sensorName ($sensorType): Disponível" -ForegroundColor Green
        $sensorReport.sensors[$sensorType] = @{
            name = $sensorName
            available = $true
        }
    } else {
        Write-Host "  ❌ $sensorName ($sensorType): Não encontrado" -ForegroundColor Red
        $sensorReport.sensors[$sensorType] = @{
            name = $sensorName
            available = $false
        }
    }
}

# Verificar tipos numéricos também
Write-Host ""
Write-Host "Verificando tipos numéricos de sensores..." -ForegroundColor Cyan

$numericSensors = @{
    '2' = 'TYPE_ACCELEROMETER'
    '4' = 'TYPE_GYROSCOPE'
    '2|4' = 'TYPE_ACCELEROMETER ou TYPE_GYROSCOPE'
    '13' = 'TYPE_MAGNETIC_FIELD'
    '9' = 'TYPE_GRAVITY'
    '10' = 'TYPE_LINEAR_ACCELERATION'
    '11' = 'TYPE_ROTATION_VECTOR'
    '17' = 'TYPE_SIGNIFICANT_MOTION'
    '18' = 'TYPE_STATIONARY_DETECT'
    '19' = 'TYPE_MOTION_DETECT'
}

foreach ($sensorNum in $numericSensors.GetEnumerator()) {
    $num = $sensorNum.Key
    $name = $sensorNum.Value
    
    $result = adb shell dumpsys sensorservice | Select-String -Pattern "^\s+$num\s+\|" -CaseSensitive:$false
    
    if ($result) {
        Write-Host "  ✅ $name (tipo $num): Disponível" -ForegroundColor Green
    }
}

# Salvar relatório
$reportFile = "available_sensors_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
$sensorReport | ConvertTo-Json -Depth 3 | Out-File $reportFile -Encoding UTF8

Write-Host ""
Write-Host "Relatório salvo em: $reportFile" -ForegroundColor Cyan



