# ============================================================
# AuraTracking Ingest Worker - Dockerfile
# ============================================================
# Worker Python para ingestão de telemetria MQTT → TimescaleDB
# Com fila offline SQLite e reconexão automática
# ============================================================

FROM python:3.12-slim

# Metadata
LABEL maintainer="AuraTracking Team"
LABEL description="MQTT to TimescaleDB Ingest Worker"
LABEL version="1.0.0"

# Variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Criar diretórios
WORKDIR /app
RUN mkdir -p /app/queue /app/logs

# Copiar requirements primeiro (cache de build)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fonte
COPY src/ ./src/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Usuário não-root
RUN useradd -m -u 1000 ingest && \
    chown -R ingest:ingest /app
USER ingest

# Porta do health check
EXPOSE 8080

# Entrypoint
CMD ["python", "-m", "src.main"]
