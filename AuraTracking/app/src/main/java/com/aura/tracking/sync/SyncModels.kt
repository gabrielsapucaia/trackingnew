package com.aura.tracking.sync

import kotlinx.serialization.Serializable

/**
 * Payload para eventos de geofencing enviados via MQTT.
 * Movido de GeofenceEventFlushWorker (deprecado).
 */
@Serializable
data class GeofenceEventPayload(
    val eventId: String,
    val zoneId: Long,
    val zoneName: String,
    val zoneType: String,
    val eventType: String,
    val durationSeconds: Int,
    val latitude: Double,
    val longitude: Double,
    val gpsAccuracy: Float,
    val speed: Float,
    val deviceId: String,
    val operatorId: String,
    val timestamp: Long
)
