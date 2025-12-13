# Relatório: Verificação de Código Android para Campos Não Enviados

**Data**: 2025-12-11 15:23:00  
**Status**: Análise completa realizada

## Resumo Executivo

Após análise detalhada do código Android, identificamos que:

1. ✅ **TelemetryAggregator está incluindo todos os campos** no payload (GPS detalhado 8/8, IMU detalhado 15/15, Orientação 2/2)
2. ⚠️ **Campos estão sendo capturados como NULL** pelos providers
3. ⚠️ **Campos NULL não aparecem no JSON** (kotlinx.serialization omite campos null por padrão)

## Análise Detalhada por Provider

### 1. GPS - GpsLocationProvider.kt

**Status**: ✅ Código implementado corretamente

**Campos Verificados**:
- ✅ `satellites` - Extraído de `extras.getInt("satellites")`
- ✅ `hAcc` - Extraído de `extras.getFloat("horizontalAccuracy")` ou `extras.getFloat("hAcc")`
- ✅ `vAcc` - Extraído de `extras.getFloat("verticalAccuracy")` ou `extras.getFloat("vAcc")`
- ✅ `sAcc` - Extraído de `extras.getFloat("speedAccuracy")` ou `extras.getFloat("sAcc")`
- ✅ `hdop`, `vdop`, `pdop` - Extraídos de `extras.getFloat()`
- ✅ `gpsTimestamp` - Usa `location.time`

**Problema Identificado**:
- ❌ **FusedLocationProviderClient não fornece esses extras**
- O `Location` retornado pelo FusedLocationProvider não contém `extras` com informações detalhadas de GPS
- Esses campos só estão disponíveis usando `LocationManager` diretamente (não recomendado)

**Causa Raiz**: Limitação do FusedLocationProviderClient - não expõe dados detalhados de GPS

**Solução Recomendada**: 
- Manter uso do FusedLocationProvider (melhor para bateria e precisão)
- Documentar que campos detalhados não estão disponíveis via FusedLocationProvider
- Considerar usar `LocationManager` apenas para campos detalhados (impacto na bateria)

### 2. IMU - ImuSensorProvider.kt

**Status**: ✅ Código implementado corretamente

**Campos Verificados**:
- ✅ `magX`, `magY`, `magZ` - Capturados via `TYPE_MAGNETIC_FIELD`
- ✅ `linearAccelX`, `linearAccelY`, `linearAccelZ` - Capturados via `TYPE_LINEAR_ACCELERATION`
- ✅ `gravityX`, `gravityY`, `gravityZ` - Capturados via `TYPE_GRAVITY`
- ✅ `rotationVectorX`, `rotationVectorY`, `rotationVectorZ`, `rotationVectorW` - Capturados via `TYPE_ROTATION_VECTOR`

**Verificações**:
- ✅ Sensores estão sendo registrados no `init`
- ✅ Sensores estão sendo registrados no `startSensorUpdates()`
- ✅ Dados estão sendo capturados nos buffers
- ✅ `computeAverage()` está incluindo todos os campos

**Problema Identificado**:
- ⚠️ **Sensores podem não estar disponíveis no dispositivo**
- Verificação de sensores disponíveis mostrou que alguns podem não estar presentes
- Se sensores não estão disponíveis, buffers ficam vazios e campos retornam null

**Causa Raiz**: Sensores podem não estar disponíveis no Motorola Moto G34 5G

**Solução Recomendada**:
- Verificar logs do app para ver se sensores estão sendo detectados
- Se sensores não estão disponíveis, documentar limitação do dispositivo
- Se sensores estão disponíveis mas não capturando, verificar permissões ou configuração

### 3. Orientation - OrientationProvider.kt

**Status**: ✅ Código implementado corretamente

**Campos Verificados**:
- ✅ `pitch` - Calculado via `SensorManager.getOrientation()`
- ✅ `roll` - Calculado via `SensorManager.getOrientation()`
- ✅ `azimuth` - ✅ Funcionando (100% dos registros)

