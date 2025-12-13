# Análise Completa: Dados Atualmente Capturados vs Disponíveis

## Resumo Executivo

O app AuraTracking atualmente captura **16 campos** de dados (GPS + IMU básico). Existem **25 campos adicionais** disponíveis no dispositivo Android que não estão sendo capturados, sendo **15 deles críticos** para análise de movimento de caminhões.

---

## 1. Dados Atualmente Capturados

### 1.1 GPS (GpsData) - 10 campos

| Campo | Tipo | Unidade | Descrição |
|-------|------|---------|-----------|
| latitude | Double | graus | Latitude GPS |
| longitude | Double | graus | Longitude GPS |
| altitude | Double | metros | Altitude GPS |
| speed | Float | m/s | Velocidade |
| bearing | Float | graus | Direção (0-360°) |
| accuracy | Float | metros | Precisão do fix |
| timestamp | Long | ms | Timestamp do app |
| ageMs | Long | ms | Idade do fix GPS |
| intervalSinceLastFixMs | Long | ms | Intervalo desde último fix |
| temporalQuality | String | - | Qualidade temporal |

**Total GPS:** 10 campos ✅

### 1.2 IMU (ImuData) - 6 campos

| Campo | Tipo | Unidade | Descrição |
|-------|------|---------|-----------|
| accelX | Float | m/s² | Aceleração X |
| accelY | Float | m/s² | Aceleração Y |
| accelZ | Float | m/s² | Aceleração Z |
| gyroX | Float | rad/s | Rotação X |
| gyroY | Float | rad/s | Rotação Y |
| gyroZ | Float | rad/s | Rotação Z |

**Total IMU:** 6 campos ✅

**TOTAL ATUAL:** 16 campos

---

## 2. Dados Disponíveis mas NÃO Capturados

### 2.1 GPS Detalhado - 5 campos faltando

| Campo | Tipo | Unidade | Prioridade | Motivo |
|-------|------|---------|------------|--------|
| satellites | Integer | - | 🔴 CRÍTICA | Qualidade do fix GPS |
| hdop | Float | - | 🔴 CRÍTICA | Precisão horizontal |
| vdop | Float | - | 🔴 CRÍTICA | Precisão vertical |
| pdop | Float | - | 🟡 MÉDIA | Precisão geral |
| gpsTimestamp | Long | ms | 🟡 MÉDIA | Timestamp do fix (não do app) |

**Impacto:** Sem esses dados, não é possível filtrar dados GPS ruins ou avaliar confiabilidade da posição.

---

### 2.2 Sensores IMU Avançados - 9 campos faltando

| Campo | Tipo | Unidade | Sensor | Prioridade | Motivo |
|-------|------|---------|--------|------------|--------|
| magX | Float | μT | Magnetômetro | 🔴 CRÍTICA | Direção real (mão vs contramão) |
| magY | Float | μT | Magnetômetro | 🔴 CRÍTICA | Direção real (mão vs contramão) |
| magZ | Float | μT | Magnetômetro | 🔴 CRÍTICA | Direção real (mão vs contramão) |
| pressure | Float | hPa | Barômetro | 🔴 CRÍTICA | Altitude precisa, detectar rampas |
| linearAccelX | Float | m/s² | Linear Accel | 🔴 CRÍTICA | Aceleração real do veículo |
| linearAccelY | Float | m/s² | Linear Accel | 🔴 CRÍTICA | Aceleração real do veículo |
| linearAccelZ | Float | m/s² | Linear Accel | 🔴 CRÍTICA | Aceleração real do veículo |
| gravityX | Float | m/s² | Gravity | 🟡 MÉDIA | Inclinação (redundante) |
| gravityY | Float | m/s² | Gravity | 🟡 MÉDIA | Inclinação (redundante) |
| gravityZ | Float | m/s² | Gravity | 🟡 MÉDIA | Inclinação (redundante) |

**Impacto:** Sem magnetômetro, não é possível separar mão vs contramão. Sem barômetro, não é possível detectar rampas com precisão. Sem aceleração linear, não é possível detectar frenagens/acelerações bruscas.

---

### 2.3 Orientação - 3 campos faltando (calculáveis)

| Campo | Tipo | Unidade | Requer | Prioridade | Motivo |
|-------|------|---------|--------|------------|--------|
| azimuth | Float | graus | Accel + Mag | 🔴 CRÍTICA | Direção do movimento |
| pitch | Float | graus | Accel + Mag | 🔴 CRÍTICA | Inclinação frontal (rampas) |
| roll | Float | graus | Accel + Mag | 🔴 CRÍTICA | Inclinação lateral (curvas) |

