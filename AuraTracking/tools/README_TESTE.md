# Guia de Teste e Monitoramento - AuraTracking

Este guia explica como testar a implementação completa no dispositivo Motorola e monitorar os dados sendo enviados via MQTT.

## Scripts Disponíveis

### 1. `test_master.ps1` (RECOMENDADO)
Script master que coordena todo o processo de teste e monitoramento.

**Uso:**
```powershell
cd D:\tracking\AuraTracking\tools
.\test_master.ps1 [MQTT_HOST] [MQTT_PORT]
```

**Exemplo:**
```powershell
.\test_master.ps1 10.10.10.10 1883
```

**O que faz:**
- Verifica conexão ADB e dispositivo
- Verifica se app está instalado e serviço rodando
- Inicia monitoramento simultâneo de logcat e MQTT
- Salva logs em diretório timestampado
- Gera relatório final

---

### 2. `test_sensor_status.ps1`
Verifica status dos sensores e do app no dispositivo.

**Uso:**
```powershell
.\test_sensor_status.ps1
```

**Output:**
- Lista sensores disponíveis
- Status do app (instalado, versão)
- Status do serviço de tracking
- Permissões concedidas

---

### 3. `test_logcat_monitor.ps1`
Monitora logs Android filtrados por tags relevantes.

**Uso:**
```powershell
.\test_logcat_monitor.ps1
```

**Filtra tags:**
- GPS
- IMU
- OrientationProvider
- SystemDataProvider
- MotionDetectorProvider
- TelemetryAggregator
- TrackingService

---

### 4. `test_mqtt_monitor.ps1`
Monitora tópicos MQTT e exibe payloads formatados.

**Uso:**
```powershell
.\test_mqtt_monitor.ps1 [MQTT_HOST] [MQTT_PORT] [TOPIC]
```

**Exemplo:**
```powershell
.\test_mqtt_monitor.ps1 10.10.10.10 1883 "aura/tracking/#"
```

**Requisitos:**
- `mosquitto_sub` instalado OU
- Docker com imagem `eclipse-mosquitto`

**Output:**
- Payloads JSON formatados
- Campos extraídos (messageId, deviceId, transmissionMode, etc.)
- Dados GPS, IMU, Orientation, System

---

### 5. `test_capture_mqtt_sample.ps1`
Captura amostras de payloads MQTT e salva em arquivo JSON.

**Uso:**
```powershell
.\test_capture_mqtt_sample.ps1 [MQTT_HOST] [MQTT_PORT] [NUM_SAMPLES] [OUTPUT_FILE]
```

**Exemplo:**
```powershell
.\test_capture_mqtt_sample.ps1 10.10.10.10 1883 10 mqtt_sample.json
```

**Output:**
- Arquivo JSON com amostras capturadas
- Validação básica de payloads

---

### 6. `test_validate_payload.ps1`
Valida estrutura JSON dos payloads contra estrutura esperada.

**Uso:**
```powershell
.\test_validate_payload.ps1 <arquivo_json>
```

**Exemplo:**
```powershell
.\test_validate_payload.ps1 mqtt_sample.json
```

**Valida:**
- Campos obrigatórios (messageId, deviceId, timestamp, gps)
- Campos expandidos GPS (satellites, hAcc, vAcc, sAcc)
- Campos expandidos IMU (magnitudes, magnetômetro, aceleração linear)
- Orientação (azimuth, pitch, roll)
- Sistema (bateria, conectividade)
- Flag de transmissão (transmissionMode)

---

## Fluxo Recomendado de Testes

### Passo 1: Preparação
```powershell
# Verifica status do dispositivo e app
.\test_sensor_status.ps1
```

### Passo 2: Compilar e Instalar (se necessário)
```powershell
cd ..\..
.\gradlew.bat assembleDebug
.\gradlew.bat installDebug
```

### Passo 3: Monitoramento Completo
```powershell
cd tools
.\test_master.ps1 10.10.10.10 1883
```

Este script irá:
1. Verificar ambiente
2. Iniciar monitoramento simultâneo
3. Capturar dados em tempo real
4. Salvar logs para análise posterior

### Passo 4: Capturar Amostras
```powershell
.\test_capture_mqtt_sample.ps1 10.10.10.10 1883 20 amostras.json
```

### Passo 5: Validar Payloads
```powershell
.\test_validate_payload.ps1 amostras.json
```

