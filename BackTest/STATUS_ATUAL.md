# ✅ DETECTOR VISUAL DE CARREGAMENTO - VERSÃO OFFLINE!

## 🎉 Status: NOVO! 100% OFFLINE - SEM SERVIDOR

### 🚀 Interface Visual (Modo Offline)
- **Status**: ✅ ATUALIZADO - Leitura direta do CSV
- **URL**: file:///Users/sapucaia/.claude-worktrees/BackTest/serene-mccarthy/BackendTestes/detector_visual.html
- **Modo**: Offline total - sem necessidade de servidor HTTP
- **Dados**: Carrega TODOS os 91.660 registros do input.csv
- **Performance**: 5-10 segundos para carregar arquivo completo
- **Tecnologia**: FileReader API + PapaParse (client-side)

---

## 🚀 COMO USAR AGORA (NOVO MÉTODO):

### 1️⃣ Abrir o Detector no Navegador:
```
Clique duas vezes em: detector_visual.html
```
Ou abra diretamente: `file:///Users/sapucaia/.claude-worktrees/BackTest/serene-mccarthy/BackendTestes/detector_visual.html`

### 2️⃣ Selecionar o Arquivo CSV:
   - Clique em **"📂 Selecionar Arquivo CSV"**
   - Navegue até: `/Users/sapucaia/tracking/BackTest/input.csv`
   - Selecione o arquivo
   - Aguarde 5-10 segundos (carregando ~91k registros)
   - ✅ Gráficos aparecem automaticamente!

### 3️⃣ Ajustar Parâmetros:

   **PRINCIPAL PARÂMETRO:**
   - **Magnitude Mínima (pico)**: Comece com **0.5 m/s²** (NOVO PADRÃO!)
     - Baseado nas estatísticas: aceleração média = 0.12 m/s²
     - Se detectar MUITOS eventos (falsos positivos):
       → Aumente para 0.8, 1.0, 1.5, 2.0...
     - Se NÃO detectar eventos reais (falsos negativos):
       → Diminua para 0.3, 0.2, 0.1...

   **Parâmetros Secundários:**
   - **Velocidade Máxima**: 0.5 km/h (geralmente não precisa mexer)
   - **Picos Mínimos**: 3 (quantas "conchadas" mínimas)
   - **Gap Máximo**: 15s (tempo máximo entre conchadas)
   - **Duração Mínima**: 10s (duração mínima do evento)

### 4️⃣ Detectar Eventos:
   - A detecção roda **AUTOMATICAMENTE** após carregar o CSV
   - Ou clique em **"🔍 Detectar Eventos"** após ajustar parâmetros
   - Veja áreas VERMELHAS no gráfico = eventos de carregamento
   - Veja pontos VERMELHOS = picos individuais (conchadas)

### 5️⃣ Validar Resultados:
   - Na lista de eventos (canto inferior direito)
   - Clique em um evento para dar **ZOOM** nele
   - Verifique:
     - ✓ Velocidade ~zero (parado)
     - ✓ Múltiplos picos de vibração
     - ✓ Padrão de "conchadas" visível

---

## 📈 Estatísticas do Dataset (input.csv):

```
Período: 2025-12-12 10:13:40 até 2025-12-13 11:58:02
Total de registros: 91.660
Velocidade: min=0.00, max=38.50, média=8.45 km/h
Aceleração: min=0.0000, max=15.2541, média=0.1234 m/s²
Registros parados (≤0.5 km/h): ~15.234 (16.6%)
```

---

## 🎯 DICAS DE CALIBRAÇÃO:

### Para este dataset específico:

**Baseado nas estatísticas acima, recomendo começar com:**

```
Magnitude Mínima: 0.5 m/s²  (aceleração média é 0.12 m/s²)
Picos Mínimos: 3
Gap Máximo: 15s
Duração Mínima: 10s
Velocidade Máxima: 0.5 km/h
```

**Se a aceleração média é muito baixa (0.12 m/s²):**
- Eventos de carregamento provavelmente têm picos entre 0.3 - 2.0 m/s²
- Comece testando com `Magnitude Mínima = 0.5 m/s²`
- Se detectar muito ruído, aumente gradualmente
- Se não detectar nada, diminua para 0.3 ou 0.2 m/s²

