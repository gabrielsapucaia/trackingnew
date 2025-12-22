"""
Configurações específicas para a aplicação Streamlit de Telemetria.
"""
from config import DB_CONFIG, POOL_CONFIG

# Query SQL original para buscar dados de telemetria
# IMPORTANTE: Esta query deve retornar todos os dados que serão visualizados
TELEMETRY_QUERY = """
    SELECT *
    FROM telemetry
    ORDER BY time
"""

# Nome da coluna de timestamp nos dados
# A tabela telemetry usa a coluna 'time' como timestamp principal
TIMESTAMP_COLUMN = "time"

# Configurações de timezone
FROM_TIMEZONE = "UTC"  # Timezone dos dados no banco
TO_TIMEZONE = "America/Sao_Paulo"  # UTC-3 (timezone local)

# Diretório de cache
CACHE_DIR = ".cache"

# Configurações do Streamlit
APP_TITLE = "Gráficos Telemetria"
SIDEBAR_TITLE = "Filtros"

