package com.aura.tracking.background

import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.aura.tracking.AuraTrackingApp
import com.aura.tracking.R
import com.aura.tracking.data.room.AppDatabase
import com.aura.tracking.logging.AuraLog
import java.util.concurrent.TimeUnit

/**
 * ServiceWatchdogWorker - Industrial-grade service monitoring.
 * Runs every 15 minutes to ensure telemetry service health.
 * Auto-restarts service if anomalies detected.
 */
class ServiceWatchdogWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    companion object {
        private const val TAG = "Watchdog"
        const val WORK_NAME = "service_watchdog_periodic"
        
        // Thresholds - mais tolerantes para dar tempo do GPS fazer fix
        private const val GPS_TIMEOUT_MS = 120_000L     // 2 minutos sem GPS (primeiro fix pode demorar)
        private const val IMU_TIMEOUT_MS = 60_000L      // 1 minuto sem IMU
        private const val MQTT_TIMEOUT_MS = 60_000L     // 1 minuto sem MQTT
        private const val MAX_QUEUE_SIZE = 5_000        // Warning threshold
        
        // Notification
        private const val WATCHDOG_NOTIFICATION_ID = 2001

        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<ServiceWatchdogWorker>(
                repeatInterval = 15,
                repeatIntervalTimeUnit = TimeUnit.MINUTES,
                flexTimeInterval = 5,
                flexTimeIntervalUnit = TimeUnit.MINUTES
            )
                .setBackoffCriteria(
                    BackoffPolicy.LINEAR,
                    30,
                    TimeUnit.SECONDS
                )
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.UPDATE,
                request
            )

            AuraLog.Watchdog.i("Watchdog worker scheduled (15min interval)")
        }

        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
            AuraLog.Watchdog.i("Watchdog worker cancelled")
        }
    }

    override suspend fun doWork(): Result {
        AuraLog.Watchdog.d("Watchdog check started")

        val issues = mutableListOf<String>()
        var requiresRestart = false

        try {
            // 1. Check if service is running
            if (!TrackingForegroundService.isRunning) {
                issues.add("Service not running")
                requiresRestart = true
                AuraLog.Watchdog.w("Service is NOT running")
            } else {
                AuraLog.Watchdog.d("Service is running ✓")
            }

            // 2. Check WakeLock status
            val wakeLockHeld = checkWakeLock()
            if (!wakeLockHeld) {
                issues.add("WakeLock not held")
                AuraLog.Watchdog.w("WakeLock is NOT held")
            } else {
                AuraLog.Watchdog.d("WakeLock is held ✓")
            }

            // 3. Check GPS activity
            val lastGpsTime = TrackingForegroundService.lastGpsData.value?.timestamp ?: 0
            val gpsSilence = System.currentTimeMillis() - lastGpsTime
            if (TrackingForegroundService.isRunning && gpsSilence > GPS_TIMEOUT_MS && lastGpsTime > 0) {
                issues.add("GPS silent for ${gpsSilence / 1000}s")
                AuraLog.Watchdog.w("GPS has been silent for ${gpsSilence / 1000}s")
            } else if (lastGpsTime > 0) {
                AuraLog.Watchdog.d("GPS active (last: ${gpsSilence / 1000}s ago) ✓")
            }

            // 4. Check IMU activity
            val lastImuTime = TrackingForegroundService.lastImuData.value?.timestamp ?: 0
            val imuSilence = System.currentTimeMillis() - lastImuTime
            if (TrackingForegroundService.isRunning && imuSilence > IMU_TIMEOUT_MS && lastImuTime > 0) {
                issues.add("IMU silent for ${imuSilence / 1000}s")
                AuraLog.Watchdog.w("IMU has been silent for ${imuSilence / 1000}s")
            } else if (lastImuTime > 0) {
                AuraLog.Watchdog.d("IMU active (last: ${imuSilence / 1000}s ago) ✓")
            }

            // 5. Check MQTT status
            val mqttConnected = TrackingForegroundService.mqttConnected.value
            if (TrackingForegroundService.isRunning && !mqttConnected) {
                issues.add("MQTT disconnected")
                AuraLog.Watchdog.w("MQTT is disconnected")
            } else if (mqttConnected) {
                AuraLog.Watchdog.d("MQTT connected ✓")
            }

            // 6. Check queue size
            val database = AppDatabase.getInstance(applicationContext)
            val queueSize = database.telemetryQueueDao().getCount()
            if (queueSize > MAX_QUEUE_SIZE) {
                issues.add("Queue size: $queueSize (high)")
                AuraLog.Watchdog.w("Queue size is high: $queueSize messages")
            } else {
                AuraLog.Watchdog.d("Queue size: $queueSize ✓")
            }

            // 7. Check battery optimization
            val powerManager = applicationContext.getSystemService(Context.POWER_SERVICE) as PowerManager
            val ignoringOptimizations = powerManager.isIgnoringBatteryOptimizations(applicationContext.packageName)
            if (!ignoringOptimizations) {
                issues.add("Battery optimizations not disabled")
                AuraLog.Watchdog.w("App is NOT ignoring battery optimizations")
            }

            // Take action if needed
            if (requiresRestart) {
                restartService()
                showNotification("Service Restarted", "Watchdog detected service was stopped and restarted it.")
            } else if (issues.isNotEmpty()) {
                AuraLog.Watchdog.w("Watchdog found ${issues.size} issues: ${issues.joinToString(", ")}")
                // Apenas loga os problemas, não reinicia agressivamente
                // O GPS pode demorar para fazer o primeiro fix
            } else {
                AuraLog.Watchdog.i("Watchdog check passed - all systems nominal ✓")
            }

            return Result.success()

        } catch (e: Exception) {
            AuraLog.Watchdog.e("Watchdog check failed", e)
            return Result.retry()
        }
    }

    private fun checkWakeLock(): Boolean {
        // We can't directly check WakeLock status, but we can infer from service state
        return TrackingForegroundService.isRunning
    }

    private fun restartService() {
        AuraLog.Watchdog.i("Restarting TrackingForegroundService")
        
        try {
            // Stop service if running
            val stopIntent = Intent(applicationContext, TrackingForegroundService::class.java)
            applicationContext.stopService(stopIntent)
            
            // Wait a moment
            Thread.sleep(1000)
            
            // Start service
            val startIntent = Intent(applicationContext, TrackingForegroundService::class.java)
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                applicationContext.startForegroundService(startIntent)
            } else {
                applicationContext.startService(startIntent)
            }
            
            AuraLog.Watchdog.i("Service restart initiated")
        } catch (e: Exception) {
            AuraLog.Watchdog.e("Failed to restart service", e)
        }
    }

    private fun showNotification(title: String, message: String) {
        try {
            val notification = NotificationCompat.Builder(applicationContext, AuraTrackingApp.NOTIFICATION_CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_notification)
                .setContentTitle(title)
                .setContentText(message)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .setAutoCancel(true)
                .build()

            val notificationManager = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.notify(WATCHDOG_NOTIFICATION_ID, notification)
        } catch (e: Exception) {
            AuraLog.Watchdog.e("Failed to show notification", e)
        }
    }
}
