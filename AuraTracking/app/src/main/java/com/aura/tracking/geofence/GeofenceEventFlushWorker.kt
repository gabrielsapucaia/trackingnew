package com.aura.tracking.geofence

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.aura.tracking.background.TrackingForegroundService
import com.aura.tracking.data.room.AppDatabase
import com.aura.tracking.data.room.GeofenceEventEntity
import com.aura.tracking.logging.AuraLog
import kotlinx.coroutines.delay
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.concurrent.TimeUnit

/**
 * GeofenceEventFlushWorker - Envia eventos de geofencing pendentes via MQTT.
 *
 * Executa periodicamente para garantir que eventos de entrada/saída
 * sejam enviados ao servidor mesmo se o MQTT estava offline no momento.
 */
class GeofenceEventFlushWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    companion object {
        private const val TAG = "GeofenceEventFlush"
        const val WORK_NAME = "geofence_event_flush_periodic"
        private const val BATCH_SIZE = 50
        private const val MAX_EVENTS_PER_EXECUTION = 500

        /**
         * Agenda o worker periódico
         */
        fun schedule(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val request = PeriodicWorkRequestBuilder<GeofenceEventFlushWorker>(
                repeatInterval = 15,
                repeatIntervalTimeUnit = TimeUnit.MINUTES,
                flexTimeInterval = 5,
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
                ExistingPeriodicWorkPolicy.KEEP,
                request
            )

            AuraLog.Geofence.i("Geofence event flush worker scheduled")
        }

        /**
         * Cancela o worker periódico
         */
        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
            AuraLog.Geofence.i("Geofence event flush worker cancelled")
        }
    }

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    override suspend fun doWork(): Result {
        AuraLog.Geofence.i("Geofence event flush worker started")

        return try {
            val database = AppDatabase.getInstance(applicationContext)
            val eventDao = database.geofenceEventDao()

            // Verifica se há eventos pendentes
            val unsentCount = eventDao.getUnsentCount()
            if (unsentCount == 0) {
                AuraLog.Geofence.d("No pending geofence events")
                return Result.success()
            }

            AuraLog.Geofence.i("Found $unsentCount pending geofence events")

            // Obtém cliente MQTT
            val mqttClient = TrackingForegroundService.getMqttClient()
            if (mqttClient == null) {
                AuraLog.Geofence.w("MQTT client not available")
                return Result.retry()
            }

            if (!mqttClient.isConnected.value) {
                AuraLog.Geofence.w("MQTT not connected")
                return Result.retry()
            }

            // Obtém configuração para topic
            val config = database.configDao().getConfig()
            val deviceId = config?.equipmentName ?: "unknown"
            val baseTopic = "aura/tracking/$deviceId/geofence"

            var totalSent = 0
            var totalFailed = 0

            // Processa em batches
            while (totalSent + totalFailed < MAX_EVENTS_PER_EXECUTION) {
                val events = eventDao.getUnsentEvents(BATCH_SIZE)
                if (events.isEmpty()) break

                for (event in events) {
                    if (!mqttClient.isConnected.value) {
                        AuraLog.Geofence.w("MQTT disconnected during flush")
                        break
                    }

                    val payload = createPayload(event)
                    val success = mqttClient.publish(baseTopic, payload, qos = 1)

                    if (success) {
                        eventDao.markSent(event.id)
                        totalSent++
                    } else {
                        eventDao.incrementRetry(event.id)
                        totalFailed++
                    }
                }

                // Pequena pausa entre batches
                delay(50)
            }

            AuraLog.Geofence.i("Geofence flush complete: sent=$totalSent, failed=$totalFailed")

            // Limpa eventos antigos já enviados (mais de 7 dias)
            val cutoff = System.currentTimeMillis() - (7 * 24 * 60 * 60 * 1000L)
            eventDao.deleteSentOlderThan(cutoff)

            if (totalFailed > 0 && totalSent == 0) {
                Result.retry()
            } else {
                Result.success()
            }
        } catch (e: Exception) {
            AuraLog.Geofence.e("Geofence event flush failed: ${e.message}")
            Result.retry()
        }
    }

    /**
     * Cria payload JSON para evento de geofencing
     */
    private fun createPayload(event: GeofenceEventEntity): String {
        val payload = GeofenceEventPayload(
            eventId = event.eventId,
            zoneId = event.zoneId,
            zoneName = event.zoneName,
            zoneType = event.zoneType,
            eventType = event.eventType,
            durationSeconds = event.durationSeconds,
            latitude = event.latitude,
            longitude = event.longitude,
            gpsAccuracy = event.gpsAccuracy,
            speed = event.speed,
            deviceId = event.deviceId,
            operatorId = event.operatorId,
            timestamp = event.timestamp
        )
        return json.encodeToString(payload)
    }

    @Serializable
    data class GeofenceEventPayload(
        val eventId: String,
        val zoneId: Long,
        val zoneName: String,
        val zoneType: String,
        val eventType: String,
        val durationSeconds: Int,
        val latitude: Double,
        val longitude: Double,
        val gpsAccuracy: Float,
        val speed: Float,
        val deviceId: String,
        val operatorId: String,
        val timestamp: Long
    )
}
