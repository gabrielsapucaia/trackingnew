package com.aura.tracking.analytics

import com.aura.tracking.data.room.TelemetryQueueDao
import com.aura.tracking.logging.AuraLog
import com.aura.tracking.mqtt.MqttClientManager.PublishFailureReason
import com.google.firebase.crashlytics.ktx.crashlytics
import com.google.firebase.ktx.Firebase
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.atomic.AtomicLong

/**
 * TelemetryAnalytics - Sistema de métricas de qualidade de telemetria
 *
 * Monitora e reporta métricas críticas para o Firebase Crashlytics:
 * - Taxa de envio (sucesso/falha)
 * - Status da fila offline
 * - Uptime da conexão MQTT
 * - Latência end-to-end
 * - Impacto na bateria
 *
 * Padrão singleton, similar ao LatencyDiagnostics.
 * Todas as operações são assíncronas e não bloqueantes.
 */
object TelemetryAnalytics {

    private const val TAG = "TelemetryAnalytics"

    // Configuração
    private const val FLUSH_INTERVAL_MS = 60_000L        // Flush para Crashlytics a cada 60s
    private const val MAX_EVENTS_BUFFER = 1000           // Max eventos no buffer
    private const val LATENCY_SAMPLE_SIZE = 100          // Amostras para média de latência
    private const val QUEUE_HISTORY_SIZE = 60            // Histórico de 60 amostras para trend

    // Thresholds
    private const val QUEUE_WARNING_PERCENT = 80f
    private const val QUEUE_CRITICAL_PERCENT = 95f
    private const val MAX_QUEUE_SIZE = 3_000_000         // 3M mensagens

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    // === Contadores Atômicos ===
    private val publishSuccessCount = AtomicLong(0)
    private val publishFailureCount = AtomicLong(0)
    private val reconnectCount = AtomicLong(0)
    private val totalBytesPublished = AtomicLong(0)

    // === Buffers de Eventos ===
    private val eventBuffer = ConcurrentLinkedQueue<AnalyticsEvent>()
    private val latencySamples = ConcurrentLinkedQueue<Long>()
    private val queueSizeHistory = ConcurrentLinkedQueue<Int>()

    // === Estado da Conexão ===
    @Volatile
    private var mqttConnected = false
    @Volatile
    private var connectionStartTime = 0L
    @Volatile
    private var totalUptimeMs = 0L
    @Volatile
    private var sessionStartTime = System.currentTimeMillis()

    // === StateFlows para UI ===
    private val _snapshot = MutableStateFlow(createEmptySnapshot())
    val snapshot: StateFlow<AnalyticsSnapshot> = _snapshot.asStateFlow()

    private val _queueTrend = MutableStateFlow(QueueTrend.STABLE)
    val queueTrend: StateFlow<QueueTrend> = _queueTrend.asStateFlow()

    private val _successRate = MutableStateFlow(100f)
    val successRate: StateFlow<Float> = _successRate.asStateFlow()

    // === Habilitado/Desabilitado ===
    @Volatile
    var enabled: Boolean = true

    // === Inicialização ===
    private var initialized = false

    /**
     * Inicializa o sistema de analytics.
     * Deve ser chamado no Application.onCreate()
     */
    fun initialize() {
        if (initialized) return
        initialized = true

        AuraLog.Analytics.i("TelemetryAnalytics initialized")

        // Inicia loop de flush periódico para Crashlytics
        scope.launch {
            while (isActive) {
                delay(FLUSH_INTERVAL_MS)
                flushToCrashlytics()
            }
        }

        // Inicia loop de atualização de snapshot
        scope.launch {
            while (isActive) {
                delay(5_000) // Atualiza a cada 5s
                updateSnapshot()
            }
        }
    }

    // ========================================================
    // MÉTODOS DE REGISTRO DE EVENTOS
    // ========================================================

    /**
     * Registra publicação MQTT bem-sucedida
     */
    fun recordPublishSuccess(topic: String, bytes: Int, latencyMs: Long = 0) {
        if (!enabled) return

        publishSuccessCount.incrementAndGet()
        totalBytesPublished.addAndGet(bytes.toLong())

        if (latencyMs > 0) {
            recordLatencySample(latencyMs)
        }

        bufferEvent(AnalyticsEvent.PublishEvent(
            success = true,
            bytes = bytes,
            topic = topic,
            latencyMs = latencyMs
        ))

        updateSuccessRate()
    }

