package com.aura.tracking.sensors.orientation

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Handler
import android.os.HandlerThread
import com.aura.tracking.logging.AuraLog
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlin.math.atan2
import kotlin.math.sqrt

/**
 * OrientationProvider - Calcula orientação (azimuth, pitch, roll) usando acelerômetro + magnetômetro.
 * Emite orientação a 1Hz.
 */
class OrientationProvider(private val context: Context) : SensorEventListener {

    companion object {
        private const val TAG = "OrientationProvider"
        private const val SENSOR_DELAY = SensorManager.SENSOR_DELAY_FASTEST
        private const val OUTPUT_INTERVAL_MS = 1000L // 1Hz
    }

    private val sensorManager: SensorManager by lazy {
        context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    }

    private var accelerometer: Sensor? = null
    private var magnetometer: Sensor? = null
    private var isRunning = false

    // Buffers para média
    private val accelBuffer = mutableListOf<FloatArray>()
    private val magBuffer = mutableListOf<FloatArray>()
    private val bufferLock = Any()

    // Handler para output a 1Hz
    private var handlerThread: HandlerThread? = null
    private var handler: Handler? = null
    private var outputRunnable: Runnable? = null

    // Estado reativo do último dado de orientação
    private val _lastOrientationData = kotlinx.coroutines.flow.MutableStateFlow<OrientationData?>(null)
    val lastOrientationData: kotlinx.coroutines.flow.StateFlow<OrientationData?> = _lastOrientationData.asStateFlow()

    // Listeners
    var onOrientationDataUpdate: ((OrientationData) -> Unit)? = null

    init {
        accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        magnetometer = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD)

        if (accelerometer == null) {
            AuraLog.IMU.w("Accelerometer not available for orientation calculation")
        }
        if (magnetometer == null) {
            AuraLog.IMU.w("Magnetometer not available for orientation calculation - azimuth will be inaccurate")
        }
    }

    /**
     * Start receiving orientation updates at 1Hz.
     */
    fun startOrientationUpdates() {
        if (isRunning) {
            AuraLog.IMU.d("Orientation updates already running")
            return
        }

        AuraLog.IMU.i("Starting orientation updates at 1Hz")

        // Registra sensores
        accelerometer?.let { sensor ->
            sensorManager.registerListener(this, sensor, SENSOR_DELAY)
        }

        magnetometer?.let { sensor ->
            sensorManager.registerListener(this, sensor, SENSOR_DELAY)
        }

        // Inicia thread para output a 1Hz
        handlerThread = HandlerThread("OrientationOutputThread").apply { start() }
        handler = Handler(handlerThread!!.looper)

        outputRunnable = object : Runnable {
            override fun run() {
                emitOrientationData()
                handler?.postDelayed(this, OUTPUT_INTERVAL_MS)
            }
        }

        handler?.postDelayed(outputRunnable!!, OUTPUT_INTERVAL_MS)
        isRunning = true
    }

    /**
     * Stop receiving orientation updates.
     */
    fun stopOrientationUpdates() {
        if (!isRunning) {
            AuraLog.IMU.d("Orientation updates not running")
            return
        }

        AuraLog.IMU.i("Stopping orientation updates")

        outputRunnable?.let { handler?.removeCallbacks(it) }
        handlerThread?.quitSafely()
        handlerThread = null
        handler = null
        outputRunnable = null

        sensorManager.unregisterListener(this)

        synchronized(bufferLock) {
            accelBuffer.clear()
            magBuffer.clear()
        }

        isRunning = false
    }

    override fun onSensorChanged(event: SensorEvent) {
        synchronized(bufferLock) {
            when (event.sensor.type) {
                Sensor.TYPE_ACCELEROMETER -> {
                    accelBuffer.add(event.values.copyOf())
                }
                Sensor.TYPE_MAGNETIC_FIELD -> {
                    magBuffer.add(event.values.copyOf())
                }
                else -> {
                    // Outros tipos de sensores não são usados aqui
                }
            }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor, accuracy: Int) {
        AuraLog.IMU.d("Sensor accuracy changed: ${sensor.name} -> $accuracy")
    }

    /**
     * Emite dados de orientação a 1Hz.
     */
    private fun emitOrientationData() {
        val orientationData: OrientationData

        synchronized(bufferLock) {
            if (accelBuffer.isEmpty() || magBuffer.isEmpty()) {
                // Não temos dados suficientes
                return
            }

            // Calcula média dos buffers
            val accelAvg = if (accelBuffer.isNotEmpty()) {
                floatArrayOf(
                    accelBuffer.map { it[0] }.average().toFloat(),
                    accelBuffer.map { it[1] }.average().toFloat(),
                    accelBuffer.map { it[2] }.average().toFloat()
                )
            } else {
                floatArrayOf(0f, 0f, 0f)
            }

            val magAvg = if (magBuffer.isNotEmpty()) {
                floatArrayOf(
                    magBuffer.map { it[0] }.average().toFloat(),
                    magBuffer.map { it[1] }.average().toFloat(),
                    magBuffer.map { it[2] }.average().toFloat()
                )
            } else {
                floatArrayOf(0f, 0f, 0f)
            }

            // Calcula matriz de rotação
            val rotationMatrix = FloatArray(9)
            val inclinationMatrix = FloatArray(9)
            val success = SensorManager.getRotationMatrix(
                rotationMatrix,
                inclinationMatrix,
                accelAvg,
                magAvg
            )

            if (success) {
                // Converte para azimuth, pitch, roll
                val orientationValues = FloatArray(3)
                SensorManager.getOrientation(rotationMatrix, orientationValues)

                val azimuth = Math.toDegrees(orientationValues[0].toDouble()).toFloat()
                val pitch = Math.toDegrees(orientationValues[1].toDouble()).toFloat()
                val roll = Math.toDegrees(orientationValues[2].toDouble()).toFloat()

                // Normaliza azimuth para 0-360
                val normalizedAzimuth = if (azimuth < 0) azimuth + 360f else azimuth

                orientationData = OrientationData(
                    azimuth = normalizedAzimuth,
                    pitch = pitch,
                    roll = roll,
                    rotationMatrix = rotationMatrix
                )
            } else {
                // Fallback: calcular apenas pitch e roll usando apenas acelerômetro
                val pitch = Math.toDegrees(atan2(-accelAvg[0].toDouble(), sqrt(accelAvg[1] * accelAvg[1] + accelAvg[2] * accelAvg[2]).toDouble())).toFloat()
                val roll = Math.toDegrees(atan2(accelAvg[1].toDouble(), accelAvg[2].toDouble())).toFloat()

                orientationData = OrientationData(
                    azimuth = 0f, // Não podemos calcular sem magnetômetro
                    pitch = pitch,
                    roll = roll,
                    rotationMatrix = null
                )
            }

            accelBuffer.clear()
            magBuffer.clear()
        }

        _lastOrientationData.value = orientationData

        AuraLog.IMU.d("Orientation 1Hz: azimuth=${String.format("%.1f", orientationData.azimuth)}°, pitch=${String.format("%.1f", orientationData.pitch)}°, roll=${String.format("%.1f", orientationData.roll)}°")

        onOrientationDataUpdate?.invoke(orientationData)
    }

    fun isRunning(): Boolean = isRunning
    fun hasRequiredSensors(): Boolean = accelerometer != null && magnetometer != null
}

