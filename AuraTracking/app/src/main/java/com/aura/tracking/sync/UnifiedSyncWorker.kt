package com.aura.tracking.sync

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.aura.tracking.AuraTrackingApp
import com.aura.tracking.data.room.AppDatabase
import com.aura.tracking.logging.AuraLog
import com.google.firebase.crashlytics.ktx.crashlytics
import com.google.firebase.ktx.Firebase
import java.util.concurrent.TimeUnit

/**
 * UnifiedSyncWorker - Worker único que substitui todos os workers de sync.
 *
 * Executa a cada 15 minutos e coordena:
 * - Download: Operators, Geofences, Equipment (Supabase → Room)
 * - Upload: Telemetry queue, Geofence events (Room → MQTT)
 *
 * Substitui:
 * - SyncDataWorker (download operators/equipment)
 * - ZoneSyncWorker (download geofences)
 * - QueueFlushWorker (upload telemetry)
 * - GeofenceEventFlushWorker (upload geofence events)
 */
class UnifiedSyncWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    companion object {
        /**
         * Agenda o worker periódico
         */
        fun schedule(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val request = PeriodicWorkRequestBuilder<UnifiedSyncWorker>(
                repeatInterval = SyncConfig.SYNC_INTERVAL_MINUTES,
                repeatIntervalTimeUnit = TimeUnit.MINUTES,
                flexTimeInterval = SyncConfig.SYNC_FLEX_INTERVAL_MINUTES,
                flexTimeIntervalUnit = TimeUnit.MINUTES
            )
                .setConstraints(constraints)
                .setBackoffCriteria(
                    BackoffPolicy.EXPONENTIAL,
                    30,
                    TimeUnit.SECONDS
                )
                .addTag(SyncConfig.WORK_TAG)
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                SyncConfig.WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request
            )

            AuraLog.Sync.i("UnifiedSyncWorker scheduled: every ${SyncConfig.SYNC_INTERVAL_MINUTES} min")
        }

        /**
         * Cancela o worker periódico
         */
        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(SyncConfig.WORK_NAME)
            AuraLog.Sync.i("UnifiedSyncWorker cancelled")
        }

        /**
         * Cancela workers antigos (deprecados)
         */
        fun cancelLegacyWorkers(context: Context) {
            val workManager = WorkManager.getInstance(context)

            // SyncDataWorker
            workManager.cancelUniqueWork("sync_data_worker")

            // ZoneSyncWorker
            workManager.cancelUniqueWork("zone_sync_periodic")

            // QueueFlushWorker
            workManager.cancelUniqueWork("queue_flush_periodic")

            // GeofenceEventFlushWorker
            workManager.cancelUniqueWork("geofence_event_flush_periodic")

            AuraLog.Sync.i("Legacy workers cancelled")
        }
    }

    override suspend fun doWork(): Result {
        AuraLog.Sync.i("UnifiedSyncWorker started (attempt $runAttemptCount)")

        // Usar lock para evitar sync concorrente
        val syncResult = SyncOrchestrator.withSyncLock {
            try {
                val database = AppDatabase.getInstance(applicationContext)
                val supabaseApi = AuraTrackingApp.supabaseApi

                val orchestrator = SyncOrchestrator(
                    context = applicationContext,
                    supabaseApi = supabaseApi,
                    database = database
                )

                orchestrator.syncAll()
            } catch (e: Exception) {
                AuraLog.Sync.e("UnifiedSyncWorker exception: ${e.message}")
                Firebase.crashlytics.apply {
                    log("UnifiedSyncWorker failed: ${e.message}")
                    recordException(e)
                }
                SyncResult.Error(e.message ?: "Unknown error")
            }
        }

        // Se lock não foi adquirido, outro sync está em andamento
        if (syncResult == null) {
            AuraLog.Sync.d("Sync already in progress, skipping this execution")
            return Result.success()
        }

        return when (syncResult) {
            is SyncResult.Success -> {
                AuraLog.Sync.i("Sync completed: ${syncResult.downloadedCount} downloaded, ${syncResult.uploadedCount} uploaded")
                Result.success()
            }

            is SyncResult.Partial -> {
                // Partial é OK - pelo menos uma fase funcionou
                AuraLog.Sync.w("Sync partial: download=${syncResult.downloadResult.javaClass.simpleName}, upload=${syncResult.uploadResult.javaClass.simpleName}")
                if (syncResult.downloadResult.isFailed && syncResult.uploadResult.isFailed) {
                    Result.retry()
                } else {
                    Result.success()
                }
            }

            is SyncResult.NoNetwork -> {
                AuraLog.Sync.d("No network, sync skipped")
                Result.success() // OK, tentará na próxima execução
            }

            is SyncResult.Error -> {
                AuraLog.Sync.e("Sync error: ${syncResult.message}")
                Result.retry()
            }
        }
    }
}
