#!/usr/bin/env python3
"""
Script de teste de conectividade com banco de dados AuraTracking
Testa conexão, timezone e conversões UTC/UTC-3
"""

import psycopg2
import pandas as pd
from datetime import datetime
import pytz

# Configurações de conexão
DB_CONFIG = {
    "host": "10.135.22.3",
    "port": 5432,
    "dbname": "auratracking",
    "user": "aura",
    "password": "aura2025",
    "connect_timeout": 5,
}

# Timezones
TIMEZONE_BR = pytz.timezone("America/Sao_Paulo")  # UTC-3
TIMEZONE_UTC = pytz.UTC

def test_connection():
    """Testa conexão básica com o banco."""
    print("=" * 60)
    print("TESTE 1: Conexão Básica")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print(f"✅ Conexão estabelecida com sucesso!")
        print(f"   Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"   Database: {DB_CONFIG['dbname']}")
        print(f"   User: {DB_CONFIG['user']}")
        
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"   PostgreSQL Version: {version.split(',')[0]}")
        
        cur.close()
        conn.close()
        return True
    except psycopg2.OperationalError as e:
        print(f"❌ Erro de conexão: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False

def test_timezone_conversion():
    """Testa conversão de timezone UTC para UTC-3."""
    print("\n" + "=" * 60)
    print("TESTE 2: Conversão de Timezone")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Obter range de datas do banco
        cur.execute("SELECT MIN(time), MAX(time), COUNT(*) FROM telemetry;")
        min_time_utc, max_time_utc, count = cur.fetchone()
        
        if not min_time_utc or not max_time_utc:
            print("❌ Nenhum dado encontrado na tabela telemetry.")
            cur.close()
            conn.close()
            return False
        
        print(f"\n📊 Dados no banco (UTC):")
        print(f"   Primeiro registro: {min_time_utc}")
        print(f"   Último registro:   {max_time_utc}")
        print(f"   Total de registros: {count:,}")
        
        # Verificar se os dados já têm timezone
        if min_time_utc.tzinfo is None:
            print("\n⚠️  AVISO: Dados no banco NÃO têm timezone (timezone-naive)")
            print("   Assumindo que estão em UTC e convertendo...")
            min_time_utc = TIMEZONE_UTC.localize(min_time_utc)
            max_time_utc = TIMEZONE_UTC.localize(max_time_utc)
        else:
            print(f"\n✅ Dados no banco têm timezone: {min_time_utc.tzinfo}")
        
        # Converter para UTC-3 (Brasília)
        min_time_br = min_time_utc.astimezone(TIMEZONE_BR)
        max_time_br = max_time_utc.astimezone(TIMEZONE_BR)
        
        print(f"\n📅 Dados convertidos para UTC-3 (Brasília):")
        print(f"   Primeiro registro: {min_time_br.strftime('%d/%m/%Y %H:%M:%S %Z')}")
        print(f"   Último registro:   {max_time_br.strftime('%d/%m/%Y %H:%M:%S %Z')}")
        
        # Verificar diferença de horas
        utc_offset = (min_time_br.utcoffset().total_seconds() / 3600)
        print(f"\n🕐 Offset UTC-3: {utc_offset:.0f} horas")
        
        # Testar query com filtro de data
        print(f"\n📋 Testando query com filtro de data...")
        test_start_br = min_time_br.replace(hour=10, minute=13, second=0, microsecond=0)
        test_end_br = min_time_br.replace(hour=11, minute=0, second=0, microsecond=0)
        
        # Converter de volta para UTC para query
        test_start_utc = test_start_br.astimezone(TIMEZONE_UTC)
        test_end_utc = test_end_br.astimezone(TIMEZONE_UTC)
        
        print(f"   Período selecionado (UTC-3): {test_start_br.strftime('%d/%m/%Y %H:%M')} até {test_end_br.strftime('%d/%m/%Y %H:%M')}")
        print(f"   Período para query (UTC):    {test_start_utc.strftime('%d/%m/%Y %H:%M')} até {test_end_utc.strftime('%d/%m/%Y %H:%M')}")
        
        query = "SELECT COUNT(*) FROM telemetry WHERE time >= %s AND time <= %s;"
        cur.execute(query, (test_start_utc, test_end_utc))
        result_count = cur.fetchone()[0]
        print(f"   ✅ Registros encontrados: {result_count:,}")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de timezone: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_data_retrieval():
    """Testa recuperação de dados com colunas numéricas."""
    print("\n" + "=" * 60)
    print("TESTE 3: Recuperação de Dados")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Obter colunas numéricas
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'telemetry'
            AND data_type IN ('integer', 'bigint', 'double precision', 'real', 'numeric')
            ORDER BY ordinal_position;
        """)
        numeric_cols = [row[0] for row in cur.fetchall()]
        
        print(f"✅ Encontradas {len(numeric_cols)} colunas numéricas")
        
        # Testar query com algumas colunas
        test_cols = ['time', 'latitude', 'longitude', 'altitude', 'speed_kmh', 'battery_level']
        available_cols = [col for col in test_cols if col in numeric_cols or col == 'time']
        
        cols_str = ', '.join(available_cols)
        query = f"SELECT {cols_str} FROM telemetry ORDER BY time DESC LIMIT 5;"
        
        cur.execute(query)
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]
        
        print(f"\n📊 Últimos 5 registros:")
        print("-" * 80)
        df = pd.DataFrame(rows, columns=col_names)
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            # Converter para UTC-3 se necessário
            if df['time'].dt.tz is None:
                df['time'] = pd.to_datetime(df['time']).dt.tz_localize('UTC').dt.tz_convert(TIMEZONE_BR)
            else:
                df['time'] = df['time'].dt.tz_convert(TIMEZONE_BR)
        
        print(df.to_string(index=False))
        print("-" * 80)
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro na recuperação de dados: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Executa todos os testes."""
    print("\n" + "=" * 60)
    print("TESTE DE CONECTIVIDADE E TIMEZONE - AuraTracking")
    print("=" * 60)
    print(f"\nData/hora atual do sistema: {datetime.now()}")
    print(f"Timezone local: {TIMEZONE_BR}")
    print(f"UTC offset: UTC-3 (Brasília)")
    
    results = []
    
    # Teste 1: Conexão
    results.append(("Conexão Básica", test_connection()))
    
    if results[0][1]:  # Se conexão funcionou, continuar testes
        # Teste 2: Timezone
        results.append(("Conversão de Timezone", test_timezone_conversion()))
        
        # Teste 3: Recuperação de dados
        results.append(("Recuperação de Dados", test_data_retrieval()))
    
    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO DOS TESTES")
    print("=" * 60)
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{status} - {test_name}")
    
    all_passed = all(result for _, result in results)
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ TODOS OS TESTES PASSARAM!")
    else:
        print("❌ ALGUNS TESTES FALHARAM")
    print("=" * 60)

if __name__ == "__main__":
    main()



