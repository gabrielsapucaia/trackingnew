# Guia de Troubleshooting para Campos NULL

Este guia ajuda a diagnosticar por que campos estão NULL no banco de dados.

## Fluxo de Dados

```
Provider (Android) → TelemetryAggregator → MQTT → Ingest → TimescaleDB
```

## Passo 1: Verificar se Campo Está Sendo Capturado pelo Provider

### 1.1 Verificar Código do Provider

Verifique se o provider está tentando capturar o campo:

```bash
# Exemplo: Verificar se GpsLocationProvider está extraindo satellites
grep -r "satellites" AuraTracking/app/src/main/java/com/aura/tracking/sensors/gps/
```

### 1.2 Verificar Logs do App Android

```powershell
# Capturar logs do app
adb logcat | Select-String -Pattern "GpsLocationProvider|ImuSensorProvider|SystemDataProvider|OrientationProvider"
```

**Procurar por**:
- Mensagens de erro ou warning
- Valores sendo capturados
- Sensores não disponíveis

### 1.3 Verificar Sensores Disponíveis

```powershell
# Verificar sensores disponíveis no dispositivo
.\check_available_sensors.ps1
```

**Verificar**:
- Se sensor necessário está disponível
- Se sensor está sendo registrado corretamente

## Passo 2: Verificar se Campo Está Sendo Incluído no Payload

### 2.1 Verificar TelemetryAggregator

Verifique se o campo está sendo incluído no payload:

```bash
# Exemplo: Verificar se satellites está sendo incluído no GpsPayload
grep -A 5 "GpsPayload" AuraTracking/app/src/main/java/com/aura/tracking/background/TelemetryAggregator.kt
```

### 2.2 Verificar Payload MQTT Real

```powershell
# Comparar payload vs banco
.\compare_provider_payload.ps1 -Samples 5
```

**Verificar**:
- Se campo está presente no payload JSON
- Se campo está sendo mapeado corretamente no banco

### 2.3 Verificar Payload no Banco

```sql
-- Verificar payload JSON de registros recentes
SELECT 
    time,
    device_id,
    raw_payload::json->'gps'->>'satellites' as satellites_in_payload,
    satellites as satellites_in_db
FROM telemetry
WHERE time > NOW() - INTERVAL '5 minutes'
ORDER BY time DESC
LIMIT 10;
```

**Interpretação**:
- Se `satellites_in_payload` é NULL mas `satellites_in_db` não é NULL: problema no mapeamento Python
- Se ambos são NULL: app não está enviando o campo
- Se `satellites_in_payload` não é NULL mas `satellites_in_db` é NULL: problema no ingest Python

## Passo 3: Verificar se Campo Está Sendo Salvo no Banco

### 3.1 Verificar Schema do Banco

```sql
-- Verificar se coluna existe
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'telemetry' AND column_name = 'satellites';
```

### 3.2 Verificar Ingest Python

Verifique se o campo está sendo mapeado corretamente:

```bash
# Verificar mapeamento no código Python
grep -r "satellites" AuraTrackingServer/ingest/src/main.py
```

### 3.3 Verificar Logs do Ingest

```powershell
# Verificar logs do serviço de ingest
docker compose logs ingest | Select-String -Pattern "error|Error|ERROR|satellites"
```

## Problemas Comuns e Soluções

### Problema 1: Campo Sempre NULL - Sensor Não Disponível

**Sintomas**:
- Campo sempre NULL no banco
- Logs mostram "sensor not available"
- `check_available_sensors.ps1` confirma sensor não disponível

**Solução**:
- Documentar limitação do dispositivo
- Verificar se há alternativa (outro sensor ou cálculo)
- Considerar se campo é realmente necessário

**Exemplo**: `TYPE_GRAVITY` não disponível → `gravity_x/y/z` sempre NULL

### Problema 2: Campo Sempre NULL - Permissão Faltando

**Sintomas**:
- Campo sempre NULL no banco
- Logs mostram "permission not granted"
- `AndroidManifest.xml` não tem permissão

**Solução**:
- Adicionar permissão ao `AndroidManifest.xml`
- Recompilar app
- Verificar se usuário concedeu permissão em runtime (Android 6.0+)

**Exemplo**: `READ_PHONE_STATE` faltando → `cellular_network_type` sempre NULL

### Problema 3: Campo Sempre NULL - Limitação Conhecida

**Sintomas**:
- Campo sempre NULL no banco
- Código está correto
- Limitação documentada

**Solução**:
- Documentar limitação
- Considerar alternativa se campo for crítico
- Aceitar limitação se campo não for crítico

**Exemplo**: FusedLocationProvider não fornece `satellites` → sempre NULL

