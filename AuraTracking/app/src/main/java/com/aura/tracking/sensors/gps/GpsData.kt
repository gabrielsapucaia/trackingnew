package com.aura.tracking.sensors.gps

import kotlinx.serialization.Serializable

/**
 * Modelo de dados para localização GPS
 */
@Serializable
data class GpsData(
    val latitude: Double,
    val longitude: Double,
    val altitude: Double,
    val speed: Float,           // m/s
    val bearing: Float,         // graus (0-360)
    val accuracy: Float,        // metros
    val timestamp: Long = System.currentTimeMillis()
) {
    val isValid: Boolean
        get() = latitude != 0.0 && longitude != 0.0 && accuracy < 100
    
    val speedKmh: Float
        get() = speed * 3.6f
}
