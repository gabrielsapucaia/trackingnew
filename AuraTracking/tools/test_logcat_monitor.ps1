# Script PowerShell para monitorar logs Android filtrados
# Uso: .\test_logcat_monitor.ps1

Write-Host "=========================================="
Write-Host "Logcat Monitor - AuraTracking"
Write-Host "=========================================="
Write-Host "Filtrando tags: GPS, IMU, Orientation, System, Motion, TelemetryAggregator"
Write-Host "=========================================="
Write-Host ""

# Limpa logcat anterior
adb logcat -c

# Monitora logs filtrados por tags relevantes
adb logcat -v time GPS:* IMU:* OrientationProvider:* SystemDataProvider:* MotionDetectorProvider:* TelemetryAggregator:* TrackingService:* *:S | 
    Select-String -Pattern "(GPS|IMU|Orientation|System|Motion|Telemetry|Tracking)" | 
    ForEach-Object {
        $line = $_.Line
        if ($line -match "GPS") { Write-Host $line -ForegroundColor Cyan }
        elseif ($line -match "IMU") { Write-Host $line -ForegroundColor Green }
        elseif ($line -match "Orientation") { Write-Host $line -ForegroundColor Yellow }
        elseif ($line -match "System") { Write-Host $line -ForegroundColor Magenta }
        elseif ($line -match "Motion") { Write-Host $line -ForegroundColor Blue }
        elseif ($line -match "Telemetry|Tracking") { Write-Host $line -ForegroundColor White }
        else { Write-Host $line }
    }

