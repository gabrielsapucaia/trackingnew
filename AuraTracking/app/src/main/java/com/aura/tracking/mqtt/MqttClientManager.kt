package com.aura.tracking.mqtt

import android.content.Context
import com.aura.tracking.logging.AuraLog
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.eclipse.paho.client.mqttv3.IMqttActionListener
import org.eclipse.paho.client.mqttv3.IMqttDeliveryToken
import org.eclipse.paho.client.mqttv3.IMqttToken
import org.eclipse.paho.client.mqttv3.MqttAsyncClient
import org.eclipse.paho.client.mqttv3.MqttCallback
import org.eclipse.paho.client.mqttv3.MqttConnectOptions
import org.eclipse.paho.client.mqttv3.MqttException
import org.eclipse.paho.client.mqttv3.MqttMessage
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence
import kotlin.coroutines.resume
import kotlin.coroutines.suspendCoroutine

/**
 * MqttClientManager - Manages MQTT connection using Eclipse Paho client.
 * 
 * FASE 3: Implementação industrial:
 * - MemoryPersistence (Room DB já faz persistência offline)
 * - Heartbeat a cada 30s
 * - QoS 1 com retry
 * - Exponential backoff com jitter
 * - Logging persistente
 * 
 * NOTA: Usamos MemoryPersistence em vez de FilePersistence para evitar
 * duplicatas. A fila Room (TelemetryQueueDao) já garante persistência
 * offline, então não precisamos de 2 sistemas de persistência.
 */
class MqttClientManager(private val context: Context) {

