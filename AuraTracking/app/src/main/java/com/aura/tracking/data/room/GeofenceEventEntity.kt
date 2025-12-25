package com.aura.tracking.data.room

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import java.util.UUID

/**
 * GeofenceEventEntity - Evento de geofencing (entrada/saída de zona).
 *
 * Registra eventos localmente para:
 * - Envio via MQTT quando online
 * - Queue offline quando sem conexão
 * - Analytics e histórico local
 */
@Entity(
    tableName = "geofence_events",
    indices = [
        Index(name = "idx_geofence_timestamp", value = ["timestamp"]),
        Index(name = "idx_geofence_zone", value = ["zoneId"]),
        Index(name = "idx_geofence_sent", value = ["sent"])
    ]
)
data class GeofenceEventEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,

    /**
     * UUID único para deduplicação server-side
     */
    @ColumnInfo(name = "eventId")
    val eventId: String = UUID.randomUUID().toString(),

    /**
     * ID da zona relacionada
     */
    @ColumnInfo(name = "zoneId")
    val zoneId: Long,

    /**
     * Nome da zona (cache para exibição offline)
     */
    @ColumnInfo(name = "zoneName")
    val zoneName: String,

    /**
     * Tipo da zona (loading_zone, unloading_zone, etc.)
     */
    @ColumnInfo(name = "zoneType")
    val zoneType: String,

    /**
     * Tipo do evento:
     * - enter: Entrada na zona
     * - exit: Saída da zona
     * - dwell: Permanência na zona (gerado no exit com duração)
     */
    @ColumnInfo(name = "eventType")
    val eventType: String,

    /**
     * Duração em segundos (apenas para eventos de saída/dwell)
     */
    @ColumnInfo(name = "durationSeconds")
    val durationSeconds: Int = 0,

    /**
     * Coordenadas do evento
     */
    val latitude: Double,
    val longitude: Double,

    /**
     * Precisão GPS no momento do evento (metros)
     */
    @ColumnInfo(name = "gpsAccuracy")
    val gpsAccuracy: Float,

    /**
     * Velocidade no momento do evento (m/s)
     */
    val speed: Float = 0f,

    /**
     * ID do dispositivo/equipamento
     */
    @ColumnInfo(name = "deviceId")
    val deviceId: String,

    /**
     * Matrícula do operador
     */
    @ColumnInfo(name = "operatorId")
    val operatorId: String,

    /**
     * Timestamp do evento (Unix millis)
     */
    val timestamp: Long = System.currentTimeMillis(),

    /**
     * Se o evento foi enviado via MQTT
     */
    val sent: Boolean = false,

    /**
     * Timestamp de quando foi enviado
     */
    @ColumnInfo(name = "sentAt")
    val sentAt: Long? = null,

    /**
     * Número de tentativas de envio
     */
    @ColumnInfo(name = "retryCount")
    val retryCount: Int = 0
)

/**
 * Tipos de eventos de geofencing
 */
object GeofenceEventType {
    const val ENTER = "enter"
    const val EXIT = "exit"
    const val DWELL = "dwell"
}
