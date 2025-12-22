"""Script para verificar estrutura e quantidade de dados nos arquivos Parquet."""
import pandas as pd
from pathlib import Path

cache_dir = Path('.cache')
parquet_files = list(cache_dir.glob("cache_*.parquet"))

print("=" * 80)
print("ANÁLISE DOS DADOS NO CACHE PARQUET")
print("=" * 80)

if not parquet_files:
    print("Nenhum arquivo Parquet encontrado no cache!")
else:
    total_records = 0
    all_columns = set()
    
    for i, file in enumerate(parquet_files, 1):
        print(f"\n{'='*80}")
        print(f"ARQUIVO {i}: {file.name}")
        print(f"{'='*80}")
        
        try:
            df = pd.read_parquet(file)
            
            print(f"\nShape: {df.shape} (linhas x colunas)")
            print(f"Registros: {len(df):,}")
            print(f"Colunas: {len(df.columns)}")
            
            total_records += len(df)
            all_columns.update(df.columns)
            
            print(f"\nColunas disponíveis:")
            for col in df.columns:
                dtype = df[col].dtype
                null_count = df[col].isna().sum()
                null_pct = (null_count / len(df)) * 100 if len(df) > 0 else 0
                print(f"  - {col:30s} | Tipo: {str(dtype):20s} | Nulls: {null_count:6d} ({null_pct:5.1f}%)")
            
            # Verificar se tem coluna de timestamp
            timestamp_cols = [col for col in df.columns 
                            if any(keyword in col.lower() for keyword in ['timestamp', 'time', 'datetime', 'date'])]
            if timestamp_cols:
                print(f"\nColunas de timestamp encontradas: {timestamp_cols}")
                for ts_col in timestamp_cols:
                    if ts_col in df.columns:
                        print(f"  {ts_col}:")
                        print(f"    Min: {df[ts_col].min()}")
                        print(f"    Max: {df[ts_col].max()}")
                        if len(df) > 0:
                            print(f"    Range: {(df[ts_col].max() - df[ts_col].min())}")
            
            # Mostrar primeiras linhas
            print(f"\nPrimeiras 3 linhas:")
            print(df.head(3).to_string())
            
            # Estatísticas básicas para colunas numéricas
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                print(f"\nEstatísticas básicas (colunas numéricas):")
                print(df[numeric_cols].describe().to_string())
            
        except Exception as e:
            print(f"Erro ao processar {file.name}: {e}")
            import traceback
            traceback.print_exc()

print(f"\n{'='*80}")
print("RESUMO GERAL")
print(f"{'='*80}")
print(f"Total de arquivos: {len(parquet_files)}")
print(f"Total de registros: {total_records:,}")
print(f"Total de colunas únicas: {len(all_columns)}")
print(f"\nTodas as colunas encontradas:")
for col in sorted(all_columns):
    print(f"  - {col}")

