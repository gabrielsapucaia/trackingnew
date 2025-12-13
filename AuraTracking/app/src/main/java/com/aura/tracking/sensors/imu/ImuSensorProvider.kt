package com.aura.tracking.sensors.imu

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Handler
import android.os.HandlerThread
import com.aura.tracking.diagnostics.LatencyDiagnostics
import com.aura.tracking.logging.AuraLog
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.callbackFlow

/**
 * ImuSensorProvider - Provides accelerometer and gyroscope data at 1Hz (averaged).
 * Samples sensors at ~100Hz internally and averages to 1Hz output.
 * 
 * FASE 3: Otimizações industriais para Moto G34:
 * - SENSOR_DELAY_FASTEST para máxima precisão
 * - Auto-recovery de listeners
 * - Detecção de starvation (>5s sem IMU)
 * - Logging persistente
 */
class ImuSensorProvider(private val context: Context) : SensorEventListener {

    companion object {
        private const val TAG = "ImuSensorProvider"

        // SENSOR_DELAY_FASTEST = ~100Hz para máxima amostragem
        private const val SENSOR_DELAY = SensorManager.SENSOR_DELAY_FASTEST
        
        // Intervalo de output: 1Hz = 1000ms
        private const val OUTPUT_INTERVAL_MS = 1000L
        
        // Threshold de starvation IMU (5 segundos)
        private const val IMU_STARVATION_THRESHOLD_MS = 5000L
    }

    private val sensorManager: SensorManager by lazy {
        context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    }

    private var accelerometer: Sensor? = null
    private var gyroscope: Sensor? = null
    private var magnetometer: Sensor? = null
    private var linearAccelerometer: Sensor? = null
    private var gravitySensor: Sensor? = null
    private var rotationVectorSensor: Sensor? = null
    private var isRunning = false

    // Buffers para média
    private val accelBuffer = mutableListOf<FloatArray>()
    private val gyroBuffer = mutableListOf<FloatArray>()
    private val magBuffer = mutableListOf<FloatArray>()
    private val linearAccelBuffer = mutableListOf<FloatArray>()
    private val gravityBuffer = mutableListOf<FloatArray>()
    private val rotationVectorBuffer = mutableListOf<FloatArray>()
    private val bufferLock = Any()
    
    // Timestamps para detecção de starvation
    private var lastAccelTimestamp: Long = 0L
    private var lastGyroTimestamp: Long = 0L
    private var lastMagTimestamp: Long = 0L
    private var lastLinearAccelTimestamp: Long = 0L
    private var lastGravityTimestamp: Long = 0L
    private var lastRotationVectorTimestamp: Long = 0L
    private var recoveryAttempts: Int = 0

    // Handler para output a 1Hz
    private var handlerThread: HandlerThread? = null
    private var handler: Handler? = null
    private var outputRunnable: Runnable? = null

    // Estado reativo do último dado IMU
    private val _lastImuData = MutableStateFlow<ImuData?>(null)
    val lastImuData: StateFlow<ImuData?> = _lastImuData.asStateFlow()

    // Raw last readings (para debug)
    var lastAcceleration: FloatArray = floatArrayOf(0f, 0f, 0f)
        private set

    var lastGyroscope: FloatArray = floatArrayOf(0f, 0f, 0f)
        private set

    // Listeners
    var onImuUpdate: ((accel: FloatArray, gyro: FloatArray) -> Unit)? = null
    var onImuDataUpdate: ((ImuData) -> Unit)? = null

