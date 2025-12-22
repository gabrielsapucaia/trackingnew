# Aplicação Streamlit - Gráficos Telemetria

Aplicação web para visualização de dados de telemetria com cache Parquet, múltiplos eixos Y e conversão de timezone.

## Instalação

```bash
pip install -r requirements.txt
```

## Configuração

### 1. Configurar Query SQL

Edite o arquivo `streamlit_config.py` e ajuste a query SQL conforme sua estrutura de banco:

```python
TELEMETRY_QUERY = """
    SELECT *
    FROM sua_tabela_telemetria
    ORDER BY timestamp
"""
```

### 2. Verificar Nome da Coluna Timestamp

Confirme que o nome da coluna de timestamp está correto:

```python
TIMESTAMP_COLUMN = "timestamp"  # Ajuste se necessário
```

## Executar Aplicação

```bash
streamlit run app.py
```

A aplicação será aberta automaticamente no navegador em `http://localhost:8501`

## Funcionalidades

### Sidebar

- **Atualizar Dados**: Botão para forçar atualização do cache do banco de dados
- **Última Atualização**: Informação sobre quando os dados foram atualizados pela última vez
- **Filtros de Período**: 
  - Data/hora inicial
  - Data/hora final
  - Filtragem em UTC-3 (timezone local)

### Área Principal

- **Métricas**: Quantidade de registros, período de dados carregados
- **Seleção de Variáveis**: Multiselect para escolher quais variáveis visualizar
- **Gráfico Interativo**: 
  - Para 1-2 variáveis: eixos Y separados
  - Para 3-4 variáveis: subplots verticais (uma variável por linha)
  - Para mais variáveis: mesmo eixo Y com cores diferentes
  - Zoom, pan e hover habilitados
  - Legenda interativa (clicar para mostrar/ocultar séries)
- **Exportar CSV**: Botão para baixar dados filtrados como CSV

## Como Funciona

1. **Carregamento Inicial**: 
   - Verifica se cache Parquet está atualizado
   - Se não estiver, atualiza automaticamente usando busca incremental
   - Carrega todos os arquivos Parquet do cache e combina

2. **Conversão de Timezone**:
   - Dados no banco estão em UTC+0
   - Convertidos automaticamente para UTC-3 (America/Sao_Paulo)
   - Filtros e visualização usam UTC-3

3. **Filtragem**:
   - Filtra dados pelo período selecionado no sidebar
   - Mostra apenas colunas que têm valores não-null

4. **Visualização**:
   - Detecta automaticamente colunas disponíveis
   - Permite seleção múltipla de variáveis
   - Cria gráfico apropriado baseado no número de variáveis selecionadas

## Estrutura de Arquivos

- `app.py`: Aplicação Streamlit principal
- `data_loader.py`: Funções para carregar e processar dados Parquet
- `streamlit_config.py`: Configurações específicas do Streamlit
- `database.py`: Módulo de cache incremental (existente)
- `config.py`: Configurações do banco de dados (existente)

## Troubleshooting

### Erro: "Nenhum dado encontrado no cache"

- Clique no botão "Atualizar Dados" no sidebar
- Verifique se a query SQL em `streamlit_config.py` está correta
- Verifique conexão com banco de dados

### Erro: "Coluna timestamp não encontrada"

- Verifique o nome da coluna em `streamlit_config.py`
- Confirme que a coluna existe nos dados Parquet

### Gráfico não aparece

- Verifique se selecionou pelo menos uma variável
- Verifique se há dados no período selecionado
- Verifique se as colunas selecionadas têm valores não-null

## Notas

- O cache é atualizado automaticamente ao iniciar se detectar dados novos no banco
- Dados são carregados uma vez e mantidos em cache na sessão do Streamlit
- Para forçar recarregamento completo, clique em "Atualizar Dados"
- Exportação CSV inclui apenas dados do período filtrado e variáveis selecionadas

