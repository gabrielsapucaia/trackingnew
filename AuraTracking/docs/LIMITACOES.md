# Limitações Conhecidas do Sistema

Este documento descreve limitações conhecidas do sistema de tracking e suas causas.

## GPS Detalhado - FusedLocationProvider

### Campos Afetados

Os seguintes campos de GPS detalhado **não estão disponíveis** quando usando `FusedLocationProviderClient`:

- `satellites` - Número de satélites GPS usados
- `h_acc` - Horizontal accuracy (metros)
- `v_acc` - Vertical accuracy (metros)
- `s_acc` - Speed accuracy (m/s)
- `hdop` - Horizontal Dilution of Precision
- `vdop` - Vertical Dilution of Precision
- `pdop` - Position Dilution of Precision
- `gps_timestamp` - Timestamp do fix GPS

### Causa

O `FusedLocationProviderClient` do Google Play Services não expõe informações detalhadas de GPS através dos `extras` do objeto `Location`. Esses dados só estão disponíveis usando `LocationManager` diretamente.

### Por Que Mantemos FusedLocationProvider?

Mantemos o uso do `FusedLocationProviderClient` porque:

1. **Melhor eficiência de bateria**: O FusedLocationProvider otimiza o uso de GPS, WiFi e redes celulares para determinar localização
2. **Melhor precisão**: Combina múltiplas fontes de localização
3. **Atualizações automáticas**: Google Play Services mantém o provider atualizado
4. **Compatibilidade**: Funciona melhor em diferentes dispositivos e versões do Android

### Alternativa

Se os campos detalhados de GPS forem críticos para sua aplicação, é possível usar `LocationManager` diretamente apenas para esses campos extras. No entanto, isso:

- Aumenta o consumo de bateria
- Requer mais código de gerenciamento
- Pode não funcionar bem em todos os dispositivos

**Recomendação**: Manter uso do FusedLocationProvider e documentar que campos detalhados não estão disponíveis.

## Motion Detection - Sensores Específicos (REMOVIDO)

### Status: Campos Removidos do Sistema

Os seguintes campos de motion detection foram **removidos do código** porque os sensores físicos não existem no dispositivo Moto G34 5G:

- `significantMotion` - Movimento significativo
- `stationaryDetect` - Detecção de estacionário
- `motionDetect` - Detecção de movimento
- `flatUp`, `flatDown`, `stowed`, `displayRotate` - Sensores específicos Motorola

### Causa

Esses sensores não estão disponíveis fisicamente no dispositivo Moto G34 5G. Sensores específicos de fabricante (como os da Motorola) só estão disponíveis em dispositivos daquela marca que possuem esses sensores.

### Decisão

**Campos removidos do sistema** (código comentado, não coletados):
- Código Android: MotionDetectorProvider desabilitado
- Payload MQTT: Campo `motion` removido
- Backend: Campos motion removidos do modelo e INSERT SQL
- Banco de Dados: Colunas mantidas (sempre NULL) para flexibilidade futura

### Nota

Se trocar para um dispositivo que tenha esses sensores, o código pode ser reativado facilmente (está comentado, não deletado).

## WiFi - Campos Dependentes de Conexão

### Campos Afetados

Os seguintes campos de WiFi podem ser NULL se o dispositivo não estiver conectado a uma rede WiFi:

- `wifi_rssi` - Força do sinal (dBm)
- `wifi_ssid` - Nome da rede
- `wifi_channel` - Canal WiFi

### Causa

Esses campos só estão disponíveis quando o dispositivo está conectado a uma rede WiFi ativa.

### Campos Sempre Disponíveis

Mesmo sem conexão WiFi, os seguintes campos podem estar disponíveis:

- `wifi_bssid` - Endereço MAC do ponto de acesso
- `wifi_frequency` - Frequência do WiFi (MHz)

## Celular - Permissões Necessárias

### Campos Afetados

Os seguintes campos de celular requerem a permissão `READ_PHONE_STATE`:

- `cellular_network_type` - Tipo de rede (LTE, 5G, etc.)
- `cellular_operator` - Nome da operadora
- `cellular_rsrp` - Reference Signal Received Power (dBm)
- `cellular_rsrq` - Reference Signal Received Quality (dB)
- `cellular_rssnr` - Reference Signal Signal-to-Noise Ratio (dB)

### Permissão Necessária

```xml
<uses-permission android:name="android.permission.READ_PHONE_STATE" />
```

**Nota**: Esta permissão foi adicionada ao `AndroidManifest.xml` na versão atual do app.

### Campos Sem Permissão

Alguns campos podem estar disponíveis mesmo sem a permissão:

- `cellular_ci` - Cell Identity
- `cellular_pci` - Physical Cell Identity

## Bateria - Campos Opcionais

### Campos Que Podem Ser NULL

Alguns campos de bateria podem não estar disponíveis em todos os dispositivos ou versões do Android:

- `battery_level` - Nível de bateria (0-100%) - pode ser null se não disponível
- `battery_temperature` - Temperatura da bateria (°C)
- `battery_voltage` - Voltagem (mV)
- `battery_health` - Saúde da bateria (GOOD, OVERHEAT, etc.)
- `battery_technology` - Tecnologia da bateria (Li-ion, etc.)

### Campos Sempre Disponíveis

- `battery_status` - Status da bateria (CHARGING, DISCHARGING, FULL, etc.)
- `battery_charge_counter` - Contador de carga (μAh) - Android 5.0+
- `battery_full_capacity` - Capacidade total (μAh) - Android 5.0+

## Orientação - Dependência de Sensores

### Campos Disponíveis

Todos os campos de orientação estão disponíveis:

- `azimuth` - Direção (0-360°)
- `pitch` - Inclinação vertical (-180° a +180°)
- `roll` - Rotação lateral (-90° a +90°)

### Requisitos

Para calcular orientação completa, são necessários:

- Acelerômetro
- Magnetômetro

Se o magnetômetro não estiver disponível, apenas `pitch` e `roll` podem ser calculados (usando apenas acelerômetro).

## IMU Detalhado - Sensores Opcionais

### Campos Que Podem Ser NULL

Alguns campos IMU detalhados dependem de sensores específicos:

- `mag_x`, `mag_y`, `mag_z` - Magnetômetro (requer `TYPE_MAGNETIC_FIELD`)
- `linear_accel_x`, `linear_accel_y`, `linear_accel_z` - Aceleração linear (requer `TYPE_LINEAR_ACCELERATION`)
- `gravity_x`, `gravity_y`, `gravity_z` - Gravidade isolada (requer `TYPE_GRAVITY`)
- `rotation_vector_x`, `rotation_vector_y`, `rotation_vector_z`, `rotation_vector_w` - Rotação vetorial (requer `TYPE_ROTATION_VECTOR`)

### Campos Sempre Disponíveis

- `accel_x`, `accel_y`, `accel_z` - Acelerômetro básico
- `gyro_x`, `gyro_y`, `gyro_z` - Giroscópio básico
- `accel_magnitude` - Magnitude da aceleração (calculada)
- `gyro_magnitude` - Magnitude da rotação (calculada)

## Resumo de Limitações por Categoria

| Categoria | Campos Afetados | Causa | Solução |
|-----------|----------------|-------|---------|
| GPS Detalhado | 8 campos | FusedLocationProvider não fornece | Documentar limitação |
| Motion Detection | 7 campos | Sensores podem não estar disponíveis | Verificar disponibilidade |
| WiFi | 3 campos | WiFi pode não estar conectado | Conectar a WiFi |
| Celular | 5 campos | Permissão faltando | Adicionar `READ_PHONE_STATE` ✅ |
| Bateria | 6 campos | Campos opcionais | Documentar como opcionais |
| Orientação | 0 campos | Todos funcionam | - |
| IMU Detalhado | 12 campos | Sensores opcionais | Verificar disponibilidade |

## Verificação de Limitações

Para verificar quais limitações se aplicam ao seu dispositivo:

1. Execute `check_available_sensors.ps1` para verificar sensores disponíveis
2. Execute `analyze_nulls.ps1` para verificar campos NULL no banco
3. Verifique logs do app para erros de permissão ou sensores não disponíveis

