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
import com.aura.tracking.data.model.Geofence
import com.aura.tracking.data.room.AppDatabase
import com.aura.tracking.data.room.ZoneEntity
import com.aura.tracking.AuraTrackingApp
import com.aura.tracking.logging.AuraLog
import java.util.concurrent.TimeUnit

/**
 * ZoneSyncWorker - Sincroniza zonas de geofencing com Supabase.
 *
 * Executa periodicamente para:
 * - Baixar novas zonas criadas no dashboard
 * - Atualizar zonas modificadas
 * - Remover zonas deletadas
 *
 * As zonas são armazenadas localmente no Room para
 * funcionamento offline do geofencing.
 */
class ZoneSyncWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    companion object {
        private const val TAG = "ZoneSyncWorker"
        const val WORK_NAME = "zone_sync_periodic"

        /**
         * Agenda o worker periódico
         */
        fun schedule(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val request = PeriodicWorkRequestBuilder<ZoneSyncWorker>(
                repeatInterval = 30,
                repeatIntervalTimeUnit = TimeUnit.MINUTES,
                flexTimeInterval = 10,
                flexTimeIntervalUnit = TimeUnit.MINUTES
            )
                .setConstraints(constraints)
                .setBackoffCriteria(
                    BackoffPolicy.EXPONENTIAL,
                    1,
                    TimeUnit.MINUTES
                )
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request
            )

            AuraLog.Geofence.i("Zone sync worker scheduled")
        }

        /**
         * Cancela o worker periódico
         */
        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
            AuraLog.Geofence.i("Zone sync worker cancelled")
        }
    }

    override suspend fun doWork(): Result {
        AuraLog.Geofence.i("Zone sync worker started")

        return try {
            val database = AppDatabase.getInstance(applicationContext)
            val zoneDao = database.zoneDao()
            val supabaseApi = AuraTrackingApp.supabaseApi

            // Obtém zonas do Supabase
            val result = supabaseApi.getGeofences()

            if (result.isFailure) {
                AuraLog.Geofence.e("Failed to fetch geofences: ${result.exceptionOrNull()?.message}")
                return Result.retry()
            }

            val remoteZones = result.getOrNull() ?: emptyList()

            if (remoteZones.isEmpty()) {
                AuraLog.Geofence.i("No zones found in Supabase")
                return Result.success()
            }

            // Converte para entidades Room
            val zoneEntities = remoteZones.map { it.toZoneEntity() }

            // Upsert todas as zonas
            zoneDao.upsertAll(zoneEntities)

            // Remove zonas que não existem mais no servidor
            val remoteIds = zoneEntities.map { it.id }
            zoneDao.deleteNotIn(remoteIds)

            AuraLog.Geofence.i("Zone sync complete: ${zoneEntities.size} zones synced")

            // Notifica o GeofenceManager para recarregar
            // (O serviço observa o Flow do zoneDao)

            Result.success()
        } catch (e: Exception) {
            AuraLog.Geofence.e("Zone sync failed: ${e.message}")
            Result.retry()
        }
    }

    /**
     * Extensão para converter Geofence do Supabase para ZoneEntity do Room
     */
    private fun Geofence.toZoneEntity(): ZoneEntity {
        return ZoneEntity(
            id = id,
            name = name,
            zoneType = zoneType,
            polygonJson = polygonJson,
            centerLat = null,  // Polígono usa polygonJson
            centerLon = null,
            radiusMeters = null,
            color = color,
            isActive = isActive,
            updatedAt = parseTimestamp(updatedAt),
            createdAt = parseTimestamp(createdAt)
        )
    }

    /**
     * Converte timestamp ISO do Supabase para milissegundos
     */
    private fun parseTimestamp(isoTimestamp: String?): Long {
        if (isoTimestamp == null) return System.currentTimeMillis()
        return try {
            java.time.Instant.parse(isoTimestamp).toEpochMilli()
        } catch (e: Exception) {
            System.currentTimeMillis()
        }
    }
}