    /**
     * Registra falha de publicação MQTT
     */
    fun recordPublishFailure(reason: PublishFailureReason?, topic: String = "", bytes: Int = 0) {
        if (!enabled) return

        publishFailureCount.incrementAndGet()

        bufferEvent(AnalyticsEvent.PublishEvent(
            success = false,
            reason = reason,
            bytes = bytes,
            topic = topic
        ))

        updateSuccessRate()

        // Log de alerta para falhas frequentes
        val failures = publishFailureCount.get()
        if (failures % 10 == 0L) {
            AuraLog.Analytics.w("Publish failures: $failures total, reason: $reason")
        }
    }

    /**
     * Registra mudança de estado da conexão MQTT
     */
    fun recordConnectionChange(connected: Boolean, host: String = "", port: Int = 0, attemptNumber: Int = 0) {
        if (!enabled) return

        val now = System.currentTimeMillis()

        if (connected && !mqttConnected) {
            // Conectou
            connectionStartTime = now
            AuraLog.Analytics.i("MQTT connected to $host:$port")
        } else if (!connected && mqttConnected) {
            // Desconectou
            if (connectionStartTime > 0) {
                totalUptimeMs += (now - connectionStartTime)
            }
            reconnectCount.incrementAndGet()
            AuraLog.Analytics.w("MQTT disconnected, attempt #$attemptNumber")
        }

        mqttConnected = connected

        bufferEvent(AnalyticsEvent.ConnectionEvent(
            connected = connected,
            host = host,
            port = port,
            attemptNumber = attemptNumber
        ))
    }

    /**
     * Registra métricas da fila offline
     */
    fun recordQueueMetrics(size: Int, oldestTimestampMs: Long?, action: QueueAction = QueueAction.ENQUEUE) {
        if (!enabled) return

        val now = System.currentTimeMillis()
        val oldestAgeMs = oldestTimestampMs?.let { now - it } ?: 0L

        // Atualiza histórico para calcular trend
        queueSizeHistory.add(size)
        while (queueSizeHistory.size > QUEUE_HISTORY_SIZE) {
            queueSizeHistory.poll()
        }

        // Calcula trend
        updateQueueTrend(size)

        bufferEvent(AnalyticsEvent.QueueEvent(
            size = size,
            oldestAgeMs = oldestAgeMs,
            action = action
        ))

        // Alertas de threshold
        val capacityPercent = (size.toFloat() / MAX_QUEUE_SIZE) * 100
        when {
            capacityPercent >= QUEUE_CRITICAL_PERCENT -> {
                AuraLog.Analytics.e("Queue CRITICAL: $size messages (${capacityPercent.toInt()}%)")
            }
            capacityPercent >= QUEUE_WARNING_PERCENT -> {
                AuraLog.Analytics.w("Queue WARNING: $size messages (${capacityPercent.toInt()}%)")
            }
        }
    }

    /**
     * Registra resultado de flush da fila
     */
    fun recordQueueFlush(batchSize: Int, sent: Int, failed: Int, remainingSize: Int) {
        if (!enabled) return

        bufferEvent(AnalyticsEvent.QueueEvent(
            size = remainingSize,
            oldestAgeMs = 0,
            action = if (failed == 0) QueueAction.FLUSH_SUCCESS else QueueAction.FLUSH_FAILED,
            batchSize = batchSize,
            batchFailed = failed
        ))

        AuraLog.Analytics.i("Queue flush: sent=$sent, failed=$failed, remaining=$remainingSize")
    }

    /**
     * Registra amostra de latência
     */
    fun recordLatency(stage: LatencyStage, delayMs: Long) {
        if (!enabled) return

        if (stage == LatencyStage.END_TO_END) {
            recordLatencySample(delayMs)
        }

        bufferEvent(AnalyticsEvent.LatencyEvent(
            stage = stage,
            delayMs = delayMs
        ))
    }

