"""
============================================================
AuraTracking Ingest Worker
============================================================
Worker Python para ingestão de telemetria MQTT → TimescaleDB

Funcionalidades:
- Subscribe MQTT wildcard (aura/tracking/#)
- Validação JSON com Pydantic
- Batch insert assíncrono
- Fila offline SQLite para resiliência
- Reconexão automática com backoff exponencial
- Health check HTTP endpoint
- Métricas Prometheus

============================================================
"""

import asyncio
import json
import os
import signal
import sqlite3
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from typing import Any, Optional

import paho.mqtt.client as mqtt
import psycopg2
import psycopg2.extras
import structlog
from fastapi import FastAPI
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential
import uvicorn

# ============================================================
# CONFIGURAÇÃO
# ============================================================

@dataclass
class Config:
    """Configuração do Ingest Worker via variáveis de ambiente."""
    
    # MQTT
    mqtt_host: str = field(default_factory=lambda: os.getenv("MQTT_HOST", "10.10.10.10"))
    mqtt_port: int = field(default_factory=lambda: int(os.getenv("MQTT_PORT", "1883")))
    mqtt_topic: str = field(default_factory=lambda: os.getenv("MQTT_TOPIC", "aura/tracking/#"))
    mqtt_client_id: str = field(default_factory=lambda: os.getenv("MQTT_CLIENT_ID", "aura_ingest_worker"))
    mqtt_qos: int = field(default_factory=lambda: int(os.getenv("MQTT_QOS", "1")))
    mqtt_keepalive: int = field(default_factory=lambda: int(os.getenv("MQTT_KEEPALIVE", "60")))
    
    # Database
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "10.10.10.20"))
    db_port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    db_name: str = field(default_factory=lambda: os.getenv("DB_NAME", "auratracking"))
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "aura"))
    db_password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", "aura2025"))
    
    # Ingest
    batch_size: int = field(default_factory=lambda: int(os.getenv("BATCH_SIZE", "100")))
    batch_timeout_ms: int = field(default_factory=lambda: int(os.getenv("BATCH_TIMEOUT_MS", "5000")))
    offline_queue_path: str = field(default_factory=lambda: os.getenv("OFFLINE_QUEUE_PATH", "/app/queue/offline.db"))
    
    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_path: str = field(default_factory=lambda: os.getenv("LOG_PATH", "/app/logs"))
    
    # Health
    health_port: int = field(default_factory=lambda: int(os.getenv("HEALTH_PORT", "8080")))


# ============================================================
# MODELOS PYDANTIC
# ============================================================

class GpsData(BaseModel):
    """Dados GPS do dispositivo.
    
    Aceita campos do Android app:
    - latitude/longitude OU lat/lon
    - altitude OU alt
    """
    # Campos podem vir como latitude/longitude (Android) ou lat/lon (compact)
    latitude: Optional[float] = Field(None, ge=-90, le=90, alias="latitude")
    longitude: Optional[float] = Field(None, ge=-180, le=180, alias="longitude")
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    altitude: Optional[float] = Field(None, alias="altitude")
    alt: Optional[float] = None
    speed: Optional[float] = Field(None, ge=0)  # m/s
    bearing: Optional[float] = Field(None, ge=0, le=360)
    accuracy: Optional[float] = Field(None, ge=0)
    
    @property
    def lat_value(self) -> Optional[float]:
        """Retorna latitude (aceita ambos os formatos)."""
        return self.latitude if self.latitude is not None else self.lat
    
    @property
    def lon_value(self) -> Optional[float]:
        """Retorna longitude (aceita ambos os formatos)."""
        return self.longitude if self.longitude is not None else self.lon
    
    @property
    def alt_value(self) -> Optional[float]:
        """Retorna altitude (aceita ambos os formatos)."""
        return self.altitude if self.altitude is not None else self.alt
    
    model_config = {"populate_by_name": True}


class ImuData(BaseModel):
    """Dados IMU do dispositivo."""
    accelX: float
    accelY: float
    accelZ: float
    gyroX: Optional[float] = 0.0
    gyroY: Optional[float] = 0.0
    gyroZ: Optional[float] = 0.0


