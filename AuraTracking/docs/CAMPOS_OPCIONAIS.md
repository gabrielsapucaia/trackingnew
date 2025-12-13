# Campos Opcionais e Condições de Disponibilidade

Este documento lista todos os campos opcionais do sistema de tracking e explica quando podem ser NULL.

## GPS

### Campos Básicos (Sempre Disponíveis)

- `latitude`, `longitude`, `altitude` - Coordenadas GPS
- `speed` - Velocidade (m/s)
- `bearing` - Direção (graus)
- `accuracy` - Precisão (metros)

### Campos Detalhados (Opcionais - Limitação do FusedLocationProvider)

**Sempre NULL** devido à limitação do `FusedLocationProviderClient`:

- `satellites` - Número de satélites GPS usados
- `h_acc` - Horizontal accuracy (metros)
- `v_acc` - Vertical accuracy (metros)
- `s_acc` - Speed accuracy (m/s)
- `hdop` - Horizontal Dilution of Precision
- `vdop` - Vertical Dilution of Precision
- `pdop` - Position Dilution of Precision
- `gps_timestamp` - Timestamp do fix GPS

**Condição**: Não disponível via FusedLocationProvider (limitação conhecida)

## IMU

### Campos Básicos (Sempre Disponíveis)

- `accel_x`, `accel_y`, `accel_z` - Acelerômetro (m/s²)
- `gyro_x`, `gyro_y`, `gyro_z` - Giroscópio (rad/s)
- `accel_magnitude` - Magnitude da aceleração (calculada)
- `gyro_magnitude` - Magnitude da rotação (calculada)

### Campos Detalhados (Opcionais - Dependem de Sensores)

**Magnetômetro** (requer `TYPE_MAGNETIC_FIELD`):
- `mag_x`, `mag_y`, `mag_z` - Campo magnético (μT)
- `mag_magnitude` - Magnitude do campo magnético (calculada)

**Aceleração Linear** (requer `TYPE_LINEAR_ACCELERATION`):
- `linear_accel_x`, `linear_accel_y`, `linear_accel_z` - Aceleração sem gravidade (m/s²)
- `linear_accel_magnitude` - Magnitude da aceleração linear (calculada)

**Gravidade** (requer `TYPE_GRAVITY`):
- `gravity_x`, `gravity_y`, `gravity_z` - Componente de gravidade (m/s²)

**Rotação Vetorial** (requer `TYPE_ROTATION_VECTOR`):
- `rotation_vector_x`, `rotation_vector_y`, `rotation_vector_z`, `rotation_vector_w` - Quaternion de rotação

**Condição**: NULL se sensor não estiver disponível no dispositivo

## Orientação

### Campos (Sempre Disponíveis)

- `azimuth` - Direção (0-360°) ✅
- `pitch` - Inclinação vertical (-180° a +180°) ✅
- `roll` - Rotação lateral (-90° a +90°) ✅

**Condição**: Todos funcionam. Se magnetômetro não disponível, `azimuth` pode ser 0 mas `pitch` e `roll` ainda são calculados.

## Sistema - Bateria

### Campos Sempre Disponíveis

- `battery_status` - Status (CHARGING, DISCHARGING, FULL, etc.) ✅
- `battery_charge_counter` - Contador de carga (μAh) - Android 5.0+ ✅
- `battery_full_capacity` - Capacidade total (μAh) - Android 5.0+ ✅

### Campos Opcionais

- `battery_level` - Nível (0-100%) - NULL se não disponível
- `battery_temperature` - Temperatura (°C) - NULL se não disponível
- `battery_voltage` - Voltagem (mV) - NULL se não disponível
- `battery_health` - Saúde (GOOD, OVERHEAT, etc.) - NULL se não disponível
- `battery_technology` - Tecnologia (Li-ion, etc.) - NULL se não disponível

**Condição**: NULL se dados não estiverem disponíveis no dispositivo ou versão do Android

## Sistema - WiFi

### Campos Sempre Disponíveis (Quando WiFi Ativo)

- `wifi_bssid` - Endereço MAC do ponto de acesso ✅
- `wifi_frequency` - Frequência (MHz) ✅

### Campos Dependentes de Conexão

- `wifi_rssi` - Força do sinal (dBm) - NULL se não conectado
- `wifi_ssid` - Nome da rede - NULL se não conectado
- `wifi_channel` - Canal WiFi - NULL se não conectado ou frequência inválida

**Condição**: NULL se dispositivo não estiver conectado a uma rede WiFi ativa

## Sistema - Celular