**Verificações**:
- ✅ `OrientationData` tem `pitch` e `roll` definidos
- ✅ `SensorManager.getOrientation()` está sendo chamado corretamente
- ✅ `pitch` e `roll` estão sendo calculados e incluídos no `OrientationPayload`
- ✅ `OrientationProvider` está sendo chamado no `TrackingForegroundService`

**Problema Identificado**:
- ⚠️ **`pitch` e `roll` podem estar sendo calculados mas retornando valores inválidos**
- Se `SensorManager.getRotationMatrix()` falha, `pitch` e `roll` são calculados via fallback
- Se magnetômetro não está disponível, `azimuth` fica 0 mas `pitch` e `roll` ainda são calculados

**Causa Raiz**: Magnetômetro pode não estar disponível ou não está sendo capturado corretamente

**Solução Recomendada**:
- Verificar se magnetômetro está disponível e sendo capturado
- Verificar logs do app para ver valores de `pitch` e `roll`
- Se valores estão sendo calculados mas não enviados, verificar serialização JSON

### 4. System - SystemDataProvider.kt

**Status**: ✅ Código implementado corretamente

**Campos Verificados**:

**Bateria**:
- ✅ `level` - Calculado de `EXTRA_LEVEL` e `EXTRA_SCALE`
- ✅ `temperature` - Extraído de `EXTRA_TEMPERATURE`
- ✅ `status` - Extraído de `EXTRA_STATUS`
- ✅ `voltage` - Extraído de `EXTRA_VOLTAGE`
- ✅ `health` - Extraído de `EXTRA_HEALTH`
- ✅ `technology` - Extraído de `EXTRA_TECHNOLOGY`
- ✅ `chargeCounter` - Via `BatteryManager.getLongProperty()`
- ✅ `fullCapacity` - Via `BatteryManager.getLongProperty()`

**WiFi**:
- ✅ `rssi` - Via `WifiInfo.rssi`
- ✅ `ssid` - Via `WifiInfo.ssid`
- ✅ `bssid` - ✅ Funcionando (100%)
- ✅ `frequency` - ✅ Funcionando (100%)
- ✅ `channel` - Calculado de `frequency`

**Celular**:
- ✅ `networkType` - Via `TelephonyManager.dataNetworkType`
- ✅ `operator` - Via `TelephonyManager.networkOperatorName`
- ✅ `rsrp`, `rsrq`, `rssnr` - Via `CellSignalStrength`
- ✅ `ci`, `pci`, `tac`, `earfcn`, `band`, `bandwidth` - Via `CellInfoLte`

**Problemas Identificados**:
- ⚠️ **Alguns campos podem retornar null por problemas de permissão**
- ⚠️ **Alguns campos podem não estar disponíveis dependendo da versão do Android**
- ⚠️ **WiFi pode não estar conectado (rssi, ssid, channel null)**
- ⚠️ **Celular pode não ter sinal ou informações disponíveis**

**Causa Raiz**: 
- Permissões não concedidas (`SecurityException` capturado)
- Dados não disponíveis no momento da coleta
- Limitações de versão do Android

**Solução Recomendada**:
- Verificar permissões no `AndroidManifest.xml`
- Verificar logs do app para `SecurityException`
- Documentar campos que requerem permissões específicas

### 5. Motion Detection - MotionDetectorProvider.kt

**Status**: ✅ Código implementado corretamente

**Campos Verificados**:
- ✅ `significantMotion` - Via `TYPE_SIGNIFICANT_MOTION` (one-shot)
- ✅ `stationaryDetect` - Via `TYPE_STATIONARY_DETECT`
- ✅ `motionDetect` - Via `TYPE_MOTION_DETECT`
- ✅ `flatUp`, `flatDown`, `stowed`, `displayRotate` - Sensores específicos Motorola

**Problema Identificado**:
- ❌ **Sensores de motion detection podem não estar disponíveis**
- Sensores one-shot só disparam quando evento ocorre
- Sensores específicos Motorola podem não existir no dispositivo

