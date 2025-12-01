package com.aura.tracking.data.room

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import kotlinx.coroutines.flow.Flow

/**
 * DAO for ConfigEntity operations.
 */
@Dao
interface ConfigDao {

    /**
     * Get the current configuration.
     * Returns null if no configuration exists.
     */
    @Query("SELECT * FROM config WHERE id = 1 LIMIT 1")
    suspend fun getConfig(): ConfigEntity?

    /**
     * Observe the current configuration as a Flow.
     */
    @Query("SELECT * FROM config WHERE id = 1 LIMIT 1")
    fun observeConfig(): Flow<ConfigEntity?>

    /**
     * Insert or replace the configuration.
     */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertConfig(config: ConfigEntity)

    /**
     * Update the existing configuration.
     */
    @Update
    suspend fun updateConfig(config: ConfigEntity)

    /**
     * Delete all configuration data.
     */
    @Query("DELETE FROM config")
    suspend fun deleteConfig()

    /**
     * Check if configuration exists.
     */
    @Query("SELECT EXISTS(SELECT 1 FROM config WHERE id = 1)")
    suspend fun hasConfig(): Boolean

    // ==================== FASE 3 - BOOT RECOVERY ====================
    
    /**
     * Define o estado do tracking (ativo/inativo).
     * Chamado pelo TrackingForegroundService no start/stop.
     * Usado pelo BootCompletedReceiver para decidir se deve reiniciar após reboot.
     */
    @Query("UPDATE config SET tracking_enabled = :enabled, updated_at = :timestamp WHERE id = 1")
    suspend fun setTrackingEnabled(enabled: Boolean, timestamp: Long = System.currentTimeMillis())
    
    /**
     * Verifica se o tracking estava ativo quando o app foi fechado/crashed.
     * Retorna false se não houver configuração.
     */
    @Query("SELECT tracking_enabled FROM config WHERE id = 1 LIMIT 1")
    suspend fun isTrackingEnabled(): Boolean?
}
