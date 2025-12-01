-- ============================================================
-- AuraTracking TimescaleDB Schema
-- ============================================================
-- Schema completo para armazenamento de telemetria GPS/IMU
-- Otimizado para séries temporais com:
--   - Hypertables
--   - Compressão automática
--   - Políticas de retenção
--   - Índices eficientes
-- ============================================================

-- Habilitar extensão TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;
-- PostGIS é opcional - descomentar se a imagem suportar
-- CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================
-- TABELA: devices
-- ============================================================
-- Registro de dispositivos ativos
-- ============================================================
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(100) NOT NULL UNIQUE,
    device_model VARCHAR(100),
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    total_telemetry_count BIGINT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_devices_device_id ON devices(device_id);
CREATE INDEX idx_devices_is_active ON devices(is_active);

-- ============================================================
-- TABELA: operators
-- ============================================================
-- Registro de operadores
-- ============================================================
CREATE TABLE IF NOT EXISTS operators (
    id SERIAL PRIMARY KEY,
    operator_id VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255),
    matricula VARCHAR(50),
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_operators_operator_id ON operators(operator_id);

-- ============================================================
-- TABELA: telemetry (HYPERTABLE PRINCIPAL)
-- ============================================================
-- Dados de GPS e IMU combinados
-- Particionado por tempo (chunk de 1 dia)
-- ============================================================
CREATE TABLE IF NOT EXISTS telemetry (
    -- Timestamp do evento (chave de partição)
    time TIMESTAMPTZ NOT NULL,
    
    -- Identificadores
    device_id VARCHAR(100) NOT NULL,
    operator_id VARCHAR(100),
    
    -- Dados GPS
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    altitude DOUBLE PRECISION,
    speed DOUBLE PRECISION,           -- m/s
    bearing DOUBLE PRECISION,         -- graus (0-360)
    gps_accuracy DOUBLE PRECISION,    -- metros
    
    -- Dados IMU
    accel_x DOUBLE PRECISION,         -- m/s²
    accel_y DOUBLE PRECISION,
    accel_z DOUBLE PRECISION,
    gyro_x DOUBLE PRECISION,          -- rad/s
    gyro_y DOUBLE PRECISION,
    gyro_z DOUBLE PRECISION,
    
    -- Dados calculados
    speed_kmh DOUBLE PRECISION GENERATED ALWAYS AS (speed * 3.6) STORED,
    accel_magnitude DOUBLE PRECISION GENERATED ALWAYS AS (
        sqrt(accel_x * accel_x + accel_y * accel_y + accel_z * accel_z)
    ) STORED,
    
    -- Metadados
    topic VARCHAR(255),
    received_at TIMESTAMPTZ DEFAULT NOW(),
    raw_payload JSONB
);

