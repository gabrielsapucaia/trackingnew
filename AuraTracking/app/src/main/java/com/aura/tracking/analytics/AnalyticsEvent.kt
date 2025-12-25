package com.aura.tracking.analytics

import com.aura.tracking.mqtt.MqttClientManager.PublishFailureReason

/**
 * Sealed class representing analytics events for telemetry monitoring.
 * Each event type captures specific metrics for quality tracking.
 */
sealed class AnalyticsEvent {
    abstract val timestamp: Long

    /**
     * MQTT publish event - tracks message send success/failure
     */
    data class PublishEvent(
        override val timestamp: Long = System.currentTimeMillis(),
        val success: Boolean,
        val reason: PublishFailureReason? = null,
        val bytes: Int,
        val topic: String,
        val latencyMs: Long = 0
    ) : AnalyticsEvent()

    /**
     * Queue status event - tracks offline queue metrics
     */
    data class QueueEvent(
        override val timestamp: Long = System.currentTimeMillis(),
        val size: Int,
        val oldestAgeMs: Long,
        val action: QueueAction,
        val batchSize: Int = 0,
        val batchFailed: Int = 0
    ) : AnalyticsEvent()

    /**
     * MQTT connection event - tracks connection state changes
     */
    data class ConnectionEvent(
        override val timestamp: Long = System.currentTimeMillis(),
        val connected: Boolean,
        val host: String,
        val port: Int,
        val attemptNumber: Int = 0,
        val reconnectDelayMs: Long = 0
    ) : AnalyticsEvent()

    /**
     * Latency measurement event - tracks end-to-end timing
     */
    data class LatencyEvent(
        override val timestamp: Long = System.currentTimeMillis(),
        val stage: LatencyStage,
        val delayMs: Long
    ) : AnalyticsEvent()

    /**
     * Battery status event - tracks power consumption impact
     */
    data class BatteryEvent(
        override val timestamp: Long = System.currentTimeMillis(),
        val level: Int,
        val temperature: Float,
        val status: String,
        val isCharging: Boolean
    ) : AnalyticsEvent()
}

/**
 * Queue actions for tracking queue operations
 */
enum class QueueAction {
    ENQUEUE,        // Message added to offline queue
    FLUSH_START,    // Flush operation started
    FLUSH_SUCCESS,  // Flush batch completed successfully
    FLUSH_FAILED,   // Flush batch failed
    MAINTENANCE     // TTL/size maintenance performed
}

/**
 * Latency measurement stages in the telemetry pipeline
 */
enum class LatencyStage {
    GPS_AGE,            // T2 - T0: GNSS satellite time to app receipt
    HARDWARE_LATENCY,   // T2 - T1: FusedLocationProvider delay
    CHIPSET_LATENCY,    // T1 - T0: GNSS chip computation time
    PACKET_CREATION,    // T3 - T2: Building TelemetryPacket
    MQTT_PUBLISH,       // T4 - T3: MQTT publish operation
    END_TO_END          // T4 - T0: Total collection to send
}

/**
 * Queue trend indicator for UI display
 */
enum class QueueTrend {
    STABLE,     // Queue size relatively constant
    GROWING,    // Queue size increasing
    DRAINING,   // Queue size decreasing
    CRITICAL    // Queue at 95%+ capacity
}

/**
 * Aggregated metrics snapshot for reporting
 */
data class AnalyticsSnapshot(
    val timestamp: Long = System.currentTimeMillis(),

    // Publish metrics
    val publishSuccessCount: Long,
    val publishFailureCount: Long,
    val publishSuccessRate: Float,
    val avgPublishLatencyMs: Long,

    // Queue metrics
    val queueSize: Int,
    val queueOldestAgeMs: Long,
    val queueTrend: QueueTrend,
    val queueCapacityPercent: Float,

    // Connection metrics
    val mqttConnected: Boolean,
    val connectionUptimeMs: Long,
    val reconnectCount: Int,

    // Latency metrics (averages)
    val avgGpsAgeMs: Long,
    val avgEndToEndMs: Long,

    // Battery metrics
    val batteryLevel: Int,
    val batteryTemperature: Float
)
