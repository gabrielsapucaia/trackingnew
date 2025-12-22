"""
Módulo para carregar e gerenciar dados Parquet para visualização.
"""
import pandas as pd
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import pytz
from database import get_db
from streamlit_config import (
    TELEMETRY_QUERY, 
    TIMESTAMP_COLUMN, 
    FROM_TIMEZONE, 
    TO_TIMEZONE,
    CACHE_DIR
)


def load_all_parquet_files(cache_dir: str = CACHE_DIR) -> pd.DataFrame:
    """
    Carrega e combina todos os arquivos Parquet do cache.
    Detecta automaticamente a coluna de timestamp se existir.
    
    Args:
        cache_dir: Diretório onde estão os arquivos Parquet
        
    Returns:
        DataFrame combinado com todos os dados
    """
    cache_path = Path(cache_dir)
    if not cache_path.exists():
        return pd.DataFrame()
    
    parquet_files = list(cache_path.glob("cache_*.parquet"))
    
    if not parquet_files:
        return pd.DataFrame()
    
    # Carrega todos os arquivos Parquet
    dfs = []
    for file in parquet_files:
        try:
            df = pd.read_parquet(file)
            # Filtra apenas arquivos que têm coluna 'time' (dados de telemetria)
            # Ignora arquivos de teste (information_schema, etc)
            if 'time' in df.columns or TIMESTAMP_COLUMN in df.columns:
                dfs.append(df)
        except Exception as e:
            print(f"Erro ao carregar {file}: {e}")
            continue
    
    if not dfs:
        return pd.DataFrame()
    
    # Combina todos os DataFrames (apenas os que têm estrutura de telemetria)
    # Usa join='outer' para lidar com colunas diferentes entre arquivos
    combined_df = pd.concat(dfs, ignore_index=True, sort=False)
    
    # Detecta coluna de timestamp automaticamente (pode ser 'timestamp', 'time', 'datetime', etc.)
    timestamp_cols = [col for col in combined_df.columns 
                     if any(keyword in col.lower() for keyword in ['timestamp', 'time', 'datetime', 'date'])]
    
    # Remove duplicatas se houver (baseado em timestamp se disponível)
    if timestamp_cols:
        timestamp_col = timestamp_cols[0]  # Usa a primeira coluna de timestamp encontrada
        combined_df = combined_df.drop_duplicates(subset=[timestamp_col], keep='last')
        # Tenta converter para datetime e ordenar
        try:
            combined_df[timestamp_col] = pd.to_datetime(combined_df[timestamp_col])
            combined_df = combined_df.sort_values(by=timestamp_col).reset_index(drop=True)
        except:
            combined_df = combined_df.sort_values(by=timestamp_col).reset_index(drop=True)
    
    return combined_df


def check_cache_up_to_date(db, query: str = TELEMETRY_QUERY, 
                          timestamp_col: str = TIMESTAMP_COLUMN) -> bool:
    """
    Compara o último timestamp do cache com o banco de dados.
    
    Args:
        db: Instância do DatabaseCache
        query: Query SQL original
        timestamp_col: Nome da coluna de timestamp
        
    Returns:
        True se cache está atualizado, False caso contrário
    """
    # Carregar cache
    cache_files = list(Path(CACHE_DIR).glob("cache_*.parquet"))
    if not cache_files:
        return False
    
    try:
        # Ler todos e pegar máximo timestamp
        dfs = [pd.read_parquet(f) for f in cache_files]
        if not dfs:
            return False
        
        combined = pd.concat(dfs, ignore_index=True)
        
        if timestamp_col not in combined.columns:
            return False
        
        max_cache_time = combined[timestamp_col].max()
        
        # Buscar máximo do banco (query rápida)
        # Usa subquery para pegar apenas o MAX
        db_query = f"""
            SELECT MAX({timestamp_col}) as max_time 
            FROM ({query}) as subquery
        """
        max_db_result = db.execute_query(db_query, use_cache=False)
        
        if max_db_result.empty or max_db_result.iloc[0]['max_time'] is None:
            return True  # Se não há dados no banco, cache está OK
        
        max_db_time = max_db_result.iloc[0]['max_time']
        
        # Compara timestamps
        return pd.to_datetime(max_cache_time) >= pd.to_datetime(max_db_time)
        
    except Exception as e:
        print(f"Erro ao verificar atualização do cache: {e}")
        return False


