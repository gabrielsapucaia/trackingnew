# Scripts de Diagnóstico de Dados NULL

Este diretório contém scripts para identificar, testar e diagnosticar campos NULL no banco de dados TimescaleDB.

## Scripts Disponíveis

### 1. `analyze_nulls.ps1`
Analisa todos os campos NULL no banco e gera um relatório JSON.

**Uso:**
```powershell
.\analyze_nulls.ps1 -Hours 1 -OutputFile "null_analysis.json"
```

**Parâmetros:**
- `-Hours`: Período em horas para análise (padrão: 1)
- `-OutputFile`: Nome do arquivo de saída (padrão: `null_analysis_YYYYMMDD_HHMMSS.json`)

**Saída:**
- Arquivo JSON com análise completa de todos os campos
- Lista de campos sempre NULL
- Lista de campos parcialmente NULL com percentual

### 2. `compare_payload_db.ps1`
Compara dados do payload MQTT (`raw_payload`) com dados extraídos nas colunas do banco.

**Uso:**
```powershell
.\compare_payload_db.ps1 -Samples 10
```

**Parâmetros:**
- `-Samples`: Número de amostras para comparar (padrão: 10)

**Saída:**
- Tabela comparando payload vs banco para campos críticos
- Identifica se problema está no mapeamento Python ou no app Android

### 3. `test_nulls_continuous.ps1`
Monitora campos NULL continuamente ao longo do tempo.

**Uso:**
```powershell
.\test_nulls_continuous.ps1 -DurationMinutes 5 -IntervalSeconds 30
```

**Parâmetros:**
- `-DurationMinutes`: Duração do monitoramento em minutos (padrão: 5)
- `-IntervalSeconds`: Intervalo entre verificações em segundos (padrão: 30)

**Saída:**
- Monitoramento em tempo real de campos críticos
- Percentuais de preenchimento ao longo do tempo

### 4. `diagnose_nulls.ps1`
Diagnóstico completo comparando payload com código Python e verificando logs.

**Uso:**
```powershell
.\diagnose_nulls.ps1 -Samples 5
```

**Parâmetros:**
- `-Samples`: Número de amostras para análise (padrão: 5)

**Saída:**
- Análise de campos críticos
- Verificação de logs do ingest para erros
- Diagnóstico da causa raiz

### 5. `run_all_null_tests.ps1` (Master)
Executa todos os testes em sequência.

**Uso:**
```powershell
.\run_all_null_tests.ps1 -Hours 1 -Samples 10 -DurationMinutes 5 -IntervalSeconds 30
```

**Parâmetros:**
- `-Hours`: Período para análise inicial (padrão: 1)
- `-Samples`: Número de amostras (padrão: 10)
- `-DurationMinutes`: Duração do monitoramento contínuo (padrão: 5)
- `-IntervalSeconds`: Intervalo do monitoramento (padrão: 30)
- `-SkipContinuous`: Pular monitoramento contínuo

**Saída:**
- Todos os resultados salvos em diretório timestamped
- Relatório consolidado

## Ordem Recomendada de Execução

1. **Análise Inicial**: `.\analyze_nulls.ps1 -Hours 1`
   - Identifica quais campos estão NULL

2. **Comparação Payload**: `.\compare_payload_db.ps1 -Samples 10`
   - Verifica se dados estão no payload mas não no banco

3. **Monitoramento Contínuo**: `.\test_nulls_continuous.ps1 -DurationMinutes 5`
   - Verifica se NULLs persistem ao longo do tempo

4. **Diagnóstico Completo**: `.\diagnose_nulls.ps1 -Samples 5`
   - Identifica causa raiz

5. **Ou execute tudo**: `.\run_all_null_tests.ps1`

## Diagnósticos Possíveis

### Cenário 1: Payload tem valor, banco NULL
**Causa**: Problema no mapeamento Python (`_convert_packet_to_record`)
**Solução**: Corrigir lógica de extração no código Python (`ingest/src/main.py`)

### Cenário 2: Payload NULL, banco NULL
**Causa**: App Android não está enviando o campo
**Solução**: Verificar código Android (`TelemetryAggregator.kt` e providers)

### Cenário 3: Payload tem valor, banco NULL (intermitente)
**Causa**: Validação Pydantic rejeitando valores ou erro de tipo
**Solução**: Verificar logs do ingest e modelos Pydantic

### Cenário 4: Campo sempre NULL
**Causa**: Sensor não disponível no dispositivo ou não implementado no app
**Solução**: Verificar disponibilidade do sensor e implementação no app

## Campos Críticos Monitorados

- **GPS**: `satellites`, `h_acc`, `v_acc`, `s_acc`, `hdop`, `vdop`, `pdop`, `gps_timestamp`
- **IMU**: `gyro_magnitude`, `mag_x`, `mag_y`, `mag_z`, `mag_magnitude`, `linear_accel_x`, `linear_accel_magnitude`, `gravity_x`, `rotation_vector_x`
- **Orientação**: `azimuth`, `pitch`, `roll`
- **Bateria**: `battery_level`, `battery_temperature`, `battery_status`, `battery_voltage`, `battery_health`, `battery_technology`, `battery_charge_counter`, `battery_full_capacity`
- **WiFi**: `wifi_rssi`, `wifi_ssid`, `wifi_bssid`, `wifi_frequency`, `wifi_channel`
- **Celular**: `cellular_network_type`, `cellular_operator`, `cellular_rsrp`, `cellular_rsrq`, `cellular_rssnr`, `cellular_ci`, `cellular_pci`, `cellular_tac`, `cellular_earfcn`, `cellular_band`, `cellular_bandwidth`
- **Motion Detection**: `motion_significant_motion`, `motion_stationary_detect`, `motion_motion_detect`, `motion_flat_up`, `motion_flat_down`, `motion_stowed`, `motion_display_rotate`

## Requisitos

- Docker Compose rodando com serviços `timescaledb` e `ingest`
- PowerShell 5.1 ou superior
- Acesso ao banco de dados TimescaleDB

## Exemplos de Uso

### Análise rápida (última hora):
```powershell
cd D:\tracking\AuraTrackingServer\tools
.\analyze_nulls.ps1 -Hours 1
```

### Comparação detalhada:
```powershell
.\compare_payload_db.ps1 -Samples 20
```

### Monitoramento longo:
```powershell
.\test_nulls_continuous.ps1 -DurationMinutes 30 -IntervalSeconds 60
```

### Execução completa:
```powershell
.\run_all_null_tests.ps1 -Hours 2 -Samples 20 -DurationMinutes 10
```