    companion object {
        private const val TAG = "MqttClientManager"

        const val DEFAULT_HOST = "localhost"
        const val DEFAULT_PORT = 1883
        const val DEFAULT_TOPIC = "aura/tracking"
        
        private const val CONNECTION_TIMEOUT = 30
        private const val KEEP_ALIVE_INTERVAL = 30 // 30 segundos heartbeat
        private const val MAX_RECONNECT_DELAY = 120_000L // 2 min max
        private const val MAX_INFLIGHT = 50 // Max mensagens em voo
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    
    // MQTT Client
    private var mqttClient: MqttAsyncClient? = null
    
    // Estado reativo de conexão
    private val _isConnected = MutableStateFlow(false)
    val isConnected: StateFlow<Boolean> = _isConnected.asStateFlow()

    // Configuration
    private var host: String = DEFAULT_HOST
    private var port: Int = DEFAULT_PORT
    private var baseTopic: String = DEFAULT_TOPIC
    private var clientId: String = "aura_${android.os.Build.MODEL}_${System.currentTimeMillis()}"
    private var username: String? = null
    private var password: String? = null
    
    // Reconnect state
    private var reconnectAttempts = 0
    private var shouldReconnect = true
    
    // Estatísticas
    private var messagesPublished: Long = 0L
    private var messagesFailed: Long = 0L
    private var lastPublishTimestamp: Long = 0L

    // Listeners
    var onConnectionStatusChange: ((Boolean) -> Unit)? = null
    var onMessageDelivered: ((String) -> Unit)? = null
    var onError: ((Exception) -> Unit)? = null

    /**
     * Configure the MQTT client.
     */
    fun configure(
        host: String, 
        port: Int, 
        topic: String = DEFAULT_TOPIC,
        username: String? = null,
        password: String? = null
    ) {
        AuraLog.MQTT.i("Configuring MQTT: $host:$port, topic: $topic")
        this.host = host
        this.port = port
        this.baseTopic = topic
        this.username = username
        this.password = password
    }

    /**
     * Connect to the MQTT broker with automatic reconnection.
     */
    fun connect() {
        if (_isConnected.value) {
            AuraLog.MQTT.d("Already connected")
            return
        }

        shouldReconnect = true
        scope.launch {
            connectInternal()
        }
    }

    private suspend fun connectInternal() {
        try {
            AuraLog.MQTT.i("Connecting to MQTT broker: tcp://$host:$port")

            // Fecha cliente existente se houver
            mqttClient?.let {
                try {
                    if (it.isConnected) it.disconnect()
                    it.close()
                } catch (e: Exception) {
                    AuraLog.MQTT.w("Error closing old client: ${e.message}")
                }
            }

            val serverUri = "tcp://$host:$port"
            
            // Usa MemoryPersistence para evitar duplicatas
            // A fila Room (TelemetryQueueDao) já garante persistência offline
            // Não precisamos de FilePersistence que causava reenvio duplo
            val memoryPersistence = MemoryPersistence()
            mqttClient = MqttAsyncClient(serverUri, clientId, memoryPersistence)
            
            mqttClient?.setCallback(object : MqttCallback {
                override fun connectionLost(cause: Throwable?) {
                    AuraLog.MQTT.w("Connection lost: ${cause?.message}")
                    _isConnected.value = false
                    onConnectionStatusChange?.invoke(false)
                    
                    if (shouldReconnect) {
                        scope.launch { scheduleReconnect() }
                    }
                }

                override fun messageArrived(topic: String?, message: MqttMessage?) {
                    AuraLog.MQTT.d("Message arrived on $topic: ${message?.toString()}")
                }

                override fun deliveryComplete(token: IMqttDeliveryToken?) {
                    messagesPublished++
                    lastPublishTimestamp = System.currentTimeMillis()
                    AuraLog.MQTT.d("Delivery complete: ${token?.messageId}")
                }
            })

            val options = MqttConnectOptions().apply {
                isCleanSession = false // Manter sessão para QoS 1
                isAutomaticReconnect = false // Gerenciamos manualmente
                connectionTimeout = CONNECTION_TIMEOUT
                keepAliveInterval = KEEP_ALIVE_INTERVAL
                maxInflight = MAX_INFLIGHT
                this@MqttClientManager.username?.let { userName = it }
                this@MqttClientManager.password?.let { setPassword(it.toCharArray()) }
            }

            val connected = suspendCoroutine<Boolean> { cont ->
                mqttClient?.connect(options, null, object : IMqttActionListener {
                    override fun onSuccess(asyncActionToken: IMqttToken?) {
                        AuraLog.MQTT.i("MQTT connected successfully")
                        cont.resume(true)
                    }

                    override fun onFailure(asyncActionToken: IMqttToken?, exception: Throwable?) {
                        AuraLog.MQTT.e("MQTT connection failed: ${exception?.message}")
                        cont.resume(false)
                    }
                })
            }

            if (connected) {
                _isConnected.value = true
                reconnectAttempts = 0
                onConnectionStatusChange?.invoke(true)
                AuraLog.MQTT.i("MQTT connected to $host:$port")
            } else {
                scheduleReconnect()
            }

        } catch (e: MqttException) {
            AuraLog.MQTT.e("MQTT connection error: ${e.message}")
            onError?.invoke(e)
            scheduleReconnect()
        } catch (e: Exception) {
            AuraLog.MQTT.e("Unexpected error: ${e.message}")
            onError?.invoke(e)
            scheduleReconnect()
        }
    }

    private suspend fun scheduleReconnect() {
        if (!shouldReconnect) return
        
        reconnectAttempts++
        // Exponential backoff com jitter: base * 2^attempt + random jitter
        val baseDelay = 1000L * (1 shl minOf(reconnectAttempts, 7))
        val jitter = (Math.random() * 1000).toLong()
        val delayMs = minOf(baseDelay + jitter, MAX_RECONNECT_DELAY)
        
        AuraLog.MQTT.i("Scheduling reconnect attempt $reconnectAttempts in ${delayMs}ms")
        delay(delayMs)
        
        if (shouldReconnect && !_isConnected.value) {
            connectInternal()
        }
    }

    /**
     * Disconnect from the MQTT broker.
     */
    fun disconnect() {
        AuraLog.MQTT.i("Disconnecting from MQTT broker")
        shouldReconnect = false
        
        scope.launch {
            try {
                mqttClient?.let { client ->
                    try {
                        if (client.isConnected) {
                            AuraLog.MQTT.d("Client is connected, disconnecting...")
                            suspendCoroutine<Unit> { cont ->
                                client.disconnect(null, object : IMqttActionListener {
                                    override fun onSuccess(asyncActionToken: IMqttToken?) {
                                        AuraLog.MQTT.d("Disconnect successful")
                                        cont.resume(Unit)
                                    }
                                    override fun onFailure(asyncActionToken: IMqttToken?, exception: Throwable?) {
                                        AuraLog.MQTT.w("Disconnect failed: ${exception?.message}, closing anyway")
                                        cont.resume(Unit)
                                    }
                                })
                            }
                        } else {
                            AuraLog.MQTT.d("Client not connected, skipping disconnect")
                        }
                    } catch (e: MqttException) {
                        AuraLog.MQTT.w("MqttException during disconnect: ${e.message}, closing anyway")
                    } catch (e: Exception) {
                        AuraLog.MQTT.w("Exception during disconnect: ${e.message}, closing anyway")
                    }
                    
                    try {
                        client.close()
                        AuraLog.MQTT.d("Client closed")
                    } catch (e: Exception) {
                        AuraLog.MQTT.w("Error closing client: ${e.message}")
                    }
                }
            } catch (e: Exception) {
                AuraLog.MQTT.e("Error disconnecting: ${e.message}")
            }
            
            mqttClient = null
            _isConnected.value = false
            onConnectionStatusChange?.invoke(false)
            AuraLog.MQTT.i("MQTT disconnected")
        }
    }

    /**
     * Publish a message to a topic.
     * @return true se a mensagem foi enviada com sucesso
     */
    suspend fun publish(topic: String, payload: String, qos: Int = 1, retained: Boolean = false): Boolean {
        return publishWithResult(topic, payload, qos, retained).success
    }

    /**
     * Publish a message and return a detailed result (used for backpressure handling).
     */
    suspend fun publishWithResult(
        topic: String,
        payload: String,
        qos: Int = 1,
        retained: Boolean = false
    ): PublishResult {
        val client = mqttClient
        if (client == null || !client.isConnected) {
            AuraLog.MQTT.w("Cannot publish - not connected")
            messagesFailed++
            return PublishResult(success = false, failureReason = PublishFailureReason.NOT_CONNECTED)
        }

        return try {
            val message = MqttMessage(payload.toByteArray(Charsets.UTF_8)).apply {
                this.qos = qos
                isRetained = retained
            }

            suspendCoroutine<PublishResult> { cont ->
                client.publish(topic, message, null, object : IMqttActionListener {
                    override fun onSuccess(asyncActionToken: IMqttToken?) {
                        AuraLog.MQTT.d("Published to $topic (${payload.length} bytes)")
                        onMessageDelivered?.invoke(topic)
                        cont.resume(PublishResult(success = true))
                    }

                    override fun onFailure(asyncActionToken: IMqttToken?, exception: Throwable?) {
                        AuraLog.MQTT.e("Publish failed: ${exception?.message}")
                        messagesFailed++
                        val reason = mapFailureReason(exception)
                        cont.resume(PublishResult(success = false, failureReason = reason))
                    }
                })
            }
        } catch (e: MqttException) {
            AuraLog.MQTT.e("Publish error: ${e.message}")
            messagesFailed++
            onError?.invoke(e)
            PublishResult(
                success = false,
                failureReason = mapFailureReason(e)
            )
        }
    }

    /**
     * Publish telemetry data (fire-and-forget).
     */
    fun publishTelemetryAsync(payload: String) {
        scope.launch {
            publish("$baseTopic/telemetry", payload, qos = 1, retained = false)
        }
    }

    /**
     * Publish device status.
     */
    fun publishStatusAsync(payload: String) {
        scope.launch {
            publish("$baseTopic/status", payload, qos = 1, retained = true)
        }
    }

    /**
     * Get the full topic path for a subtopic.
     */
    fun getFullTopic(subtopic: String): String = "$baseTopic/$subtopic"
    
    /**
     * Force reconnect.
     */
    fun reconnect() {
        AuraLog.MQTT.i("Force reconnect requested")
        scope.launch {
            _isConnected.value = false
            reconnectAttempts = 0
            connectInternal()
        }
    }
    
    /**
     * Estatísticas de publicação
     */
    fun getMessagesPublished(): Long = messagesPublished
    fun getMessagesFailed(): Long = messagesFailed
    fun getReconnectAttempts(): Int = reconnectAttempts
    fun getLastPublishTimestamp(): Long = lastPublishTimestamp

    data class PublishResult(
        val success: Boolean,
        val failureReason: PublishFailureReason? = null
    )

    enum class PublishFailureReason {
        NOT_CONNECTED,
        MAX_INFLIGHT,
        TIMEOUT,
        UNKNOWN
    }

    private fun mapFailureReason(exception: Throwable?): PublishFailureReason? {
        val mqttException = exception as? MqttException
        return when (mqttException?.reasonCode) {
            MqttException.REASON_CODE_MAX_INFLIGHT.toInt() -> PublishFailureReason.MAX_INFLIGHT
            MqttException.REASON_CODE_CLIENT_TIMEOUT.toInt(),
            MqttException.REASON_CODE_NO_MESSAGE_IDS_AVAILABLE.toInt() -> PublishFailureReason.TIMEOUT
            else -> mqttException?.let { PublishFailureReason.UNKNOWN }
        }
    }
}
