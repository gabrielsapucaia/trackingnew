#!/bin/bash

# Script para monitorar logs Android filtrados
# Uso: ./test_logcat_monitor.sh

echo "=========================================="
echo "Logcat Monitor - AuraTracking"
echo "=========================================="
echo "Filtrando tags: GPS, IMU, Orientation, System, Motion, TelemetryAggregator"
echo "=========================================="
echo ""

# Limpa logcat anterior
adb logcat -c

# Monitora logs filtrados por tags relevantes
adb logcat -v time \
    GPS:* IMU:* OrientationProvider:* SystemDataProvider:* MotionDetectorProvider:* \
    TelemetryAggregator:* TrackingService:* \
    *:S | grep -E "(GPS|IMU|Orientation|System|Motion|Telemetry|Tracking)" --color=always

