# Script PowerShell para verificar status dos sensores no dispositivo
# Uso: .\test_sensor_status.ps1

Write-Host "=========================================="
Write-Host "Status dos Sensores - Motorola Moto G34"
Write-Host "=========================================="
Write-Host ""

# Verifica sensores disponíveis
Write-Host "Sensores Disponíveis:"
adb shell dumpsys sensorservice | Select-String -Pattern "(Accelerometer|Gyroscope|Magnetic|Linear|Gravity|Rotation)" | Select-Object -First 20

Write-Host ""
Write-Host "=========================================="
Write-Host "Status do App:"
Write-Host ""

# Verifica se app está instalado
$PACKAGE = "com.aura.tracking"
$installed = adb shell pm list packages | Select-String -Pattern $PACKAGE

if ($installed) {
    Write-Host "✓ App instalado: $PACKAGE" -ForegroundColor Green
    
    # Versão do app
    $version = adb shell dumpsys package $PACKAGE | Select-String -Pattern "versionName" | Select-Object -First 1
    if ($version) {
        Write-Host "  Versão: $($version.ToString().Trim())"
    }
    
    # Verifica se serviço está rodando
    $service = adb shell dumpsys activity services | Select-String -Pattern "TrackingForegroundService"
    if ($service) {
        Write-Host "✓ Serviço de tracking está rodando" -ForegroundColor Green
    } else {
        Write-Host "✗ Serviço de tracking NÃO está rodando" -ForegroundColor Red
    }
} else {
    Write-Host "✗ App NÃO instalado: $PACKAGE" -ForegroundColor Red
}

Write-Host ""
Write-Host "=========================================="
Write-Host "Permissões:"
Write-Host ""

# Verifica permissões críticas
$PERMISSIONS = @("android.permission.ACCESS_FINE_LOCATION", "android.permission.ACCESS_COARSE_LOCATION")
$packageInfo = adb shell dumpsys package $PACKAGE

foreach ($perm in $PERMISSIONS) {
    if ($packageInfo -match [regex]::Escape($perm)) {
        Write-Host "✓ $perm" -ForegroundColor Green
    } else {
        Write-Host "✗ $perm" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=========================================="

