package com.aura.tracking.data.room

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

/**
 * DAO para operações com zonas de geofencing.
 */
@Dao
interface ZoneDao {

    /**
     * Insere ou atualiza uma zona
     */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(zone: ZoneEntity)

    /**
     * Insere ou atualiza múltiplas zonas (sync com Supabase)
     */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(zones: List<ZoneEntity>)

    /**
     * Obtém todas as zonas ativas
     */
    @Query("SELECT * FROM zones WHERE isActive = 1")
    suspend fun getActiveZones(): List<ZoneEntity>

    /**
     * Obtém todas as zonas ativas como Flow (observável)
     */
    @Query("SELECT * FROM zones WHERE isActive = 1")
    fun observeActiveZones(): Flow<List<ZoneEntity>>

    /**
     * Obtém zona por ID
     */
    @Query("SELECT * FROM zones WHERE id = :id")
    suspend fun getZoneById(id: Long): ZoneEntity?

    /**
     * Obtém zonas por tipo
     */
    @Query("SELECT * FROM zones WHERE zoneType = :type AND isActive = 1")
    suspend fun getZonesByType(type: String): List<ZoneEntity>

    /**
     * Conta total de zonas ativas
     */
    @Query("SELECT COUNT(*) FROM zones WHERE isActive = 1")
    suspend fun getActiveCount(): Int

    /**
     * Obtém timestamp da última atualização
     */
    @Query("SELECT MAX(updatedAt) FROM zones")
    suspend fun getLastUpdatedAt(): Long?

    /**
     * Remove zonas que não estão na lista de IDs (sync com Supabase)
     */
    @Query("DELETE FROM zones WHERE id NOT IN (:ids)")
    suspend fun deleteNotIn(ids: List<Long>)

    /**
     * Remove todas as zonas
     */
    @Query("DELETE FROM zones")
    suspend fun deleteAll()

    /**
     * Desativa uma zona por ID
     */
    @Query("UPDATE zones SET isActive = 0 WHERE id = :id")
    suspend fun deactivate(id: Long)
}
