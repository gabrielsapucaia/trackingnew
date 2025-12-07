package com.aura.tracking.sensors.gps

import android.annotation.SuppressLint
import android.content.Context
import android.location.Location
import android.os.Handler
import android.os.Looper
import com.aura.tracking.diagnostics.LatencyDiagnostics
import com.aura.tracking.logging.AuraLog
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.callbackFlow

/**
 * GpsLocationProvider - Provides GPS location updates at 1Hz using FusedLocationProviderClient.
 * Emits GpsData via Kotlin Flow for reactive consumption.
 * 
 * FASE 3: Otimizações industriais para Moto G34:
 * - Auto-recovery de listeners
 * - Detecção de starvation (>30s sem GPS)
 * - Forçar restart agressivo
 * - Logging persistente
 */
class GpsLocationProvider(private val context: Context) {

    companion object {
        private const val TAG = "GpsLocationProvider"

        // 1 Hz = 1000ms interval
        private const val INTERVAL_1HZ_MS = 1000L
        private const val FASTEST_INTERVAL_MS = 500L
        
        // Thresholds para recovery
        private const val GPS_STARVATION_THRESHOLD_MS = 30_000L // 30 segundos sem GPS
        private const val RECOVERY_CHECK_INTERVAL_MS = 10_000L // Verifica a cada 10s
        
        // STALE FILTER: Idade máxima aceitável para uma posição GPS
        // Posições mais antigas que isso são descartadas (causadas por batching em background)
        private const val MAX_LOCATION_AGE_MS = 4000L // 4 segundos, mais tolerante a batching legítimo
    }

    private val fusedLocationClient: FusedLocationProviderClient by lazy {
        LocationServices.getFusedLocationProviderClient(context)
    }

    private var locationCallback: LocationCallback? = null
    private var isRunning = false
    
    // Métricas de observabilidade
    private var totalReceived: Long = 0
    private var totalAccepted: Long = 0
    private var totalDiscardedStale: Long = 0
    private var totalAcceptedByCadence: Long = 0
    
    // Cadência do provedor
    private val recentCallbackIntervalsMs = ArrayDeque<Long>()
    private var lastCallbackElapsedRealtimeNanos: Long = 0L
    private var lastAcceptedElapsedRealtimeNanos: Long = 0L
    private var lastCadenceDegraded: Boolean = false

    // Timestamp da última atualização para detecção de starvation
    private var lastUpdateTimestamp: Long = 0L
    private var recoveryAttempts: Int = 0
    private val recoveryHandler = Handler(Looper.getMainLooper())
    private var recoveryRunnable: Runnable? = null

    // Estado reativo do último dado GPS
    private val _lastGpsData = MutableStateFlow<GpsData?>(null)
    val lastGpsData: StateFlow<GpsData?> = _lastGpsData.asStateFlow()

    // Last known Android Location
    var lastLocation: Location? = null
        private set

    // Listener callback (legacy support)
    var onLocationUpdate: ((Location) -> Unit)? = null

    // Listener para GpsData
    var onGpsDataUpdate: ((GpsData) -> Unit)? = null

