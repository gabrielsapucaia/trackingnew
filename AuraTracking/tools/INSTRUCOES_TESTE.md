# Instruções Rápidas para Teste

## Status Atual

✅ **Dispositivo:** Motorola Moto G34 5G conectado via ADB  
✅ **App:** Instalado (versão 1.0.0)  
✅ **Serviço:** Rodando  
✅ **Scripts:** Criados e prontos para uso  

## IMPORTANTE: Compilar Nova Versão

Antes de testar, você precisa compilar e instalar a nova versão do app com todas as mudanças implementadas:

```powershell
cd D:\tracking\AuraTracking
.\gradlew.bat assembleDebug
.\gradlew.bat installDebug
```

Isso garantirá que o app tenha:
- Novos providers (Orientation, SystemData, MotionDetection)
- Campos expandidos GPS (satellites, hAcc, vAcc, sAcc, etc.)
- Campos expandidos IMU (magnetômetro, aceleração linear, gravidade, rotation vector)
- Flag de transmissão (transmissionMode)
- Todas as magnitudes calculadas

## Teste Rápido (Recomendado)

### Opção 1: Script Master (Mais Completo)
```powershell
cd D:\tracking\AuraTracking\tools
.\test_master.ps1 10.10.10.10 1883
```

Este script faz tudo automaticamente:
- Verifica ambiente
- Monitora logcat e MQTT simultaneamente
- Salva logs em diretório timestampado
- Gera relatório final

### Opção 2: Monitoramento Manual

**Terminal 1 - Logcat:**
```powershell
cd D:\tracking\AuraTracking\tools
.\test_logcat_monitor.ps1
```

**Terminal 2 - MQTT:**
```powershell
cd D:\tracking\AuraTracking\tools
.\test_mqtt_monitor.ps1 10.10.10.10 1883
```

**Terminal 3 - Capturar Amostras:**
```powershell
cd D:\tracking\AuraTracking\tools
.\test_capture_mqtt_sample.ps1 10.10.10.10 1883 20 amostras.json
```

Depois validar:
```powershell
.\test_validate_payload.ps1 amostras.json
```

## O que Observar

### No Logcat:
- Mensagens de inicialização dos providers:
  - `OrientationProvider: Starting orientation updates`
  - `SystemDataProvider: Starting system data updates`
  - `MotionDetectorProvider: Starting motion detection sensors`
- Mensagens de dados sendo capturados:
  - `GPS: ...`
  - `IMU: ...`
  - `Orientation: Azimuth=...`
  - `System: battery=...`
- Mensagens de telemetria:
  - `TelemetryAggregator: Publishing telemetry...`
  - `TelemetryAggregator: Queuing telemetry...`

### No MQTT:
- Payloads JSON completos
- Campo `transmissionMode` presente ("online" ou "queued")
- Campos expandidos GPS presentes quando disponíveis
- Campos expandidos IMU presentes quando sensores disponíveis
- Orientação (azimuth, pitch, roll) presente
- Sistema (bateria, conectividade) presente

## Validação Esperada

Após capturar amostras, execute:

```powershell
.\test_validate_payload.ps1 amostras.json
```

Deve mostrar:
- ✓ JSON válido
- ✓ Todos os campos obrigatórios presentes
- ✓ Campos expandidos GPS presentes (satellites, hAcc, vAcc, sAcc)
- ✓ Campos expandidos IMU presentes (magnitudes, magnetômetro, etc.)
- ✓ Orientação presente (azimuth, pitch, roll)
- ✓ Sistema presente (bateria, conectividade)
- ✓ Flag de transmissão presente (transmissionMode)

## Problemas Comuns

**Se não aparecer dados MQTT:**
1. Verifique se broker está rodando: `docker ps` (se usar Docker)
2. Verifique configuração MQTT no app (host/porta)
3. Verifique logs do app para erros de conexão

**Se campos expandidos não aparecerem:**
1. Verifique se app foi recompilado e reinstalado
2. Verifique logs para erros de sensores
3. Alguns sensores podem não estar disponíveis no dispositivo

**Se transmissionMode sempre for "online":**
1. Desconecte MQTT temporariamente (pare o broker)
2. App deve continuar capturando e marcando como "queued"
3. Reconecte e verifique se dados queued são enviados

## Próximos Passos Após Validação

1. ✅ Validar backend está recebendo dados corretamente
2. ✅ Validar dashboard está exibindo novos campos
3. ✅ Testar cenário offline completo
4. ✅ Analisar volume de dados e performance