    init {
        accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        gyroscope = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
        magnetometer = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD)
        linearAccelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_LINEAR_ACCELERATION)
        gravitySensor = sensorManager.getDefaultSensor(Sensor.TYPE_GRAVITY)
        rotationVectorSensor = sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)

        if (accelerometer == null) {
            AuraLog.IMU.w("Accelerometer not available on this device")
        }
        if (gyroscope == null) {
            AuraLog.IMU.w("Gyroscope not available on this device")
        }
        if (magnetometer == null) {
            AuraLog.IMU.w("Magnetometer not available on this device")
        }
        if (linearAccelerometer == null) {
            AuraLog.IMU.w("Linear Accelerometer not available on this device")
        }
        if (gravitySensor == null) {
            AuraLog.IMU.w("Gravity sensor not available on this device")
        }
        if (rotationVectorSensor == null) {
            AuraLog.IMU.w("Rotation Vector sensor not available on this device")
        }
    }

    /**
     * Flow de dados IMU a 1Hz (média de ~100 amostras).
     */
    fun imuFlow(): Flow<ImuData> = callbackFlow {
        val localAccelBuffer = mutableListOf<FloatArray>()
        val localGyroBuffer = mutableListOf<FloatArray>()
        
        val listener = object : SensorEventListener {
            override fun onSensorChanged(event: SensorEvent) {
                when (event.sensor.type) {
                    Sensor.TYPE_ACCELEROMETER -> {
                        synchronized(localAccelBuffer) {
                            localAccelBuffer.add(event.values.copyOf())
                        }
                    }
                    Sensor.TYPE_GYROSCOPE -> {
                        synchronized(localGyroBuffer) {
                            localGyroBuffer.add(event.values.copyOf())
                        }
                    }
                }
            }

            override fun onAccuracyChanged(sensor: Sensor, accuracy: Int) {}
        }

        // Registra sensores
        accelerometer?.let { sensorManager.registerListener(listener, it, SENSOR_DELAY) }
        gyroscope?.let { sensorManager.registerListener(listener, it, SENSOR_DELAY) }

        // Thread para output a 1Hz
        val thread = HandlerThread("ImuFlowThread").apply { start() }
        val handler = Handler(thread.looper)
        
        val runnable = object : Runnable {
            override fun run() {
                val imuData: ImuData
                
                synchronized(localAccelBuffer) {
                    synchronized(localGyroBuffer) {
                        imuData = computeAverage(
                            localAccelBuffer, 
                            localGyroBuffer,
                            emptyList(), // magBuffer
                            emptyList(), // linearAccelBuffer
                            emptyList(), // gravityBuffer
                            emptyList()  // rotationVectorBuffer
                        )
                        localAccelBuffer.clear()
                        localGyroBuffer.clear()
                    }
                }
                
                trySend(imuData)
                handler.postDelayed(this, OUTPUT_INTERVAL_MS)
            }
        }
        
        handler.postDelayed(runnable, OUTPUT_INTERVAL_MS)
        AuraLog.IMU.i("IMU Flow started at 1Hz")

        awaitClose {
            handler.removeCallbacks(runnable)
            thread.quitSafely()
            sensorManager.unregisterListener(listener)
            AuraLog.IMU.i("IMU Flow stopped")
        }
    }

    /**
     * Start receiving sensor updates at 1Hz averaged output.
     */
    fun startSensorUpdates() {
        if (isRunning) {
            AuraLog.IMU.d("Sensor updates already running")
            return
        }

        AuraLog.IMU.i("Starting sensor updates at 1Hz averaged (SENSOR_DELAY_FASTEST)")
        
        val now = System.currentTimeMillis()
        lastAccelTimestamp = now
        lastGyroTimestamp = now
        recoveryAttempts = 0

        // Registra sensores para amostragem
        accelerometer?.let { sensor ->
            sensorManager.registerListener(this, sensor, SENSOR_DELAY)
            AuraLog.IMU.i("Accelerometer registered with DELAY_FASTEST")
        }

        gyroscope?.let { sensor ->
            sensorManager.registerListener(this, sensor, SENSOR_DELAY)
            AuraLog.IMU.i("Gyroscope registered with DELAY_FASTEST")
        }
        
        magnetometer?.let { sensor ->
            sensorManager.registerListener(this, sensor, SENSOR_DELAY)
            AuraLog.IMU.i("Magnetometer registered with DELAY_FASTEST")
        }
        
        linearAccelerometer?.let { sensor ->
            sensorManager.registerListener(this, sensor, SENSOR_DELAY)
            AuraLog.IMU.i("Linear Accelerometer registered with DELAY_FASTEST")
        }
        
        gravitySensor?.let { sensor ->
            sensorManager.registerListener(this, sensor, SENSOR_DELAY)
            AuraLog.IMU.i("Gravity sensor registered with DELAY_FASTEST")
        }
        
        rotationVectorSensor?.let { sensor ->
            sensorManager.registerListener(this, sensor, SENSOR_DELAY)
            AuraLog.IMU.i("Rotation Vector sensor registered with DELAY_FASTEST")
        }

        // Inicia thread para output a 1Hz
        handlerThread = HandlerThread("ImuOutputThread").apply { start() }
        handler = Handler(handlerThread!!.looper)
        
        outputRunnable = object : Runnable {
            override fun run() {
                emitAveragedData()
                
                // Verifica starvation e tenta recovery se necessário
                checkAndRecoverIfNeeded()
                
                handler?.postDelayed(this, OUTPUT_INTERVAL_MS)
            }
        }
        
        handler?.postDelayed(outputRunnable!!, OUTPUT_INTERVAL_MS)
        isRunning = true
    }

    /**
     * Stop receiving sensor updates.
     */
    fun stopSensorUpdates() {
        if (!isRunning) {
            AuraLog.IMU.d("Sensor updates not running")
            return
        }

        AuraLog.IMU.i("Stopping sensor updates")
        
        outputRunnable?.let { handler?.removeCallbacks(it) }
        handlerThread?.quitSafely()
        handlerThread = null
        handler = null
        outputRunnable = null
        
        sensorManager.unregisterListener(this)
        
        synchronized(bufferLock) {
            accelBuffer.clear()
            gyroBuffer.clear()
            magBuffer.clear()
            linearAccelBuffer.clear()
            gravityBuffer.clear()
            rotationVectorBuffer.clear()
        }
        
        isRunning = false
    }
    
    /**
     * Verifica se há starvation de sensores e tenta recuperar
     */
    private fun checkAndRecoverIfNeeded() {
        val now = System.currentTimeMillis()
        val accelAge = now - lastAccelTimestamp
        val gyroAge = now - lastGyroTimestamp
        
        val needsRecovery = (accelerometer != null && accelAge > IMU_STARVATION_THRESHOLD_MS) ||
                (gyroscope != null && gyroAge > IMU_STARVATION_THRESHOLD_MS)
        
        if (needsRecovery) {
            recoveryAttempts++
            AuraLog.IMU.w("IMU starvation detected (accel: ${accelAge}ms, gyro: ${gyroAge}ms). Recovery attempt #$recoveryAttempts")
            
            // Re-registra sensores
            sensorManager.unregisterListener(this)
            
            accelerometer?.let { sensor ->
                sensorManager.registerListener(this, sensor, SENSOR_DELAY)
            }
            
            gyroscope?.let { sensor ->
                sensorManager.registerListener(this, sensor, SENSOR_DELAY)
            }
            
            magnetometer?.let { sensor ->
                sensorManager.registerListener(this, sensor, SENSOR_DELAY)
            }
            
            linearAccelerometer?.let { sensor ->
                sensorManager.registerListener(this, sensor, SENSOR_DELAY)
            }
            
            gravitySensor?.let { sensor ->
                sensorManager.registerListener(this, sensor, SENSOR_DELAY)
            }
            
            rotationVectorSensor?.let { sensor ->
                sensorManager.registerListener(this, sensor, SENSOR_DELAY)
            }
            
            AuraLog.IMU.i("IMU recovery: listeners re-registered")
        }
    }

    /**
     * SensorEventListener callback - accumula amostras.
     * 
     * LATENCY DIAGNOSTICS: Registra amostras de IMU para correlação cruzada com GPS.
     */
    override fun onSensorChanged(event: SensorEvent) {
        val now = System.currentTimeMillis()
        
        when (event.sensor.type) {
            Sensor.TYPE_ACCELEROMETER -> {
                lastAcceleration = event.values.copyOf()
                lastAccelTimestamp = now
                synchronized(bufferLock) {
                    accelBuffer.add(event.values.copyOf())
                }
                
                // LATENCY DIAGNOSTICS: Registrar amostra de IMU para correlação
                LatencyDiagnostics.recordImuSample(
                    accelX = event.values[0],
                    accelY = event.values[1],
                    accelZ = event.values[2],
                    timestamp = now
                )
            }
            Sensor.TYPE_GYROSCOPE -> {
                lastGyroscope = event.values.copyOf()
                lastGyroTimestamp = now
                synchronized(bufferLock) {
                    gyroBuffer.add(event.values.copyOf())
                }
            }
            Sensor.TYPE_MAGNETIC_FIELD -> {
                lastMagTimestamp = now
                synchronized(bufferLock) {
                    magBuffer.add(event.values.copyOf())
                }
            }
            Sensor.TYPE_LINEAR_ACCELERATION -> {
                lastLinearAccelTimestamp = now
                synchronized(bufferLock) {
                    linearAccelBuffer.add(event.values.copyOf())
                }
            }
            Sensor.TYPE_GRAVITY -> {
                lastGravityTimestamp = now
                synchronized(bufferLock) {
                    gravityBuffer.add(event.values.copyOf())
                }
            }
            Sensor.TYPE_ROTATION_VECTOR -> {
                lastRotationVectorTimestamp = now
                synchronized(bufferLock) {
                    rotationVectorBuffer.add(event.values.copyOf())
                }
            }
        }
        
        // Reset recovery attempts ao receber dados
        if (recoveryAttempts > 0) {
            AuraLog.IMU.i("IMU recovered after $recoveryAttempts attempts")
            recoveryAttempts = 0
        }
    }

    override fun onAccuracyChanged(sensor: Sensor, accuracy: Int) {
        AuraLog.IMU.d("Sensor accuracy changed: ${sensor.name} -> $accuracy")
    }

    /**
     * Emite dados médios a 1Hz.
     */
    private fun emitAveragedData() {
        val imuData: ImuData
        val sampleCount: Int
        
        synchronized(bufferLock) {
            sampleCount = accelBuffer.size.coerceAtLeast(gyroBuffer.size)
            imuData = computeAverage(
                accelBuffer, 
                gyroBuffer,
                magBuffer,
                linearAccelBuffer,
                gravityBuffer,
                rotationVectorBuffer
            )
            accelBuffer.clear()
            gyroBuffer.clear()
            magBuffer.clear()
            linearAccelBuffer.clear()
            gravityBuffer.clear()
            rotationVectorBuffer.clear()
        }
        
        _lastImuData.value = imuData
        
        AuraLog.IMU.d("IMU 1Hz ($sampleCount samples): accel=(${String.format("%.2f", imuData.accelX)}, ${String.format("%.2f", imuData.accelY)}, ${String.format("%.2f", imuData.accelZ)})")
        
        onImuUpdate?.invoke(
            floatArrayOf(imuData.accelX, imuData.accelY, imuData.accelZ),
            floatArrayOf(imuData.gyroX, imuData.gyroY, imuData.gyroZ)
        )
        onImuDataUpdate?.invoke(imuData)
    }

    /**
     * Calcula média dos buffers.
     */
    private fun computeAverage(
        accelBuffer: List<FloatArray>,
        gyroBuffer: List<FloatArray>,
        magBuffer: List<FloatArray>,
        linearAccelBuffer: List<FloatArray>,
        gravityBuffer: List<FloatArray>,
        rotationVectorBuffer: List<FloatArray>
    ): ImuData {
        val accelAvg = if (accelBuffer.isNotEmpty()) {
            floatArrayOf(
                accelBuffer.map { it[0] }.average().toFloat(),
                accelBuffer.map { it[1] }.average().toFloat(),
                accelBuffer.map { it[2] }.average().toFloat()
            )
        } else {
            floatArrayOf(0f, 0f, 0f)
        }

        val gyroAvg = if (gyroBuffer.isNotEmpty()) {
            floatArrayOf(
                gyroBuffer.map { it[0] }.average().toFloat(),
                gyroBuffer.map { it[1] }.average().toFloat(),
                gyroBuffer.map { it[2] }.average().toFloat()
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
        } else null
        
        val linearAccelAvg = if (linearAccelBuffer.isNotEmpty()) {
            floatArrayOf(
                linearAccelBuffer.map { it[0] }.average().toFloat(),
                linearAccelBuffer.map { it[1] }.average().toFloat(),
                linearAccelBuffer.map { it[2] }.average().toFloat()
            )
        } else null
        
        val gravityAvg = if (gravityBuffer.isNotEmpty()) {
            floatArrayOf(
                gravityBuffer.map { it[0] }.average().toFloat(),
                gravityBuffer.map { it[1] }.average().toFloat(),
                gravityBuffer.map { it[2] }.average().toFloat()
            )
        } else null
        
        val rotationVectorAvg = if (rotationVectorBuffer.isNotEmpty()) {
            floatArrayOf(
                rotationVectorBuffer.map { it[0] }.average().toFloat(),
                rotationVectorBuffer.map { it[1] }.average().toFloat(),
                rotationVectorBuffer.map { it[2] }.average().toFloat(),
                rotationVectorBuffer.map { it.getOrNull(3) ?: 0f }.average().toFloat() // W component
            )
        } else null

        return ImuData(
            accelX = accelAvg[0],
            accelY = accelAvg[1],
            accelZ = accelAvg[2],
            gyroX = gyroAvg[0],
            gyroY = gyroAvg[1],
            gyroZ = gyroAvg[2],
            magX = magAvg?.get(0),
            magY = magAvg?.get(1),
            magZ = magAvg?.get(2),
            linearAccelX = linearAccelAvg?.get(0),
            linearAccelY = linearAccelAvg?.get(1),
            linearAccelZ = linearAccelAvg?.get(2),
            gravityX = gravityAvg?.get(0),
            gravityY = gravityAvg?.get(1),
            gravityZ = gravityAvg?.get(2),
            rotationVectorX = rotationVectorAvg?.get(0),
            rotationVectorY = rotationVectorAvg?.get(1),
            rotationVectorZ = rotationVectorAvg?.get(2),
            rotationVectorW = rotationVectorAvg?.get(3)
        )
    }

    fun isRunning(): Boolean = isRunning
    fun hasAccelerometer(): Boolean = accelerometer != null
    fun hasGyroscope(): Boolean = gyroscope != null
    fun getRecoveryAttempts(): Int = recoveryAttempts
}