    /**
     * Create a LocationRequest for 1Hz high accuracy updates.
     * Otimizado para Moto G34 com configurações agressivas.
     * Força atualizações mesmo quando parado (distância 0).
     */
    private fun createLocationRequest(intervalMs: Long = INTERVAL_1HZ_MS): LocationRequest {
        return LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, intervalMs)
            .setMinUpdateIntervalMillis(FASTEST_INTERVAL_MS)
            .setMaxUpdateDelayMillis(intervalMs) // Sem batching
            .setMinUpdateDistanceMeters(0f) // CRÍTICO: força atualização mesmo parado
            .setWaitForAccurateLocation(false) // Don't wait, we want 1Hz
            .build()
    }

    /**
     * Flow de dados GPS a 1Hz.
     * Emite GpsData a cada atualização de localização.
     */
    @SuppressLint("MissingPermission")
    fun gpsFlow(): Flow<GpsData> = callbackFlow {
        val callback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                val locations = result.locations
                if (locations.isEmpty()) return

                locations.forEach { location ->
                    val gpsData = location.toGpsData()
                    trySend(gpsData)
                }
            }
        }

        val request = createLocationRequest()
        fusedLocationClient.requestLocationUpdates(
            request,
            callback,
            Looper.getMainLooper()
        )
        
        AuraLog.GPS.i("GPS Flow started at 1Hz")

        awaitClose {
            fusedLocationClient.removeLocationUpdates(callback)
            AuraLog.GPS.i("GPS Flow stopped")
        }
    }

    /**
     * Start receiving location updates at 1Hz.
     */
    @SuppressLint("MissingPermission")
    fun startLocationUpdates(intervalMs: Long = INTERVAL_1HZ_MS) {
        if (isRunning) {
            AuraLog.GPS.d("Location updates already running")
            return
        }

        AuraLog.GPS.i("Starting location updates at 1Hz (${intervalMs}ms)")
        lastUpdateTimestamp = System.currentTimeMillis()
        recoveryAttempts = 0

        locationCallback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                val locations = result.locations
                if (locations.isEmpty()) return

                locations.forEach { location ->
                    handleLocationUpdate(location, batchSize = locations.size)
                }
            }
        }

        try {
            val locationRequest = createLocationRequest(intervalMs)
            fusedLocationClient.requestLocationUpdates(
                locationRequest,
                locationCallback!!,
                Looper.getMainLooper()
            )
            isRunning = true
            
            // Inicia monitoramento de starvation
            startStarvationMonitor()
            
            AuraLog.GPS.i("Location updates started at 1Hz")
        } catch (e: Exception) {
            AuraLog.GPS.e("Error starting location updates: ${e.message}")
        }
    }

    /**
     * Stop receiving location updates.
     */
    fun stopLocationUpdates() {
        if (!isRunning) {
            AuraLog.GPS.d("Location updates not running")
            return
        }

        AuraLog.GPS.i("Stopping location updates")

        // Para monitoramento de starvation
        stopStarvationMonitor()

        locationCallback?.let { callback ->
            fusedLocationClient.removeLocationUpdates(callback)
        }
        locationCallback = null
        isRunning = false

        AuraLog.GPS.i("Location updates stopped")
    }

    /**
     * Inicia monitoramento de starvation GPS
     */
    private fun startStarvationMonitor() {
        stopStarvationMonitor() // Limpa qualquer monitor anterior
        
        recoveryRunnable = object : Runnable {
            override fun run() {
                if (!isRunning) return
                
                val timeSinceLastUpdate = System.currentTimeMillis() - lastUpdateTimestamp
                
                if (timeSinceLastUpdate > GPS_STARVATION_THRESHOLD_MS) {
                    AuraLog.GPS.w("GPS starvation detected! ${timeSinceLastUpdate}ms since last update. Attempting recovery...")
                    attemptRecovery()
                }
                
                recoveryHandler.postDelayed(this, RECOVERY_CHECK_INTERVAL_MS)
            }
        }
        
        recoveryHandler.postDelayed(recoveryRunnable!!, RECOVERY_CHECK_INTERVAL_MS)
    }
    
    /**
     * Para monitoramento de starvation
     */
    private fun stopStarvationMonitor() {
        recoveryRunnable?.let { recoveryHandler.removeCallbacks(it) }
        recoveryRunnable = null
    }
    
    /**
     * Tenta recuperar GPS após starvation
     */
    @SuppressLint("MissingPermission")
    private fun attemptRecovery() {
        recoveryAttempts++
        AuraLog.GPS.w("GPS Recovery attempt #$recoveryAttempts")
        
        try {
            // Remove callback atual
            locationCallback?.let { callback ->
                fusedLocationClient.removeLocationUpdates(callback)
            }
            
            // Cria novo callback
            locationCallback = object : LocationCallback() {
                override fun onLocationResult(result: LocationResult) {
                    val locations = result.locations
                    if (locations.isEmpty()) return

                    locations.forEach { location ->
                        handleLocationUpdate(location, batchSize = locations.size)
                    }
                }
            }
            
            // Re-registra com configuração agressiva
            val locationRequest = createLocationRequest(INTERVAL_1HZ_MS)
            fusedLocationClient.requestLocationUpdates(
                locationRequest,
                locationCallback!!,
                Looper.getMainLooper()
            )
            
            AuraLog.GPS.i("GPS recovery: listener re-registered")
            
            // Força uma request de última localização conhecida
            fusedLocationClient.lastLocation.addOnSuccessListener { location ->
                location?.let { 
                    AuraLog.GPS.i("GPS recovery: got last known location")
                    handleLocationUpdate(it) 
                }
            }
            
        } catch (e: Exception) {
            AuraLog.GPS.e("GPS recovery failed: ${e.message}")
        }
    }

    /**
     * Handle a new location update.
     * 
     * LATENCY DIAGNOSTICS: Registra timestamps para diagnóstico de latência.
     * STALE FILTER: Prefere posições recentes, mas aceita stale como fallback.
     */
    private fun handleLocationUpdate(location: Location, batchSize: Int = 1) {
        totalReceived++

        val currentElapsedNanos = android.os.SystemClock.elapsedRealtimeNanos()

        // Atualiza cadência observada do provedor
        if (lastCallbackElapsedRealtimeNanos > 0) {
            val intervalMs = (currentElapsedNanos - lastCallbackElapsedRealtimeNanos) / 1_000_000
            recentCallbackIntervalsMs.addLast(intervalMs)
            if (recentCallbackIntervalsMs.size > 10) {
                recentCallbackIntervalsMs.removeFirst()
            }
        }
        lastCallbackElapsedRealtimeNanos = currentElapsedNanos

        val observedCadenceMs = if (recentCallbackIntervalsMs.isNotEmpty()) {
            recentCallbackIntervalsMs.average().toLong()
        } else {
            INTERVAL_1HZ_MS
        }

        // Considera degradado se média da janela > 2s (duas vezes o alvo)
        val isCadenceDegraded = observedCadenceMs > 2000
        if (isCadenceDegraded != lastCadenceDegraded) {
            AuraLog.GPS.i("Cadence state changed: degraded=$isCadenceDegraded (avg=${observedCadenceMs}ms)")
            lastCadenceDegraded = isCadenceDegraded
        }

        // STALE FILTER: Calcular idade da posição
        val locationAge = android.os.SystemClock.elapsedRealtime() - 
            (location.elapsedRealtimeNanos / 1_000_000)
        
        // LATENCY DIAGNOSTICS: Sempre registra para análise
        LatencyDiagnostics.recordGpsCallback(location)
        
        // Decide se aceita a posição
        val isStale = locationAge > MAX_LOCATION_AGE_MS
        val timeSinceLastValid = System.currentTimeMillis() - lastUpdateTimestamp
        val needsFallback = timeSinceLastValid > GPS_STARVATION_THRESHOLD_MS / 2 // 15s sem dados válidos
        val isBatchDelivery = batchSize > 1 // Aceita pontos atrasados se vierem em lote
        val intervalSinceLastAcceptedMs = if (lastAcceptedElapsedRealtimeNanos > 0) {
            (currentElapsedNanos - lastAcceptedElapsedRealtimeNanos) / 1_000_000
        } else {
            0L
        }

        var temporalQuality = "normal"
        var accepted = false

        if (isStale) {
            if (isCadenceDegraded) {
                temporalQuality = "stale_cadence"
                totalAcceptedByCadence++
                AuraLog.GPS.w("Accepting stale GPS due to degraded cadence: age=${locationAge}ms interval=${intervalSinceLastAcceptedMs}ms observedCadence=${observedCadenceMs}ms")
                accepted = true
            } else if (needsFallback || isBatchDelivery) {
                temporalQuality = "stale_fallback"
                AuraLog.GPS.w("Accepting stale GPS: age=${locationAge}ms (batch=$isBatchDelivery, no valid data for ${timeSinceLastValid}ms)")
                accepted = true
            } else {
                totalDiscardedStale++
                AuraLog.GPS.d("Ignoring stale GPS: age=${locationAge}ms (have recent data, observedCadence=${observedCadenceMs}ms)")
                return // Temos dados recentes, não precisa de fallback
            }
        } else {
            accepted = true
        }

        if (!accepted) return
        
        lastLocation = location
        lastUpdateTimestamp = System.currentTimeMillis()
        lastAcceptedElapsedRealtimeNanos = currentElapsedNanos
        totalAccepted++
        if (totalAccepted % 50L == 0L || totalDiscardedStale % 50L == 0L) {
            AuraLog.GPS.d("GPS metrics: received=$totalReceived accepted=$totalAccepted discarded_stale=$totalDiscardedStale accepted_cadence=$totalAcceptedByCadence")
        }
        
        // Reset recovery attempts ao receber atualização válida
        if (recoveryAttempts > 0) {
            AuraLog.GPS.i("GPS recovered after $recoveryAttempts attempts")
            recoveryAttempts = 0
        }
        
        // Converte para GpsData
        val gpsData = location.toGpsData(
            ageMs = locationAge,
            intervalSinceLastFixMs = intervalSinceLastAcceptedMs,
            temporalQuality = temporalQuality
        )
        _lastGpsData.value = gpsData

        AuraLog.GPS.d("GPS: lat=${gpsData.latitude}, lon=${gpsData.longitude}, " +
                "speed=${gpsData.speedKmh}km/h, acc=${gpsData.accuracy}m, age=${locationAge}ms, interval=${intervalSinceLastAcceptedMs}ms, tq=${temporalQuality}")

        // Notifica listeners
        onLocationUpdate?.invoke(location)
        onGpsDataUpdate?.invoke(gpsData)
    }

    /**
     * Converte Location para GpsData
     */
    private fun Location.toGpsData(
        ageMs: Long = 0L,
        intervalSinceLastFixMs: Long = 0L,
        temporalQuality: String = "normal"
    ): GpsData {
        return GpsData(
            latitude = latitude,
            longitude = longitude,
            altitude = altitude,
            speed = speed,
            bearing = bearing,
            accuracy = accuracy,
            timestamp = time,
            ageMs = ageMs,
            intervalSinceLastFixMs = intervalSinceLastFixMs,
            temporalQuality = temporalQuality
        )
    }

    /**
     * Get the last known location (one-shot).
     */
    @SuppressLint("MissingPermission")
    fun getLastKnownLocation(callback: (Location?) -> Unit) {
        fusedLocationClient.lastLocation
            .addOnSuccessListener { location ->
                AuraLog.GPS.d("Last known location: $location")
                location?.let { handleLocationUpdate(it) }
                callback(location)
            }
            .addOnFailureListener { exception ->
                AuraLog.GPS.e("Error getting last location: ${exception.message}")
                callback(null)
            }
    }

    /**
     * Check if location updates are currently running.
     */
    fun isRunning(): Boolean = isRunning
    
    /**
     * Retorna tempo desde última atualização GPS em ms
     */
    fun getTimeSinceLastUpdate(): Long {
        return if (lastUpdateTimestamp > 0) {
            System.currentTimeMillis() - lastUpdateTimestamp
        } else {
            Long.MAX_VALUE
        }
    }
    
    /**
     * Retorna número de tentativas de recovery
     */
    fun getRecoveryAttempts(): Int = recoveryAttempts
}