**Impacto:** Essencial para análise de comportamento e separação de fluxos em rampas.

---

### 2.4 Dados de Sistema - 5 campos faltando

| Campo | Tipo | Unidade | Prioridade | Motivo |
|-------|------|---------|------------|--------|
| batteryLevel | Integer | % | 🟠 ALTA | Detectar quando carregando |
| batteryStatus | String | - | 🟠 ALTA | Filtrar dados quando parado |
| batteryTemperature | Float | °C | 🟡 MÉDIA | Saúde do dispositivo |
| networkType | String | - | 🟢 BAIXA | Contexto (debugging) |
| signalStrength | Integer | dBm | 🟢 BAIXA | Qualidade transmissão |

**Impacto:** Sem status de bateria, não é possível filtrar dados quando dispositivo está carregando (pode estar parado).

---

## 3. Análise Crítica: O que VALE A PENA Capturar

### 3.1 🔴 CRÍTICO (Implementar Primeiro)

#### Magnetômetro + Orientação
- **Por quê:** Detectar direção real do movimento (mão vs contramão)
- **Uso:** Separação de fluxos em rampas, análise de comportamento
- **Impacto:** Resolve problema de contaminação de dados em rampas

#### Barômetro (Pressão)
- **Por quê:** Altitude mais precisa que GPS (resolução ~1m vs ~10m)
- **Uso:** Detectar subidas/descidas, calcular inclinação da estrada
- **Impacto:** Identificar rampas, separar caminhões subindo vs descendo

#### Aceleração Linear
- **Por quê:** Aceleração real do veículo (sem gravidade)
- **Uso:** Detectar frenagens/acelerações bruscas
- **Impacto:** Análise de comportamento de direção, segurança

#### GPS Detalhado (Satélites, HDOP, VDOP)
- **Por quê:** Qualidade do fix GPS, confiabilidade da posição
- **Uso:** Filtrar dados ruins, melhorar análise
- **Impacto:** Dados mais confiáveis, menos ruído

#### Bateria (Nível, Status)
- **Por quê:** Detectar quando dispositivo está carregando (pode estar parado)
- **Uso:** Filtrar dados quando dispositivo não está em movimento
- **Impacto:** Dados mais limpos, menos falsos positivos

---

### 3.2 🟡 MÉDIA PRIORIDADE (Opcional)

#### Gravidade Isolada
- **Por quê:** Pode ajudar a detectar inclinação do veículo
- **Contra:** Redundante com barômetro + aceleração linear
- **Decisão:** Implementar apenas se fácil, como backup

#### Rotação Vetorial (Quaternion)
- **Por quê:** Orientação 3D precisa
- **Contra:** Redundante com magnetômetro + orientação calculada
- **Decisão:** Pode ser calculada, não precisa do sensor direto

#### Conectividade (Tipo de Rede)
- **Por quê:** Contexto de onde dados foram coletados
- **Contra:** Não afeta análise de movimento diretamente
- **Decisão:** Útil para debugging, implementar se fácil

---

### 3.3 ❌ BAIXA PRIORIDADE (Não Implementar)

- **Umidade Relativa:** Não afeta análise de movimento
- **Luminosidade:** Não afeta análise de movimento
- **CPU/Memória:** Dados de sistema não relevantes
- **Temperatura Ambiente:** Não afeta análise diretamente
- **Modelo/Versão Android:** Metadados estáticos (enviar uma vez por sessão)

---

## 4. Estrutura MQTT Proposta

### 4.1 Payload Expandido (JSON)

