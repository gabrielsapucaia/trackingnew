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
    val timestamp: Long = System.currentTimeMillis(),
    // Metadados de temporalidade
    val ageMs: Long = 0L,                   // Idade do fix no momento do aceite
    val intervalSinceLastFixMs: Long = 0L,  // Delta desde o último fix aceito
    val temporalQuality: String = "normal",  // normal | stale_fallback | stale_cadence
    // Dados detalhados (opcionais)
    val satellites: Int? = null,            // Número de satélites GPS usados
    val hAcc: Float? = null,                 // Horizontal accuracy (metros)
    val vAcc: Float? = null,                 // Vertical accuracy (metros)
    val sAcc: Float? = null,                 // Speed accuracy (m/s)
    val hdop: Float? = null,                 // Horizontal Dilution of Precision
    val vdop: Float? = null,                 // Vertical Dilution of Precision
    val pdop: Float? = null,                 // Position Dilution of Precision
    val gpsTimestamp: Long? = null           // Timestamp do fix GPS (não do app)
) {
    val isValid: Boolean
        get() = latitude != 0.0 && longitude != 0.0 && accuracy < 100
    
    val speedKmh: Float
        get() = speed * 3.6f
}
