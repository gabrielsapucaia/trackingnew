package com.aura.tracking.background

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
import com.aura.tracking.data.room.TelemetryQueueDao
import com.aura.tracking.analytics.QueueAction
import com.aura.tracking.analytics.TelemetryAnalytics
import com.aura.tracking.logging.AuraLog
import com.aura.tracking.mqtt.MqttClientManager
import com.google.firebase.crashlytics.ktx.crashlytics
import com.google.firebase.ktx.Firebase
import kotlinx.coroutines.delay
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.concurrent.TimeUnit

/**
 * Worker periódico para flush da fila de telemetria offline.
 * Executa a cada 15 minutos quando há conectividade de rede.
 * 
 * FASE 3 - QUEUE 30 DIAS:
 * - Limite de 2.000 mensagens por execução (evita timeout WorkManager de 10min)
 * - Delay de 50ms entre batches para não monopolizar CPU
 * - Mutex global para evitar flush concorrente (race condition)
 * - Logs otimizados: resumo a cada 500 mensagens
 * - Manutenção da fila: TTL 30 dias + limite 3M registros
 */
class QueueFlushWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    companion object {
        private const val TAG = "QueueFlushWorker"
        private const val WORK_NAME = "queue_flush_periodic"
        
        // FASE 3: Parâmetros otimizados para queue de 3M registros
        private const val BATCH_SIZE = 50  // Mensagens por batch
        private const val MAX_MESSAGES_PER_EXECUTION = 2_000  // Limite por execução do Worker
        private const val INTER_BATCH_DELAY_MS = 50L  // Delay entre batches para yield CPU
        private const val LOG_INTERVAL = 500  // Log a cada N mensagens
        
