package com.aura.tracking.data.room

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import java.util.UUID

/**
 * Entity para fila de telemetria offline.
 * Armazena pacotes de telemetria quando MQTT está desconectado.
 * 
 * FASE 3 - QUEUE 30 DIAS:
 * - messageId: UUID globalmente único para idempotência e deduplicação server-side
 * - Índice em createdAt: acelera queries ORDER BY e purge (crítico para 3M registros)
 * - Capacidade: até 3.000.000 registros (~1.2 GB)
 * - TTL: 30 dias (720 horas)
 */
@Entity(
    tableName = "telemetry_queue",
    indices = [
        Index(name = "idx_queue_created_at", value = ["createdAt"])
    ]
)
data class TelemetryQueueEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    
    /**
     * UUID globalmente único para esta mensagem.
     * Usado para:
     * - Deduplicação no servidor (ON CONFLICT message_id DO NOTHING)
     * - Correlação entre queue Android e banco TimescaleDB
     * - Garantia de idempotência em retries e crashes
     */
    @ColumnInfo(name = "message_id")
    val messageId: String = UUID.randomUUID().toString(),
    
    /** Tópico MQTT destino */
    val topic: String,
    
    /** Payload JSON do pacote de telemetria */
    val payload: String,
    
    /** Timestamp de criação (millis) - INDEXADO para queries eficientes */
    val createdAt: Long = System.currentTimeMillis(),
    
    /** Número de tentativas de envio */
    val retryCount: Int = 0,
    
    /** QoS desejado para o envio */
    val qos: Int = 1
)
