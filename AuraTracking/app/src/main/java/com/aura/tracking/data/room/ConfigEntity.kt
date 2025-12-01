package com.aura.tracking.data.room

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Entity representing the application configuration stored locally.
 * Includes MQTT settings and selected fleet/equipment.
 */
@Entity(tableName = "config")
data class ConfigEntity(
    @PrimaryKey
    @ColumnInfo(name = "id")
    val id: Int = 1, // Singleton row

    @ColumnInfo(name = "mqtt_host")
    val mqttHost: String = "localhost",

    @ColumnInfo(name = "mqtt_port")
    val mqttPort: Int = 1883,

    @ColumnInfo(name = "mqtt_topic")
    val mqttTopic: String = "aura/tracking",

    @ColumnInfo(name = "fleet_id")
    val fleetId: String? = null,

    @ColumnInfo(name = "fleet_name")
    val fleetName: String? = null,

    @ColumnInfo(name = "equipment_id")
    val equipmentId: String? = null,

    @ColumnInfo(name = "equipment_name")
    val equipmentName: String? = null,

    @ColumnInfo(name = "device_id")
    val deviceId: String = android.os.Build.MODEL,

    @ColumnInfo(name = "operator_id")
    val operatorId: String? = null,

    @ColumnInfo(name = "gps_interval_ms")
    val gpsIntervalMs: Long = 1000L, // 1 second = 1Hz

    @ColumnInfo(name = "imu_enabled")
    val imuEnabled: Boolean = true,

    /**
     * FASE 3 - BOOT RECOVERY:
     * Flag que indica se o tracking estava ativo quando o app foi fechado/crashed.
     * Usado pelo BootCompletedReceiver para decidir se deve reiniciar o serviço após reboot.
     * 
     * - true: TrackingForegroundService estava rodando → reiniciar após boot
     * - false: Tracking estava parado → não reiniciar
     */
    @ColumnInfo(name = "tracking_enabled", defaultValue = "0")
    val trackingEnabled: Boolean = false,

    @ColumnInfo(name = "created_at")
    val createdAt: Long = System.currentTimeMillis(),

    @ColumnInfo(name = "updated_at")
    val updatedAt: Long = System.currentTimeMillis()
)
