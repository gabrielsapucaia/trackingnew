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
import com.aura.tracking.data.room.AppDatabase
import com.aura.tracking.data.room.ZoneEntity
import com.aura.tracking.data.supabase.SupabaseApi
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
            val remoteZones = fetchZonesFromSupabase(supabaseApi)

            if (remoteZones.isEmpty()) {
                AuraLog.Geofence.i("No zones found in Supabase")
                return Result.success()
            }

            // Converte para entidades Room
            val zoneEntities = remoteZones.map { it.toEntity() }

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
     * Busca zonas do Supabase
     *
     * TODO: Implementar endpoint real no SupabaseApi
     * Por enquanto retorna lista vazia (zonas serão criadas manualmente)
     */
    private suspend fun fetchZonesFromSupabase(api: SupabaseApi): List<RemoteZone> {
        // TODO: Implementar chamada real ao Supabase
        // return api.getZones()
        return emptyList()
    }

    /**
     * Representa uma zona do Supabase
     */
    data class RemoteZone(
        val id: Long,
        val name: String,
        val zoneType: String,
        val polygonJson: String? = null,
        val centerLat: Double? = null,
        val centerLon: Double? = null,
        val radiusMeters: Float? = null,
        val color: String = "#4CAF50",
        val isActive: Boolean = true,
        val updatedAt: Long = System.currentTimeMillis(),
        val createdAt: Long = System.currentTimeMillis()
    ) {
        fun toEntity(): ZoneEntity = ZoneEntity(
            id = id,
            name = name,
            zoneType = zoneType,
            polygonJson = polygonJson,
            centerLat = centerLat,
            centerLon = centerLon,
            radiusMeters = radiusMeters,
            color = color,
            isActive = isActive,
            updatedAt = updatedAt,
            createdAt = createdAt
        )
    }
}
