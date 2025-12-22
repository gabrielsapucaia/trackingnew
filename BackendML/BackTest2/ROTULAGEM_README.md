# Sistema de Rotulagem Interativa de Carregamento

Sistema para rotular períodos de parada como "Carregamento" ou "Não Carregamento" e treinar modelo de Machine Learning.

## Instalação

```bash
pip install -r requirements.txt
```

## Uso

### 1. Rotular Períodos

Execute a aplicação Streamlit de rotulagem:

```bash
streamlit run app_labeling.py
```

A aplicação abrirá no navegador em `http://localhost:8501`.

**Funcionalidades:**
- Carrega automaticamente períodos não catalogados (>= 1 minuto, velocidade < 1.0 km/h)
- Mostra gráficos de velocidade e vibração para cada período
- Botões para rotular:
  - ✅ **Carregamento** - marca como carregamento
  - ❌ **Não Carregamento** - marca como não carregamento
  - ⏭️ **Pular** - pula sem rotular
- Navegação entre períodos (Primeiro, Anterior, Próximo)
- Barra de progresso mostrando quantos períodos foram rotulados
- Exportar rótulos em CSV

**Configurações na Sidebar:**
- Duração mínima (padrão: 1.0 minuto)
- Velocidade máxima (padrão: 1.0 km/h)

### 2. Treinar Modelo de Machine Learning

Após rotular uma quantidade suficiente de períodos (recomendado: pelo menos 20-30 de cada classe), execute:

```bash
python ml_treinar_modelo.py
```

O script irá:
- Carregar rótulos de `amostra/rotulos_carregamento.csv`
- Extrair features de cada período rotulado
- Treinar modelo Random Forest
- Validar com validação cruzada
- Salvar modelo em `amostra/modelo_carregamento.pkl`
- Gerar relatório em `amostra/relatorio_ml_carregamento.txt`

### 3. Arquivos Gerados

- **`amostra/rotulos_carregamento.csv`** - Rótulos salvos pelo usuário
- **`amostra/modelo_carregamento.pkl`** - Modelo treinado
- **`amostra/scaler_carregamento.pkl`** - Scaler para normalização
- **`amostra/relatorio_ml_carregamento.txt`** - Relatório de treinamento

## Estrutura dos Dados

### Rótulos (rotulos_carregamento.csv)
```csv
period_id,start_time,end_time,duration_minutes,label,labeled_at
20251212_101340_101341,2025-12-12 10:13:40,2025-12-12 10:13:41,0.02,Carregamento,2025-12-13 14:30:00
```

### Features Extraídas
- Features básicas: média, desvio padrão, máximo, mínimo da vibração
- Features de picos: número, frequência, regularidade, variabilidade
- Features temporais: distribuição, intervalos entre picos
- Features de atividade: razão de atividade, períodos de alta atividade

## Requisitos Mínimos para Treinamento

- Pelo menos 2 classes diferentes (Carregamento e Não Carregamento)
- Recomendado: mínimo 20-30 amostras de cada classe
- Períodos com duração >= 1 minuto
- Dados de vibração válidos

## Próximos Passos

Após treinar o modelo, você pode:
1. Aplicar o modelo em períodos não rotulados
2. Comparar resultados ML com regras baseadas em heurísticas
3. Refinar o modelo com mais dados rotulados
4. Integrar o modelo em produção
