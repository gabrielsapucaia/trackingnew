package com.aura.tracking.sync

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

/**
 * SyncStateDao - DAO para estado de sincronização.
 */
@Dao
interface SyncStateDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(state: SyncStateEntity)

    @Query("SELECT * FROM sync_state WHERE data_type = :dataType")
    suspend fun getState(dataType: String): SyncStateEntity?

    @Query("SELECT * FROM sync_state WHERE data_type = :dataType")
    fun observeState(dataType: String): Flow<SyncStateEntity?>

    @Query("SELECT * FROM sync_state ORDER BY last_sync_at DESC")
    suspend fun getAllStates(): List<SyncStateEntity>

    @Query("SELECT * FROM sync_state ORDER BY last_sync_at DESC")
    fun observeAllStates(): Flow<List<SyncStateEntity>>

    @Query("SELECT last_sync_at FROM sync_state WHERE data_type = :dataType")
    suspend fun getLastSyncTime(dataType: String): Long?

    @Query("SELECT consecutive_failures FROM sync_state WHERE data_type = :dataType")
    suspend fun getConsecutiveFailures(dataType: String): Int?

    @Query("DELETE FROM sync_state")
    suspend fun clearAll()

    /**
     * Verifica se o download está atualizado (synced dentro do intervalo)
     */
    @Query("""
        SELECT CASE
            WHEN last_sync_at > :sinceTimestamp AND last_sync_status = 'success'
            THEN 1 ELSE 0
        END
        FROM sync_state
        WHERE data_type = :dataType
    """)
    suspend fun isSyncedSince(dataType: String, sinceTimestamp: Long): Boolean
}
