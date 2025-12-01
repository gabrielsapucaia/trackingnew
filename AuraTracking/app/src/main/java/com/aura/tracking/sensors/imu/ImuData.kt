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
    val timestamp: Long = System.currentTimeMillis()
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
    
    companion object {
        val EMPTY = ImuData(0f, 0f, 0f, 0f, 0f, 0f)
    }
}
