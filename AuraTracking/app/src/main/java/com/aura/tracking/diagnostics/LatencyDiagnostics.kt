package com.aura.tracking.diagnostics

import android.location.Location
import android.os.SystemClock
import com.aura.tracking.logging.AuraLog
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.concurrent.ConcurrentLinkedQueue
import kotlin.math.abs
import kotlin.math.sqrt

/**
 * LatencyDiagnostics - Sistema de diagnóstico de latência GNSS
 * 
 * Implementa o plano de diagnóstico completo para identificar
 * a origem do atraso entre IMU (instantâneo) e GNSS (atrasado).
 * 
 * Instrumentação de 6 pontos de timestamp:
 * - T0: GNSS Satellite Time (Location.getTime())
 * - T1: GNSS Hardware Delivery (Location.getElapsedRealtimeNanos())
 * - T2: App Callback Receipt
 * - T3: Packet Creation
 * - T4: MQTT Publish
 * - T5/T6: Server Ingest / DB Insert (server-side)
 * 
 * Cross-correlation IMU vs GPS para detectar lag.
 */
object LatencyDiagnostics {
    
    private const val TAG = "LatencyDiagnostics"
    private const val MAX_SAMPLES = 600 // 10 minutos de dados a 1Hz
    private const val CORRELATION_WINDOW_SEC = 10 // Janela de correlação
    
    private val json = Json { prettyPrint = true }
    
    // Buffer circular de amostras para análise
    private val gpsLatencySamples = ConcurrentLinkedQueue<GpsLatencySample>()
    private val imuSamples = ConcurrentLinkedQueue<ImuSample>()
    private val correlationResults = ConcurrentLinkedQueue<CorrelationResult>()
    
    // Estatísticas em tempo real
    private val _stats = MutableStateFlow(LatencyStats())
    val stats: StateFlow<LatencyStats> = _stats.asStateFlow()
    
    // Último diagnóstico
    private val _lastDiagnosis = MutableStateFlow<LatencyDiagnosis?>(null)
    val lastDiagnosis: StateFlow<LatencyDiagnosis?> = _lastDiagnosis.asStateFlow()
    
    // Habilitado/desabilitado
    @Volatile
    var enabled: Boolean = true
    
    /**
     * Registra amostra de GPS com todos os timestamps
     * Chamado no momento do callback do FusedLocationProvider
     */
    fun recordGpsCallback(location: Location) {
        if (!enabled) return
        
        val t2CallbackTime = System.currentTimeMillis()
        val elapsedNow = SystemClock.elapsedRealtime()
        
        // T0: Tempo do satélite (quando o satélite calculou a posição)
        val t0SatelliteTime = location.time
        
        // T1: Tempo de entrega do hardware (convertido para wall clock)
        // Location.getElapsedRealtimeNanos() indica quando o fix foi computado
        val elapsedAtFix = location.elapsedRealtimeNanos / 1_000_000 // para ms
        val t1HardwareDelivery = t2CallbackTime - (elapsedNow - elapsedAtFix)
        
        // Cálculos de latência
        val gpsAge = t2CallbackTime - t0SatelliteTime // Idade do dado GPS
        val hardwareLatency = t2CallbackTime - t1HardwareDelivery // Latência do FusedLocationProvider
        val chipsetLatency = t1HardwareDelivery - t0SatelliteTime // Latência do chipset GNSS
        
        val sample = GpsLatencySample(
            t0SatelliteTime = t0SatelliteTime,
            t1HardwareDelivery = t1HardwareDelivery,
            t2CallbackTime = t2CallbackTime,
            gpsAge = gpsAge,
            hardwareLatency = hardwareLatency,
            chipsetLatency = chipsetLatency,
            latitude = location.latitude,
            longitude = location.longitude,
            speed = location.speed,
            accuracy = location.accuracy,
            satellites = location.extras?.getInt("satellites", -1) ?: -1
        )
        
        // Adicionar ao buffer (manter tamanho máximo)
        gpsLatencySamples.add(sample)
        while (gpsLatencySamples.size > MAX_SAMPLES) {
            gpsLatencySamples.poll()
        }
        
        // Atualizar estatísticas
        updateStats(sample)
        
        // Log de diagnóstico
        AuraLog.GPS.d("GPS Latency: age=${gpsAge}ms, hardware=${hardwareLatency}ms, " +
                "chipset=${chipsetLatency}ms, acc=${location.accuracy}m")
    }
    
    /**
     * Registra timestamp de criação do pacote
     */
    fun recordPacketCreation(messageId: String): Long {
        val t3 = System.currentTimeMillis()
        // Armazenar para correlação posterior
        return t3
    }
    
