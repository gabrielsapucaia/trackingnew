package com.aura.tracking.background

import android.util.Log
import com.aura.tracking.analytics.TelemetryAnalytics
import com.aura.tracking.data.room.TelemetryQueueDao
import com.aura.tracking.data.room.TelemetryQueueEntity
import com.aura.tracking.diagnostics.LatencyDiagnostics
import com.aura.tracking.mqtt.MqttClientManager
import com.aura.tracking.mqtt.MqttClientManager.PublishFailureReason
import com.aura.tracking.sensors.gps.GpsData
import com.aura.tracking.sensors.imu.ImuData
import com.aura.tracking.sensors.orientation.OrientationData
import com.aura.tracking.sensors.system.SystemData
// REMOVIDO: import com.aura.tracking.sensors.motion.MotionDetectionData  // Sensores não disponíveis
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.UUID

/**
 * Agregador de telemetria que combina dados de GPS e IMU,
 * publica via MQTT a 1Hz (timer fixo) ou enfileira para envio posterior.
 * 
 * IMPORTANTE: O timer de 1Hz é independente da frequência do GPS.
 * Mesmo que o GPS atualize a cada 7s, publicamos a cada 1s usando
 * o último valor conhecido.
 * 
 * FASE 3 - QUEUE 30 DIAS:
 * - Cada mensagem tem um messageId (UUID) globalmente único
 * - messageId é incluído no payload JSON para deduplicação server-side
 * - messageId é gerado na criação e persiste em retries
 */
