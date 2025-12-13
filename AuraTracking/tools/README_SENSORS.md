# Guia de Teste e Análise de Sensores Android

Este guia explica como usar os scripts ADB para testar e analisar quais dados são possíveis extrair do dispositivo Motorola antes de implementar no código do app.

## Scripts Disponíveis

### 1. `inventory_all_sensors.sh`
Lista TODOS os sensores disponíveis no dispositivo e suas capacidades.

**Uso:**
```bash
./inventory_all_sensors.sh
./inventory_all_sensors.sh -o meu_inventario.json
```

**Output:** JSON com lista completa de sensores, incluindo tipo, nome, vendor, versão, resolução máxima.

**Quando usar:** Primeiro passo para descobrir quais sensores o dispositivo possui.

---

### 2. `monitor_telemetry.sh`
Monitora em tempo real TODOS os dados possíveis (GPS, IMU, bateria, conectividade).

**Uso:**
```bash
# Monitora por 60 segundos (padrão)
./monitor_telemetry.sh

# Monitora por 120 segundos com intervalo de 2 segundos
./monitor_telemetry.sh -d 120 -i 2

# Salva em arquivo específico
./monitor_telemetry.sh -o meus_dados.json
```

**Opções:**
- `-d, --duration`: Duração em segundos (padrão: 60)
- `-i, --interval`: Intervalo entre amostras em segundos (padrão: 1)
- `-o, --output`: Arquivo de saída JSON

**Output:** JSON com amostras contínuas de todos os dados disponíveis.

**Quando usar:** Para coletar dados reais em movimento e validar o que está disponível.

---

### 3. `extract_current_data.sh`
Extrai e documenta os dados que o app AuraTracking já captura atualmente.

**Uso:**
```bash
./extract_current_data.sh
./extract_current_data.sh -o dados_atuais.json
```

**Output:** JSON documentando todos os campos GPS e IMU que o app já captura, e quais estão disponíveis mas não capturados.

**Quando usar:** Para entender o estado atual do app e identificar gaps.

---

### 4. `compare_current_vs_available.sh`
Compara o que o app captura vs o que está disponível. Gera relatório de gaps e recomendações.

**Uso:**
```bash
./compare_current_vs_available.sh
./compare_current_vs_available.sh -o comparacao.json
```

**Output:** JSON com:
- Comparação detalhada campo por campo
- Prioridades (CRITICAL, HIGH, MEDIUM, LOW)
- Recomendações do que implementar
- Resumo de sensores disponíveis

**Quando usar:** Após executar os outros scripts, para ter uma visão consolidada das oportunidades.

---

## Fluxo Recomendado de Testes

1. **Inventário Inicial**
   ```bash
   ./inventory_all_sensors.sh -o inventario.json
   ```
   Verifica quais sensores estão disponíveis no Motorola.

2. **Monitoramento em Movimento**
   ```bash
   # Coloque o dispositivo em movimento (dentro de um veículo)
   ./monitor_telemetry.sh -d 300 -i 1 -o dados_movimento.json
   ```
   Coleta dados reais durante movimento para validar qualidade.

3. **Análise de Dados Atuais**
   ```bash
   ./extract_current_data.sh -o dados_atuais.json
   ```
   Documenta o que já está sendo capturado.

4. **Comparação e Recomendações**
   ```bash
   ./compare_current_vs_available.sh -o comparacao_final.json
   ```
   Gera relatório completo com recomendações.

---

## Visualizando Resultados

Todos os scripts geram JSON. Para visualizar melhor:

```bash
# Se tiver jq instalado
cat inventario.json | jq '.'
cat comparacao_final.json | jq '.recommendations.critical'

# Ou abra o arquivo JSON em um editor de texto
```

---

## Requisitos

- ADB instalado e no PATH
- Dispositivo Android conectado via USB com depuração USB ativada
- (Opcional) `jq` para formatação melhor do JSON
- (Opcional) `bc` para cálculos matemáticos no monitor_telemetry.sh

---

## Troubleshooting

**Erro: "Nenhum dispositivo Android conectado"**
- Verifique se o dispositivo está conectado: `adb devices`
- Ative "Depuração USB" nas opções de desenvolvedor
- Aceite o prompt de autorização no dispositivo

**Erro: "ADB não encontrado"**
- Instale Android SDK Platform Tools
- Adicione ao PATH ou use caminho completo

**Dados não aparecem:**
- Alguns dados requerem permissões específicas no app
- Sensores podem não estar disponíveis em todos os dispositivos
- Verifique logs do dispositivo: `adb logcat`

---

## Próximos Passos

Após executar os testes e analisar os resultados:

1. Validar quais sensores estão realmente disponíveis no Motorola
2. Confirmar estrutura MQTT proposta
3. Planejar implementação no código Android
4. Implementar sensores críticos primeiro
5. Testar e validar dados capturados