---

## Usando Docker para MQTT (Alternativa)

Se `mosquitto_sub` não estiver instalado, use Docker:

```powershell
# Monitorar MQTT via Docker
docker run -it --rm eclipse-mosquitto mosquitto_sub -h 10.10.10.10 -p 1883 -t "aura/tracking/#" -v

# Capturar amostras
docker run -it --rm eclipse-mosquitto mosquitto_sub -h 10.10.10.10 -p 1883 -t "aura/tracking/#" -C 10 > mqtt_samples.txt
```

---

## O que Validar

### Campos Obrigatórios
- ✓ `messageId` (UUID)
- ✓ `deviceId`
- ✓ `timestamp`
- ✓ `gps` (lat, lon, alt, speed, bearing, accuracy)

### Campos Expandidos GPS
- ✓ `satellites` (número de satélites)
- ✓ `hAcc` (horizontal accuracy)
- ✓ `vAcc` (vertical accuracy)
- ✓ `sAcc` (speed accuracy)
- ✓ `hdop`, `vdop`, `pdop` (dilution of precision)

### Campos Expandidos IMU
- ✓ `accelMagnitude` (magnitude da aceleração)
- ✓ `gyroMagnitude` (magnitude do giroscópio)
- ✓ `magX`, `magY`, `magZ` (magnetômetro)
- ✓ `magMagnitude` (magnitude do magnetômetro)
- ✓ `linearAccelX/Y/Z` (aceleração linear)
- ✓ `linearAccelMagnitude` (magnitude aceleração linear)
- ✓ `gravityX/Y/Z` (vetor gravidade)
- ✓ `rotationVectorX/Y/Z/W` (quaternion)

### Orientação
- ✓ `azimuth` (0-360 graus)
- ✓ `pitch` (-180 a +180 graus)
- ✓ `roll` (-90 a +90 graus)

### Sistema
- ✓ `battery.level` (0-100%)
- ✓ `battery.status` (CHARGING, DISCHARGING, etc.)
- ✓ `battery.temperature` (Celsius)
- ✓ `connectivity.cellular.networkType` (LTE, 5G, etc.)
- ✓ `connectivity.cellular.signalStrength.rsrp` (dBm)

### Flag de Transmissão
- ✓ `transmissionMode` ("online" ou "queued")

---

## Troubleshooting

**Erro: "Nenhum dispositivo conectado"**
```powershell
adb devices
# Se não aparecer, verifique:
# - Cabo USB conectado
# - Depuração USB ativada
# - Autorização concedida no dispositivo
```

**Erro: "App não instalado"**
```powershell
cd ..\..
.\gradlew.bat installDebug
```

**Erro: "Serviço não está rodando"**
- Abra o app no dispositivo
- Vá para Dashboard
- Inicie o tracking manualmente

**Erro: "mosquitto_sub não encontrado"**
- Instale: `sudo apt-get install mosquitto-clients` (Linux)
- OU use Docker: `docker run -it --rm eclipse-mosquitto mosquitto_sub ...`

**Não recebe dados MQTT:**
- Verifique se broker MQTT está rodando
- Verifique host/porta configurados no app
- Verifique se app está conectado ao broker (veja logs)
- Verifique se tópico está correto: `aura/tracking/{deviceId}/telemetry`

---

## Análise de Resultados

Após capturar dados, analise:

1. **Frequência de envio:** Deve ser ~1Hz (1 mensagem por segundo)
2. **Campos presentes:** Todos os campos expandidos devem aparecer quando sensores disponíveis
3. **Flag de transmissão:** Deve alternar entre "online" e "queued" conforme conexão
4. **Qualidade GPS:** Verificar `satellites`, `hAcc`, `vAcc`
5. **Sensores IMU:** Verificar se magnitudes estão sendo calculadas
6. **Orientação:** Verificar se azimuth, pitch, roll estão sendo calculados
7. **Sistema:** Verificar se bateria e conectividade estão sendo capturados

---

## Próximos Passos

Após validar que todos os dados estão sendo capturados e transmitidos:

1. Validar backend está recebendo e processando corretamente
2. Validar dashboard está exibindo novos campos
3. Testar cenário offline (desconectar MQTT temporariamente)
4. Validar que dados queued são enviados quando reconecta
5. Analisar performance e volume de dados

