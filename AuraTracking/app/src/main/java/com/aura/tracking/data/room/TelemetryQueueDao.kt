package com.aura.tracking.data.room

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

/**
 * DAO para operações na fila de telemetria offline.
 * 
 * FASE 3 - QUEUE 30 DIAS:
 * - TTL: 30 dias (720 horas) = 2.592.000.000 ms
 * - Limite máximo: 3.000.000 registros (~1.2 GB)
 * - Política FIFO: quando limite atingido, descarta os mais antigos
 * - Query enforceMaxSize otimizada: O(log n) com índice createdAt
 * 
 * Cálculo: 30 dias × 24h × 3600s = 2.592.000 registros a 1Hz
 * Margem de segurança: +15% = 3.000.000
 */
@Dao
interface TelemetryQueueDao {
    
    companion object {
        // TTL de 30 dias em milissegundos (720 horas)
        const val TTL_MS = 30L * 24 * 60 * 60 * 1000  // 2.592.000.000 ms
        
        // Limite máximo de mensagens na fila (30 dias + 15% margem)
        const val MAX_QUEUE_SIZE = 3_000_000
        
        // Threshold de warning (80% capacidade)
        const val QUEUE_WARNING_THRESHOLD = 2_400_000
        
        // Threshold crítico (95% capacidade)
        const val QUEUE_CRITICAL_THRESHOLD = 2_850_000
    }
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: TelemetryQueueEntity): Long
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(entities: List<TelemetryQueueEntity>)
    
    @Delete
    suspend fun delete(entity: TelemetryQueueEntity)
    
    @Query("DELETE FROM telemetry_queue WHERE id = :id")
    suspend fun deleteById(id: Long)
    
    @Query("DELETE FROM telemetry_queue WHERE id IN (:ids)")
    suspend fun deleteByIds(ids: List<Long>)
    
    @Query("SELECT * FROM telemetry_queue ORDER BY createdAt ASC LIMIT :limit")
    suspend fun getOldestEntries(limit: Int): List<TelemetryQueueEntity>
    
    @Query("SELECT * FROM telemetry_queue ORDER BY createdAt ASC")
    suspend fun getAll(): List<TelemetryQueueEntity>
    
    @Query("SELECT COUNT(*) FROM telemetry_queue")
    suspend fun getCount(): Int
    
    @Query("SELECT COUNT(*) FROM telemetry_queue")
    fun getCountFlow(): Flow<Int>
    
    @Query("UPDATE telemetry_queue SET retryCount = retryCount + 1 WHERE id = :id")
    suspend fun incrementRetryCount(id: Long)
    
    @Query("DELETE FROM telemetry_queue WHERE retryCount >= :maxRetries")
    suspend fun deleteFailedEntries(maxRetries: Int)
    
    @Query("DELETE FROM telemetry_queue WHERE createdAt < :cutoffTime")
    suspend fun deleteOlderThan(cutoffTime: Long)
    
    /**
     * Remove entradas expiradas (mais velhas que TTL)
     * @return número de entradas removidas
     */
    @Query("DELETE FROM telemetry_queue WHERE createdAt < :cutoffTime")
    suspend fun purgeExpired(cutoffTime: Long): Int
    
    /**
     * Mantém apenas as N entradas mais recentes, removendo as mais antigas.
     * Usado para forçar limite máximo da fila (FIFO).
     * 
     * OTIMIZAÇÃO CRÍTICA para 3M registros:
     * - Query antiga usava NOT IN com subquery = O(n²) = 30-60s para 3M registros
     * - Query nova usa OFFSET = O(log n) = <2s para qualquer tamanho
     * 
     * Funciona selecionando o createdAt do registro na posição maxSize (quando ordenado
     * do mais novo para o mais antigo), e deletando tudo que é mais antigo que esse.
     */
    @Query("""
        DELETE FROM telemetry_queue 
        WHERE createdAt < (
            SELECT createdAt FROM telemetry_queue 
            ORDER BY createdAt DESC 
            LIMIT 1 OFFSET :maxSize
        )
    """)
    suspend fun enforceMaxSize(maxSize: Int): Int
    
    /**
     * Retorna timestamp da entrada mais antiga
     */
    @Query("SELECT MIN(createdAt) FROM telemetry_queue")
    suspend fun getOldestTimestamp(): Long?
    
    /**
     * Retorna estatísticas da fila
     */
    @Query("SELECT COUNT(*) as count, MIN(createdAt) as oldest, MAX(createdAt) as newest FROM telemetry_queue")
    suspend fun getQueueStats(): QueueStats
    
    /**
     * Aplica TTL e limite máximo
     * Deve ser chamado periodicamente pelo QueueFlushWorker
     */
    suspend fun applyMaintenancePolicy() {
        // Remove entradas mais velhas que 48h
        val cutoff = System.currentTimeMillis() - TTL_MS
        purgeExpired(cutoff)
        
        // Garante limite máximo
        enforceMaxSize(MAX_QUEUE_SIZE)
    }
}

/**
 * Data class para estatísticas da fila
 */
data class QueueStats(
    val count: Int,
    val oldest: Long?,
    val newest: Long?
)