class TelemetryPacket(BaseModel):
    """Pacote de telemetria completo.
    
    FASE 3 - QUEUE 30 DIAS:
    - messageId: UUID globalmente único para deduplicação (opcional para retrocompatibilidade)
    - Servidor usa ON CONFLICT (time, device_id) como fallback
    """
    messageId: Optional[str] = Field(None, min_length=1, max_length=100)  # UUID para deduplicação
    deviceId: str = Field(..., min_length=1, max_length=100)
    operatorId: Optional[str] = None
    timestamp: int = Field(..., gt=0)  # Unix ms
    gps: Optional[GpsData] = None
    imu: Optional[ImuData] = None


class EventPacket(BaseModel):
    """Pacote de evento."""
    deviceId: str
    operatorId: Optional[str] = None
    timestamp: int
    eventType: str
    data: Optional[dict] = None


# ============================================================
# LOGGER ESTRUTURADO
# ============================================================

def setup_logging(config: Config):
    """Configura logging estruturado."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    import logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, config.log_level.upper()),
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(Path(config.log_path) / "ingest.log")
        ]
    )


# ============================================================
# FILA OFFLINE (SQLite)
# ============================================================

class OfflineQueue:
    """Fila offline persistente usando SQLite."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = structlog.get_logger("offline_queue")
        self._init_db()
    
    def _init_db(self):
        """Inicializa o banco SQLite."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    retries INTEGER DEFAULT 0,
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_timestamp ON queue(timestamp)")
            conn.commit()
        
        self.logger.info("offline_queue_initialized", path=self.db_path)
    
    def enqueue(self, topic: str, payload: str, timestamp: float):
        """Adiciona mensagem à fila offline."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO queue (topic, payload, timestamp) VALUES (?, ?, ?)",
                    (topic, payload, timestamp)
                )
                conn.commit()
            self.logger.debug("message_queued_offline", topic=topic)
        except Exception as e:
            self.logger.error("offline_queue_error", error=str(e))
    
    def dequeue_batch(self, batch_size: int = 100) -> list[tuple]:
        """Remove e retorna um batch de mensagens."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT id, topic, payload, timestamp FROM queue ORDER BY timestamp LIMIT ?",
                    (batch_size,)
                )
                rows = cursor.fetchall()
                
                if rows:
                    ids = [r[0] for r in rows]
                    placeholders = ",".join("?" * len(ids))
                    conn.execute(f"DELETE FROM queue WHERE id IN ({placeholders})", ids)
                    conn.commit()
                
                return rows
        except Exception as e:
            self.logger.error("dequeue_error", error=str(e))
            return []
    
    def size(self) -> int:
        """Retorna o tamanho da fila."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM queue")
                return cursor.fetchone()[0]
        except:
            return 0
    
    def purge_old(self, max_age_hours: int = 48):
        """Remove mensagens antigas."""
        try:
            cutoff = time.time() - (max_age_hours * 3600)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM queue WHERE timestamp < ?",
                    (cutoff,)
                )
                deleted = cursor.rowcount
                conn.commit()
                if deleted > 0:
                    self.logger.info("purged_old_messages", count=deleted)
        except Exception as e:
            self.logger.error("purge_error", error=str(e))


# ============================================================
# DATABASE CONNECTION POOL
# ============================================================