def update_cache_if_needed(db, query: str = TELEMETRY_QUERY,
                          timestamp_col: str = TIMESTAMP_COLUMN,
                          force: bool = False) -> bool:
    """
    Atualiza o cache se necessário usando busca incremental.
    
    Args:
        db: Instância do DatabaseCache
        query: Query SQL original
        timestamp_col: Nome da coluna de timestamp
        force: Se True, força atualização mesmo se cache estiver atualizado
        
    Returns:
        True se atualização foi realizada, False caso contrário
    """
    if not force:
        if check_cache_up_to_date(db, query, timestamp_col):
            return False
    
    try:
        # Usa busca incremental para atualizar cache
        df = db.execute_incremental_query(
            query=query,
            order_column=timestamp_col,
            use_cache=True
        )
        return True
    except Exception as e:
        print(f"Erro ao atualizar cache: {e}")
        return False


def convert_timezone(df: pd.DataFrame, 
                     timestamp_col: str = TIMESTAMP_COLUMN,
                     from_tz: str = FROM_TIMEZONE,
                     to_tz: str = TO_TIMEZONE) -> pd.DataFrame:
    """
    Converte timestamp de UTC para UTC-3 (America/Sao_Paulo).
    
    Args:
        df: DataFrame com dados
        timestamp_col: Nome da coluna de timestamp
        from_tz: Timezone de origem (padrão: UTC)
        to_tz: Timezone de destino (padrão: America/Sao_Paulo)
        
    Returns:
        DataFrame com timestamps convertidos
    """
    if df.empty or timestamp_col not in df.columns:
        return df
    
    df = df.copy()
    
    try:
        # Converte para datetime se necessário
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])
        
        # Se não tem timezone, localiza como UTC
        if df[timestamp_col].dt.tz is None:
            df[timestamp_col] = df[timestamp_col].dt.tz_localize(from_tz)
        
        # Converte para timezone de destino
        df[timestamp_col] = df[timestamp_col].dt.tz_convert(to_tz)
        
    except Exception as e:
        print(f"Erro ao converter timezone: {e}")
    
    return df


def get_non_null_columns(df: pd.DataFrame, 
                        exclude_cols: Optional[List[str]] = None) -> List[str]:
    """
    Retorna lista de colunas que têm pelo menos um valor não-null.
    
    Args:
        df: DataFrame para analisar
        exclude_cols: Lista de colunas para excluir (ex: timestamp)
        
    Returns:
        Lista de nomes de colunas não-null
    """
    if df.empty:
        return []
    
    exclude_cols = exclude_cols or []
    
    # Filtra colunas que têm pelo menos um valor não-null
    non_null_cols = df.columns[df.notna().any()].tolist()
    
    # Remove colunas excluídas
    non_null_cols = [col for col in non_null_cols if col not in exclude_cols]
    
    return non_null_cols


def filter_by_date_range(df: pd.DataFrame,
                         timestamp_col: str = TIMESTAMP_COLUMN,
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> pd.DataFrame:
    """
    Filtra DataFrame por range de data/hora.
    
    Args:
        df: DataFrame com dados
        timestamp_col: Nome da coluna de timestamp
        start_date: Data/hora inicial (inclusive)
        end_date: Data/hora final (inclusive)
        
    Returns:
        DataFrame filtrado
    """
    if df.empty or timestamp_col not in df.columns:
        return df
    
    df_filtered = df.copy()
    
    # Converte timestamps para comparar
    if start_date:
        if start_date.tzinfo is None:
            # Se start_date não tem timezone, assume timezone local
            start_date = pytz.timezone(TO_TIMEZONE).localize(start_date)
        df_filtered = df_filtered[df_filtered[timestamp_col] >= start_date]
    
    if end_date:
        if end_date.tzinfo is None:
            # Se end_date não tem timezone, assume timezone local
            end_date = pytz.timezone(TO_TIMEZONE).localize(end_date)
        # Adiciona 1 dia e subtrai 1 segundo para incluir todo o dia final
        end_date = end_date.replace(hour=23, minute=59, second=59)
        df_filtered = df_filtered[df_filtered[timestamp_col] <= end_date]
    
    return df_filtered


def get_last_update_time(cache_dir: str = CACHE_DIR) -> Optional[datetime]:
    """
    Retorna o timestamp do último registro no cache.
    
    Args:
        cache_dir: Diretório do cache
        
    Returns:
        Timestamp do último registro ou None
    """
    df = load_all_parquet_files(cache_dir)
    
    if df.empty or TIMESTAMP_COLUMN not in df.columns:
        return None
    
    max_time = df[TIMESTAMP_COLUMN].max()
    
    # Converte para timezone local se necessário
    if isinstance(max_time, pd.Timestamp):
        if max_time.tzinfo is None:
            max_time = pytz.timezone(FROM_TIMEZONE).localize(max_time)
        max_time = max_time.astimezone(pytz.timezone(TO_TIMEZONE))
    
    return max_time

