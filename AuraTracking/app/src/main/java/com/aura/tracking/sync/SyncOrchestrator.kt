package com.aura.tracking.sync

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import com.aura.tracking.AuraTrackingApp
import com.aura.tracking.background.TelemetryAggregator
import com.aura.tracking.background.TrackingForegroundService
import com.aura.tracking.data.model.Geofence
import com.aura.tracking.data.model.Operator
import com.aura.tracking.data.room.AppDatabase
import com.aura.tracking.data.room.OperatorEntity
import com.aura.tracking.data.room.ZoneEntity
import com.aura.tracking.data.supabase.SupabaseApi
import com.aura.tracking.logging.AuraLog
import com.aura.tracking.mqtt.MqttClientManager
import androidx.room.withTransaction
import kotlinx.coroutines.delay
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.Json

/**
 * SyncOrchestrator - Orquestrador unificado de sincronização.
 *
 * Coordena downloads (Supabase → App) e uploads (App → MQTT)
 * com validação, transações atômicas e guardrails de resiliência.
 *
 * Substitui: SyncDataWorker, ZoneSyncWorker, QueueFlushWorker, GeofenceEventFlushWorker
 */
class SyncOrchestrator(
    private val context: Context,
    private val supabaseApi: SupabaseApi,
    private val database: AppDatabase
) {
    companion object {
        private val syncMutex = Mutex()

        /**
         * Executa sync com lock para evitar execuções concorrentes
         */
        suspend fun <T> withSyncLock(block: suspend () -> T): T? {
            return if (syncMutex.tryLock()) {
                try {
                    block()
                } finally {
                    syncMutex.unlock()
                }
            } else {
                AuraLog.Sync.d("Sync already in progress, skipping")
                null
            }
        }
    }

    private val json = Json { ignoreUnknownKeys = true }
    private val syncStateDao by lazy { database.syncStateDao() }
    private val operatorDao by lazy { database.operatorDao() }
    private val zoneDao by lazy { database.zoneDao() }
    private val telemetryQueueDao by lazy { database.telemetryQueueDao() }
    private val geofenceEventDao by lazy { database.geofenceEventDao() }
    private val configDao by lazy { database.configDao() }

    /**
     * Executa sincronização completa (download + upload)
     */
    suspend fun syncAll(): SyncResult {
        AuraLog.Sync.i("=== SyncOrchestrator.syncAll() started ===")

        // ========== FASE 1: DOWNLOAD ==========
        val downloadResult = executeDownloadPhase()
        AuraLog.Sync.i("Download phase: ${downloadResult.javaClass.simpleName}")

        // ========== FASE 2: UPLOAD ==========
        // Upload continua mesmo se download falhou (dados locais ainda válidos)
        val uploadResult = executeUploadPhase()
        AuraLog.Sync.i("Upload phase: ${uploadResult.javaClass.simpleName}")

        val result = SyncResult.fromPhases(downloadResult, uploadResult)
        AuraLog.Sync.i("=== SyncOrchestrator completed: ${result.javaClass.simpleName} ===")

        return result
    }

    // ==================== FASE 1: DOWNLOAD ====================

    /**
     * Executa download de dados do Supabase com validação e commit atômico.
     */
    private suspend fun executeDownloadPhase(): SyncPhaseResult {
        // Guardrail: Verificar conectividade
        if (!isNetworkAvailable()) {
            AuraLog.Sync.d("No network available, skipping download")
            syncStateDao.upsert(SyncStateEntity.skipped(SyncStateEntity.TYPE_DOWNLOAD, "No network"))
            return SyncPhaseResult.Skipped("No network")
        }

        return try {
            // 1. Fetch com retry e timeout
            val operators = fetchWithRetry("operators") { supabaseApi.getOperators() }
            val geofences = fetchWithRetry("geofences") { supabaseApi.getGeofences() }

            if (operators == null || geofences == null) {
                throw SyncValidationException("Failed to fetch data after retries")
            }

            // 2. Validar antes de commit (guardrails)
            SyncValidator.validateAll(operators, geofences)

            // 3. Commit atômico com transação Room
            val totalItems = operators.size + geofences.size
            database.withTransaction {
                // Operators: limpar e reinserir
                operatorDao.clearAllOperators()
                operators.forEach { operator ->
                    operatorDao.insertOperator(operator.toEntity())
                }

                // Geofences: upsert e limpar removidos
                val zoneEntities = geofences.map { it.toZoneEntity() }
                zoneDao.upsertAll(zoneEntities)
                zoneDao.deleteNotIn(zoneEntities.map { it.id })
            }

            // 4. Atualizar estado de sync
            syncStateDao.upsert(SyncStateEntity.success(SyncStateEntity.TYPE_DOWNLOAD, totalItems))
            syncStateDao.upsert(SyncStateEntity.success(SyncStateEntity.TYPE_OPERATORS, operators.size))
            syncStateDao.upsert(SyncStateEntity.success(SyncStateEntity.TYPE_GEOFENCES, geofences.size))

            AuraLog.Sync.i("Download success: ${operators.size} operators, ${geofences.size} geofences")
            SyncPhaseResult.Success(totalItems)

        } catch (e: SyncValidationException) {
            AuraLog.Sync.e("Download validation failed: ${e.message}")
            val previousFailures = syncStateDao.getConsecutiveFailures(SyncStateEntity.TYPE_DOWNLOAD) ?: 0
            syncStateDao.upsert(SyncStateEntity.failed(SyncStateEntity.TYPE_DOWNLOAD, e.message ?: "Validation failed", previousFailures))
            SyncPhaseResult.Failed(e.message ?: "Validation failed")

        } catch (e: Exception) {
            AuraLog.Sync.e("Download failed: ${e.message}")
            val previousFailures = syncStateDao.getConsecutiveFailures(SyncStateEntity.TYPE_DOWNLOAD) ?: 0
            syncStateDao.upsert(SyncStateEntity.failed(SyncStateEntity.TYPE_DOWNLOAD, e.message ?: "Unknown error", previousFailures))
            SyncPhaseResult.Failed(e.message ?: "Unknown error")
        }
    }

    /**
     * Fetch com retry e backoff exponencial
     */
    private suspend fun <T> fetchWithRetry(
        name: String,
        fetch: suspend () -> Result<T>
    ): T? {
        var lastError: Throwable? = null
        var delay = SyncConfig.RETRY_INITIAL_DELAY_MS

        repeat(SyncConfig.MAX_RETRIES) { attempt ->
            try {
                val result = withTimeout(SyncConfig.FETCH_TIMEOUT_MS) {
                    fetch()
                }

                if (result.isSuccess) {
                    return result.getOrNull()
                } else {
                    lastError = result.exceptionOrNull()
                    AuraLog.Sync.w("Fetch $name attempt ${attempt + 1} failed: ${lastError?.message}")
                }
            } catch (e: Exception) {
                lastError = e
                AuraLog.Sync.w("Fetch $name attempt ${attempt + 1} exception: ${e.message}")
            }

            if (attempt < SyncConfig.MAX_RETRIES - 1) {
                delay(delay)
                delay = (delay * SyncConfig.RETRY_BACKOFF_MULTIPLIER).toLong()
            }
        }

        AuraLog.Sync.e("Fetch $name failed after ${SyncConfig.MAX_RETRIES} attempts: ${lastError?.message}")
        return null
    }

    // ==================== FASE 2: UPLOAD ====================

    /**
     * Executa upload de dados pendentes via MQTT.
     */
    private suspend fun executeUploadPhase(): SyncPhaseResult {
        // Guardrail: Verificar MQTT conectado
        val mqttClient = TrackingForegroundService.getMqttClient()
        if (mqttClient == null || !mqttClient.isConnected.value) {
            AuraLog.Sync.d("MQTT not connected, skipping upload")
            syncStateDao.upsert(SyncStateEntity.skipped(SyncStateEntity.TYPE_UPLOAD, "MQTT offline"))
            return SyncPhaseResult.Skipped("MQTT offline")
        }

        return try {
            var totalUploaded = 0

            // 2.1 Flush telemetry queue
            val telemetrySent = flushTelemetryQueue(mqttClient)
            totalUploaded += telemetrySent
            syncStateDao.upsert(SyncStateEntity.success(SyncStateEntity.TYPE_TELEMETRY, telemetrySent))

            // 2.2 Flush geofence events
            val eventsSent = flushGeofenceEvents(mqttClient)
            totalUploaded += eventsSent
            syncStateDao.upsert(SyncStateEntity.success(SyncStateEntity.TYPE_GEOFENCE_EVENTS, eventsSent))

            // Atualizar estado geral de upload
            syncStateDao.upsert(SyncStateEntity.success(SyncStateEntity.TYPE_UPLOAD, totalUploaded))

            AuraLog.Sync.i("Upload success: $telemetrySent telemetry, $eventsSent events")
            SyncPhaseResult.Success(totalUploaded)

        } catch (e: Exception) {
            AuraLog.Sync.e("Upload failed: ${e.message}")
            val previousFailures = syncStateDao.getConsecutiveFailures(SyncStateEntity.TYPE_UPLOAD) ?: 0
            syncStateDao.upsert(SyncStateEntity.failed(SyncStateEntity.TYPE_UPLOAD, e.message ?: "Unknown error", previousFailures))
            SyncPhaseResult.Failed(e.message ?: "Unknown error")
        }
    }

    /**
     * Flush da fila de telemetria (lógica do QueueFlushWorker)
     */
    private suspend fun flushTelemetryQueue(mqttClient: MqttClientManager): Int {
        val initialCount = telemetryQueueDao.getCount()
        if (initialCount == 0) {
            AuraLog.Sync.d("Telemetry queue empty")
            return 0
        }

        AuraLog.Sync.i("Flushing telemetry queue: $initialCount items")

        // Aplicar política de manutenção
        try {
            telemetryQueueDao.applyMaintenancePolicy()
        } catch (e: Exception) {
            AuraLog.Sync.w("Maintenance policy failed: ${e.message}")
        }

        // Obter configuração
        val config = configDao.getConfig()
        val deviceId = config?.equipmentName ?: "unknown"
        val currentOperator = operatorDao.getCurrentOperator()
        val operatorId = currentOperator?.registration?.takeIf { it.isNotEmpty() } ?: "TEST"

        val aggregator = TelemetryAggregator(
            mqttClient = mqttClient,
            queueDao = telemetryQueueDao,
            deviceId = deviceId,
            operatorId = operatorId
        )

        var totalSent = 0
        var totalFailed = 0

        while (totalSent + totalFailed < SyncConfig.TELEMETRY_MAX_PER_EXECUTION) {
            if (!mqttClient.isConnected.value) {
                AuraLog.Sync.w("MQTT disconnected during telemetry flush")
                break
            }

            val result = aggregator.flushQueue(SyncConfig.TELEMETRY_BATCH_SIZE)
            totalSent += result.sent
            totalFailed += result.failed

            if (result.remaining == 0) break
            if (result.sent == 0 && result.failed > 0) break

            delay(SyncConfig.BATCH_DELAY_MS)
        }

        AuraLog.Sync.i("Telemetry flush: sent=$totalSent, failed=$totalFailed")
        return totalSent
    }

    /**
     * Flush de eventos de geofence (lógica do GeofenceEventFlushWorker)
     */
    private suspend fun flushGeofenceEvents(mqttClient: MqttClientManager): Int {
        val unsentCount = geofenceEventDao.getUnsentCount()
        if (unsentCount == 0) {
            AuraLog.Sync.d("No pending geofence events")
            return 0
        }

        AuraLog.Sync.i("Flushing geofence events: $unsentCount pending")

        val config = configDao.getConfig()
        val deviceId = config?.equipmentName ?: "unknown"
        val baseTopic = "aura/tracking/$deviceId/geofence"

        var totalSent = 0
        var totalFailed = 0

        while (totalSent + totalFailed < SyncConfig.GEOFENCE_EVENT_MAX_PER_EXECUTION) {
            val events = geofenceEventDao.getUnsentEvents(SyncConfig.GEOFENCE_EVENT_BATCH_SIZE)
            if (events.isEmpty()) break

            for (event in events) {
                if (!mqttClient.isConnected.value) {
                    AuraLog.Sync.w("MQTT disconnected during geofence event flush")
                    break
                }

                val payload = json.encodeToString(
                    GeofenceEventPayload.serializer(),
                    GeofenceEventPayload(
                        eventId = event.eventId,
                        zoneId = event.zoneId,
                        zoneName = event.zoneName,
                        zoneType = event.zoneType,
                        eventType = event.eventType,
                        durationSeconds = event.durationSeconds,
                        latitude = event.latitude,
                        longitude = event.longitude,
                        gpsAccuracy = event.gpsAccuracy,
                        speed = event.speed,
                        deviceId = event.deviceId,
                        operatorId = event.operatorId,
                        timestamp = event.timestamp
                    )
                )

                val success = mqttClient.publish(baseTopic, payload, qos = 1)
                if (success) {
                    geofenceEventDao.markSent(event.id)
                    totalSent++
                } else {
                    geofenceEventDao.incrementRetry(event.id)
                    totalFailed++
                }
            }

            delay(SyncConfig.BATCH_DELAY_MS)
        }

        // Limpar eventos antigos (7 dias)
        val cutoff = System.currentTimeMillis() - (7 * 24 * 60 * 60 * 1000L)
        geofenceEventDao.deleteSentOlderThan(cutoff)

        AuraLog.Sync.i("Geofence events flush: sent=$totalSent, failed=$totalFailed")
        return totalSent
    }

    // ==================== HELPERS ====================

    /**
     * Verifica se há conectividade de rede
     */
    private fun isNetworkAvailable(): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return false
        val capabilities = cm.getNetworkCapabilities(network) ?: return false
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    /**
     * Extensão: Operator → OperatorEntity
     */
    private fun Operator.toEntity(): OperatorEntity {
        return OperatorEntity(
            id = id,
            registration = registration,
            name = name,
            token = null,
            isActive = status == "active"
        )
    }

    /**
     * Extensão: Geofence → ZoneEntity
     */
    private fun Geofence.toZoneEntity(): ZoneEntity {
        return ZoneEntity(
            id = id,
            name = name,
            zoneType = zoneType,
            polygonJson = polygonJson,
            centerLat = null,
            centerLon = null,
            radiusMeters = null,
            color = color,
            isActive = isActive,
            updatedAt = parseTimestamp(updatedAt),
            createdAt = parseTimestamp(createdAt)
        )
    }

    private fun parseTimestamp(isoTimestamp: String?): Long {
        if (isoTimestamp == null) return System.currentTimeMillis()
        return try {
            java.time.Instant.parse(isoTimestamp).toEpochMilli()
        } catch (e: Exception) {
            System.currentTimeMillis()
        }
    }
}