class DatabasePool:
    """Pool de conexões PostgreSQL."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = structlog.get_logger("database")
        self._conn: Optional[psycopg2.extensions.connection] = None
        self._connected = False
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30)
    )
    def connect(self):
        """Conecta ao banco de dados."""
        try:
            self._conn = psycopg2.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                dbname=self.config.db_name,
                user=self.config.db_user,
                password=self.config.db_password,
                connect_timeout=10,
                options="-c statement_timeout=30000"
            )
            self._conn.autocommit = False
            self._connected = True
            self.logger.info("database_connected", 
                           host=self.config.db_host, 
                           database=self.config.db_name)
        except Exception as e:
            self._connected = False
            self.logger.error("database_connection_failed", error=str(e))
            raise
    
    def is_connected(self) -> bool:
        """Verifica se está conectado."""
        if not self._conn or not self._connected:
            return False
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except:
            self._connected = False
            return False
    
    def ensure_connected(self):
        """Garante que está conectado."""
        if not self.is_connected():
            self.connect()
    
    def get_connection(self):
        """Retorna a conexão ativa."""
        self.ensure_connected()
        return self._conn
    
    def insert_telemetry_batch(self, records: list[dict]) -> int:
        """Insere batch de telemetria, ignorando duplicatas.
        
        FASE 3 - QUEUE 30 DIAS:
        - Deduplicação primária: ON CONFLICT (time, device_id) DO NOTHING
        - message_id armazenado para rastreabilidade (não usado como constraint)
        """
        if not records:
            return 0
        
        self.ensure_connected()
        
        # ON CONFLICT DO NOTHING para ignorar duplicatas
        # Requer índice único em (time, device_id)
        insert_sql = """
            INSERT INTO telemetry (
                time, device_id, operator_id, message_id,
                latitude, longitude, altitude, speed, bearing, gps_accuracy,
                accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z,
                topic, received_at, raw_payload
            ) VALUES (
                %(time)s, %(device_id)s, %(operator_id)s, %(message_id)s,
                %(latitude)s, %(longitude)s, %(altitude)s, %(speed)s, %(bearing)s, %(gps_accuracy)s,
                %(accel_x)s, %(accel_y)s, %(accel_z)s, %(gyro_x)s, %(gyro_y)s, %(gyro_z)s,
                %(topic)s, %(received_at)s, %(raw_payload)s
            )
            ON CONFLICT (time, device_id) DO NOTHING
        """
        
        try:
            with self._conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, insert_sql, records, page_size=100)
            self._conn.commit()
            self.logger.info("batch_inserted", count=len(records))
            return len(records)
        except Exception as e:
            self._conn.rollback()
            self.logger.error("batch_insert_failed", error=str(e), count=len(records))
            raise
    
    def insert_event(self, record: dict):
        """Insere um evento."""
        self.ensure_connected()
        
        insert_sql = """
            INSERT INTO events (time, device_id, operator_id, event_type, event_data, topic, received_at)
            VALUES (%(time)s, %(device_id)s, %(operator_id)s, %(event_type)s, %(event_data)s, %(topic)s, %(received_at)s)
        """
        
        try:
            with self._conn.cursor() as cur:
                cur.execute(insert_sql, record)
            self._conn.commit()
        except Exception as e:
            self._conn.rollback()
            self.logger.error("event_insert_failed", error=str(e))
            raise
    
    def close(self):
        """Fecha conexão."""
        if self._conn:
            self._conn.close()
            self._connected = False


# ============================================================
# INGEST WORKER
# ============================================================

class IngestWorker:
    """Worker principal de ingestão."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = structlog.get_logger("ingest")
        
        # Componentes
        self.db = DatabasePool(config)
        self.offline_queue = OfflineQueue(config.offline_queue_path)
        
        # MQTT Client - Sessão persistente para não perder mensagens
        # clean_start=False mantém subscriptions e recebe mensagens pendentes
        self.mqtt_client = mqtt.Client(
            client_id=config.mqtt_client_id,
            protocol=mqtt.MQTTv5,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            reconnect_on_failure=True  # Reconexão automática
        )
        # Configurar sessão persistente no MQTTv5
        self.mqtt_client._clean_start = False
        # Configurar delays de reconexão (min 1s, max 60s)
        self.mqtt_client.reconnect_delay_set(min_delay=1, max_delay=60)
        self.mqtt_connected = False
        
        # Batch buffer
        self.batch_buffer: list[dict] = []
        self.last_flush_time = time.time()
        self.batch_lock = asyncio.Lock()
        
        # Stats
        self.stats = {
            "messages_received": 0,
            "messages_inserted": 0,
            "messages_failed": 0,
            "batch_count": 0,
            "mqtt_reconnects": 0,
            "db_reconnects": 0,
            "start_time": time.time()
        }
        
        # Shutdown flag
        self._running = False
        
        # Setup MQTT callbacks
        self._setup_mqtt_callbacks()
    
    def _setup_mqtt_callbacks(self):
        """Configura callbacks do MQTT."""
        
        def on_connect(client, userdata, flags, reason_code, properties):
            if reason_code == 0:
                self.mqtt_connected = True
                # Verificar se sessão foi restaurada
                session_present = flags.session_present if hasattr(flags, 'session_present') else False
                self.logger.info("mqtt_connected", 
                               broker=self.config.mqtt_host,
                               session_present=session_present)
                
                # Subscribe ao tópico (QoS 1 para garantir entrega)
                client.subscribe(self.config.mqtt_topic, qos=self.config.mqtt_qos)
                self.logger.info("mqtt_subscribed", topic=self.config.mqtt_topic, qos=self.config.mqtt_qos)
            else:
                self.mqtt_connected = False
                self.logger.error("mqtt_connect_failed", reason=str(reason_code))
        
        def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
            self.mqtt_connected = False
            self.logger.warning("mqtt_disconnected", reason=str(reason_code))
            self.stats["mqtt_reconnects"] += 1
        
        def on_message(client, userdata, msg):
            try:
                self._handle_message(msg.topic, msg.payload.decode('utf-8'))
            except Exception as e:
                self.logger.error("message_handler_error", error=str(e), topic=msg.topic)
        
        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_disconnect = on_disconnect
        self.mqtt_client.on_message = on_message
    
    def _handle_message(self, topic: str, payload: str):
        """Processa uma mensagem MQTT."""
        self.stats["messages_received"] += 1
        
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            self.logger.warning("invalid_json", topic=topic, error=str(e))
            self.stats["messages_failed"] += 1
            return
        
        # Determinar tipo de mensagem pelo tópico
        topic_parts = topic.split("/")
        
        if len(topic_parts) >= 4 and topic_parts[-1] == "events":
            self._handle_event(topic, data, payload)
        else:
            self._handle_telemetry(topic, data, payload)
    
    def _handle_telemetry(self, topic: str, data: dict, raw_payload: str):
        """Processa pacote de telemetria."""
        try:
            packet = TelemetryPacket(**data)
        except ValidationError as e:
            self.logger.warning("invalid_telemetry", topic=topic, error=str(e))
            self.stats["messages_failed"] += 1
            return
        
        # Converter para registro do banco
        # Usa lat_value/lon_value/alt_value para aceitar ambos os formatos
        # FASE 3: Inclui message_id para rastreabilidade
        record = {
            "time": datetime.fromtimestamp(packet.timestamp / 1000, tz=timezone.utc),
            "device_id": packet.deviceId,
            "operator_id": packet.operatorId,
            "message_id": packet.messageId,  # UUID do Android para rastreabilidade
            "latitude": packet.gps.lat_value if packet.gps else None,
            "longitude": packet.gps.lon_value if packet.gps else None,
            "altitude": packet.gps.alt_value if packet.gps else None,
            "speed": packet.gps.speed if packet.gps else None,
            "bearing": packet.gps.bearing if packet.gps else None,
            "gps_accuracy": packet.gps.accuracy if packet.gps else None,
            "accel_x": packet.imu.accelX if packet.imu else None,
            "accel_y": packet.imu.accelY if packet.imu else None,
            "accel_z": packet.imu.accelZ if packet.imu else None,
            "gyro_x": packet.imu.gyroX if packet.imu else None,
            "gyro_y": packet.imu.gyroY if packet.imu else None,
            "gyro_z": packet.imu.gyroZ if packet.imu else None,
            "topic": topic,
            "received_at": datetime.now(timezone.utc),
            "raw_payload": json.dumps(data)
        }
        
        # Adicionar ao buffer
        self.batch_buffer.append(record)
        
        # Verificar se deve fazer flush
        should_flush = (
            len(self.batch_buffer) >= self.config.batch_size or
            (time.time() - self.last_flush_time) * 1000 >= self.config.batch_timeout_ms
        )
        
        if should_flush:
            self._flush_batch()
    
    def _handle_event(self, topic: str, data: dict, raw_payload: str):
        """Processa pacote de evento."""
        try:
            packet = EventPacket(**data)
        except ValidationError as e:
            self.logger.warning("invalid_event", topic=topic, error=str(e))
            return
        
        record = {
            "time": datetime.fromtimestamp(packet.timestamp / 1000, tz=timezone.utc),
            "device_id": packet.deviceId,
            "operator_id": packet.operatorId,
            "event_type": packet.eventType,
            "event_data": json.dumps(packet.data) if packet.data else "{}",
            "topic": topic,
            "received_at": datetime.now(timezone.utc)
        }
        
        try:
            self.db.insert_event(record)
            self.logger.debug("event_inserted", event_type=packet.eventType, device=packet.deviceId)
        except Exception as e:
            # Enfileirar offline
            self.offline_queue.enqueue(topic, raw_payload, time.time())
            self.logger.warning("event_queued_offline", error=str(e))
    
    def _flush_batch(self):
        """Faz flush do batch buffer para o banco."""
        if not self.batch_buffer:
            return
        
        batch = self.batch_buffer.copy()
        self.batch_buffer.clear()
        self.last_flush_time = time.time()
        
        try:
            inserted = self.db.insert_telemetry_batch(batch)
            self.stats["messages_inserted"] += inserted
            self.stats["batch_count"] += 1
        except Exception as e:
            # Enfileirar offline
            for record in batch:
                payload = record.get("raw_payload", "{}")
                topic = record.get("topic", "unknown")
                self.offline_queue.enqueue(topic, payload, time.time())
            self.stats["messages_failed"] += len(batch)
            self.logger.warning("batch_queued_offline", count=len(batch), error=str(e))
    
    def _process_offline_queue(self):
        """Processa a fila offline."""
        queue_size = self.offline_queue.size()
        if queue_size == 0:
            return
        
        self.logger.info("processing_offline_queue", size=queue_size)
        
        batch = self.offline_queue.dequeue_batch(self.config.batch_size)
        records = []
        
        for _, topic, payload, timestamp in batch:
            try:
                data = json.loads(payload)
                packet = TelemetryPacket(**data)
                
                # FASE 3: Inclui message_id para rastreabilidade
                record = {
                    "time": datetime.fromtimestamp(packet.timestamp / 1000, tz=timezone.utc),
                    "device_id": packet.deviceId,
                    "operator_id": packet.operatorId,
                    "message_id": packet.messageId,  # UUID do Android
                    "latitude": packet.gps.lat_value if packet.gps else None,
                    "longitude": packet.gps.lon_value if packet.gps else None,
                    "altitude": packet.gps.alt_value if packet.gps else None,
                    "speed": packet.gps.speed if packet.gps else None,
                    "bearing": packet.gps.bearing if packet.gps else None,
                    "gps_accuracy": packet.gps.accuracy if packet.gps else None,
                    "accel_x": packet.imu.accelX if packet.imu else None,
                    "accel_y": packet.imu.accelY if packet.imu else None,
                    "accel_z": packet.imu.accelZ if packet.imu else None,
                    "gyro_x": packet.imu.gyroX if packet.imu else None,
                    "gyro_y": packet.imu.gyroY if packet.imu else None,
                    "gyro_z": packet.imu.gyroZ if packet.imu else None,
                    "topic": topic,
                    "received_at": datetime.now(timezone.utc),
                    "raw_payload": payload
                }
                records.append(record)
            except Exception as e:
                self.logger.warning("offline_record_invalid", error=str(e))
        
        if records:
            try:
                self.db.insert_telemetry_batch(records)
                self.logger.info("offline_queue_processed", count=len(records))
            except Exception as e:
                # Re-enqueue
                for record in records:
                    self.offline_queue.enqueue(
                        record.get("topic", "unknown"),
                        record.get("raw_payload", "{}"),
                        time.time()
                    )
                self.logger.error("offline_requeue", error=str(e))
    
    def start(self):
        """Inicia o worker."""
        self.logger.info("starting_ingest_worker", 
                        mqtt_host=self.config.mqtt_host,
                        mqtt_topic=self.config.mqtt_topic)
        
        self._running = True
        
        # Conectar ao banco
        try:
            self.db.connect()
        except Exception as e:
            self.logger.error("database_init_failed", error=str(e))
            # Continuar mesmo sem banco (modo offline)
        
        # Conectar ao MQTT com sessão persistente
        try:
            # MQTTv5: clean_start=False para manter sessão e receber mensagens pendentes
            self.mqtt_client.connect(
                self.config.mqtt_host,
                self.config.mqtt_port,
                keepalive=self.config.mqtt_keepalive,
                clean_start=False  # Sessão persistente
            )
        except Exception as e:
            self.logger.error("mqtt_connect_failed", error=str(e))
            raise
        
        # Loop principal em thread separada
        self.mqtt_client.loop_start()
        
        self.logger.info("ingest_worker_started")
    
    def run_maintenance_loop(self):
        """Loop de manutenção (flush, offline queue, purge)."""
        while self._running:
            try:
                # Flush batch pendente
                self._flush_batch()
                
                # Processar fila offline se banco disponível
                if self.db.is_connected():
                    self._process_offline_queue()
                
                # Purge de mensagens antigas
                self.offline_queue.purge_old(48)
                
                # Aguardar
                time.sleep(5)
                
            except Exception as e:
                self.logger.error("maintenance_error", error=str(e))
                time.sleep(10)
    
    def stop(self):
        """Para o worker."""
        self.logger.info("stopping_ingest_worker")
        self._running = False
        
        # Flush final
        self._flush_batch()
        
        # Desconectar MQTT
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        
        # Fechar banco
        self.db.close()
        
        self.logger.info("ingest_worker_stopped", stats=self.stats)
    
    def get_stats(self) -> dict:
        """Retorna estatísticas atuais."""
        uptime = time.time() - self.stats["start_time"]
        return {
            **self.stats,
            "uptime_seconds": uptime,
            "messages_per_second": self.stats["messages_received"] / max(uptime, 1),
            "mqtt_connected": self.mqtt_connected,
            "db_connected": self.db.is_connected(),
            "offline_queue_size": self.offline_queue.size(),
            "batch_buffer_size": len(self.batch_buffer)
        }