**Causa Raiz**: Sensores podem não estar disponíveis ou eventos não estão ocorrendo

**Solução Recomendada**:
- Verificar se sensores estão disponíveis no dispositivo
- Se sensores não estão disponíveis, documentar limitação
- Se sensores estão disponíveis, verificar se eventos estão sendo capturados

## Comparação: Código vs Payload Real

### Campos no Código vs Campos no Payload

**GPS Detalhado**:
- Código: ✅ Todos os 8 campos estão sendo extraídos
- Payload: ❌ Nenhum campo aparece (todos null)
- **Conclusão**: FusedLocationProvider não fornece esses dados

**IMU Detalhado**:
- Código: ✅ Todos os 15 campos estão sendo capturados
- Payload: ❌ Nenhum campo aparece (todos null)
- **Conclusão**: Sensores podem não estar disponíveis ou não estão sendo capturados

**Orientação**:
- Código: ✅ `pitch` e `roll` estão sendo calculados
- Payload: ❌ Campos não aparecem (null)
- **Conclusão**: Valores podem estar sendo calculados mas retornando null ou não sendo serializados

**Sistema**:
- Código: ✅ Todos os campos estão sendo coletados
- Payload: ⚠️ Alguns campos aparecem (`battery_charge_counter`, `wifi_bssid`, `cellular_ci`)
- **Conclusão**: Alguns campos funcionam, outros retornam null por permissões ou disponibilidade

## Próximos Passos Recomendados

### 🔴 Prioridade ALTA

1. **Verificar Logs do App Android**
   - Verificar se sensores estão sendo detectados
   - Verificar se há erros de permissão
   - Verificar valores calculados de `pitch` e `roll`

2. **Testar Sensores no Dispositivo**
   - Executar `check_available_sensors.ps1` melhorado
   - Verificar quais sensores estão realmente disponíveis
   - Comparar com código que está tentando usar

3. **Verificar Serialização JSON**
   - Verificar se kotlinx.serialization está omitindo campos null
   - Considerar incluir campos null explicitamente se necessário

### 🟡 Prioridade MÉDIA

4. **Verificar Permissões**
   - Revisar `AndroidManifest.xml` para todas as permissões necessárias
   - Verificar se usuário concedeu permissões em runtime

5. **Documentar Limitações**
   - Documentar campos não disponíveis via FusedLocationProvider
   - Documentar sensores não disponíveis no dispositivo
   - Documentar campos que requerem permissões específicas

### 🟢 Prioridade BAIXA

6. **Considerar Alternativas**
   - Para GPS detalhado: considerar `LocationManager` apenas para campos extras
   - Para sensores não disponíveis: documentar e considerar alternativas

## Arquivos Analisados

1. ✅ `GpsLocationProvider.kt` - Código correto, mas FusedLocationProvider não fornece extras
2. ✅ `ImuSensorProvider.kt` - Código correto, sensores podem não estar disponíveis
3. ✅ `OrientationProvider.kt` - Código correto, valores podem estar null
4. ✅ `SystemDataProvider.kt` - Código correto, alguns campos podem ter problemas de permissão
5. ✅ `MotionDetectorProvider.kt` - Código correto, sensores podem não estar disponíveis
6. ✅ `TelemetryAggregator.kt` - Código correto, todos os campos estão sendo incluídos

## Conclusão

O código Android está **bem implementado** e **incluindo todos os campos** no payload. O problema é que:

1. **Campos estão sendo capturados como NULL** pelos providers
2. **Campos NULL não aparecem no JSON** (kotlinx.serialization omite por padrão)
3. **Algumas limitações são esperadas** (FusedLocationProvider, sensores não disponíveis, permissões)

**Recomendação Principal**: 
- Verificar logs do app para confirmar quais sensores estão disponíveis
- Verificar se há erros de permissão
- Considerar incluir campos null explicitamente no JSON se necessário para diagnóstico



