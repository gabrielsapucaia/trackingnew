package com.aura.tracking.sync

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * SyncStateEntity - Persiste o estado de sincronização.
 *
 * Permite saber:
 * - Quando foi a última sync bem sucedida
 * - Quantos itens foram sincronizados
 * - Se houve erro e qual foi
 */
@Entity(tableName = "sync_state")
data class SyncStateEntity(
    /** Tipo de dados: "download", "upload", "operators", "geofences" */
    @PrimaryKey
    @ColumnInfo(name = "data_type")
    val dataType: String,

    /** Timestamp da última sync */
    @ColumnInfo(name = "last_sync_at")
    val lastSyncAt: Long,

    /** Status: "success", "failed", "skipped" */
    @ColumnInfo(name = "last_sync_status")
    val lastSyncStatus: String,

    /** Quantidade de itens sincronizados */
    @ColumnInfo(name = "item_count")
    val itemCount: Int = 0,

    /** Mensagem de erro (se houver) */
    @ColumnInfo(name = "error_message")
    val errorMessage: String? = null,

    /** Número de tentativas consecutivas com falha */
    @ColumnInfo(name = "consecutive_failures")
    val consecutiveFailures: Int = 0
) {
    companion object {
        const val TYPE_DOWNLOAD = "download"
        const val TYPE_UPLOAD = "upload"
        const val TYPE_OPERATORS = "operators"
        const val TYPE_GEOFENCES = "geofences"
        const val TYPE_TELEMETRY = "telemetry"
        const val TYPE_GEOFENCE_EVENTS = "geofence_events"

        const val STATUS_SUCCESS = "success"
        const val STATUS_FAILED = "failed"
        const val STATUS_SKIPPED = "skipped"

        fun success(dataType: String, count: Int): SyncStateEntity {
            return SyncStateEntity(
                dataType = dataType,
                lastSyncAt = System.currentTimeMillis(),
                lastSyncStatus = STATUS_SUCCESS,
                itemCount = count,
                errorMessage = null,
                consecutiveFailures = 0
            )
        }

        fun failed(dataType: String, error: String, previousFailures: Int = 0): SyncStateEntity {
            return SyncStateEntity(
                dataType = dataType,
                lastSyncAt = System.currentTimeMillis(),
                lastSyncStatus = STATUS_FAILED,
                itemCount = 0,
                errorMessage = error,
                consecutiveFailures = previousFailures + 1
            )
        }

        fun skipped(dataType: String, reason: String): SyncStateEntity {
            return SyncStateEntity(
                dataType = dataType,
                lastSyncAt = System.currentTimeMillis(),
                lastSyncStatus = STATUS_SKIPPED,
                itemCount = 0,
                errorMessage = reason,
                consecutiveFailures = 0
            )
        }
    }
}