# ============================================================
# HEALTH CHECK API + REST API
# ============================================================

from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime, timedelta

def create_health_app(worker: IngestWorker) -> FastAPI:
    """Cria app FastAPI para health check e REST API."""
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
    
    app = FastAPI(
        title="AuraTracking API",
        description="API para telemetria em tempo real e histórico",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORS para frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Em produção, especificar domínios
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # ========== Health Endpoints ==========
    
    @app.get("/health")
    async def health():
        stats = worker.get_stats()
        healthy = stats["mqtt_connected"] and stats["db_connected"]
        return {
            "status": "healthy" if healthy else "degraded",
            "mqtt_connected": stats["mqtt_connected"],
            "db_connected": stats["db_connected"],
            "uptime_seconds": stats["uptime_seconds"],
            "messages_received": stats["messages_received"],
            "messages_inserted": stats["messages_inserted"],
            "offline_queue_size": stats["offline_queue_size"]
        }
    
    @app.get("/stats")
    async def stats():
        return worker.get_stats()
    
    @app.get("/ready")
    async def ready():
        if worker.mqtt_connected:
            return {"status": "ready"}
        return {"status": "not_ready"}, 503
    
    # ========== REST API Endpoints ==========
    
    @app.get("/api/devices")
    async def get_devices():
        """Lista todos os dispositivos com última posição."""
        try:
            conn = worker.db.get_connection()
            if not conn:
                return {"error": "Database not connected"}, 503
            
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    device_id,
                    operator_id,
                    MAX(time) as last_seen,
                    (SELECT latitude FROM telemetry t2 
                     WHERE t2.device_id = t.device_id 
                     ORDER BY time DESC LIMIT 1) as latitude,
                    (SELECT longitude FROM telemetry t2 
                     WHERE t2.device_id = t.device_id 
                     ORDER BY time DESC LIMIT 1) as longitude,
                    (SELECT speed_kmh FROM telemetry t2 
                     WHERE t2.device_id = t.device_id 
                     ORDER BY time DESC LIMIT 1) as speed_kmh,
                    COUNT(*) as total_points
                FROM telemetry t
                WHERE time > NOW() - INTERVAL '24 hours'
                GROUP BY device_id, operator_id
                ORDER BY last_seen DESC
            """)
            
            devices = []
            for row in cursor.fetchall():
                devices.append({
                    "device_id": row[0],
                    "operator_id": row[1],
                    "last_seen": row[2].isoformat() if row[2] else None,
                    "latitude": float(row[3]) if row[3] else None,
                    "longitude": float(row[4]) if row[4] else None,
                    "speed_kmh": float(row[5]) if row[5] else None,
                    "total_points_24h": row[6],
                    "status": "online" if row[2] and (datetime.now(timezone.utc) - row[2]).seconds < 60 else "offline"
                })
            
            cursor.close()
            return {"devices": devices, "count": len(devices)}
            
        except Exception as e:
            return {"error": str(e)}, 500
    
    @app.get("/api/telemetry")
    async def get_telemetry(
        device_id: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 3600,
        granularity: str = "raw"
    ):
        """
        Busca telemetria histórica.
        
        Args:
            device_id: ID do dispositivo
            start: Data/hora início (ISO format)
            end: Data/hora fim (ISO format)
            limit: Máximo de registros (default 3600 = 1h @ 1Hz)
            granularity: raw | 1min | 1hour
        """
        try:
            conn = worker.db.get_connection()
            if not conn:
                return {"error": "Database not connected"}, 503
            
            # Parse dates
            if start:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            else:
                start_dt = datetime.now(timezone.utc) - timedelta(hours=1)
            
            if end:
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            else:
                end_dt = datetime.now(timezone.utc)
            
            cursor = conn.cursor()
            
            if granularity == "raw":
                cursor.execute("""
                    SELECT 
                        time, device_id, operator_id,
                        latitude, longitude, altitude,
                        speed, speed_kmh, bearing, gps_accuracy,
                        accel_x, accel_y, accel_z, accel_magnitude
                    FROM telemetry
                    WHERE device_id = %s AND time >= %s AND time <= %s
                    ORDER BY time ASC
                    LIMIT %s
                """, (device_id, start_dt, end_dt, limit))
                
            elif granularity == "1min":
                cursor.execute("""
                    SELECT 
                        bucket, device_id,
                        sample_count,
                        avg_speed_kmh, max_speed_kmh,
                        avg_accel_magnitude, max_accel_magnitude,
                        first_lat, first_lon, last_lat, last_lon
                    FROM telemetry_1min
                    WHERE device_id = %s AND bucket >= %s AND bucket <= %s
                    ORDER BY bucket ASC
                    LIMIT %s
                """, (device_id, start_dt, end_dt, limit))
                
            elif granularity == "1hour":
                cursor.execute("""
                    SELECT 
                        bucket, device_id, operator_id,
                        sample_count,
                        avg_speed_kmh, max_speed_kmh,
                        avg_accel_magnitude, max_accel_magnitude,
                        distance_km
                    FROM telemetry_1hour
                    WHERE device_id = %s AND bucket >= %s AND bucket <= %s
                    ORDER BY bucket ASC
                    LIMIT %s
                """, (device_id, start_dt, end_dt, limit))
            
            columns = [desc[0] for desc in cursor.description]
            rows = []
            for row in cursor.fetchall():
                row_dict = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    if isinstance(val, datetime):
                        row_dict[col] = val.isoformat()
                    elif val is not None:
                        row_dict[col] = float(val) if isinstance(val, (int, float)) else val
                    else:
                        row_dict[col] = None
                rows.append(row_dict)
            
            cursor.close()
            return {
                "device_id": device_id,
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "granularity": granularity,
                "count": len(rows),
                "data": rows
            }
            
        except Exception as e:
            return {"error": str(e)}, 500
    
    @app.get("/api/events")
    async def get_events(
        device_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 100
    ):
        """Busca eventos (alertas, impactos, etc)."""
        try:
            conn = worker.db.get_connection()
            if not conn:
                return {"error": "Database not connected"}, 503
            
            if start:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            else:
                start_dt = datetime.now(timezone.utc) - timedelta(hours=24)
            
            if end:
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            else:
                end_dt = datetime.now(timezone.utc)
            
            cursor = conn.cursor()
            
            query = """
                SELECT time, device_id, operator_id, event_type, severity, data
                FROM events
                WHERE time >= %s AND time <= %s
            """
            params = [start_dt, end_dt]
            
            if device_id:
                query += " AND device_id = %s"
                params.append(device_id)
            
            if event_type:
                query += " AND event_type = %s"
                params.append(event_type)
            
            query += " ORDER BY time DESC LIMIT %s"
            params.append(limit)
            
            cursor.execute(query, params)
            
            events = []
            for row in cursor.fetchall():
                events.append({
                    "time": row[0].isoformat() if row[0] else None,
                    "device_id": row[1],
                    "operator_id": row[2],
                    "event_type": row[3],
                    "severity": row[4],
                    "data": row[5]
                })
            
            cursor.close()
            return {"events": events, "count": len(events)}
            
        except Exception as e:
            return {"error": str(e)}, 500
    
    @app.get("/api/summary")
    async def get_summary(hours: int = 24):
        """Resumo geral do sistema."""
        try:
            conn = worker.db.get_connection()
            if not conn:
                return {"error": "Database not connected"}, 503
            
            cursor = conn.cursor()
            
            # Dispositivos ativos
            cursor.execute("""
                SELECT COUNT(DISTINCT device_id)
                FROM telemetry
                WHERE time > NOW() - INTERVAL '5 minutes'
            """)
            active_devices = cursor.fetchone()[0]
            
            # Total de telemetrias no período
            cursor.execute("""
                SELECT COUNT(*)
                FROM telemetry
                WHERE time > NOW() - INTERVAL '%s hours'
            """, (hours,))
            total_telemetries = cursor.fetchone()[0]
            
            # Velocidade média e máxima
            cursor.execute("""
                SELECT AVG(speed_kmh), MAX(speed_kmh)
                FROM telemetry
                WHERE time > NOW() - INTERVAL '%s hours'
                AND speed_kmh IS NOT NULL
            """, (hours,))
            row = cursor.fetchone()
            avg_speed = float(row[0]) if row[0] else 0
            max_speed = float(row[1]) if row[1] else 0
            
            # Aceleração máxima
            cursor.execute("""
                SELECT MAX(accel_magnitude)
                FROM telemetry
                WHERE time > NOW() - INTERVAL '%s hours'
                AND accel_magnitude IS NOT NULL
            """, (hours,))
            max_accel = float(cursor.fetchone()[0] or 0)
            
            # Eventos por severidade (se tabela existir)
            events_by_severity = {}
            try:
                cursor.execute("""
                    SELECT event_type, COUNT(*)
                    FROM events
                    WHERE time > NOW() - INTERVAL '%s hours'
                    GROUP BY event_type
                """, (hours,))
                events_by_severity = {row[0]: row[1] for row in cursor.fetchall()}
            except Exception:
                pass  # Tabela events pode não existir
            
            cursor.close()
            
            return {
                "period_hours": hours,
                "active_devices": active_devices,
                "total_telemetries": total_telemetries,
                "avg_speed_kmh": round(avg_speed, 1),
                "max_speed_kmh": round(max_speed, 1),
                "max_acceleration": round(max_accel, 2),
                "events": events_by_severity,
                "ingest_stats": worker.get_stats()
            }
            
        except Exception as e:
            return {"error": str(e)}, 500
    
    return app


# ============================================================
# MAIN
# ============================================================

def main():
    """Função principal."""
    
    # Carregar configuração
    config = Config()
    
    # Setup logging
    setup_logging(config)
    logger = structlog.get_logger("main")
    
    logger.info("==============================================")
    logger.info("  AuraTracking Ingest Worker v1.0.0")
    logger.info("==============================================")
    logger.info("config", 
               mqtt_host=config.mqtt_host,
               mqtt_topic=config.mqtt_topic,
               db_host=config.db_host,
               batch_size=config.batch_size)
    
    # Criar worker
    worker = IngestWorker(config)
    
    # Criar health app
    health_app = create_health_app(worker)
    
    # Handler de shutdown
    def signal_handler(signum, frame):
        logger.info("shutdown_signal_received", signal=signum)
        worker.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Iniciar worker
    worker.start()
    
    # Iniciar thread de manutenção
    maintenance_thread = Thread(target=worker.run_maintenance_loop, daemon=True)
    maintenance_thread.start()
    
    # Rodar health server (blocking)
    logger.info("starting_health_server", port=config.health_port)
    uvicorn.run(
        health_app,
        host="0.0.0.0",
        port=config.health_port,
        log_level="warning"
    )


if __name__ == "__main__":
    main()
