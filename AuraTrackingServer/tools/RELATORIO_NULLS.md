# Relatório de Diagnóstico de Dados NULL

**Data**: 2025-12-11 14:44:29  
**Período Analisado**: Últimas 1 hora  
**Total de Registros**: 0 (última hora) | 600+ (últimos 10 minutos)

## Resumo Executivo

### ✅ Campos Funcionando Corretamente (100% preenchidos nos últimos 10 minutos)

- **GPS Básico**: `latitude`, `longitude`, `altitude`, `speed`, `bearing`, `gps_accuracy`
- **IMU Básico**: `accel_x`, `accel_y`, `accel_z`, `gyro_x`, `gyro_y`, `gyro_z`
- **Magnitudes**: `gyro_magnitude` ✅
- **Orientação**: `azimuth` ✅ (600/600 registros)
- **Bateria**: `battery_level` ✅ (600/600 registros)
- **WiFi**: `wifi_bssid` ✅, `wifi_frequency` ✅ (600/600 registros)
- **Celular**: `cellular_ci` ✅, `cellular_pci` ✅ (600/600 registros)
- **Bateria Detalhada**: `battery_charge_counter` ✅, `battery_full_capacity` ✅ (600/600 registros)

### ⚠️ Problema Identificado: `accel_magnitude` sempre NULL

**Status**: ❌ **CRÍTICO** - Campo está no payload mas não está sendo salvo no banco

**Evidência**:
- Payload MQTT contém `accelMagnitude` com valores válidos (ex: 9.861437, 9.862827)
- Banco de dados mostra `accel_magnitude` sempre NULL (0/600 registros)
- `accel_x`, `accel_y`, `accel_z` estão sendo salvos corretamente
- `gyro_magnitude` está sendo salvo corretamente (600/600 registros)

**Causa Raiz Identificada**:
O código Python em `ingest/src/main.py` está:
1. ✅ Extraindo `accelMagnitude` do payload (linha 698)
2. ✅ Adicionando ao dicionário `record` com chave `accel_magnitude`
3. ❌ **NÃO incluindo `accel_magnitude` na lista de colunas do INSERT** (linhas 478-499)
4. ❌ **NÃO incluindo `%(accel_magnitude)s` na lista de VALUES** (linhas 500-521)

**Comparação**:
- `gyro_magnitude` está na lista de colunas (linha 483) ✅
- `accel_magnitude` **NÃO está** na lista de colunas ❌

### 📊 Campos Sempre NULL (última hora)

**Total**: 50 campos sempre NULL

#### GPS Detalhado (8 campos)
- `satellites`, `h_acc`, `v_acc`, `s_acc`, `hdop`, `vdop`, `pdop`, `gps_timestamp`

**Diagnóstico**: App Android pode não estar enviando esses campos ou GPS não está fornecendo dados detalhados.

#### IMU Detalhado (9 campos)
- `mag_x`, `mag_y`, `mag_z`, `mag_magnitude`
- `linear_accel_x`, `linear_accel_magnitude`
- `gravity_x`
- `rotation_vector_x`
- **`accel_magnitude`** ⚠️ (problema no código Python)

**Diagnóstico**: 
- Magnetômetro, aceleração linear, gravidade e rotação vetorial podem não estar sendo enviados pelo app
- `accel_magnitude` tem problema no código Python (ver acima)

#### Orientação (3 campos)
- `pitch`, `roll`
- `azimuth` ✅ (funcionando nos últimos 10 minutos)

**Diagnóstico**: `azimuth` está funcionando, mas `pitch` e `roll` podem não estar sendo enviados.

#### Sistema - Bateria (8 campos)
- `battery_temperature`, `battery_status`, `battery_voltage`
- `battery_health`, `battery_technology`
- `battery_charge_counter` ✅ (funcionando nos últimos 10 minutos)
- `battery_full_capacity` ✅ (funcionando nos últimos 10 minutos)
- `battery_level` ✅ (funcionando nos últimos 10 minutos)

**Diagnóstico**: Alguns campos de bateria estão funcionando, outros podem não estar disponíveis no dispositivo.