    /**
     * Registra timestamp de publicação MQTT
     */
    fun recordMqttPublish(messageId: String, t3PacketCreation: Long): Long {
        val t4 = System.currentTimeMillis()
        val publishLatency = t4 - t3PacketCreation
        
        AuraLog.MQTT.d("Publish latency: ${publishLatency}ms (msgId=${messageId.take(8)})")
        return t4
    }
    
    /**
     * Registra amostra de IMU para correlação cruzada
     * Chamado a cada amostra do acelerômetro (~100Hz)
     */
    fun recordImuSample(
        accelX: Float,
        accelY: Float,
        accelZ: Float,
        timestamp: Long = System.currentTimeMillis()
    ) {
        if (!enabled) return
        
        // Magnitude da aceleração (removendo gravidade é mais complexo, usar magnitude)
        val magnitude = sqrt(accelX * accelX + accelY * accelY + accelZ * accelZ)
        
        val sample = ImuSample(
            timestamp = timestamp,
            accelMagnitude = magnitude,
            accelX = accelX,
            accelY = accelY,
            accelZ = accelZ
        )
        
        imuSamples.add(sample)
        while (imuSamples.size > MAX_SAMPLES * 100) { // 100x mais amostras que GPS
            imuSamples.poll()
        }
    }
    
    /**
     * Registra velocidade GPS para correlação
     * Chamado junto com recordGpsCallback
     */
    fun recordGpsSpeed(speed: Float, timestamp: Long) {
        // Velocidade já está no GpsLatencySample
    }
    
    /**
     * Executa análise de correlação cruzada IMU vs GPS
     * Detecta o lag entre mudança de aceleração e mudança de velocidade GPS
     * 
     * Retorna o lag em milissegundos (positivo = GPS atrasado)
     */
    fun analyzeCorrelation(): CorrelationResult {
        val gpsSamples = gpsLatencySamples.toList()
        val imuSamplesList = imuSamples.toList()
        
        if (gpsSamples.size < 30 || imuSamplesList.size < 300) {
            return CorrelationResult(
                lagMs = 0,
                correlation = 0.0,
                sampleCount = gpsSamples.size,
                diagnosis = "Dados insuficientes para análise"
            )
        }
        
        // Calcular derivada da velocidade GPS (aproximação da aceleração)
        val gpsAccel = mutableListOf<Pair<Long, Double>>()
        for (i in 1 until gpsSamples.size) {
            val dt = (gpsSamples[i].t2CallbackTime - gpsSamples[i-1].t2CallbackTime) / 1000.0
            if (dt > 0) {
                val dv = gpsSamples[i].speed - gpsSamples[i-1].speed
                val accel = dv / dt
                gpsAccel.add(gpsSamples[i].t2CallbackTime to accel.toDouble())
            }
        }
        
        // Reduzir IMU para mesma frequência do GPS (média por segundo)
        val imuReduced = mutableListOf<Pair<Long, Double>>()
        val imuBySecond = imuSamplesList.groupBy { it.timestamp / 1000 }
        for ((sec, samples) in imuBySecond) {
            val avgMag = samples.map { it.accelMagnitude.toDouble() }.average()
            // Remover gravidade aproximadamente (subtrair ~9.8)
            val accelNoGravity = abs(avgMag - 9.81)
            imuReduced.add(sec * 1000 to accelNoGravity)
        }
        
        if (gpsAccel.size < 10 || imuReduced.size < 10) {
            return CorrelationResult(
                lagMs = 0,
                correlation = 0.0,
                sampleCount = gpsSamples.size,
                diagnosis = "Dados insuficientes após processamento"
            )
        }
        
        // Cross-correlation: testar lags de -5s a +5s
        var bestLag = 0
        var bestCorrelation = -1.0
        
        for (lag in -5000..5000 step 100) {
            val corr = calculateCorrelation(gpsAccel, imuReduced, lag)
            if (corr > bestCorrelation) {
                bestCorrelation = corr
                bestLag = lag
            }
        }
        
        val diagnosis = when {
            bestLag < 100 -> "GPS quase instantâneo (excelente)"
            bestLag < 300 -> "Latência normal de GNSS consumer"
            bestLag < 500 -> "Filtro de suavização ativo"
            bestLag < 1000 -> "Smoothing agressivo ou batching"
            else -> "Problema sério (batching, Doze, throttling)"
        }
        
        val result = CorrelationResult(
            lagMs = bestLag,
            correlation = bestCorrelation,
            sampleCount = gpsSamples.size,
            diagnosis = diagnosis
        )
        
        correlationResults.add(result)
        while (correlationResults.size > 100) {
            correlationResults.poll()
        }
        
        AuraLog.GPS.i("Correlation analysis: lag=${bestLag}ms, corr=${"%.3f".format(bestCorrelation)}, $diagnosis")
        
        return result
    }
    