```json
{
  "messageId": "uuid-v4",
  "deviceId": "motorola-001",
  "matricula": "OP12345",
  "timestamp": 1704067200000,
  
  "gps": {
    "lat": -22.906847,
    "lon": -43.172896,
    "alt": 15.5,
    "speed": 8.33,
    "bearing": 45.0,
    "accuracy": 5.0,
    "satellites": 12,
    "hdop": 1.2,
    "vdop": 2.1,
    "pdop": 2.4,
    "gpsTimestamp": 1704067199500
  },
  
  "imu": {
    "accelX": 0.5,
    "accelY": -0.2,
    "accelZ": 9.8,
    "gyroX": 0.01,
    "gyroY": 0.02,
    "gyroZ": -0.01,
    "magX": 25.3,
    "magY": -5.2,
    "magZ": 42.1,
    "pressure": 1013.25,
    "linearAccelX": 0.3,
    "linearAccelY": -0.1,
    "linearAccelZ": 0.0,
    "gravityX": 0.2,
    "gravityY": -0.1,
    "gravityZ": 9.8
  },
  
  "orientation": {
    "azimuth": 45.0,
    "pitch": 2.5,
    "roll": -1.2,
    "rotationMatrix": [0.707, -0.707, 0.0, 0.707, 0.707, 0.0, 0.0, 0.0, 1.0]
  },
  
  "system": {
    "battery": {
      "level": 85,
      "temperature": 28.5,
      "status": "DISCHARGING",
      "voltage": 4200
    },
    "connectivity": {
      "networkType": "CELLULAR_4G",
      "signalStrength": -85,
      "operator": "VIVO"
    }
  },
  
  "metadata": {
    "deviceModel": "motorola g34",
    "androidVersion": "13",
    "appVersion": "1.0.0"
  }
}
```

### 4.2 Estrutura por Prioridade

#### Campos Obrigatórios (sempre presentes)
- `messageId`, `deviceId`, `matricula`, `timestamp`
- `gps.lat`, `gps.lon`, `gps.alt`, `gps.speed`, `gps.bearing`, `gps.accuracy`

#### Campos Críticos (alta prioridade, null se não disponível)
- `gps.satellites`, `gps.hdop`, `gps.vdop`, `gps.pdop`
- `imu.magX`, `imu.magY`, `imu.magZ`, `imu.pressure`
- `imu.linearAccelX`, `imu.linearAccelY`, `imu.linearAccelZ`
- `orientation.azimuth`, `orientation.pitch`, `orientation.roll`
- `system.battery.level`, `system.battery.status`

#### Campos Opcionais (média prioridade, null se não disponível)
- `imu.gravityX`, `imu.gravityY`, `imu.gravityZ`
- `orientation.rotationMatrix`
- `system.connectivity.networkType`, `system.connectivity.signalStrength`

#### Campos de Metadados (baixa frequência, enviar uma vez por sessão)
- `metadata.deviceModel`, `metadata.androidVersion`, `metadata.appVersion`

### 4.3 Tamanho Estimado

- **Payload Atual:** ~200 bytes
- **Payload Expandido (crítico):** ~400 bytes
- **Payload Completo (crítico + opcional):** ~600 bytes

**Impacto:** Aumento de 2-3x no tamanho, mas ainda aceitável para MQTT a 1Hz.

---

## 5. Recomendações de Implementação

### Fase 1: Sensores Críticos (Prioridade Máxima)
1. ✅ Magnetômetro (magX, magY, magZ)
2. ✅ Barômetro (pressure)
3. ✅ Aceleração Linear (linearAccelX, linearAccelY, linearAccelZ)
4. ✅ GPS Detalhado (satellites, hdop, vdop)
5. ✅ Orientação Calculada (azimuth, pitch, roll)
6. ✅ Bateria (level, status)

### Fase 2: Sensores Opcionais (Se Fácil)
7. ⚠️ Gravidade Isolada (gravityX, gravityY, gravityZ)
8. ⚠️ Rotação Vetorial (rotationVector)
9. ⚠️ Conectividade (networkType, signalStrength)

### Fase 3: Metadados (Uma Vez por Sessão)
10. ℹ️ Metadados do dispositivo (deviceModel, androidVersion, appVersion)

---

## 6. Benefícios Esperados

### Análise de Movimento
- ✅ Separação precisa de mão vs contramão
- ✅ Detecção automática de rampas
- ✅ Cálculo de inclinação da estrada
- ✅ Identificação de comportamento de direção

### Qualidade de Dados
- ✅ Filtro de dados GPS ruins (via HDOP/VDOP)
- ✅ Filtro de dados quando dispositivo está carregando
- ✅ Dados mais confiáveis e precisos

### Análise de Comportamento
- ✅ Detecção de frenagens bruscas
- ✅ Detecção de acelerações fortes
- ✅ Análise de curvas e mudanças de direção

---

## 7. Próximos Passos

1. ✅ Executar scripts ADB no Motorola real
2. ✅ Analisar resultados e confirmar disponibilidade
3. ✅ Validar estrutura MQTT proposta
4. ⏳ Planejar implementação no código Android
5. ⏳ Implementar sensores críticos primeiro
6. ⏳ Testar e validar dados capturados
7. ⏳ Expandir para sensores opcionais se necessário