    /**
     * Registra status da bateria
     */
    fun recordBatteryStatus(level: Int, temperature: Float, status: String, isCharging: Boolean) {
        if (!enabled) return

        bufferEvent(AnalyticsEvent.BatteryEvent(
            level = level,
            temperature = temperature,
            status = status,
            isCharging = isCharging
        ))
    }

    // ========================================================
    // MÉTODOS INTERNOS
    // ========================================================

    private fun bufferEvent(event: AnalyticsEvent) {
        eventBuffer.add(event)
        while (eventBuffer.size > MAX_EVENTS_BUFFER) {
            eventBuffer.poll()
        }
    }

    private fun recordLatencySample(latencyMs: Long) {
        latencySamples.add(latencyMs)
        while (latencySamples.size > LATENCY_SAMPLE_SIZE) {
            latencySamples.poll()
        }
    }

    private fun updateSuccessRate() {
        val success = publishSuccessCount.get()
        val failure = publishFailureCount.get()
        val total = success + failure

        _successRate.value = if (total > 0) {
            (success.toFloat() / total) * 100
        } else {
            100f
        }
    }

    private fun updateQueueTrend(currentSize: Int) {
        val history = queueSizeHistory.toList()
        if (history.size < 3) {
            _queueTrend.value = QueueTrend.STABLE
            return
        }

        val capacityPercent = (currentSize.toFloat() / MAX_QUEUE_SIZE) * 100
        if (capacityPercent >= QUEUE_CRITICAL_PERCENT) {
            _queueTrend.value = QueueTrend.CRITICAL
            return
        }

        // Calcula tendência baseado na diferença entre início e fim do histórico
        val oldAvg = history.take(history.size / 3).average()
        val newAvg = history.takeLast(history.size / 3).average()
        val diff = newAvg - oldAvg

        _queueTrend.value = when {
            diff > 100 -> QueueTrend.GROWING
            diff < -100 -> QueueTrend.DRAINING
            else -> QueueTrend.STABLE
        }
    }

    private fun updateSnapshot() {
        val success = publishSuccessCount.get()
        val failure = publishFailureCount.get()
        val total = success + failure

        val avgLatency = latencySamples.toList().let { samples ->
            if (samples.isEmpty()) 0L else samples.average().toLong()
        }

        val currentQueueSize = queueSizeHistory.lastOrNull() ?: 0

        // Calcula uptime atual
        val currentUptime = if (mqttConnected && connectionStartTime > 0) {
            totalUptimeMs + (System.currentTimeMillis() - connectionStartTime)
        } else {
            totalUptimeMs
        }

        _snapshot.value = AnalyticsSnapshot(
            publishSuccessCount = success,
            publishFailureCount = failure,
            publishSuccessRate = if (total > 0) (success.toFloat() / total) * 100 else 100f,
            avgPublishLatencyMs = avgLatency,
            queueSize = currentQueueSize,
            queueOldestAgeMs = 0, // Seria necessário consultar o DAO
            queueTrend = _queueTrend.value,
            queueCapacityPercent = (currentQueueSize.toFloat() / MAX_QUEUE_SIZE) * 100,
            mqttConnected = mqttConnected,
            connectionUptimeMs = currentUptime,
            reconnectCount = reconnectCount.get().toInt(),
            avgGpsAgeMs = 0, // Integrar com LatencyDiagnostics
            avgEndToEndMs = avgLatency,
            batteryLevel = 0, // Última leitura de bateria
            batteryTemperature = 0f
        )
    }