### Campos Sempre Disponíveis

- `cellular_ci` - Cell Identity ✅
- `cellular_pci` - Physical Cell Identity ✅

### Campos Dependentes de Permissão

**Requerem `READ_PHONE_STATE`** (adicionada ao manifest):

- `cellular_network_type` - Tipo de rede (LTE, 5G, etc.)
- `cellular_operator` - Nome da operadora
- `cellular_rsrp` - Reference Signal Received Power (dBm)
- `cellular_rsrq` - Reference Signal Received Quality (dB)
- `cellular_rssnr` - Reference Signal Signal-to-Noise Ratio (dB)

**Condição**: NULL se permissão não concedida ou dados não disponíveis

### Campos Opcionais Adicionais

- `cellular_tac` - Tracking Area Code - NULL se não disponível
- `cellular_earfcn` - E-UTRAN Absolute Radio Frequency Channel Number - NULL se não disponível
- `cellular_band` - LTE Band (array) - NULL se não disponível
- `cellular_bandwidth` - Largura de banda (kHz) - NULL se não disponível

**Condição**: NULL se dados não estiverem disponíveis na célula atual

## Motion Detection (REMOVIDO)

### Status: Campos Removidos do Sistema

**Todos os campos de motion detection foram removidos do código** porque os sensores físicos não existem no dispositivo Moto G34 5G:

- `significantMotion` - Movimento significativo
- `stationaryDetect` - Detecção de estacionário
- `motionDetect` - Detecção de movimento
- `flatUp` - Sensor específico Motorola
- `flatDown` - Sensor específico Motorola
- `stowed` - Sensor específico Motorola
- `displayRotate` - Sensor específico Motorola

**Status**: Campos não são mais coletados ou enviados no payload MQTT. Colunas no banco de dados permanecem (sempre NULL) para flexibilidade futura.

**Nota**: Se trocar para um dispositivo que tenha esses sensores, o código pode ser reativado facilmente.

## Resumo por Categoria

### ✅ Sempre Disponíveis (100%)

**GPS Básico**: `latitude`, `longitude`, `altitude`, `speed`, `bearing`, `accuracy`  
**IMU Básico**: `accel_x/y/z`, `gyro_x/y/z`, `accel_magnitude`, `gyro_magnitude`  
**Orientação**: `azimuth`, `pitch`, `roll`  
**Sistema**: `battery_status`, `battery_charge_counter`, `battery_full_capacity`, `wifi_bssid`, `wifi_frequency`, `cellular_ci`, `cellular_pci`

### ⚠️ Opcionais - Dependem de Sensores

**IMU Detalhado**: `mag_x/y/z`, `linear_accel_x/y/z`, `gravity_x/y/z`, `rotation_vector_x/y/z/w`  
**Motion Detection**: REMOVIDO (sensores não disponíveis no dispositivo)

### ⚠️ Opcionais - Dependem de Conexão

**WiFi**: `wifi_rssi`, `wifi_ssid`, `wifi_channel` (requer WiFi conectado)

### ⚠️ Opcionais - Dependem de Permissão

**Celular**: `cellular_network_type`, `cellular_operator`, `cellular_rsrp`, `cellular_rsrq`, `cellular_rssnr` (requer `READ_PHONE_STATE`)

### ⚠️ Opcionais - Dependem de Dados do Dispositivo

**Bateria**: `battery_level`, `battery_temperature`, `battery_voltage`, `battery_health`, `battery_technology`  
**Celular**: `cellular_tac`, `cellular_earfcn`, `cellular_band`, `cellular_bandwidth`

### ❌ Sempre NULL (Limitação Conhecida)

**GPS Detalhado**: `satellites`, `h_acc`, `v_acc`, `s_acc`, `hdop`, `vdop`, `pdop`, `gps_timestamp` (limitação do FusedLocationProvider)

## Verificação de Disponibilidade

Para verificar quais campos estão disponíveis:

1. **Sensores**: Execute `check_available_sensors.ps1`
2. **Banco de Dados**: Execute `analyze_nulls.ps1`
3. **Logs**: Verifique logs do app para erros de permissão ou sensores não disponíveis
4. **Payload**: Execute `compare_provider_payload.ps1` para comparar payload vs banco

## Troubleshooting

Se um campo opcional está sempre NULL:

1. Verifique se a condição de disponibilidade está sendo atendida (sensor, conexão, permissão)
2. Verifique logs do app para erros
3. Verifique se o campo está sendo incluído no payload MQTT
4. Consulte `TROUBLESHOOTING_NULLS.md` para guia detalhado

