package com.aura.tracking.sensors.imu

import kotlinx.serialization.Serializable

/**
 * Modelo de dados para sensores IMU (acelerômetro + giroscópio)
 */
@Serializable
data class ImuData(
    val accelX: Float,          // m/s²
    val accelY: Float,          // m/s²
    val accelZ: Float,          // m/s²
    val gyroX: Float,           // rad/s
    val gyroY: Float,           // rad/s
    val gyroZ: Float,           // rad/s
    val timestamp: Long = System.currentTimeMillis(),
    // Magnetômetro (opcional)
    val magX: Float? = null,   // μT
    val magY: Float? = null,   // μT
    val magZ: Float? = null,   // μT
    // Aceleração Linear (opcional)
    val linearAccelX: Float? = null,  // m/s² (sem gravidade)
    val linearAccelY: Float? = null,  // m/s² (sem gravidade)
    val linearAccelZ: Float? = null,  // m/s² (sem gravidade)
    // Gravidade Isolada (opcional)
    val gravityX: Float? = null,  // m/s²
    val gravityY: Float? = null,  // m/s²
    val gravityZ: Float? = null,  // m/s²
    // Rotação Vetorial - Quaternion (opcional)
    val rotationVectorX: Float? = null,  // Quaternion component X
    val rotationVectorY: Float? = null,  // Quaternion component Y
    val rotationVectorZ: Float? = null,  // Quaternion component Z
    val rotationVectorW: Float? = null   // Quaternion component W
) {
    /**
     * Magnitude da aceleração total
     */
    val accelMagnitude: Float
        get() = kotlin.math.sqrt(accelX * accelX + accelY * accelY + accelZ * accelZ)
    
    /**
     * Magnitude da rotação total
     */
    val gyroMagnitude: Float
        get() = kotlin.math.sqrt(gyroX * gyroX + gyroY * gyroY + gyroZ * gyroZ)
    
    /**
     * Magnitude do campo magnético (quando disponível)
     */
    val magMagnitude: Float?
        get() = if (magX != null && magY != null && magZ != null) {
            kotlin.math.sqrt(magX * magX + magY * magY + magZ * magZ)
        } else null
    
    /**
     * Magnitude da aceleração linear (quando disponível)
     */
    val linearAccelMagnitude: Float?
        get() = if (linearAccelX != null && linearAccelY != null && linearAccelZ != null) {
            kotlin.math.sqrt(linearAccelX * linearAccelX + linearAccelY * linearAccelY + linearAccelZ * linearAccelZ)
        } else null
    
    companion object {
        val EMPTY = ImuData(0f, 0f, 0f, 0f, 0f, 0f)
    }
}
