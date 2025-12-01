package com.aura.tracking.background

import android.content.Context
import android.util.Log
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.aura.tracking.AuraTrackingApp
import java.util.concurrent.TimeUnit

/**
 * SyncDataWorker - Sincroniza dados do Supabase a cada hora quando há WiFi.
 * Sincroniza operadores, tipos de equipamento e equipamentos.
 */
class SyncDataWorker(
    context: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(context, workerParams) {

    companion object {
        private const val TAG = "SyncDataWorker"
        const val WORK_NAME = "sync_data_worker"

        /**
         * Agenda sincronização a cada hora com WiFi
         */
        fun schedule(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.UNMETERED) // WiFi
                .build()

            val syncWork = PeriodicWorkRequestBuilder<SyncDataWorker>(
                1, TimeUnit.HOURS // A cada hora
            )
                .setConstraints(constraints)
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                syncWork
            )

            Log.i(TAG, "SyncDataWorker scheduled: every 1 hour with WiFi")
        }

        /**
         * Cancela sincronização
         */
        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
            Log.i(TAG, "SyncDataWorker cancelled")
        }
    }

    override suspend fun doWork(): Result {
        Log.i(TAG, "Starting data synchronization...")

        return try {
            val supabaseApi = AuraTrackingApp.supabaseApi
            val operatorDao = AuraTrackingApp.database.operatorDao()

            var operatorsSynced = 0
            var equipmentTypesSynced = 0
            var equipmentsSynced = 0

            // 1. Sincronizar operadores
            val operatorsResult = supabaseApi.getOperators()
            operatorsResult.fold(
                onSuccess = { operators ->
                    // Limpar operadores existentes e inserir novos
                    operatorDao.clearAllOperators()
                    operators.forEach { operator ->
                        val entity = com.aura.tracking.data.room.OperatorEntity(
                            id = operator.id,
                            registration = operator.registration,
                            name = operator.name,
                            token = null,
                            isActive = true
                        )
                        operatorDao.insertOperator(entity)
                    }
                    operatorsSynced = operators.size
                    Log.i(TAG, "Synced $operatorsSynced operators")
                },
                onFailure = { error ->
                    Log.w(TAG, "Failed to sync operators: ${error.message}")
                }
            )

            // 2. Sincronizar tipos de equipamento
            val typesResult = supabaseApi.getEquipmentTypes()
            typesResult.fold(
                onSuccess = { types ->
                    equipmentTypesSynced = types.size
                    Log.i(TAG, "Synced $equipmentTypesSynced equipment types")
                    // Tipos são apenas para referência, não salvamos localmente
                },
                onFailure = { error ->
                    Log.w(TAG, "Failed to sync equipment types: ${error.message}")
                }
            )

            // 3. Sincronizar equipamentos
            val equipmentsResult = supabaseApi.getEquipments()
            equipmentsResult.fold(
                onSuccess = { equipments ->
                    equipmentsSynced = equipments.size
                    Log.i(TAG, "Synced $equipmentsSynced equipments")
                    // Equipamentos são apenas para referência, não salvamos localmente
                },
                onFailure = { error ->
                    Log.w(TAG, "Failed to sync equipments: ${error.message}")
                }
            )

            Log.i(TAG, "Data synchronization completed: $operatorsSynced ops, $equipmentTypesSynced types, $equipmentsSynced eqps")
            Result.success()

        } catch (e: Exception) {
            Log.e(TAG, "Data synchronization failed: ${e.message}", e)
            Result.retry()
        }
    }
}