### Problema 4: Campo Parcialmente NULL - Condição Não Atendida

**Sintomas**:
- Campo NULL em alguns registros, não NULL em outros
- Padrão relacionado a condições (WiFi conectado, etc.)

**Solução**:
- Verificar condição de disponibilidade
- Documentar quando campo pode ser NULL
- Considerar se comportamento é esperado

**Exemplo**: `wifi_rssi` NULL quando WiFi não conectado → comportamento esperado

### Problema 5: Campo no Payload mas NULL no Banco

**Sintomas**:
- Campo presente no `raw_payload` JSON
- Campo NULL na coluna do banco
- `compare_provider_payload.ps1` mostra diferença

**Solução**:
- Verificar mapeamento no código Python (`_convert_packet_to_record`)
- Verificar se coluna está no INSERT statement
- Verificar logs do ingest para erros de parsing

**Exemplo**: `mag_x` no payload mas NULL no banco → verificar mapeamento Python

### Problema 6: Campo NULL no Payload mas Provider Captura

**Sintomas**:
- Provider está capturando dados (logs confirmam)
- Campo NULL no payload MQTT
- Campo NULL no banco

**Solução**:
- Verificar se `TelemetryAggregator` está incluindo campo
- Verificar se campo está sendo serializado corretamente (kotlinx.serialization)
- Verificar se campo nullable está sendo omitido do JSON

**Exemplo**: `battery_level` capturado mas NULL no payload → verificar serialização

## Scripts Úteis

### analyze_nulls.ps1

Analisa campos NULL no banco:

```powershell
.\analyze_nulls.ps1 -Hours 1
```

**Uso**: Identificar quais campos estão sempre NULL

### compare_provider_payload.ps1

Compara payload MQTT com dados extraídos:

```powershell
.\compare_provider_payload.ps1 -Samples 10
```

**Uso**: Verificar se campo está no payload mas não no banco

### check_available_sensors.ps1

Verifica sensores disponíveis no dispositivo:

```powershell
.\check_available_sensors.ps1
```

**Uso**: Verificar se sensores necessários estão disponíveis

### analyze_android_code.ps1

Analisa código Android para verificar campos:

```powershell
.\analyze_android_code.ps1
```

**Uso**: Verificar se código está tentando capturar campo

## Checklist de Diagnóstico

Use este checklist para diagnosticar campos NULL:

- [ ] Campo está sendo capturado pelo provider? (verificar logs)
- [ ] Sensor necessário está disponível? (`check_available_sensors.ps1`)
- [ ] Permissão necessária está no manifest? (verificar `AndroidManifest.xml`)
- [ ] Campo está sendo incluído no payload? (`compare_provider_payload.ps1`)
- [ ] Campo está no schema do banco? (verificar SQL)
- [ ] Campo está sendo mapeado no ingest? (verificar código Python)
- [ ] Campo está no INSERT statement? (verificar código Python)
- [ ] Há erros nos logs do ingest? (`docker compose logs ingest`)

## Exemplos de Diagnóstico

### Exemplo 1: satellites sempre NULL

1. **Verificar código**: ✅ GpsLocationProvider está tentando extrair
2. **Verificar logs**: ❌ FusedLocationProvider não fornece extras
3. **Conclusão**: Limitação conhecida do FusedLocationProvider
4. **Solução**: Documentar limitação

### Exemplo 2: cellular_network_type sempre NULL

1. **Verificar código**: ✅ SystemDataProvider está tentando coletar
2. **Verificar logs**: ❌ "Telephony permission not granted"
3. **Verificar manifest**: ❌ `READ_PHONE_STATE` faltando
4. **Solução**: Adicionar permissão ao manifest ✅

### Exemplo 3: wifi_rssi sempre NULL

1. **Verificar código**: ✅ SystemDataProvider está tentando coletar
2. **Verificar logs**: ✅ Sem erros
3. **Verificar conexão**: ❌ WiFi não conectado
4. **Conclusão**: Comportamento esperado (WiFi não conectado)
5. **Solução**: Conectar WiFi e verificar novamente

## Próximos Passos

Após diagnosticar:

1. **Se problema identificado**: Implementar correção
2. **Se limitação conhecida**: Documentar
3. **Se comportamento esperado**: Documentar condições
4. **Se problema não resolvido**: Investigar mais profundamente

## Referências

- `LIMITACOES.md` - Limitações conhecidas do sistema
- `CAMPOS_OPCIONAIS.md` - Campos opcionais e condições de disponibilidade
- `RELATORIO_CONSOLIDADO_FINAL.md` - Relatório completo de verificação



