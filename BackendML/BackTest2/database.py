"""
Módulo de conexão com banco de dados PostgreSQL com cache incremental em Parquet.
"""
import psycopg2
from psycopg2 import pool
from typing import Optional, Dict, Any, List, Tuple
import hashlib
from pathlib import Path
from contextlib import contextmanager
import pandas as pd
import numpy as np


class DatabaseCache:
    """Classe para gerenciar conexões e cache incremental de consultas ao banco de dados."""
    
    def __init__(self, host: str, port: int, dbname: str, user: str, password: str,
                 min_conn: int = 1, max_conn: int = 10, cache_dir: str = ".cache"):
        """
        Inicializa o gerenciador de banco de dados com cache incremental em Parquet.
        
        Args:
            host: Endereço do servidor PostgreSQL
            port: Porta do servidor
            dbname: Nome do banco de dados
            user: Usuário do banco
            password: Senha do banco
            min_conn: Número mínimo de conexões no pool
            max_conn: Número máximo de conexões no pool
            cache_dir: Diretório onde os arquivos Parquet serão salvos
        """
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password
        
        # Configura diretório de cache
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Pool de conexões
        self.connection_pool: Optional[pool.ThreadedConnectionPool] = None
        self._init_connection_pool(min_conn, max_conn)
    
    def _init_connection_pool(self, min_conn: int, max_conn: int):
        """Inicializa o pool de conexões."""
        try:
            self.connection_pool = pool.ThreadedConnectionPool(
                min_conn,
                max_conn,
                host=self.host,
                port=self.port,
                dbname=self.dbname,
                user=self.user,
                password=self.password
            )
            print(f"[OK] Pool de conexoes criado: {min_conn}-{max_conn} conexoes")
        except Exception as e:
            print(f"[ERRO] Erro ao criar pool de conexoes: {e}")
            raise
    
    def _get_cache_filename(self, query: str, params: Optional[Tuple] = None) -> Path:
        """Gera o nome do arquivo Parquet baseado na query."""
        # Cria hash da query para nome de arquivo único
        query_str = f"{query}:{params}" if params else query
        query_hash = hashlib.md5(query_str.encode()).hexdigest()[:12]
        return self.cache_dir / f"cache_{query_hash}.parquet"
    
    @contextmanager
    def get_connection(self):
        """Context manager para obter uma conexão do pool."""
        conn = None
        try:
            conn = self.connection_pool.getconn()
            yield conn
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def _query_to_dataframe(self, query: str, params: Optional[Tuple] = None) -> pd.DataFrame:
        """Executa uma query e retorna como DataFrame."""
        with self.get_connection() as conn:
            if params:
                df = pd.read_sql_query(query, conn, params=params)
            else:
                df = pd.read_sql_query(query, conn)
            return df
    
    def execute_incremental_query(self, query: str, order_column: str,
                                 params: Optional[Tuple] = None,
                                 use_cache: bool = True) -> pd.DataFrame:
        """
        Executa uma consulta SQL com cache incremental em Parquet.
        Busca apenas dados novos que não estão no cache.
        
        Args:
            query: Query SQL base (deve retornar todos os dados quando executada completa)
            order_column: Nome da coluna usada para ordenação (timestamp, id, etc.)
                         Deve ser uma coluna que sempre aumenta (timestamp, auto-increment, etc.)
            params: Parâmetros para a query (tupla)
            use_cache: Se True, usa cache incremental. Se False, busca tudo do banco.
            
        Returns:
            DataFrame com todos os dados (cache + novos)
        """
        cache_file = self._get_cache_filename(query, params)
        
        # Se não usar cache, busca tudo do banco
        if not use_cache or not cache_file.exists():
            print(f"> Buscando todos os dados do banco...")
            df = self._query_to_dataframe(query, params)
            
            if use_cache and len(df) > 0:
                # Salva no cache
                df.to_parquet(cache_file, index=False, compression='snappy')
                print(f"[OK] Cache salvo: {len(df)} registros em {cache_file.name}")
            
            return df
        
        # Carrega cache existente
        print(f"> Carregando cache existente de {cache_file.name}...")
        df_cached = pd.read_parquet(cache_file)
        
        if len(df_cached) == 0:
            print("  Cache vazio, buscando todos os dados...")
            df = self._query_to_dataframe(query, params)
            if len(df) > 0:
                df.to_parquet(cache_file, index=False, compression='snappy')
                print(f"[OK] Cache atualizado: {len(df)} registros")
            return df
        
        # Verifica se a coluna de ordenação existe
        if order_column not in df_cached.columns:
            print(f"[AVISO] Coluna '{order_column}' nao encontrada no cache. Buscando todos os dados...")
            df = self._query_to_dataframe(query, params)
            df.to_parquet(cache_file, index=False, compression='snappy')
            return df
        
        # Obtém o valor máximo da coluna de ordenação no cache
        max_value = df_cached[order_column].max()
        print(f"  Último valor em cache ({order_column}): {max_value}")
        
        # Modifica a query para buscar apenas dados novos
        # Usa regex para encontrar posições corretas
        import re
        query_clean = query.rstrip().rstrip(';')
        query_lower = query_clean.lower()
        
        # Encontra ORDER BY (case-insensitive)
        order_by_match = re.search(r'\s+order\s+by\s+', query_lower, re.IGNORECASE)
        order_by_pos = order_by_match.start() if order_by_match else len(query_clean)
        
        # Detecta se já tem WHERE na query
        where_match = re.search(r'\s+where\s+', query_lower, re.IGNORECASE)
        has_where = where_match is not None
        
        if has_where:
            # Adiciona condição AND antes do ORDER BY
            # Pega a parte antes do ORDER BY e adiciona AND no final
            part_before_order = query_clean[:order_by_pos].rstrip()
            part_after_order = query_clean[order_by_pos:] if order_by_pos < len(query_clean) else ""
            
            query_incremental = f"{part_before_order} AND {order_column} > %s {part_after_order}".strip()
            
            # Prepara parâmetros
            if params:
                new_params = params + (max_value,)
            else:
                new_params = (max_value,)
        else:
            # Adiciona WHERE antes do ORDER BY
            part_before_order = query_clean[:order_by_pos].rstrip()
            part_after_order = query_clean[order_by_pos:] if order_by_pos < len(query_clean) else ""
            
            query_incremental = f"{part_before_order} WHERE {order_column} > %s {part_after_order}".strip()
            
            if params:
                new_params = params + (max_value,)
            else:
                new_params = (max_value,)
        
        # Busca apenas dados novos
        print(f"> Buscando apenas dados novos ({order_column} > {max_value})...")
        df_new = self._query_to_dataframe(query_incremental, new_params)
        
        if len(df_new) == 0:
            print(f"[OK] Nenhum dado novo encontrado. Retornando cache: {len(df_cached)} registros")
            return df_cached
        
        print(f"[OK] Encontrados {len(df_new)} registros novos")
        
        # Combina cache + novos dados
        df_combined = pd.concat([df_cached, df_new], ignore_index=True)
        
        # Remove duplicatas baseado na coluna de ordenação (caso haja sobreposição)
        df_combined = df_combined.drop_duplicates(subset=[order_column], keep='last')
        df_combined = df_combined.sort_values(by=order_column).reset_index(drop=True)
        
        # Salva cache atualizado
        df_combined.to_parquet(cache_file, index=False, compression='snappy')
        print(f"[OK] Cache atualizado: {len(df_combined)} registros totais ({len(df_cached)} antigos + {len(df_new)} novos)")
        
        return df_combined
    
    def execute_query(self, query: str, params: Optional[Tuple] = None,
                     use_cache: bool = True) -> pd.DataFrame:
        """
        Executa uma consulta SQL simples (sem busca incremental).
        Útil para queries que não precisam de cache incremental.
        
        Args:
            query: Query SQL a ser executada
            params: Parâmetros para a query (tupla)
            use_cache: Se True, salva resultado em Parquet para próxima vez
            
        Returns:
            DataFrame com os resultados
        """
        cache_file = self._get_cache_filename(query, params)
        
        # Se usar cache e arquivo existe, retorna do cache
        if use_cache and cache_file.exists():
            print(f"[OK] Retornando do cache: {cache_file.name}")
            return pd.read_parquet(cache_file)
        
        # Busca do banco
        print(f"> Executando query no banco...")
        df = self._query_to_dataframe(query, params)
        
        if use_cache and len(df) > 0:
            df.to_parquet(cache_file, index=False, compression='snappy')
            print(f"[OK] Cache salvo: {len(df)} registros")
        
        return df
    
    def execute_non_query(self, query: str, params: Optional[Tuple] = None):
        """
        Executa uma query que não retorna resultados (INSERT, UPDATE, DELETE).
        
        Args:
            query: Query SQL a ser executada
            params: Parâmetros para a query (tupla)
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                conn.commit()
    
    def clear_cache(self, pattern: Optional[str] = None):
        """
        Limpa o cache.
        
        Args:
            pattern: Se fornecido, remove apenas arquivos que contenham o padrão no nome.
                     Se None, remove todos os arquivos de cache.
        """
        if pattern:
            files = list(self.cache_dir.glob(f"*{pattern}*.parquet"))
        else:
            files = list(self.cache_dir.glob("cache_*.parquet"))
        
        removed = 0
        for cache_file in files:
            try:
                cache_file.unlink()
                removed += 1
            except Exception as e:
                print(f"Erro ao remover {cache_file}: {e}")
        
        print(f"[OK] Cache limpo: {removed} arquivo(s) removido(s)")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache."""
        cache_files = list(self.cache_dir.glob("cache_*.parquet"))
        
        total_size = sum(f.stat().st_size for f in cache_files)
        total_records = 0
        
        for cache_file in cache_files:
            try:
                df = pd.read_parquet(cache_file)
                total_records += len(df)
            except:
                pass
        
        return {
            "total_files": len(cache_files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_records": total_records,
            "cache_dir": str(self.cache_dir)
        }
    
    def close(self):
        """Fecha o pool de conexões."""
        if self.connection_pool:
            self.connection_pool.closeall()
            print("[OK] Pool de conexoes fechado")


# Instância global do banco de dados
_db_instance: Optional[DatabaseCache] = None


def init_database(host: str, port: int, dbname: str, user: str, password: str,
                 min_conn: int = 1, max_conn: int = 10, cache_dir: str = ".cache"):
    """
    Inicializa a instância global do banco de dados.
    
    Args:
        host: Endereço do servidor PostgreSQL
        port: Porta do servidor
        dbname: Nome do banco de dados
        user: Usuário do banco
        password: Senha do banco
        min_conn: Número mínimo de conexões no pool
        max_conn: Número máximo de conexões no pool
        cache_dir: Diretório onde os arquivos Parquet serão salvos
    """
    global _db_instance
    _db_instance = DatabaseCache(host, port, dbname, user, password, 
                                 min_conn, max_conn, cache_dir)


def get_db() -> DatabaseCache:
    """Retorna a instância global do banco de dados."""
    if _db_instance is None:
        raise RuntimeError("Banco de dados não foi inicializado. Chame init_database() primeiro.")
    return _db_instance
