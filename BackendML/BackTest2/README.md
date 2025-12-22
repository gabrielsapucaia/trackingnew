# Sistema de Cache Incremental com Parquet para PostgreSQL

Sistema de consulta com cache incremental em formato Parquet para o banco de dados PostgreSQL AuraTracking. Os dados são salvos em arquivos Parquet e apenas dados novos são buscados do banco em execuções subsequentes.

## Instalação

```bash
pip install -r requirements.txt
```

## Configuração

As configurações do banco de dados estão em `config.py`. Você pode modificar:
- Credenciais do banco de dados
- Configurações do pool de conexões
- Diretório de cache (padrão: `.cache`)

## Como Funciona

### Cache Incremental
- **Primeira execução**: Busca todos os dados do banco e salva em Parquet
- **Execuções seguintes**: 
  - Carrega dados do cache Parquet
  - Identifica o último valor da coluna de ordenação
  - Busca apenas dados novos do banco (WHERE coluna > último_valor)
  - Combina cache + dados novos
  - Atualiza o arquivo Parquet

### Cache Simples
- Salva resultado completo da query em Parquet
- Próxima execução retorna diretamente do cache (sem consultar banco)

## Uso Básico

### 1. Busca Incremental (Recomendado para tabelas que crescem)

```python
from database import init_database, get_db
from config import DB_CONFIG, POOL_CONFIG

# Inicializar banco de dados
init_database(
    host=DB_CONFIG["host"],
    port=DB_CONFIG["port"],
    dbname=DB_CONFIG["dbname"],
    user=DB_CONFIG["user"],
    password=DB_CONFIG["password"],
    min_conn=POOL_CONFIG["min_conn"],
    max_conn=POOL_CONFIG["max_conn"],
    cache_dir=".cache"
)

db = get_db()

# Busca incremental - busca apenas dados novos
# IMPORTANTE: A coluna de ordenação deve ser uma que sempre aumenta
# (timestamp, id auto-increment, etc.)
df = db.execute_incremental_query(
    query="""
        SELECT id, nome, created_at
        FROM usuarios
        WHERE status = 'ativo'
        ORDER BY created_at
    """,
    order_column="created_at",  # Coluna para controle incremental
    use_cache=True
)

print(f"Total de registros: {len(df)}")
```

### 2. Query Simples com Cache

```python
# Query que não precisa de busca incremental
df = db.execute_query(
    query="SELECT COUNT(*) as total FROM usuarios",
    use_cache=True
)

print(df.iloc[0]['total'])
```

### 3. Query sem Cache

```python
# Sempre busca do banco (não usa cache)
df = db.execute_query(
    query="SELECT * FROM usuarios LIMIT 10",
    use_cache=False
)
```

### 4. Executar INSERT/UPDATE/DELETE

```python
# Não usa cache (operações de escrita)
db.execute_non_query(
    "INSERT INTO usuarios (nome) VALUES (%s)",
    params=("João",)
)
```

### 5. Gerenciar Cache

```python
# Limpar todo o cache
db.clear_cache()

# Limpar cache específico (por padrão no nome do arquivo)
db.clear_cache(pattern="usuarios")

# Ver estatísticas do cache
stats = db.get_cache_stats()
print(stats)
# {
#     "total_files": 5,
#     "total_size_mb": 2.34,
#     "total_records": 15000,
#     "cache_dir": ".cache"
# }
```

## Estrutura de Arquivos

```
.cache/
  ├── cache_c2be4cb74336.parquet  # Cache de uma query específica
  ├── cache_2e3be7b7f66d.parquet  # Cache de outra query
  └── ...
```

Cada arquivo Parquet corresponde a uma query específica (identificada por hash).

## Vantagens do Parquet

- ✅ **Formato colunar**: Eficiente para leitura e análise
- ✅ **Compressão**: Arquivos menores que JSON/CSV
- ✅ **Persistência**: Dados mantidos entre execuções do programa
- ✅ **Performance**: Leitura muito rápida do disco
- ✅ **Compatibilidade**: Funciona com pandas, polars, etc.

## Exemplo Completo

```python
from database import init_database, get_db
from config import DB_CONFIG, POOL_CONFIG

# Inicializar
init_database(**DB_CONFIG, **POOL_CONFIG, cache_dir=".cache")
db = get_db()

# Primeira execução: busca tudo e salva
df1 = db.execute_incremental_query(
    query="SELECT * FROM eventos ORDER BY timestamp",
    order_column="timestamp"
)
print(f"Primeira execução: {len(df1)} registros")

# Segunda execução: busca apenas novos
df2 = db.execute_incremental_query(
    query="SELECT * FROM eventos ORDER BY timestamp",
    order_column="timestamp"
)
print(f"Segunda execução: {len(df2)} registros (cache + novos)")

# Fechar conexões
db.close()
```

## Executar Testes

```bash
python test_incremental.py
```

## Executar Exemplo

```bash
python main.py
```

## Características

- **Cache Incremental**: Busca apenas dados novos do banco
- **Cache Persistente**: Dados salvos em Parquet (persistem entre execuções)
- **Pool de Conexões**: Gerencia múltiplas conexões eficientemente
- **Thread-Safe**: Usa pool de conexões thread-safe
- **Performance**: Cache em Parquet é muito rápido para leitura
- **Eficiência**: Reduz carga no banco de dados buscando apenas deltas

## Notas Importantes

1. **Coluna de Ordenação**: Para busca incremental funcionar corretamente, a coluna de ordenação deve:
   - Ser única ou ter valores que sempre aumentam (timestamp, id auto-increment)
   - Estar presente na query com ORDER BY
   - Não ter valores NULL (ou tratar adequadamente)

2. **Queries com Parâmetros**: O cache é específico para cada combinação de query + parâmetros.

3. **Limpeza de Cache**: Considere limpar o cache periodicamente ou quando houver mudanças estruturais nas tabelas.

4. **Espaço em Disco**: Monitore o tamanho da pasta `.cache` - arquivos Parquet podem crescer com o tempo.
