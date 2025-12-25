package com.aura.tracking.sync

import com.aura.tracking.logging.AuraLog
import kotlinx.coroutines.sync.Mutex

/**
 * SyncConfig - Configurações para o SyncOrchestrator.
 * Valores configuráveis para controle de sync.
 */
object SyncConfig {
    // Mutex global para evitar flush concorrente
    private val flushMutex = Mutex()

    /**
     * Tenta adquirir lock para flush.
     * Retorna true se conseguiu, false se outro flush já está em andamento.
     */
    suspend fun tryFlushWithLock(block: suspend () -> Unit): Boolean {
        return if (flushMutex.tryLock()) {
            try {
                block()
                true
            } finally {
                flushMutex.unlock()
            }
        } else {
            AuraLog.Sync.d("Flush already in progress, skipping")
            false
        }
    }
    // Intervalo entre syncs (WorkManager)
    const val SYNC_INTERVAL_MINUTES = 15L
    const val SYNC_FLEX_INTERVAL_MINUTES = 5L

    // Timeouts para fetch do Supabase
    const val FETCH_TIMEOUT_MS = 30_000L

    // Retry configuration
    const val MAX_RETRIES = 3
    const val RETRY_INITIAL_DELAY_MS = 2_000L
    const val RETRY_BACKOFF_MULTIPLIER = 2.0

    // Validação - guardrails
    const val MIN_OPERATORS = 1
    const val MIN_POLYGON_POINTS = 3

    // Upload batch sizes
    const val TELEMETRY_BATCH_SIZE = 50
    const val TELEMETRY_MAX_PER_EXECUTION = 2_000
    const val GEOFENCE_EVENT_BATCH_SIZE = 50
    const val GEOFENCE_EVENT_MAX_PER_EXECUTION = 500

    // Inter-batch delay (ms)
    const val BATCH_DELAY_MS = 50L

    // WorkManager tags
    const val WORK_NAME = "unified_sync_periodic"
    const val WORK_TAG = "sync"
}
