# Resumo dos Resultados - Teste no Motorola Moto G34 5G

**Data do Teste:** 09/01/2025  
**Dispositivo:** Motorola Moto G34 5G (ZF524XRLK3)  
**Android:** 13

---

## ✅ Sensores Disponíveis e Status

### Sensores JÁ em Uso pelo App
- ✅ **Acelerômetro** (TDK-Invensense icm4x6xa) - 400Hz max
- ✅ **Giroscópio** (TDK-Invensense icm4x6xa) - 400Hz max

### Sensores Disponíveis mas NÃO em Uso (CRÍTICOS)
- 🔴 **Magnetômetro** (memsic mmc56x3x) - 100Hz max
  - **Impacto:** Sem isso, não é possível detectar direção real (mão vs contramão)
  - **Status:** Disponível e ativo no sistema

- 🔴 **Aceleração Linear** (qualcomm) - 200Hz max
  - **Impacto:** Sem isso, não é possível detectar aceleração real do veículo (sem gravidade)
  - **Status:** Disponível

### Sensores Disponíveis mas NÃO em Uso (OPCIONAIS)
- 🟡 **Gravidade Isolada** (qualcomm) - 200Hz max
- 🟡 **Rotação Vetorial** (qualcomm) - 200Hz max
- 🟡 **Game Rotation Vector** (qualcomm) - 200Hz max
- 🟡 **Geomagnetic Rotation Vector** (qualcomm) - 100Hz max
- 🟡 **Orientação** (qualcomm) - 200Hz max

### Sensores NÃO Disponíveis
- ❌ **Barômetro (Pressão)**
  - **Impacto:** Altitude precisa não será possível via barômetro
  - **Workaround:** Usar GPS altitude com vAcc (vertical accuracy) para filtrar dados ruins
  - **Nota:** GPS altitude tem precisão ~10m vs ~1m do barômetro

---

## 📍 GPS Detalhado

### Disponível
- ✅ **Satélites:** Sim (exemplo: 12 satélites)
  - Dados em: `Location.getExtras().getInt("satellites")`
  - Também disponível: `maxCn0=32, meanCn0=24`

- ✅ **Precisão Horizontal (hAcc):** Sim (exemplo: 11.6m)
- ✅ **Precisão Vertical (vAcc):** Sim (exemplo: 7.9m)

### Não Confirmado (Precisa Verificar no Código)
- ⚠️ **HDOP, VDOP, PDOP:** Não encontrados diretamente no dumpsys
  - **Nota:** Podem estar em `Location.getExtras()` - precisa verificar no código Android

---

## 🔋 Bateria

### Totalmente Disponível
- ✅ **Nível:** 0-100% (exemplo: 100%)
- ✅ **Temperatura:** Em décimos de grau (exemplo: 325 = 32.5°C)
- ✅ **Status:** CHARGING, DISCHARGING, FULL, etc. (exemplo: FULL)
- ✅ **Voltagem:** Em millivolts (exemplo: 4462mV)
- ✅ **Saúde:** GOOD, OVERHEAT, etc. (exemplo: GOOD)

**Implementação:** Via `BroadcastReceiver` para `ACTION_BATTERY_CHANGED`

---

## 🎯 Recomendações de Implementação

### FASE 1: Críticos (Implementar Primeiro)

1. **Magnetômetro** 🔴
   - **Por quê:** Detectar direção real (mão vs contramão)
   - **Como:** Adicionar `Sensor.TYPE_MAGNETIC_FIELD` ao `ImuSensorProvider`
   - **Impacto:** Resolve problema de contaminação de dados em rampas

2. **Aceleração Linear** 🔴
   - **Por quê:** Aceleração real do veículo (sem gravidade)
   - **Como:** Adicionar `Sensor.TYPE_LINEAR_ACCELERATION` ao `ImuSensorProvider`
   - **Impacto:** Detecta frenagens/acelerações bruscas

3. **Orientação Calculada** 🔴
   - **Por quê:** Direção e inclinação do veículo
   - **Como:** Criar `OrientationProvider` usando `SensorManager.getRotationMatrix()` com accel + mag
   - **Impacto:** Análise de comportamento, separação de fluxos

4. **GPS Satélites** 🔴
   - **Por quê:** Qualidade do fix GPS
   - **Como:** Extrair de `Location.getExtras().getInt("satellites")`
   - **Impacto:** Filtrar dados GPS ruins

5. **Bateria (Level, Status)** 🟠
   - **Por quê:** Filtrar dados quando dispositivo está carregando
   - **Como:** `BroadcastReceiver` para `ACTION_BATTERY_CHANGED`
   - **Impacto:** Dados mais limpos, menos falsos positivos

### FASE 2: Opcionais (Se Fácil)

6. **Gravidade Isolada** 🟡
   - Backup para cálculo de inclinação
   - Redundante com aceleração linear

7. **Rotação Vetorial** 🟡
   - Orientação 3D precisa
   - Pode ser calculada

---

## 📊 Estrutura MQTT Validada

### Campos que PODEM ser implementados:
- ✅ GPS: satellites, accuracy, verticalAccuracy
- ✅ IMU: magX/Y/Z, linearAccelX/Y/Z, gravityX/Y/Z
- ✅ Orientação: azimuth, pitch, roll, rotationMatrix
- ✅ Sistema: batteryLevel, batteryStatus, batteryTemperature, batteryVoltage

### Campos que NÃO podem ser implementados:
- ❌ GPS: hdop, vdop, pdop (precisa verificar no código)
- ❌ IMU: pressure (barômetro não disponível)

### Tamanho Estimado do Payload:
- **Atual:** ~200 bytes
- **Com críticos:** ~380 bytes (sem barômetro)
- **Completos:** ~550 bytes

---

## ⚠️ Limitações Identificadas

1. **Barômetro não disponível**
   - Altitude precisa não será possível via barômetro
   - GPS altitude terá precisão ~10m (vs ~1m barômetro)
   - **Solução:** Usar vAcc (vertical accuracy) para filtrar dados ruins

2. **HDOP/VDOP/PDOP não confirmados**
   - Não encontrados diretamente no dumpsys
   - Pode estar em `Location.getExtras()` - precisa verificar no código
   - **Solução:** Verificar extras do Location object no código Android

---

## ✅ Conclusão

O Motorola Moto G34 5G tem **excelente suporte de sensores** para análise de movimento:

- ✅ **8 sensores críticos disponíveis** (2 já em uso, 6 disponíveis mas não usados)
- ✅ **Magnetômetro disponível** - Resolve problema de direção (mão vs contramão)
- ✅ **Aceleração linear disponível** - Detecta aceleração real do veículo
- ✅ **GPS com satélites** - Qualidade do fix disponível
- ✅ **Bateria completa** - Todos os dados disponíveis
- ❌ **Barômetro não disponível** - Limitação, mas não crítica (GPS altitude funciona)

**Próximo passo:** Implementar sensores críticos no código Android conforme estrutura MQTT proposta.