class TelemetryAggregator(
    private val mqttClient: MqttClientManager,
    private val queueDao: TelemetryQueueDao,
    private val deviceId: String,
    private val operatorId: String
) {
    companion object {
        private const val TAG = "TelemetryAggregator"
        private const val BASE_TOPIC = "aura/tracking"
        private const val PUBLISH_INTERVAL_MS = 1000L // 1 Hz fixo
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val json = Json { encodeDefaults = true }

    // Estado atual
    @Volatile private var lastGpsData: GpsData? = null
    @Volatile private var lastImuData: ImuData? = null
    @Volatile private var lastOrientationData: OrientationData? = null
    @Volatile private var lastSystemData: SystemData? = null
    // REMOVIDO: @Volatile private var lastMotionData: MotionDetectionData? = null  // Sensores não disponíveis

    // Job do timer de 1Hz
    private var publishJob: Job? = null
    private var isRunning = false

    // Estatísticas
    private val _packetsSent = MutableStateFlow(0L)
    val packetsSent: StateFlow<Long> = _packetsSent.asStateFlow()

    private val _packetsQueued = MutableStateFlow(0L)
    val packetsQueued: StateFlow<Long> = _packetsQueued.asStateFlow()

    /**
     * Inicia o timer de publicação a 1Hz
     */
    @Synchronized
    fun start() {
        if (isRunning && publishJob?.isActive == true) {
            Log.d(TAG, "Already running")
            return
        }

        // Cancela qualquer resquício antes de iniciar um novo loop
        publishJob?.cancel()

        Log.i(TAG, "Starting 1Hz telemetry publisher")
        isRunning = true

        publishJob = scope.launch {
            var nextTick = android.os.SystemClock.elapsedRealtime()
            while (isActive) {
                sendCombinedTelemetry()
                nextTick += PUBLISH_INTERVAL_MS
                val wait = nextTick - android.os.SystemClock.elapsedRealtime()
                if (wait > 0) {
                    delay(wait)
                } else {
                    nextTick = android.os.SystemClock.elapsedRealtime()
                }
            }
        }
    }

    /**
     * Para o timer de publicação
     */
    @Synchronized
    fun stop() {
        Log.i(TAG, "Stopping 1Hz telemetry publisher")
        isRunning = false
        publishJob?.cancel()
        publishJob = null
    }

    /**
     * Atualiza dados GPS (chamado pelo GpsLocationProvider)
     */
    fun updateGps(gpsData: GpsData) {
        lastGpsData = gpsData
        Log.d(TAG, "GPS updated: lat=${gpsData.latitude}, lon=${gpsData.longitude}")
    }

    /**
     * Atualiza dados IMU (chamado pelo ImuSensorProvider)
     */
    fun updateImu(imuData: ImuData) {
        lastImuData = imuData
    }

    /**
     * Atualiza dados de orientação (chamado pelo OrientationProvider)
     */
    fun updateOrientation(orientationData: OrientationData) {
        lastOrientationData = orientationData
    }

    /**
     * Atualiza dados de sistema (chamado pelo SystemDataProvider)
     */
    fun updateSystemData(systemData: SystemData) {
        lastSystemData = systemData
    }

    // REMOVIDO: Atualiza dados de detecção de movimento - sensores não disponíveis no dispositivo
    // /**
    //  * Atualiza dados de detecção de movimento (chamado pelo MotionDetectorProvider)
    //  */
    // fun updateMotionDetection(motionData: MotionDetectionData) {
    //     lastMotionData = motionData
    // }

    /**
     * Envia telemetria combinada GPS + IMU + Orientação + Sistema + Movimento
     * Chamado pelo timer a cada 1 segundo.
     * 
     * FASE 3: Cada pacote recebe um messageId único para deduplicação.
     * LATENCY DIAGNOSTICS: Timestamps T3 e T4 são registrados.
     */
    private fun sendCombinedTelemetry() {
        val gps = lastGpsData
        if (gps == null) {
            Log.d(TAG, "No GPS data yet, skipping publish")
            return
        }
        
        // Gerar messageId único para esta mensagem
        val messageId = UUID.randomUUID().toString()
        
        // LATENCY DIAGNOSTICS: T3 - Packet Creation
        val t3PacketCreation = LatencyDiagnostics.recordPacketCreation(messageId)
        
        // Determina modo de transmissão ANTES de criar packet
        val transmissionMode = if (mqttClient.isConnected.value) "online" else "queued"
        
        val packet = TelemetryPacket(
            messageId = messageId,
            deviceId = deviceId,
            matricula = operatorId,
            timestamp = System.currentTimeMillis(),
            transmissionMode = transmissionMode,
            gps = GpsPayload(
                lat = gps.latitude,
                lon = gps.longitude,
                alt = gps.altitude,
                speed = gps.speed,
                bearing = gps.bearing,
                accuracy = gps.accuracy,
                satellites = gps.satellites,
                hAcc = gps.hAcc,
                vAcc = gps.vAcc,
                sAcc = gps.sAcc,
                hdop = gps.hdop,
                vdop = gps.vdop,
                pdop = gps.pdop,
                gpsTimestamp = gps.gpsTimestamp
            ),
            imu = lastImuData?.let { imu ->
                ImuPayload(
                    accelX = imu.accelX,
                    accelY = imu.accelY,
                    accelZ = imu.accelZ,
                    gyroX = imu.gyroX,
                    gyroY = imu.gyroY,
                    gyroZ = imu.gyroZ,
                    accelMagnitude = imu.accelMagnitude,
                    gyroMagnitude = imu.gyroMagnitude,
                    magX = imu.magX,
                    magY = imu.magY,
                    magZ = imu.magZ,
                    magMagnitude = imu.magMagnitude,
                    linearAccelX = imu.linearAccelX,
                    linearAccelY = imu.linearAccelY,
                    linearAccelZ = imu.linearAccelZ,
                    linearAccelMagnitude = imu.linearAccelMagnitude,
                    gravityX = imu.gravityX,
                    gravityY = imu.gravityY,
                    gravityZ = imu.gravityZ,
                    rotationVectorX = imu.rotationVectorX,
                    rotationVectorY = imu.rotationVectorY,
                    rotationVectorZ = imu.rotationVectorZ,
                    rotationVectorW = imu.rotationVectorW
                )
            },
            orientation = lastOrientationData?.let { orient ->
                OrientationPayload(
                    azimuth = orient.azimuth,
                    pitch = orient.pitch,
                    roll = orient.roll,
                    rotationMatrix = orient.rotationMatrix
                )
            },
            system = lastSystemData?.let { sys ->
                SystemPayload(
                    battery = sys.battery?.let { bat ->
                        BatteryPayload(
                            level = bat.level,
                            temperature = bat.temperature,
                            status = bat.status,
                            voltage = bat.voltage,
                            health = bat.health,
                            technology = bat.technology,
                            chargeCounter = bat.chargeCounter,
                            fullCapacity = bat.fullCapacity
                        )
                    },
                    connectivity = sys.connectivity?.let { conn ->
                        ConnectivityPayload(
                            wifi = conn.wifi?.let { wifi ->
                                WifiPayload(
                                    rssi = wifi.rssi,
                                    ssid = wifi.ssid,
                                    bssid = wifi.bssid,
                                    frequency = wifi.frequency,
                                    channel = wifi.channel
                                )
                            },
                            cellular = conn.cellular?.let { cell ->
                                CellularPayload(
                                    networkType = cell.networkType,
                                    operator = cell.operator,
                                    signalStrength = cell.signalStrength?.let { sig ->
                                        SignalStrengthPayload(
                                            rsrp = sig.rsrp,
                                            rsrq = sig.rsrq,
                                            rssnr = sig.rssnr,
                                            rssi = sig.rssi,
                                            level = sig.level
                                        )
                                    },
                                    cellInfo = cell.cellInfo?.let { info ->
                                        CellInfoPayload(
                                            ci = info.ci,
                                            pci = info.pci,
                                            tac = info.tac,
                                            earfcn = info.earfcn,
                                            band = info.band,
                                            bandwidth = info.bandwidth
                                        )
                                    }
                                )
                            }
                        )
                    }
                )
            }
            // REMOVIDO: motion - sensores não disponíveis no dispositivo
            // motion = lastMotionData?.let { motion ->
            //     MotionDetectionPayload(
            //         significantMotion = motion.significantMotion,
            //         stationaryDetect = motion.stationaryDetect,
            //         motionDetect = motion.motionDetect,
            //         flatUp = motion.flatUp,
            //         flatDown = motion.flatDown,
            //         stowed = motion.stowed,
            //         displayRotate = motion.displayRotate
            //     )
            // }
        )

        val topic = "$BASE_TOPIC/$deviceId/telemetry"
        val payload = json.encodeToString(packet)

        scope.launch {
            publishOrQueue(topic, payload, messageId, transmissionMode, t3PacketCreation)
        }
    }

    /**
     * Publica via MQTT ou enfileira se desconectado.
     * 
     * @param messageId UUID único para deduplicação (persistido na queue)
     * @param transmissionMode Modo de transmissão ("online" ou "queued")
     * @param t3PacketCreation Timestamp T3 para diagnóstico de latência
     */
    private suspend fun publishOrQueue(topic: String, payload: String, messageId: String, transmissionMode: String, t3PacketCreation: Long = 0) {
        if (mqttClient.isConnected.value) {
            val publishStart = System.currentTimeMillis()
            val result = mqttClient.publishWithResult(topic, payload)
            val publishLatency = System.currentTimeMillis() - publishStart

            if (result.success) {
                // LATENCY DIAGNOSTICS: T4 - MQTT Publish
                if (t3PacketCreation > 0) {
                    LatencyDiagnostics.recordMqttPublish(messageId, t3PacketCreation)
                }
                _packetsSent.value++

                // ANALYTICS: Registra sucesso de publicação
                TelemetryAnalytics.recordPublishSuccess(topic, payload.length, publishLatency)

                Log.d(TAG, "Telemetry sent: $topic (msgId=${messageId.take(8)}..., mode=$transmissionMode)")
            } else {
                // ANALYTICS: Registra falha de publicação
                TelemetryAnalytics.recordPublishFailure(result.failureReason, topic, payload.length)

                if (result.failureReason == PublishFailureReason.MAX_INFLIGHT) {
                    Log.w(TAG, "Publish blocked (max inflight), queuing message ${messageId.take(8)}")
                }
                // Payload já contém transmissionMode="queued"
                enqueue(topic, payload, messageId)
            }
        } else {
            // Payload já contém transmissionMode="queued"
            enqueue(topic, payload, messageId)
        }
    }

    /**
     * Enfileira para envio posterior.
     * O messageId é persistido na entity para manter consistência em retries.
     */
    private suspend fun enqueue(topic: String, payload: String, messageId: String) {
        val entity = TelemetryQueueEntity(
            messageId = messageId,
            topic = topic,
            payload = payload
        )
        queueDao.insert(entity)
        _packetsQueued.value++
        Log.d(TAG, "Telemetry queued: $topic (msgId=${messageId.take(8)}...)")
    }

    /**
     * Tenta enviar pacotes da fila
     */
    suspend fun flushQueue(batchSize: Int = 50): FlushResult {
        val entries = queueDao.getOldestEntries(batchSize)
        if (entries.isEmpty()) {
            return FlushResult(sent = 0, failed = 0, remaining = 0)
        }

        var sent = 0
        var failed = 0
        var hitMaxInflight = false
        val idsToDelete = mutableListOf<Long>()

        for (entry in entries) {
            if (!mqttClient.isConnected.value) {
                break
            }

            val result = mqttClient.publishWithResult(entry.topic, entry.payload, entry.qos)
            when {
                result.success -> {
                    idsToDelete.add(entry.id)
                    sent++
                    _packetsSent.value++ // Incrementar contador de enviados
                }
                result.failureReason == PublishFailureReason.MAX_INFLIGHT -> {
                    queueDao.incrementRetryCount(entry.id)
                    failed++
                    hitMaxInflight = true
                    Log.w(TAG, "Flush paused: max inflight reached, deferring remaining batch")
                    break
                }
                else -> {
                    queueDao.incrementRetryCount(entry.id)
                    failed++
                }
            }
        }

        if (idsToDelete.isNotEmpty()) {
            queueDao.deleteByIds(idsToDelete)
        }

        // Limpar entradas com muitas falhas
        queueDao.deleteFailedEntries(maxRetries = 10)

        if (hitMaxInflight) {
            // Pequena pausa para abrir espaço no broker antes de tentar de novo
            delay(250)
        }

        val remaining = queueDao.getCount()
        Log.d(TAG, "Queue flush: sent=$sent, failed=$failed, remaining=$remaining")

        return FlushResult(sent, failed, remaining)
    }

    /**
     * Envia evento discreto (login, logout, status change)
     */
    /**
     * Envia evento discreto (login, logout, status change).\n     * Eventos não precisam de messageId pois são de baixa frequência e idempotentes.\n     */
    fun sendEvent(eventType: String, data: Map<String, String> = emptyMap()) {
        val event = EventPacket(
            deviceId = deviceId,
            matricula = operatorId,
            timestamp = System.currentTimeMillis(),
            eventType = eventType,
            data = data
        )

        val topic = "$BASE_TOPIC/$deviceId/events"
        val payload = json.encodeToString(event)

        scope.launch {
            // Eventos usam messageId gerado na hora (não precisa de persistência)
            val eventMessageId = UUID.randomUUID().toString()
            val eventTransmissionMode = if (mqttClient.isConnected.value) "online" else "queued"
            publishOrQueue(topic, payload, eventMessageId, eventTransmissionMode)
        }
    }

    data class FlushResult(
        val sent: Int,
        val failed: Int,
        val remaining: Int
    )
}

// ==================== Modelos de Payload ====================

/**
 * Pacote de telemetria com GPS + IMU.
 * 
 * FASE 3: Inclui messageId para deduplicação server-side.
 * O servidor usa ON CONFLICT (message_id) DO NOTHING para ignorar duplicatas.
 */
@Serializable
data class TelemetryPacket(
    val messageId: String,  // UUID único para deduplicação
    val deviceId: String,
    val matricula: String,  // Matrícula do operador
    val timestamp: Long,
    val transmissionMode: String = "online",  // "online" ou "queued"
    val gps: GpsPayload,
    val imu: ImuPayload? = null,
    val orientation: OrientationPayload? = null,
    val system: SystemPayload? = null
    // REMOVIDO: val motion: MotionDetectionPayload? = null  // Sensores não disponíveis
)

@Serializable
data class GpsPayload(
    val lat: Double,
    val lon: Double,
    val alt: Double,
    val speed: Float,
    val bearing: Float,
    val accuracy: Float,
    val satellites: Int? = null,
    val hAcc: Float? = null,
    val vAcc: Float? = null,
    val sAcc: Float? = null,
    val hdop: Float? = null,
    val vdop: Float? = null,
    val pdop: Float? = null,
    val gpsTimestamp: Long? = null
)

@Serializable
data class ImuPayload(
    val accelX: Float,
    val accelY: Float,
    val accelZ: Float,
    val gyroX: Float,
    val gyroY: Float,
    val gyroZ: Float,
    val accelMagnitude: Float? = null,
    val gyroMagnitude: Float? = null,
    val magX: Float? = null,
    val magY: Float? = null,
    val magZ: Float? = null,
    val magMagnitude: Float? = null,
    val linearAccelX: Float? = null,
    val linearAccelY: Float? = null,
    val linearAccelZ: Float? = null,
    val linearAccelMagnitude: Float? = null,
    val gravityX: Float? = null,
    val gravityY: Float? = null,
    val gravityZ: Float? = null,
    val rotationVectorX: Float? = null,
    val rotationVectorY: Float? = null,
    val rotationVectorZ: Float? = null,
    val rotationVectorW: Float? = null
)

@Serializable
data class OrientationPayload(
    val azimuth: Float,
    val pitch: Float,
    val roll: Float,
    val rotationMatrix: FloatArray? = null
)

@Serializable
data class BatteryPayload(
    val level: Int? = null,  // 0-100% (null se não disponível)
    val temperature: Float? = null,
    val status: String,
    val voltage: Int? = null,
    val health: String? = null,
    val technology: String? = null,
    val chargeCounter: Long? = null,
    val fullCapacity: Long? = null
)

@Serializable
data class ConnectivityPayload(
    val wifi: WifiPayload? = null,
    val cellular: CellularPayload? = null
)

@Serializable
data class WifiPayload(
    val rssi: Int? = null,
    val ssid: String? = null,
    val bssid: String? = null,
    val frequency: Int? = null,
    val channel: Int? = null
)

@Serializable
data class CellularPayload(
    val networkType: String? = null,
    val operator: String? = null,
    val signalStrength: SignalStrengthPayload? = null,
    val cellInfo: CellInfoPayload? = null
)

@Serializable
data class SignalStrengthPayload(
    val rsrp: Int? = null,
    val rsrq: Int? = null,
    val rssnr: Int? = null,
    val rssi: Int? = null,
    val level: Int? = null
)

@Serializable
data class CellInfoPayload(
    val ci: Long? = null,
    val pci: Int? = null,
    val tac: Int? = null,
    val earfcn: Int? = null,
    val band: List<Int>? = null,
    val bandwidth: Int? = null
)

@Serializable
data class SystemPayload(
    val battery: BatteryPayload? = null,
    val connectivity: ConnectivityPayload? = null
)

// REMOVIDO: MotionDetectionPayload - sensores não disponíveis no dispositivo
// @Serializable
// data class MotionDetectionPayload(
//     val significantMotion: Boolean? = null,
//     val stationaryDetect: Boolean? = null,
//     val motionDetect: Boolean? = null,
//     val flatUp: Boolean? = null,
//     val flatDown: Boolean? = null,
//     val stowed: Boolean? = null,
//     val displayRotate: Int? = null
// )

@Serializable
data class EventPacket(
    val deviceId: String,
    val matricula: String,  // Matrícula do operador
    val timestamp: Long,
    val eventType: String,
    val data: Map<String, String> = emptyMap()
)
