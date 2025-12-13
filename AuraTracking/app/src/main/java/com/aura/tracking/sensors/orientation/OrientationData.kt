package com.aura.tracking.sensors.orientation

import kotlinx.serialization.Serializable

/**
 * Modelo de dados para orientação do dispositivo
 */
@Serializable
data class OrientationData(
    val azimuth: Float,      // 0-360° - direção do movimento
    val pitch: Float,         // -180° a +180° - inclinação frontal
    val roll: Float,          // -90° a +90° - inclinação lateral
    val timestamp: Long = System.currentTimeMillis(),
    val rotationMatrix: FloatArray? = null  // Matriz 3x3 (opcional)
) {
    companion object {
        val EMPTY = OrientationData(0f, 0f, 0f)
    }
}

