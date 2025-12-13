package com.aura.tracking.sensors.motion

import kotlinx.serialization.Serializable

/**
 * Modelo de dados para detecção de movimento (sensores one-shot)
 */
@Serializable
data class MotionDetectionData(
    val significantMotion: Boolean? = null,  // one-shot event
    val stationaryDetect: Boolean? = null,  // one-shot event
    val motionDetect: Boolean? = null,       // one-shot event
    val flatUp: Boolean? = null,             // Motorola específico
    val flatDown: Boolean? = null,           // Motorola específico
    val stowed: Boolean? = null,             // Motorola específico
    val displayRotate: Int? = null,          // Motorola específico (0, 90, 180, 270)
    val timestamp: Long = System.currentTimeMillis()
)

