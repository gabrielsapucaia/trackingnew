package com.aura.tracking.sensors.motion

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import com.aura.tracking.logging.AuraLog
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * MotionDetectorProvider - Detecta eventos de movimento usando sensores one-shot.
 * Emite eventos apenas quando detectados (não a 1Hz).
 */
class MotionDetectorProvider(private val context: Context) : SensorEventListener {

    companion object {
        private const val TAG = "MotionDetectorProvider"
    }

    private val sensorManager: SensorManager by lazy {
        context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    }

    private var significantMotionSensor: Sensor? = null
    private var stationaryDetectSensor: Sensor? = null
    private var motionDetectSensor: Sensor? = null
    private var isRunning = false

    // Estado atual de detecção
    private var lastSignificantMotion: Boolean = false
    private var lastStationaryDetect: Boolean = false
    private var lastMotionDetect: Boolean = false

    // Estado reativo do último dado de detecção
    private val _lastMotionData = kotlinx.coroutines.flow.MutableStateFlow<MotionDetectionData?>(null)
    val lastMotionData: kotlinx.coroutines.flow.StateFlow<MotionDetectionData?> = _lastMotionData.asStateFlow()

    // Listeners
    var onMotionDetected: ((MotionDetectionData) -> Unit)? = null

    init {
        significantMotionSensor = sensorManager.getDefaultSensor(Sensor.TYPE_SIGNIFICANT_MOTION)
        stationaryDetectSensor = sensorManager.getDefaultSensor(Sensor.TYPE_STATIONARY_DETECT)
        motionDetectSensor = sensorManager.getDefaultSensor(Sensor.TYPE_MOTION_DETECT)

        if (significantMotionSensor == null) {
            AuraLog.IMU.d("Significant Motion sensor not available")
        }
        if (stationaryDetectSensor == null) {
            AuraLog.IMU.d("Stationary Detect sensor not available")
        }
        if (motionDetectSensor == null) {
            AuraLog.IMU.d("Motion Detect sensor not available")
        }
    }

    /**
     * Start motion detection.
     */
    fun startMotionDetection() {
        if (isRunning) {
            AuraLog.IMU.d("Motion detection already running")
            return
        }

        AuraLog.IMU.i("Starting motion detection")

        // Registra sensores one-shot
        significantMotionSensor?.let { sensor ->
            sensorManager.registerListener(this, sensor, SensorManager.SENSOR_DELAY_NORMAL)
        }

        stationaryDetectSensor?.let { sensor ->
            sensorManager.registerListener(this, sensor, SensorManager.SENSOR_DELAY_NORMAL)
        }

        motionDetectSensor?.let { sensor ->
            sensorManager.registerListener(this, sensor, SensorManager.SENSOR_DELAY_NORMAL)
        }

        isRunning = true
    }

    /**
     * Stop motion detection.
     */
    fun stopMotionDetection() {
        if (!isRunning) {
            AuraLog.IMU.d("Motion detection not running")
            return
        }

        AuraLog.IMU.i("Stopping motion detection")

        sensorManager.unregisterListener(this)
        isRunning = false
    }

    override fun onSensorChanged(event: SensorEvent) {
        when (event.sensor.type) {
            Sensor.TYPE_SIGNIFICANT_MOTION -> {
                val detected = event.values[0] > 0
                if (detected != lastSignificantMotion) {
                    lastSignificantMotion = detected
                    emitMotionData(
                        significantMotion = detected
                    )
                    AuraLog.IMU.d("Significant Motion detected: $detected")
                }
            }
            Sensor.TYPE_STATIONARY_DETECT -> {
                val detected = event.values[0] > 0
                if (detected != lastStationaryDetect) {
                    lastStationaryDetect = detected
                    emitMotionData(
                        stationaryDetect = detected
                    )
                    AuraLog.IMU.d("Stationary Detect: $detected")
                }
            }
            Sensor.TYPE_MOTION_DETECT -> {
                val detected = event.values[0] > 0
                if (detected != lastMotionDetect) {
                    lastMotionDetect = detected
                    emitMotionData(
                        motionDetect = detected
                    )
                    AuraLog.IMU.d("Motion Detect: $detected")
                }
            }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor, accuracy: Int) {
        AuraLog.IMU.d("Sensor accuracy changed: ${sensor.name} -> $accuracy")
    }

    /**
     * Emite dados de detecção de movimento.
     */
    private fun emitMotionData(
        significantMotion: Boolean? = null,
        stationaryDetect: Boolean? = null,
        motionDetect: Boolean? = null,
        flatUp: Boolean? = null,
        flatDown: Boolean? = null,
        stowed: Boolean? = null,
        displayRotate: Int? = null
    ) {
        val motionData = MotionDetectionData(
            significantMotion = significantMotion ?: lastSignificantMotion.takeIf { it },
            stationaryDetect = stationaryDetect ?: lastStationaryDetect.takeIf { it },
            motionDetect = motionDetect ?: lastMotionDetect.takeIf { it },
            flatUp = flatUp,
            flatDown = flatDown,
            stowed = stowed,
            displayRotate = displayRotate
        )

        _lastMotionData.value = motionData
        onMotionDetected?.invoke(motionData)
    }

    fun isRunning(): Boolean = isRunning
}

