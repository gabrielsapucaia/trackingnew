"""
Exemplo de uso do sistema de cache incremental com Parquet.
"""
from database import init_database, get_db
from config import DB_CONFIG, POOL_CONFIG
import pandas as pd


def main():
    """Exemplo de uso do sistema de cache incremental."""
    print("=" * 60)
    print("EXEMPLO DE USO - CACHE INCREMENTAL COM PARQUET")
    print("=" * 60)
    
    # Inicializa o banco de dados
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
    
    # Exemplo 1: Busca incremental
    # Use quando você tem uma tabela que cresce ao longo do tempo
    # e quer buscar apenas dados novos
    print("\n1. BUSCA INCREMENTAL")
    print("-" * 60)
    
    # Ajuste esta query conforme sua estrutura de banco
    # IMPORTANTE: A coluna de ordenação deve ser uma que sempre aumenta
    # (timestamp, id auto-increment, etc.)
    query_incremental = """
        SELECT table_name, table_type, table_schema
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """
    
    # Primeira vez: busca tudo e salva no cache
    print("\n> Primeira execucao (busca tudo):")
    df1 = db.execute_incremental_query(
        query=query_incremental,
        order_column="table_name",  # Coluna para ordenação
        use_cache=True
    )
    print(f"  Total de registros: {len(df1)}")
    
    # Segunda vez: busca apenas dados novos
    print("\n> Segunda execucao (busca apenas novos):")
    df2 = db.execute_incremental_query(
        query=query_incremental,
        order_column="table_name",
        use_cache=True
    )
    print(f"  Total de registros: {len(df2)}")
    
    # Exemplo 2: Query simples com cache
    print("\n2. QUERY SIMPLES COM CACHE")
    print("-" * 60)
    
    query_simple = """
        SELECT table_schema, COUNT(*) as total_tables
        FROM information_schema.tables
        GROUP BY table_schema
        ORDER BY total_tables DESC
    """
    
    print("\n> Executando query (primeira vez busca do banco, proxima do cache):")
    df3 = db.execute_query(query_simple, use_cache=True)
    print(f"\nResultados:")
    print(df3.to_string(index=False))
    
    # Exemplo 3: Query sem cache
    print("\n3. QUERY SEM CACHE")
    print("-" * 60)
    
    print("\n> Executando query (sempre busca do banco):")
    df4 = db.execute_query(query_simple, use_cache=False)
    print(f"  Registros: {len(df4)}")
    
    # Estatísticas
    print("\n4. ESTATÍSTICAS DO CACHE")
    print("-" * 60)
    stats = db.get_cache_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Limpar cache específico (opcional)
    # db.clear_cache()  # Remove tudo
    # db.clear_cache(pattern="tabela_usuarios")  # Remove cache específico
    
    # Fecha conexões
    db.close()
    
    print("\n" + "=" * 60)
    print("EXEMPLO CONCLUÍDO")
    print("=" * 60)


if __name__ == "__main__":
    main()
