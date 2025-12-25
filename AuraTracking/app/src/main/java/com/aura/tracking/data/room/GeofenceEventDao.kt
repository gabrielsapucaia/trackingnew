package com.aura.tracking.data.room

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

/**
 * DAO para operações com eventos de geofencing.
 */
@Dao
interface GeofenceEventDao {

    /**
     * Insere um novo evento de geofencing
     */
    @Insert
    suspend fun insert(event: GeofenceEventEntity): Long

    /**
     * Obtém eventos não enviados para flush
     */
    @Query("SELECT * FROM geofence_events WHERE sent = 0 ORDER BY timestamp ASC LIMIT :limit")
    suspend fun getUnsentEvents(limit: Int = 100): List<GeofenceEventEntity>

    /**
     * Conta eventos não enviados
     */
    @Query("SELECT COUNT(*) FROM geofence_events WHERE sent = 0")
    suspend fun getUnsentCount(): Int

    /**
     * Marca evento como enviado
     */
    @Query("UPDATE geofence_events SET sent = 1, sentAt = :sentAt WHERE id = :id")
    suspend fun markSent(id: Long, sentAt: Long = System.currentTimeMillis())

    /**
     * Marca múltiplos eventos como enviados
     */
    @Query("UPDATE geofence_events SET sent = 1, sentAt = :sentAt WHERE id IN (:ids)")
    suspend fun markSentBatch(ids: List<Long>, sentAt: Long = System.currentTimeMillis())

    /**
     * Incrementa contador de retry
     */
    @Query("UPDATE geofence_events SET retryCount = retryCount + 1 WHERE id = :id")
    suspend fun incrementRetry(id: Long)

    /**
     * Obtém últimos eventos por zona
     */
    @Query("SELECT * FROM geofence_events WHERE zoneId = :zoneId ORDER BY timestamp DESC LIMIT :limit")
    suspend fun getEventsByZone(zoneId: Long, limit: Int = 50): List<GeofenceEventEntity>

    /**
     * Obtém último evento de uma zona específica
     */
    @Query("SELECT * FROM geofence_events WHERE zoneId = :zoneId ORDER BY timestamp DESC LIMIT 1")
    suspend fun getLastEventForZone(zoneId: Long): GeofenceEventEntity?

    /**
     * Obtém eventos do dia atual
     */
    @Query("SELECT * FROM geofence_events WHERE timestamp >= :startOfDay ORDER BY timestamp DESC")
    suspend fun getTodayEvents(startOfDay: Long): List<GeofenceEventEntity>

    /**
     * Observa eventos recentes (para UI)
     */
    @Query("SELECT * FROM geofence_events ORDER BY timestamp DESC LIMIT :limit")
    fun observeRecentEvents(limit: Int = 20): Flow<List<GeofenceEventEntity>>

    /**
     * Remove eventos antigos (mais de N dias)
     */
    @Query("DELETE FROM geofence_events WHERE timestamp < :cutoffTimestamp")
    suspend fun deleteOlderThan(cutoffTimestamp: Long)

    /**
     * Remove eventos já enviados com mais de 7 dias
     */
    @Query("DELETE FROM geofence_events WHERE sent = 1 AND timestamp < :cutoffTimestamp")
    suspend fun deleteSentOlderThan(cutoffTimestamp: Long)

    /**
     * Conta total de eventos
     */
    @Query("SELECT COUNT(*) FROM geofence_events")
    suspend fun getTotalCount(): Int

    /**
     * Estatísticas por tipo de zona (para analytics)
     */
    @Query("""
        SELECT zoneType, eventType, COUNT(*) as count
        FROM geofence_events
        WHERE timestamp >= :since
        GROUP BY zoneType, eventType
    """)
    suspend fun getStatsByZoneType(since: Long): List<ZoneEventStats>
}

/**
 * Resultado de estatísticas por tipo de zona
 */
data class ZoneEventStats(
    val zoneType: String,
    val eventType: String,
    val count: Int
)