    /**
     * Calcula correlação de Pearson entre duas séries temporais com lag
     */
    private fun calculateCorrelation(
        series1: List<Pair<Long, Double>>,
        series2: List<Pair<Long, Double>>,
        lagMs: Int
    ): Double {
        // Alinhar séries com o lag
        val aligned1 = mutableListOf<Double>()
        val aligned2 = mutableListOf<Double>()
        
        for ((t1, v1) in series1) {
            // Encontrar valor em series2 com timestamp + lag
            val targetTime = t1 + lagMs
            val closest = series2.minByOrNull { abs(it.first - targetTime) }
            if (closest != null && abs(closest.first - targetTime) < 1500) { // Tolerância de 1.5s
                aligned1.add(v1)
                aligned2.add(closest.second)
            }
        }
        
        if (aligned1.size < 5) return 0.0
        
        // Normalizar
        val mean1 = aligned1.average()
        val mean2 = aligned2.average()
        val std1 = sqrt(aligned1.map { (it - mean1) * (it - mean1) }.average())
        val std2 = sqrt(aligned2.map { (it - mean2) * (it - mean2) }.average())
        
        if (std1 < 0.001 || std2 < 0.001) return 0.0
        
        // Correlação de Pearson
        var sum = 0.0
        for (i in aligned1.indices) {
            sum += ((aligned1[i] - mean1) / std1) * ((aligned2[i] - mean2) / std2)
        }
        
        return sum / aligned1.size
    }
    
    /**
     * Atualiza estatísticas em tempo real
     */
    private fun updateStats(sample: GpsLatencySample) {
        val samples = gpsLatencySamples.toList()
        if (samples.isEmpty()) return
        
        val ages = samples.map { it.gpsAge }
        val hwLatencies = samples.map { it.hardwareLatency }
        val chipLatencies = samples.map { it.chipsetLatency }
        
        _stats.value = LatencyStats(
            sampleCount = samples.size,
            avgGpsAge = ages.average().toLong(),
            minGpsAge = ages.minOrNull() ?: 0,
            maxGpsAge = ages.maxOrNull() ?: 0,
            p95GpsAge = percentile(ages, 95),
            avgHardwareLatency = hwLatencies.average().toLong(),
            avgChipsetLatency = chipLatencies.average().toLong(),
            lastSampleTime = sample.t2CallbackTime
        )
    }
    
    /**
     * Calcula percentil de uma lista
     */
    private fun percentile(values: List<Long>, percentile: Int): Long {
        if (values.isEmpty()) return 0
        val sorted = values.sorted()
        val index = (sorted.size * percentile / 100).coerceIn(0, sorted.size - 1)
        return sorted[index]
    }
    