    /**
     * Flush das métricas para Firebase Crashlytics
     */
    private fun flushToCrashlytics() {
        if (!enabled) return

        try {
            val snap = _snapshot.value
            val sessionDurationMs = System.currentTimeMillis() - sessionStartTime

            Firebase.crashlytics.apply {
                // Métricas de publicação
                setCustomKey("analytics_publish_success", snap.publishSuccessCount)
                setCustomKey("analytics_publish_failure", snap.publishFailureCount)
                setCustomKey("analytics_success_rate", snap.publishSuccessRate)
                setCustomKey("analytics_total_bytes", totalBytesPublished.get())

                // Métricas de fila
                setCustomKey("analytics_queue_size", snap.queueSize)
                setCustomKey("analytics_queue_capacity_pct", snap.queueCapacityPercent)
                setCustomKey("analytics_queue_trend", snap.queueTrend.name)

                // Métricas de conexão
                setCustomKey("analytics_mqtt_connected", snap.mqttConnected)
                setCustomKey("analytics_reconnect_count", snap.reconnectCount)
                setCustomKey("analytics_uptime_ms", snap.connectionUptimeMs)

                // Calcular uptime percentual
                if (sessionDurationMs > 0) {
                    val uptimePercent = (snap.connectionUptimeMs.toFloat() / sessionDurationMs) * 100
                    setCustomKey("analytics_uptime_pct", uptimePercent)
                }

                // Métricas de latência
                setCustomKey("analytics_avg_latency_ms", snap.avgPublishLatencyMs)

                // Log breadcrumb
                log("Analytics flush: success=${snap.publishSuccessCount}, " +
                    "fail=${snap.publishFailureCount}, " +
                    "queue=${snap.queueSize}, " +
                    "uptime=${snap.connectionUptimeMs}ms")

                // Registra non-fatal para garantir que custom keys apareçam no console
                // Isso envia as métricas para o Firebase sem causar crash
                recordException(TelemetryHeartbeat(
                    "rate=${snap.publishSuccessRate.toInt()}% " +
                    "queue=${snap.queueSize} " +
                    "uptime=${snap.connectionUptimeMs/1000}s"
                ))
            }

            AuraLog.Analytics.d("Crashlytics flush: rate=${snap.publishSuccessRate}%, queue=${snap.queueSize}")

        } catch (e: Exception) {
            AuraLog.Analytics.e("Crashlytics flush failed: ${e.message}")
        }
    }

    // ========================================================
    // MÉTODOS PÚBLICOS DE CONSULTA
    // ========================================================

    /**
     * Retorna estatísticas atuais
     */
    fun getStats(): AnalyticsSnapshot = _snapshot.value

    /**
     * Retorna taxa de sucesso atual
     */
    fun getSuccessRate(): Float = _successRate.value

    /**
     * Retorna se está conectado
     */
    fun isConnected(): Boolean = mqttConnected

    /**
     * Retorna contagem de publicações bem-sucedidas
     */
    fun getPublishSuccessCount(): Long = publishSuccessCount.get()

    /**
     * Retorna contagem de falhas
     */
    fun getPublishFailureCount(): Long = publishFailureCount.get()

    /**
     * Reseta contadores (para testes ou nova sessão)
     */
    fun reset() {
        publishSuccessCount.set(0)
        publishFailureCount.set(0)
        reconnectCount.set(0)
        totalBytesPublished.set(0)
        totalUptimeMs = 0
        connectionStartTime = 0
        sessionStartTime = System.currentTimeMillis()
        eventBuffer.clear()
        latencySamples.clear()
        queueSizeHistory.clear()
        _snapshot.value = createEmptySnapshot()
        _queueTrend.value = QueueTrend.STABLE
        _successRate.value = 100f

        AuraLog.Analytics.i("TelemetryAnalytics reset")
    }

    private fun createEmptySnapshot() = AnalyticsSnapshot(
        publishSuccessCount = 0,
        publishFailureCount = 0,
        publishSuccessRate = 100f,
        avgPublishLatencyMs = 0,
        queueSize = 0,
        queueOldestAgeMs = 0,
        queueTrend = QueueTrend.STABLE,
        queueCapacityPercent = 0f,
        mqttConnected = false,
        connectionUptimeMs = 0,
        reconnectCount = 0,
        avgGpsAgeMs = 0,
        avgEndToEndMs = 0,
        batteryLevel = 100,
        batteryTemperature = 25f
    )
}

/**
 * Exception não-fatal usada como "heartbeat" para enviar métricas ao Firebase.
 * Aparece no Crashlytics como issue não-fatal com as custom keys atualizadas.
 */
class TelemetryHeartbeat(message: String) : Exception("Telemetry: $message") {
    override fun fillInStackTrace(): Throwable = this // Evita overhead de stacktrace
}