#### Sistema - WiFi (5 campos)
- `wifi_rssi`, `wifi_ssid`
- `wifi_bssid` ✅ (funcionando nos últimos 10 minutos)
- `wifi_frequency` ✅ (funcionando nos últimos 10 minutos)
- `wifi_channel`

**Diagnóstico**: `wifi_bssid` e `wifi_frequency` estão funcionando, outros podem não estar disponíveis.

#### Sistema - Celular (11 campos)
- `cellular_network_type`, `cellular_operator`
- `cellular_rsrp`, `cellular_rsrq`, `cellular_rssnr`
- `cellular_ci` ✅ (funcionando nos últimos 10 minutos)
- `cellular_pci` ✅ (funcionando nos últimos 10 minutos)
- `cellular_tac`, `cellular_earfcn`, `cellular_band`, `cellular_bandwidth`

**Diagnóstico**: `cellular_ci` e `cellular_pci` estão funcionando, outros podem não estar disponíveis.

#### Motion Detection (7 campos)
- `motion_significant_motion`, `motion_stationary_detect`, `motion_motion_detect`
- `motion_flat_up`, `motion_flat_down`, `motion_stowed`, `motion_display_rotate`

**Diagnóstico**: Sensores de detecção de movimento podem não estar disponíveis ou não estão sendo acionados.

## Comparação Payload vs Banco

### Amostra de 5 registros recentes:

| Campo | Payload | Banco | Status |
|-------|---------|-------|--------|
| `battery_charge_counter` | ✅ 5047078 | ✅ 5047078 | ✅ OK |
| `battery_full_capacity` | ✅ 100 | ✅ 100 | ✅ OK |
| `wifi_bssid` | ✅ 86:45:58:28:34:c3 | ✅ 86:45:58:28:34:c3 | ✅ OK |
| `wifi_frequency` | ✅ 5220 | ✅ 5220 | ✅ OK |
| `cellular_ci` | ✅ 69284324 | ✅ 69284324 | ✅ OK |
| `cellular_pci` | ✅ 52 | ✅ 52 | ✅ OK |
| `accelMagnitude` | ✅ 9.861134 | ❌ NULL | ❌ **PROBLEMA** |
| `gyroMagnitude` | ✅ 0.00027497468 | ✅ 0.00027497468 | ✅ OK |

## Recomendações

### 🔴 Prioridade ALTA

1. **Corrigir `accel_magnitude` no código Python**
   - **Arquivo**: `D:\tracking\AuraTrackingServer\ingest\src\main.py`
   - **Ação**: Adicionar `accel_magnitude` na lista de colunas do INSERT (após linha 482)
   - **Ação**: Adicionar `%(accel_magnitude)s` na lista de VALUES (após linha 504)
   - **Impacto**: Campo crítico para análise de movimento e detecção de rampas

### 🟡 Prioridade MÉDIA

2. **Verificar envio de dados GPS detalhados no app Android**
   - Verificar se `GpsLocationProvider.kt` está extraindo `satellites`, `h_acc`, `v_acc`, etc.
   - Verificar se esses dados estão sendo incluídos no payload MQTT

3. **Verificar envio de dados IMU detalhados no app Android**
   - Verificar se `ImuSensorProvider.kt` está capturando magnetômetro, aceleração linear, gravidade
   - Verificar se `OrientationProvider.kt` está enviando `pitch` e `roll`

4. **Verificar envio de dados de sistema no app Android**
   - Verificar se `SystemDataProvider.kt` está capturando todos os campos de bateria e conectividade

### 🟢 Prioridade BAIXA

5. **Documentar limitações do dispositivo**
   - Se alguns sensores não estão disponíveis no Motorola Moto G34 5G, documentar
   - Se alguns campos são opcionais por design, documentar

## Próximos Passos

1. ✅ Executar scripts de diagnóstico (CONCLUÍDO)
2. 🔴 Corrigir código Python para `accel_magnitude`
3. 🟡 Verificar logs do app Android para campos não enviados
4. 🟡 Testar após correções
5. 🟢 Documentar limitações conhecidas

## Arquivos Gerados

- `null_analysis_20251211_144428.json` - Análise completa de campos NULL
- Este relatório (`RELATORIO_NULLS.md`)