    /**
     * Executa diagnóstico completo e retorna resultado
     */
    fun runFullDiagnosis(): LatencyDiagnosis {
        val stats = _stats.value
        val correlation = analyzeCorrelation()
        val samples = gpsLatencySamples.toList()
        
        // Análise de padrões
        val patterns = mutableListOf<String>()
        val causes = mutableListOf<String>()
        val recommendations = mutableListOf<String>()
        
        // Verificar GPS Age
        when {
            stats.avgGpsAge > 500 -> {
                patterns.add("GPS Age alto (${stats.avgGpsAge}ms)")
                causes.add("Hardware GNSS lento ou FusedLocationProvider batching")
                recommendations.add("Verificar CN0, testar LocationManager direto")
            }
            stats.avgGpsAge > 300 -> {
                patterns.add("GPS Age moderado (${stats.avgGpsAge}ms)")
                causes.add("Possível smoothing do FusedLocationProvider")
            }
            else -> {
                patterns.add("GPS Age normal (${stats.avgGpsAge}ms)")
            }
        }
        
        // Verificar Hardware Latency
        when {
            stats.avgHardwareLatency > 200 -> {
                patterns.add("Hardware Latency alto (${stats.avgHardwareLatency}ms)")
                causes.add("FusedLocationProvider adicionando delay")
                recommendations.add("Considerar usar LocationManager com GPS_PROVIDER")
            }
            stats.avgHardwareLatency > 100 -> {
                patterns.add("Hardware Latency moderado (${stats.avgHardwareLatency}ms)")
            }
        }
        
        // Verificar correlação
        when {
            correlation.lagMs > 500 -> {
                patterns.add("Lag IMU vs GPS alto (${correlation.lagMs}ms)")
                causes.add("Filtro de suavização muito agressivo")
                recommendations.add("Usar RAW GNSS Doppler para velocidade")
            }
            correlation.lagMs > 200 -> {
                patterns.add("Lag IMU vs GPS moderado (${correlation.lagMs}ms)")
            }
        }
        
        // Verificar variabilidade (jitter)
        val ageVariance = if (samples.size > 1) {
            val ages = samples.map { it.gpsAge }
            val mean = ages.average()
            ages.map { (it - mean) * (it - mean) }.average()
        } else 0.0
        
        if (sqrt(ageVariance) > 200) {
            patterns.add("Alta variabilidade no GPS Age")
            causes.add("Possível batching ou condições de sinal instáveis")
            recommendations.add("Verificar CN0 e condições de teste")
        }
        
        // Conclusão
        val overallStatus = when {
            stats.avgGpsAge < 200 && correlation.lagMs < 200 -> LatencyStatus.EXCELLENT
            stats.avgGpsAge < 350 && correlation.lagMs < 400 -> LatencyStatus.NORMAL
            stats.avgGpsAge < 500 -> LatencyStatus.ACCEPTABLE
            else -> LatencyStatus.PROBLEMATIC
        }
        
        val diagnosis = LatencyDiagnosis(
            timestamp = System.currentTimeMillis(),
            status = overallStatus,
            stats = stats,
            correlation = correlation,
            patterns = patterns,
            causes = causes,
            recommendations = recommendations,
            conclusion = when (overallStatus) {
                LatencyStatus.EXCELLENT -> "Sistema operando com latência excelente (<200ms)"
                LatencyStatus.NORMAL -> "Latência dentro do esperado para GNSS consumer (200-350ms)"
                LatencyStatus.ACCEPTABLE -> "Latência aceitável mas pode ser otimizada (350-500ms)"
                LatencyStatus.PROBLEMATIC -> "Latência problemática, investigação necessária (>500ms)"
            }
        )
        
        _lastDiagnosis.value = diagnosis
        
        AuraLog.GPS.i("Diagnosis complete: ${overallStatus.name}, avgAge=${stats.avgGpsAge}ms, lag=${correlation.lagMs}ms")
        
        return diagnosis
    }
    
    /**
     * Exporta dados para análise externa (JSON)
     */
    fun exportData(): String {
        val export = DiagnosticsExport(
            exportTime = System.currentTimeMillis(),
            stats = _stats.value,
            lastDiagnosis = _lastDiagnosis.value,
            recentSamples = gpsLatencySamples.toList().takeLast(100),
            correlationHistory = correlationResults.toList()
        )
        return json.encodeToString(export)
    }
    
    /**
     * Limpa todos os dados de diagnóstico
     */
    fun clear() {
        gpsLatencySamples.clear()
        imuSamples.clear()
        correlationResults.clear()
        _stats.value = LatencyStats()
        _lastDiagnosis.value = null
    }
}

// ==================== Modelos ====================

@Serializable
data class GpsLatencySample(
    val t0SatelliteTime: Long,
    val t1HardwareDelivery: Long,
    val t2CallbackTime: Long,
    val gpsAge: Long,           // T2 - T0
    val hardwareLatency: Long,  // T2 - T1
    val chipsetLatency: Long,   // T1 - T0
    val latitude: Double,
    val longitude: Double,
    val speed: Float,
    val accuracy: Float,
    val satellites: Int
)

@Serializable
data class ImuSample(
    val timestamp: Long,
    val accelMagnitude: Float,
    val accelX: Float,
    val accelY: Float,
    val accelZ: Float
)

@Serializable
data class LatencyStats(
    val sampleCount: Int = 0,
    val avgGpsAge: Long = 0,
    val minGpsAge: Long = 0,
    val maxGpsAge: Long = 0,
    val p95GpsAge: Long = 0,
    val avgHardwareLatency: Long = 0,
    val avgChipsetLatency: Long = 0,
    val lastSampleTime: Long = 0
)

@Serializable
data class CorrelationResult(
    val lagMs: Int,
    val correlation: Double,
    val sampleCount: Int,
    val diagnosis: String
)

@Serializable
enum class LatencyStatus {
    EXCELLENT,   // <200ms
    NORMAL,      // 200-350ms
    ACCEPTABLE,  // 350-500ms
    PROBLEMATIC  // >500ms
}

@Serializable
data class LatencyDiagnosis(
    val timestamp: Long,
    val status: LatencyStatus,
    val stats: LatencyStats,
    val correlation: CorrelationResult,
    val patterns: List<String>,
    val causes: List<String>,
    val recommendations: List<String>,
    val conclusion: String
)

@Serializable
data class DiagnosticsExport(
    val exportTime: Long,
    val stats: LatencyStats,
    val lastDiagnosis: LatencyDiagnosis?,
    val recentSamples: List<GpsLatencySample>,
    val correlationHistory: List<CorrelationResult>
)
