package com.aura.tracking.background

import android.content.Context
import android.util.Log
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.aura.tracking.logging.AuraLog
import com.aura.tracking.mqtt.MqttClientManager
import java.net.InetAddress
import java.util.concurrent.TimeUnit

/**
 * MqttReconnectWorker - Aggressive MQTT reconnection worker.
 * Tests network, DNS, and broker connectivity before attempting reconnect.
 */
class MqttReconnectWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    companion object {
        private const val TAG = "MqttReconnect"
        const val WORK_NAME = "mqtt_reconnect_periodic"

        fun schedule(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val request = PeriodicWorkRequestBuilder<MqttReconnectWorker>(
                repeatInterval = 5,
                repeatIntervalTimeUnit = TimeUnit.MINUTES,
                flexTimeInterval = 2,
                flexTimeIntervalUnit = TimeUnit.MINUTES
            )
                .setConstraints(constraints)
                .setBackoffCriteria(
                    BackoffPolicy.EXPONENTIAL,
                    30,
                    TimeUnit.SECONDS
                )
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.UPDATE,
                request
            )

            AuraLog.MQTT.i("MQTT reconnect worker scheduled (5min interval)")
        }

        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
            AuraLog.MQTT.i("MQTT reconnect worker cancelled")
        }
    }

    override suspend fun doWork(): Result {
        AuraLog.MQTT.d("MQTT reconnect check started")

        try {
            // Get MQTT client from service
            val mqttClient = TrackingForegroundService.getMqttClient()
            
            if (mqttClient == null) {
                AuraLog.MQTT.w("MQTT client not available (service not running?)")
                return Result.success()
            }

            // Already connected?
            if (mqttClient.isConnected.value) {
                AuraLog.MQTT.d("MQTT already connected - sending heartbeat")
                sendHeartbeat(mqttClient)
                return Result.success()
            }

            // Test network connectivity
            if (!testNetworkConnectivity()) {
                AuraLog.MQTT.w("Network connectivity test failed")
                return Result.retry()
            }

            // Test DNS resolution for MQTT host
            val mqttHost = getMqttHost()
            if (mqttHost != null && !testDnsResolution(mqttHost)) {
                AuraLog.MQTT.w("DNS resolution failed for $mqttHost")
                return Result.retry()
            }

            // Attempt reconnection
            AuraLog.MQTT.i("Attempting MQTT reconnection")
            mqttClient.reconnect()

            // Wait for connection
            kotlinx.coroutines.delay(5000)

            if (mqttClient.isConnected.value) {
                AuraLog.MQTT.i("MQTT reconnection successful!")
                
                // Trigger queue flush
                triggerQueueFlush()
                
                return Result.success()
            } else {
                AuraLog.MQTT.w("MQTT reconnection attempt did not succeed")
                return Result.retry()
            }

        } catch (e: Exception) {
            AuraLog.MQTT.e("MQTT reconnect worker failed", e)
            return Result.retry()
        }
    }

    private fun testNetworkConnectivity(): Boolean {
        return try {
            val connectivityManager = applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) 
                as android.net.ConnectivityManager
            
            val network = connectivityManager.activeNetwork
            val capabilities = connectivityManager.getNetworkCapabilities(network)
            
            val hasInternet = capabilities?.hasCapability(
                android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET
            ) == true
            
            AuraLog.MQTT.d("Network connectivity: $hasInternet")
            hasInternet
        } catch (e: Exception) {
            AuraLog.MQTT.e("Network check failed", e)
            false
        }
    }

    private fun testDnsResolution(host: String): Boolean {
        return try {
            val addresses = InetAddress.getAllByName(host)
            val resolved = addresses.isNotEmpty()
            AuraLog.MQTT.d("DNS resolution for $host: $resolved (${addresses.size} addresses)")
            resolved
        } catch (e: Exception) {
            AuraLog.MQTT.e("DNS resolution failed for $host", e)
            false
        }
    }

    private suspend fun getMqttHost(): String? {
        return try {
            val database = com.aura.tracking.data.room.AppDatabase.getInstance(applicationContext)
            database.configDao().getConfig()?.mqttHost
        } catch (e: Exception) {
            null
        }
    }

    private suspend fun sendHeartbeat(mqttClient: MqttClientManager) {
        try {
            val heartbeat = kotlinx.serialization.json.buildJsonObject {
                put("type", kotlinx.serialization.json.JsonPrimitive("heartbeat"))
                put("timestamp", kotlinx.serialization.json.JsonPrimitive(System.currentTimeMillis()))
                put("device", kotlinx.serialization.json.JsonPrimitive(android.os.Build.MODEL))
            }.toString()

            val database = com.aura.tracking.data.room.AppDatabase.getInstance(applicationContext)
            val config = database.configDao().getConfig()
            val deviceId = config?.deviceId ?: android.os.Build.MODEL
            
            val topic = "aura/tracking/$deviceId/heartbeat"
            mqttClient.publish(topic, heartbeat, qos = 0)
            
            AuraLog.MQTT.d("Heartbeat sent")
        } catch (e: Exception) {
            AuraLog.MQTT.e("Failed to send heartbeat", e)
        }
    }

    private fun triggerQueueFlush() {
        try {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val request = androidx.work.OneTimeWorkRequestBuilder<QueueFlushWorker>()
                .setConstraints(constraints)
                .build()

            WorkManager.getInstance(applicationContext).enqueue(request)
            AuraLog.MQTT.d("Queue flush triggered after reconnection")
        } catch (e: Exception) {
            AuraLog.MQTT.e("Failed to trigger queue flush", e)
        }
    }
}
