"""Script para verificar quantidade e estrutura de dados na tabela telemetry."""
from database import init_database, get_db
from config import DB_CONFIG, POOL_CONFIG
import pandas as pd

init_database(**DB_CONFIG, **POOL_CONFIG, cache_dir='.cache')
db = get_db()

print("=" * 80)
print("ANÁLISE DA TABELA TELEMETRY NO BANCO DE DADOS")
print("=" * 80)

# Contar total de registros
print("\n1. QUANTIDADE DE DADOS")
print("-" * 80)
count_result = db.execute_query("SELECT COUNT(*) as total FROM telemetry", use_cache=False)
total_records = count_result.iloc[0]['total']
print(f"Total de registros na tabela telemetry: {count_result.iloc[0]['total']:,}")

# Verificar range de datas
print("\n2. RANGE DE DATAS")
print("-" * 80)
date_range = db.execute_query(
    """
    SELECT 
        MIN(time) as data_minima,
        MAX(time) as data_maxima,
        MAX(time) - MIN(time) as intervalo
    FROM telemetry
    """,
    use_cache=False
)
if not date_range.empty:
    print(f"Data mínima: {date_range.iloc[0]['data_minima']}")
    print(f"Data máxima: {date_range.iloc[0]['data_maxima']}")
    print(f"Intervalo: {date_range.iloc[0]['intervalo']}")

# Verificar por device_id
print("\n3. DADOS POR DISPOSITIVO")
print("-" * 80)
devices = db.execute_query(
    """
    SELECT 
        device_id,
        COUNT(*) as total_registros,
        MIN(time) as primeira_leitura,
        MAX(time) as ultima_leitura
    FROM telemetry
    GROUP BY device_id
    ORDER BY total_registros DESC
    """,
    use_cache=False
)
print(f"Total de dispositivos únicos: {len(devices)}")
print("\nTop 10 dispositivos por quantidade de registros:")
print(devices.head(10).to_string(index=False))

# Verificar estrutura completa
print("\n4. ESTRUTURA DA TABELA")
print("-" * 80)
structure = db.execute_query(
    """
    SELECT 
        column_name,
        data_type,
        is_nullable,
        character_maximum_length
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'telemetry'
    ORDER BY ordinal_position
    """,
    use_cache=False
)
print(f"Total de colunas: {len(structure)}")
print("\nColunas da tabela:")
for idx, row in structure.iterrows():
    nullable = "NULL" if row['is_nullable'] == 'YES' else "NOT NULL"
    max_len = f"({row['character_maximum_length']})" if row['character_maximum_length'] else ""
    print(f"  {idx+1:2d}. {row['column_name']:30s} | {row['data_type']:25s} {max_len:10s} | {nullable}")

# Verificar amostra de dados
print("\n5. AMOSTRA DE DADOS (3 primeiros registros)")
print("-" * 80)
sample = db.execute_query("SELECT * FROM telemetry ORDER BY time LIMIT 3", use_cache=False)
print(f"Colunas na amostra: {len(sample.columns)}")
print("\nPrimeiro registro:")
if not sample.empty:
    first_row = sample.iloc[0]
    for col in sample.columns[:20]:  # Mostrar primeiras 20 colunas
        print(f"  {col:30s}: {str(first_row[col])[:80]}")

# Estatísticas de colunas numéricas principais
print("\n6. ESTATÍSTICAS DE COLUNAS NUMÉRICAS PRINCIPAIS")
print("-" * 80)
numeric_stats = db.execute_query(
    """
    SELECT 
        COUNT(*) as total,
        AVG(latitude) as avg_latitude,
        AVG(longitude) as avg_longitude,
        AVG(altitude) as avg_altitude,
        AVG(speed) as avg_speed,
        AVG(battery_level) as avg_battery_level,
        MIN(time) as min_time,
        MAX(time) as max_time
    FROM telemetry
    """,
    use_cache=False
)
print(numeric_stats.to_string(index=False))

db.close()

