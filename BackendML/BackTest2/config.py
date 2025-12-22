"""
Configurações do banco de dados.
"""
# Configurações do banco de dados PostgreSQL
DB_CONFIG = {
    "host": "10.135.22.3",
    "port": 5432,
    "dbname": "auratracking",
    "user": "aura",
    "password": "aura2025"
}

# Configurações do pool de conexões
POOL_CONFIG = {
    "min_conn": 1,
    "max_conn": 10
}

# Configurações do cache (em segundos)
CACHE_CONFIG = {
    "ttl": 300  # 5 minutos
}