-- Converter para hypertable (chunks de 1 dia)
SELECT create_hypertable('telemetry', 'time', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ============================================================
-- ÍNDICES PARA TELEMETRY
-- ============================================================
-- Índice composto principal para queries por dispositivo
CREATE INDEX idx_telemetry_device_time 
    ON telemetry (device_id, time DESC);

-- Índice para operador
CREATE INDEX idx_telemetry_operator_time 
    ON telemetry (operator_id, time DESC) 
    WHERE operator_id IS NOT NULL;

-- Índice para localização geográfica (lat/lon separados)
CREATE INDEX idx_telemetry_location 
    ON telemetry (latitude, longitude) 
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- Índice para velocidade alta (detecção de anomalias)
CREATE INDEX idx_telemetry_high_speed 
    ON telemetry (time DESC, speed_kmh) 
    WHERE speed_kmh > 80;

-- Índice para aceleração alta (detecção de impactos)
CREATE INDEX idx_telemetry_high_accel 
    ON telemetry (time DESC, accel_magnitude) 
    WHERE accel_magnitude > 15;

-- ============================================================
-- TABELA: events
-- ============================================================
-- Eventos discretos (login, logout, alertas, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS events (
    time TIMESTAMPTZ NOT NULL,
    device_id VARCHAR(100) NOT NULL,
    operator_id VARCHAR(100),
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB DEFAULT '{}'::jsonb,
    topic VARCHAR(255),
    received_at TIMESTAMPTZ DEFAULT NOW()
);

-- Converter para hypertable
SELECT create_hypertable('events', 'time', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX idx_events_device_time ON events (device_id, time DESC);
CREATE INDEX idx_events_type_time ON events (event_type, time DESC);

-- ============================================================
-- TABELA: ingest_stats
-- ============================================================
-- Estatísticas do processo de ingestão
-- ============================================================
CREATE TABLE IF NOT EXISTS ingest_stats (
    time TIMESTAMPTZ NOT NULL,
    messages_received BIGINT DEFAULT 0,
    messages_inserted BIGINT DEFAULT 0,
    messages_failed BIGINT DEFAULT 0,
    batch_count BIGINT DEFAULT 0,
    avg_batch_size DOUBLE PRECISION DEFAULT 0,
    avg_latency_ms DOUBLE PRECISION DEFAULT 0,
    offline_queue_size BIGINT DEFAULT 0,
    mqtt_connected BOOLEAN DEFAULT TRUE,
    db_connected BOOLEAN DEFAULT TRUE
);

SELECT create_hypertable('ingest_stats', 'time', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ============================================================
-- POLÍTICAS DE COMPRESSÃO
-- ============================================================
-- Comprimir dados após 3 dias (economia de ~90% de espaço)
-- ============================================================
ALTER TABLE telemetry SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id',
    timescaledb.compress_orderby = 'time DESC'
);

ALTER TABLE events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id',
    timescaledb.compress_orderby = 'time DESC'
);

-- Política de compressão automática (após 3 dias)
SELECT add_compression_policy('telemetry', INTERVAL '3 days', if_not_exists => TRUE);
SELECT add_compression_policy('events', INTERVAL '3 days', if_not_exists => TRUE);

-- ============================================================
-- POLÍTICAS DE RETENÇÃO (TTL)
-- ============================================================
-- Manter dados por 180 dias (6 meses)
-- ============================================================
SELECT add_retention_policy('telemetry', INTERVAL '180 days', if_not_exists => TRUE);
SELECT add_retention_policy('events', INTERVAL '365 days', if_not_exists => TRUE);
SELECT add_retention_policy('ingest_stats', INTERVAL '30 days', if_not_exists => TRUE);

-- ============================================================
-- CONTINUOUS AGGREGATES (Materializações)
-- ============================================================
-- Agregações pré-calculadas para dashboards rápidos
-- ============================================================

-- Agregação por minuto (para gráficos em tempo real)
CREATE MATERIALIZED VIEW telemetry_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    device_id,
    COUNT(*) AS sample_count,
    AVG(speed_kmh) AS avg_speed_kmh,
    MAX(speed_kmh) AS max_speed_kmh,
    AVG(latitude) AS avg_lat,
    AVG(longitude) AS avg_lon,
    AVG(gps_accuracy) AS avg_accuracy,
    AVG(accel_magnitude) AS avg_accel,
    MAX(accel_magnitude) AS max_accel,
    MIN(time) AS first_sample,
    MAX(time) AS last_sample
FROM telemetry
GROUP BY bucket, device_id
WITH NO DATA;

-- Agregação por hora (para análises históricas)
CREATE MATERIALIZED VIEW telemetry_1hour
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    device_id,
    operator_id,
    COUNT(*) AS sample_count,
    AVG(speed_kmh) AS avg_speed_kmh,
    MAX(speed_kmh) AS max_speed_kmh,
    SUM(speed * 1) AS total_distance_approx,  -- Aproximação
    AVG(accel_magnitude) AS avg_accel,
    MAX(accel_magnitude) AS max_accel,
    -- Bounding box do trajeto
    MIN(latitude) AS min_lat,
    MAX(latitude) AS max_lat,
    MIN(longitude) AS min_lon,
    MAX(longitude) AS max_lon
FROM telemetry
GROUP BY bucket, device_id, operator_id
WITH NO DATA;

-- Políticas de refresh para continuous aggregates
SELECT add_continuous_aggregate_policy('telemetry_1min',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy('telemetry_1hour',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- ============================================================
-- VIEWS ÚTEIS
-- ============================================================

-- Última posição de cada dispositivo
CREATE OR REPLACE VIEW device_last_position AS
SELECT DISTINCT ON (device_id)
    device_id,
    time,
    operator_id,
    latitude,
    longitude,
    altitude,
    speed_kmh,
    bearing,
    gps_accuracy,
    accel_magnitude
FROM telemetry
WHERE time > NOW() - INTERVAL '24 hours'
ORDER BY device_id, time DESC;

-- Status dos dispositivos (ativos nas últimas horas)
CREATE OR REPLACE VIEW device_status AS
SELECT 
    d.device_id,
    d.device_model,
    d.is_active,
    d.last_seen,
    EXTRACT(EPOCH FROM (NOW() - d.last_seen)) AS seconds_since_last,
    CASE 
        WHEN d.last_seen > NOW() - INTERVAL '1 minute' THEN 'ONLINE'
        WHEN d.last_seen > NOW() - INTERVAL '5 minutes' THEN 'IDLE'
        WHEN d.last_seen > NOW() - INTERVAL '1 hour' THEN 'AWAY'
        ELSE 'OFFLINE'
    END AS status,
    (SELECT COUNT(*) FROM telemetry t 
     WHERE t.device_id = d.device_id 
     AND t.time > NOW() - INTERVAL '1 hour') AS samples_last_hour
FROM devices d;

-- ============================================================
-- FUNÇÕES UTILITÁRIAS
-- ============================================================

-- Função para calcular distância entre dois pontos (Haversine)
CREATE OR REPLACE FUNCTION haversine_distance(
    lat1 DOUBLE PRECISION, lon1 DOUBLE PRECISION,
    lat2 DOUBLE PRECISION, lon2 DOUBLE PRECISION
) RETURNS DOUBLE PRECISION AS $$
DECLARE
    R DOUBLE PRECISION := 6371000; -- Raio da Terra em metros
    phi1 DOUBLE PRECISION;
    phi2 DOUBLE PRECISION;
    delta_phi DOUBLE PRECISION;
    delta_lambda DOUBLE PRECISION;
    a DOUBLE PRECISION;
    c DOUBLE PRECISION;
BEGIN
    phi1 := radians(lat1);
    phi2 := radians(lat2);
    delta_phi := radians(lat2 - lat1);
    delta_lambda := radians(lon2 - lon1);
    
    a := sin(delta_phi/2) * sin(delta_phi/2) +
         cos(phi1) * cos(phi2) *
         sin(delta_lambda/2) * sin(delta_lambda/2);
    c := 2 * atan2(sqrt(a), sqrt(1-a));
    
    RETURN R * c;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Função para atualizar estatísticas do dispositivo
CREATE OR REPLACE FUNCTION update_device_stats()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO devices (device_id, last_seen, total_telemetry_count)
    VALUES (NEW.device_id, NEW.time, 1)
    ON CONFLICT (device_id) DO UPDATE SET
        last_seen = GREATEST(devices.last_seen, NEW.time),
        total_telemetry_count = devices.total_telemetry_count + 1,
        updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para atualizar dispositivos automaticamente
CREATE TRIGGER trg_update_device_stats
    AFTER INSERT ON telemetry
    FOR EACH ROW
    EXECUTE FUNCTION update_device_stats();

-- ============================================================
-- USUÁRIO SOMENTE LEITURA PARA GRAFANA
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'grafana_reader') THEN
        CREATE ROLE grafana_reader WITH LOGIN PASSWORD 'grafana2025';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE auratracking TO grafana_reader;
GRANT USAGE ON SCHEMA public TO grafana_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO grafana_reader;

-- ============================================================
-- DADOS INICIAIS PARA TESTE
-- ============================================================
INSERT INTO devices (device_id, device_model, metadata) 
VALUES ('moto_g34_test', 'Moto G34 5G', '{"os": "Android 14", "app_version": "1.0.0"}'::jsonb)
ON CONFLICT (device_id) DO NOTHING;

-- ============================================================
-- VERIFICAÇÃO
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE '✅ AuraTracking database schema created successfully!';
    RAISE NOTICE '   - Tables: telemetry, events, devices, operators, ingest_stats';
    RAISE NOTICE '   - Hypertables configured with 1-day chunks';
    RAISE NOTICE '   - Compression policy: 3 days';
    RAISE NOTICE '   - Retention policy: 180 days';
    RAISE NOTICE '   - Continuous aggregates: 1min, 1hour';
END
$$;
