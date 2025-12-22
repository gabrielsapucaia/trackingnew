"""
Teste do sistema de cache incremental com Parquet.
"""
from database import init_database, get_db
from config import DB_CONFIG, POOL_CONFIG
import pandas as pd
import time


def test_incremental_cache():
    """Testa o cache incremental."""
    print("=" * 60)
    print("TESTE DE CACHE INCREMENTAL COM PARQUET")
    print("=" * 60)
    
    # Inicializa banco
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
    
    # Limpa cache anterior para teste limpo
    print("\n1. Limpando cache anterior...")
    db.clear_cache()
    
    # Exemplo 1: Busca incremental de uma tabela com timestamp
    print("\n2. TESTE 1: Busca incremental com coluna de ordenação")
    print("-" * 60)
    
    # Query exemplo - ajuste conforme sua estrutura de banco
    # Assumindo que existe uma tabela com coluna de timestamp/id
    query_example = """
        SELECT table_name, table_type, table_schema
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """
    
    # Primeira execução - busca tudo
    print("\n> Primeira execucao (sem cache):")
    start_time = time.time()
    df1 = db.execute_incremental_query(
        query=query_example,
        order_column="table_name",  # Usando table_name como ordenação para teste
        use_cache=True
    )
    time1 = time.time() - start_time
    print(f"  Tempo: {time1:.3f}s | Registros: {len(df1)}")
    
    # Segunda execução - deve usar cache e buscar apenas novos
    print("\n> Segunda execucao (com cache):")
    start_time = time.time()
    df2 = db.execute_incremental_query(
        query=query_example,
        order_column="table_name",
        use_cache=True
    )
    time2 = time.time() - start_time
    print(f"  Tempo: {time2:.3f}s | Registros: {len(df2)}")
    
    # Verifica se os dados são iguais
    if len(df1) == len(df2):
        print(f"  [OK] Cache funcionando: {len(df1)} registros em ambas execucoes")
    else:
        print(f"  [AVISO] Diferenca: {len(df1)} vs {len(df2)} registros")
    
    # Exemplo 2: Query simples sem incremental
    print("\n3. TESTE 2: Query simples com cache")
    print("-" * 60)
    
    query_simple = "SELECT COUNT(*) as total FROM information_schema.tables"
    
    print("\n> Primeira execucao:")
    start_time = time.time()
    df3 = db.execute_query(query_simple, use_cache=True)
    time3 = time.time() - start_time
    print(f"  Tempo: {time3:.3f}s | Resultado: {df3.iloc[0]['total']}")
    
    print("\n> Segunda execucao (deve usar cache):")
    start_time = time.time()
    df4 = db.execute_query(query_simple, use_cache=True)
    time4 = time.time() - start_time
    print(f"  Tempo: {time4:.3f}s | Resultado: {df4.iloc[0]['total']}")
    
    if time4 < time3:
        print(f"  [OK] Cache acelerou a consulta ({time4:.3f}s vs {time3:.3f}s)")
    
    # Estatísticas do cache
    print("\n4. ESTATÍSTICAS DO CACHE")
    print("-" * 60)
    stats = db.get_cache_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Mostra alguns registros do cache
    print("\n5. AMOSTRA DOS DADOS EM CACHE")
    print("-" * 60)
    if len(df2) > 0:
        print("\nPrimeiros 5 registros:")
        print(df2.head().to_string())
    
    # Fecha conexões
    db.close()
    
    print("\n" + "=" * 60)
    print("TESTE CONCLUÍDO")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_incremental_cache()
    except Exception as e:
        print(f"\n[ERRO] Erro durante o teste: {e}")
        import traceback
        traceback.print_exc()

