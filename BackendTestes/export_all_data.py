"""
Script para exportar todos os dados do TimescaleDB para CSV.
"""

import pandas as pd
import psycopg2
from datetime import datetime
import sys

# Configuração do banco de dados
DB_CONFIG = {
    "host": "10.135.22.3",
    "port": 5432,
    "dbname": "auratracking",
    "user": "aura",
    "password": "aura2025",
    "connect_timeout": 5,
}

def export_all_data():
    """Exporta todos os dados da tabela telemetry para CSV."""
    
    print("="*60)
    print("EXPORTAÇÃO DE DADOS - TimescaleDB")
    print("="*60)
    
    try:
        # Conectar ao banco
        print("\n⏳ Conectando ao banco de dados...")
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Conexão estabelecida!")
        
        # Verificar quantidade de dados
        print("\n📊 Verificando quantidade de dados...")
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM telemetry;")
        total_records = cur.fetchone()[0]
        print(f"   Total de registros: {total_records:,}")
        
        cur.execute("SELECT MIN(time), MAX(time) FROM telemetry;")
        min_time, max_time = cur.fetchone()
        print(f"   Período: {min_time} até {max_time}")
        
        # Verificar tamanho estimado
        cur.execute("""
            SELECT pg_size_pretty(pg_total_relation_size('telemetry')) as size;
        """)
        table_size = cur.fetchone()[0]
        print(f"   Tamanho da tabela: {table_size}")
        
        # Perguntar confirmação se muitos dados
        if total_records > 100000:
            print(f"\n⚠️  ATENÇÃO: {total_records:,} registros serão exportados.")
            print("   Isso pode levar alguns minutos e gerar um arquivo grande.")
            response = input("   Continuar? (s/n): ")
            if response.lower() != 's':
                print("❌ Exportação cancelada.")
                return
        
        # Exportar dados
        print("\n⏳ Exportando dados...")
        print("   Isso pode levar alguns minutos...")
        
        query = "SELECT * FROM telemetry ORDER BY device_id, time ASC;"
        df = pd.read_sql_query(query, conn)
        
        print(f"✅ Dados carregados: {len(df):,} registros, {len(df.columns)} colunas")
        
        # Gerar nome do arquivo com timestamp
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"telemetry_all_data_{timestamp_str}.csv"
        
        print(f"\n💾 Salvando em CSV: {csv_filename}")
        df.to_csv(csv_filename, index=False)
        
        # Verificar tamanho do arquivo
        import os
        file_size = os.path.getsize(csv_filename)
        file_size_mb = file_size / (1024 * 1024)
        
        print(f"✅ Arquivo salvo com sucesso!")
        print(f"   Tamanho: {file_size_mb:.2f} MB")
        print(f"   Localização: {os.path.abspath(csv_filename)}")
        
        # Estatísticas finais
        print(f"\n📊 Estatísticas do arquivo:")
        print(f"   Registros: {len(df):,}")
        print(f"   Colunas: {len(df.columns)}")
        print(f"   Devices únicos: {df['device_id'].nunique()}")
        if 'time' in df.columns:
            print(f"   Período: {df['time'].min()} até {df['time'].max()}")
        
        cur.close()
        conn.close()
        
        print("\n" + "="*60)
        print("✅ EXPORTAÇÃO CONCLUÍDA COM SUCESSO!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Erro durante exportação: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    export_all_data()



