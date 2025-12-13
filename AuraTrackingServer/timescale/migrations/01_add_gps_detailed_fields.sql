-- Migration: Adicionar campos GPS detalhados
-- Data: 2024-12-11
-- Descrição: Adiciona campos GPS detalhados que estavam no schema mas não foram aplicados no banco existente

-- GPS Detalhado
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS satellites INTEGER;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS h_acc DOUBLE PRECISION;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS v_acc DOUBLE PRECISION;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS s_acc DOUBLE PRECISION;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS hdop DOUBLE PRECISION;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS vdop DOUBLE PRECISION;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS pdop DOUBLE PRECISION;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS gps_timestamp BIGINT;



