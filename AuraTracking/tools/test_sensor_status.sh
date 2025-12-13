#!/bin/bash

# Script para verificar status dos sensores no dispositivo
# Uso: ./test_sensor_status.sh

echo "=========================================="
echo "Status dos Sensores - Motorola Moto G34"
echo "=========================================="
echo ""

# Verifica sensores disponíveis
echo "Sensores Disponíveis:"
adb shell dumpsys sensorservice | grep -E "(Accelerometer|Gyroscope|Magnetic|Linear|Gravity|Rotation)" | head -20

echo ""
echo "=========================================="
echo "Status do App:"
echo ""

# Verifica se app está instalado
PACKAGE="com.aura.tracking"
if adb shell pm list packages | grep -q "$PACKAGE"; then
    echo "✓ App instalado: $PACKAGE"
    
    # Versão do app
    VERSION=$(adb shell dumpsys package "$PACKAGE" | grep versionName | head -1 | awk '{print $2}' | tr -d '=')
    echo "  Versão: $VERSION"
    
    # Verifica se serviço está rodando
    if adb shell dumpsys activity services | grep -q "TrackingForegroundService"; then
        echo "✓ Serviço de tracking está rodando"
    else
        echo "✗ Serviço de tracking NÃO está rodando"
    fi
else
    echo "✗ App NÃO instalado: $PACKAGE"
fi

echo ""
echo "=========================================="
echo "Permissões:"
echo ""

# Verifica permissões críticas
PERMISSIONS=("android.permission.ACCESS_FINE_LOCATION" "android.permission.ACCESS_COARSE_LOCATION")
for perm in "${PERMISSIONS[@]}"; do
    if adb shell dumpsys package "$PACKAGE" | grep -q "$perm"; then
        echo "✓ $perm"
    else
        echo "✗ $perm"
    fi
done

echo ""
echo "=========================================="