        // Mutex global para evitar flush concorrente
        // (previne race condition entre Worker, drainQueue do Service, etc.)
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
                AuraLog.Queue.d("Flush already in progress, skipping")
                false
            }
        }
        
        /**
         * Agenda o worker periódico
         */
        fun schedule(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val request = PeriodicWorkRequestBuilder<QueueFlushWorker>(
                repeatInterval = 15,
                repeatIntervalTimeUnit = TimeUnit.MINUTES,
                flexTimeInterval = 5,
                flexTimeIntervalUnit = TimeUnit.MINUTES
            )
                .setConstraints(constraints)
                .setBackoffCriteria(
                    BackoffPolicy.EXPONENTIAL,
                    30,
                    TimeUnit.SECONDS
                )
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request
            )

            AuraLog.Queue.i("Queue flush worker scheduled")
        }

        /**
         * Cancela o worker periódico
         */
        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
            AuraLog.Queue.i("Queue flush worker cancelled")
        }
    }

    override suspend fun doWork(): Result {
        AuraLog.Queue.i("Queue flush worker started")

        // Tenta adquirir lock - se outro flush já está em andamento, sai
        return if (flushMutex.tryLock()) {
            try {
                doFlushWork()
            } finally {
                flushMutex.unlock()
            }
        } else {
            AuraLog.Queue.i("Another flush in progress, skipping this execution")
            Result.success()
        }
    }
    
    private suspend fun doFlushWork(): Result {
        return try {
            val database = AppDatabase.getInstance(applicationContext)
            val queueDao = database.telemetryQueueDao()
            
            // FASE 3: Aplica política de manutenção (TTL + limite máximo)
            applyMaintenancePolicy(queueDao)
            
            // Verifica se há itens na fila
            val initialCount = queueDao.getCount()
            if (initialCount == 0) {
                AuraLog.Queue.d("Queue is empty, skipping flush")
                return Result.success()
            }
            
            // Log com threshold warnings
            logQueueStatus(initialCount, queueDao)

            // Obtém instância do MQTT (se o serviço estiver rodando)
            val mqttClient = TrackingForegroundService.getMqttClient()
            if (mqttClient == null) {
                AuraLog.Queue.w("MQTT client not available, retrying later")
                return Result.retry()
            }

            // Verifica conexão MQTT
            if (!mqttClient.isConnected.value) {
                AuraLog.Queue.d("MQTT not connected, attempting reconnect")
                mqttClient.connect()
                delay(2000)
                
                if (!mqttClient.isConnected.value) {
                    AuraLog.Queue.w("MQTT reconnect failed, retrying later")
                    return Result.retry()
                }
            }

            // Cria agregador para flush
            val configDao = database.configDao()
            val operatorDao = database.operatorDao()
            val config = configDao.getConfig()
            // Usa equipmentName como deviceId (tag do equipamento, ex: TRK-101)
            val deviceId = config?.equipmentName ?: "unknown"
            // Obtém operatorId da matrícula do operador logado
            val currentOperator = operatorDao.getCurrentOperator()
            val operatorId = currentOperator?.registration?.takeIf { it.isNotEmpty() } ?: "TEST"

            val aggregator = TelemetryAggregator(
                mqttClient = mqttClient,
                queueDao = queueDao,
                deviceId = deviceId,
                operatorId = operatorId
            )

            // FASE 3: Flush com limite por execução e throttling
            val result = flushWithThrottling(aggregator, queueDao, mqttClient)

            val finalCount = queueDao.getCount()
            AuraLog.Queue.i("Queue flush completed: sent=${result.sent}, failed=${result.failed}, remaining=$finalCount")

            // ANALYTICS: Registra resultado do flush
            TelemetryAnalytics.recordQueueFlush(
                batchSize = BATCH_SIZE,
                sent = result.sent,
                failed = result.failed,
                remainingSize = finalCount
            )

            if (result.failed > 0 && result.sent == 0) {
                Result.retry()
            } else {
                Result.success()
            }
        } catch (e: Exception) {
            AuraLog.Queue.e("Queue flush worker failed: ${e.message}")
            // Report worker failure to Crashlytics
            Firebase.crashlytics.apply {
                log("QueueFlushWorker failed: ${e.message}")
                recordException(e)
            }
            Result.retry()
        }
    }
    
    /**
     * Aplica política de manutenção com tratamento de erro isolado
     */
    private suspend fun applyMaintenancePolicy(queueDao: TelemetryQueueDao) {
        try {
            queueDao.applyMaintenancePolicy()
            AuraLog.Queue.d("Queue maintenance policy applied")
        } catch (e: Exception) {
            AuraLog.Queue.e("Failed to apply maintenance policy: ${e.message}")
        }
    }
    
    /**
     * Log do status da fila com warnings de threshold
     */
    private suspend fun logQueueStatus(count: Int, queueDao: TelemetryQueueDao) {
        val percentage = count * 100 / TelemetryQueueDao.MAX_QUEUE_SIZE

        // ANALYTICS: Registra métricas da fila
        val oldestTimestamp = try { queueDao.getOldestTimestamp() } catch (_: Exception) { null }
        TelemetryAnalytics.recordQueueMetrics(
            size = count,
            oldestTimestampMs = oldestTimestamp,
            action = QueueAction.FLUSH_START
        )

        when {
            count >= TelemetryQueueDao.QUEUE_CRITICAL_THRESHOLD -> {
                AuraLog.Queue.w("CRITICAL: Queue at ${count}/${TelemetryQueueDao.MAX_QUEUE_SIZE} ($percentage%)")
                // Report critical queue status to Crashlytics
                Firebase.crashlytics.apply {
                    log("Queue CRITICAL: $count messages ($percentage% capacity)")
                    setCustomKey("queue_size", count.toLong())
                    setCustomKey("queue_percentage", percentage.toLong())
                    recordException(Exception("Queue critical threshold reached: $count messages"))
                }
            }
            count >= TelemetryQueueDao.QUEUE_WARNING_THRESHOLD -> {
                AuraLog.Queue.w("WARNING: Queue at ${count}/${TelemetryQueueDao.MAX_QUEUE_SIZE} ($percentage%)")
                // Report warning queue status to Crashlytics
                Firebase.crashlytics.apply {
                    log("Queue WARNING: $count messages ($percentage% capacity)")
                    setCustomKey("queue_size", count.toLong())
                    setCustomKey("queue_percentage", percentage.toLong())
                }
            }
            else -> {
                AuraLog.Queue.i("Queue has $count items, attempting flush")
            }
        }
    }
    
    /**
     * Flush com throttling, limite por execução e logs otimizados.
     * 
     * Características:
     * - Máximo MAX_MESSAGES_PER_EXECUTION mensagens por execução
     * - Delay INTER_BATCH_DELAY_MS entre batches
     * - Log resumido a cada LOG_INTERVAL mensagens
     * - Para imediatamente se MQTT desconectar
     */
    private suspend fun flushWithThrottling(
        aggregator: TelemetryAggregator,
        queueDao: TelemetryQueueDao,
        mqttClient: MqttClientManager
    ): FlushStats {
        var totalSent = 0
        var totalFailed = 0
        var batchCount = 0
        var lastLogAt = 0
        
        while (totalSent + totalFailed < MAX_MESSAGES_PER_EXECUTION) {
            // Verifica conexão antes de cada batch
            if (!mqttClient.isConnected.value) {
                AuraLog.Queue.w("MQTT disconnected during flush, stopping")
                break
            }
            
            // Processa batch
            try {
                val result = aggregator.flushQueue(BATCH_SIZE)
                totalSent += result.sent
                totalFailed += result.failed
                batchCount++
                
                // Se não há mais itens ou falhou tudo, para
                if (result.remaining == 0) {
                    break
                }
                if (result.sent == 0 && result.failed > 0) {
                    AuraLog.Queue.w("All messages in batch failed, stopping flush")
                    break
                }
                
                // Log periódico a cada LOG_INTERVAL mensagens
                if (totalSent - lastLogAt >= LOG_INTERVAL) {
                    AuraLog.Queue.i("Flush progress: sent=$totalSent, remaining=${result.remaining}")
                    lastLogAt = totalSent
                }
                
                // Yield CPU entre batches
                delay(INTER_BATCH_DELAY_MS)
                
            } catch (e: Exception) {
                AuraLog.Queue.e("Batch $batchCount failed: ${e.message}")
                // Continua com próximo batch
            }
        }
        
        return FlushStats(totalSent, totalFailed)
    }
    
    private data class FlushStats(val sent: Int, val failed: Int)
}
