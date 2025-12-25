package com.aura.tracking.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Data class representing an Operator from Supabase.
 * Matches the 'operators' table in Supabase.
 */
@Serializable
data class Operator(
    @SerialName("id")
    val id: Long,

    @SerialName("name")
    val name: String,

    @SerialName("registration")
    val registration: String,

    @SerialName("pin")
    val pin: String,

    @SerialName("status")
    val status: String = "active",

    @SerialName("created_at")
    val createdAt: String? = null,

    @SerialName("updated_at")
    val updatedAt: String? = null
)

/**
 * Data class representing an Equipment Type from Supabase.
 * Matches the 'equipment_types' table in Supabase.
 */
@Serializable
data class EquipmentType(
    @SerialName("id")
    val id: Long,

    @SerialName("name")
    val name: String,

    @SerialName("description")
    val description: String? = null,

    @SerialName("seq_id")
    val seqId: Long? = null,

    @SerialName("status")
    val status: String = "active",

    @SerialName("created_at")
    val createdAt: String? = null,

    @SerialName("updated_at")
    val updatedAt: String? = null
)

/**
 * Data class representing an Equipment from Supabase.
 * Matches the 'equipment' table in Supabase.
 */
@Serializable
data class Equipment(
    @SerialName("id")
    val id: Long,

    @SerialName("tag")
    val tag: String,

    @SerialName("type_id")
    val typeId: Long? = null,

    @SerialName("status")
    val status: String = "active",

    @SerialName("location")
    val location: String? = null,

    @SerialName("fleet")
    val fleet: String? = null,

    @SerialName("created_at")
    val createdAt: String? = null,

    @SerialName("updated_at")
    val updatedAt: String? = null
)

/**
 * Data class representing a Fleet (derived from equipment.fleet field).
 */
@Serializable
data class Fleet(
    val name: String,
    val equipmentCount: Int = 0
)

/**
 * Login request payload.
 */
@Serializable
data class LoginRequest(
    @SerialName("registration")
    val registration: String,

    @SerialName("pin")
    val pin: String
)

/**
 * Data class representing a Geofence zone from Supabase.
 * Matches the 'geofence' table in Supabase.
 */
@Serializable
data class Geofence(
    @SerialName("id")
    val id: Long,

    @SerialName("name")
    val name: String,

    @SerialName("zone_type")
    val zoneType: String,

    @SerialName("area_m2")
    val areaM2: Float? = null,

    @SerialName("polygon_json")
    val polygonJson: String,

    @SerialName("color")
    val color: String = "#4CAF50",

    @SerialName("is_active")
    val isActive: Boolean = true,

    @SerialName("created_at")
    val createdAt: String? = null,

    @SerialName("updated_at")
    val updatedAt: String? = null
)

/**
 * Telemetry data point for GPS + IMU.
 */
@Serializable
data class TelemetryData(
    @SerialName("timestamp")
    val timestamp: Long,

    @SerialName("latitude")
    val latitude: Double,

    @SerialName("longitude")
    val longitude: Double,

    @SerialName("altitude")
    val altitude: Double? = null,

    @SerialName("speed")
    val speed: Float? = null,

    @SerialName("bearing")
    val bearing: Float? = null,

    @SerialName("accuracy")
    val accuracy: Float? = null,

    @SerialName("accel_x")
    val accelX: Float? = null,

    @SerialName("accel_y")
    val accelY: Float? = null,

    @SerialName("accel_z")
    val accelZ: Float? = null,

    @SerialName("gyro_x")
    val gyroX: Float? = null,

    @SerialName("gyro_y")
    val gyroY: Float? = null,

    @SerialName("gyro_z")
    val gyroZ: Float? = null,

    @SerialName("equipment_id")
    val equipmentId: Long,

    @SerialName("operator_id")
    val operatorId: Long
)