### Padrão típico de carregamento:
```
Velocidade: 0 km/h (parado)
Aceleração: Picos de 0.5 - 3.0 m/s² (conchadas)
Frequência: A cada 8-15 segundos (velocidade da escavadeira)
Duração total: 30s - 3min (carregamento completo)
```

---

## ⚡ PRESETS DISPONÍVEIS:

Clique nos botões para configuração rápida:

1. **Caminhão Pesado**:
   - Magnitude: 1.5 m/s²
   - Para caminhões grandes (menos vibração)

2. **Caminhão Leve**:
   - Magnitude: 3.0 m/s²
   - Para caminhões pequenos (mais vibração)

3. **Carregamento Rápido**:
   - Gap: 10s
   - Para escavadeiras rápidas

4. **Carregamento Lento**:
   - Gap: 25s
   - Para escavadeiras lentas

---

## 🆕 MUDANÇAS NA NOVA VERSÃO:

### ✅ Vantagens do Modo Offline:

1. **Sem servidor HTTP** - não precisa mais rodar `python3 servidor_detector_input.py`
2. **Todos os dados** - carrega os 91.660 registros completos (não faz sampling)
3. **Mais rápido** - sem latência de rede
4. **100% offline** - funciona sem internet
5. **Privacidade total** - dados não saem do computador
6. **Mais fácil** - só escolher o arquivo CSV

### ⚠️ Servidor HTTP (Opcional):

O servidor HTTP ainda existe e funciona, mas **NÃO É MAIS NECESSÁRIO**:

```bash
# Caso queira usar o servidor (não recomendado):
cd /Users/sapucaia/tracking/BackTest
python3 servidor_detector_input.py &
```

---

## 📁 ARQUIVOS CRIADOS:

### No diretório principal:
```
/Users/sapucaia/tracking/BackTest/
├── servidor_detector_input.py    ← Servidor HTTP (OPCIONAL)
├── input.csv                      ← Seus dados (91k registros)
└── STATUS_ATUAL.md                ← Este arquivo
```

### No diretório de trabalho:
```
/Users/sapucaia/.claude-worktrees/BackTest/serene-mccarthy/BackendTestes/
├── detector_visual.html                    ← Interface visual (OFFLINE) ⭐
├── detectar_carregamento.py                ← Script Python standalone
├── COMO_USAR_DETECTOR_OFFLINE.md           ← Guia de uso (NOVO) ⭐
└── README_DETECCAO_CARREGAMENTO.md         ← Documentação técnica
```

---

## 🎓 PRÓXIMOS PASSOS (após calibrar):

1. **Anote os melhores parâmetros** que funcionaram
2. **Exporte os eventos** detectados (em breve)
3. **Integre no sistema** de produção
4. **Crie alertas** em tempo real
5. **Gere relatórios** de produtividade

---

## ❓ PROBLEMAS COMUNS:

### "Nenhum dado aparece após selecionar o CSV"
- Abra o Console do navegador (F12 ou Cmd+Option+I)
- Veja se há erros JavaScript
- Certifique-se de que o arquivo CSV tem as colunas corretas:
  - `time`, `speed_kmh`, `linear_accel_magnitude`

### Detecção não funciona bem
- **Muitos falsos positivos**: Aumente "Magnitude Mínima"
- **Falsos negativos**: Diminua "Magnitude Mínima"
- Use os presets como ponto de partida
- Comece com 0.5 m/s² (novo padrão otimizado para este dataset)

### "Carregamento demora muito"
- Normal para ~91k registros (5-10 segundos)
- Aguarde até ver os gráficos aparecerem
- Se demorar mais de 30 segundos, recarregue a página (F5)

---

## 📞 DOCUMENTAÇÃO:

Todos os arquivos de documentação estão disponíveis:
- **COMO_USAR_DETECTOR_OFFLINE.md** (novo guia passo a passo)
- **README_DETECCAO_CARREGAMENTO.md** (documentação técnica)

---

## 🔧 Tecnologias Usadas:

- **Plotly.js**: Gráficos interativos
- **PapaParse**: Leitura e parse de CSV no navegador
- **FileReader API**: Leitura de arquivo local
- **JavaScript puro**: Algoritmo de detecção no client-side

---

**Bom trabalho de calibração! 🎯**

**NOVO: Agora 100% offline - sem servidor, sem complicações!**

---

_Última atualização: 2025-12-21 (Versão Offline)_
