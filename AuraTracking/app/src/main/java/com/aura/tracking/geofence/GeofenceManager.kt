package com.aura.tracking.geofence

import com.aura.tracking.data.room.GeofenceEventDao
import com.aura.tracking.data.room.GeofenceEventEntity
import com.aura.tracking.data.room.GeofenceEventType
import com.aura.tracking.data.room.ZoneDao
import com.aura.tracking.data.room.ZoneEntity
import com.aura.tracking.logging.AuraLog
import com.aura.tracking.sensors.gps.GpsData
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlin.math.PI
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * GeofenceManager - Gerencia detecção de entrada/saída em zonas geográficas.
 *
 * Características:
 * - Suporte a polígonos e círculos
 * - Detecção em tempo real (1Hz com updates GPS)
 * - Hysteresis para evitar flapping (entrada/saída rápida)
 * - Registro de eventos com duração
 * - StateFlow reativo para UI
 *
 * Uso:
 * ```kotlin
 * val manager = GeofenceManager(zoneDao, eventDao, deviceId, operatorId)
 * manager.loadZones()
 * manager.checkLocation(gpsData)
 * ```
 */
class GeofenceManager(
    private val zoneDao: ZoneDao,
    private val eventDao: GeofenceEventDao,
    private val deviceId: String,
    private val operatorId: String
) {
    companion object {
        private const val TAG = "GeofenceManager"

        // Hysteresis: distância mínima para confirmar entrada/saída (metros)
        private const val HYSTERESIS_METERS = 10.0

        // Tempo mínimo dentro da zona para confirmar entrada (ms)
        private const val MIN_DWELL_TIME_MS = 5_000L  // 5 segundos

        // Raio da Terra em metros (para cálculos de distância)
        private const val EARTH_RADIUS_METERS = 6_371_000.0
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    // Zonas ativas em cache
    private var zones: List<ZoneEntity> = emptyList()

    // Estado atual de cada zona (zoneId -> ZoneState)
    private val zoneStates = mutableMapOf<Long, ZoneState>()

    // Zona atual (última zona em que o dispositivo está)
    private val _currentZone = MutableStateFlow<ZoneEntity?>(null)
    val currentZone: StateFlow<ZoneEntity?> = _currentZone.asStateFlow()

    // Lista de zonas em que o dispositivo está atualmente
    private val _activeZones = MutableStateFlow<List<ZoneEntity>>(emptyList())
    val activeZones: StateFlow<List<ZoneEntity>> = _activeZones.asStateFlow()

    // Último evento registrado
    private val _lastEvent = MutableStateFlow<GeofenceEventEntity?>(null)
    val lastEvent: StateFlow<GeofenceEventEntity?> = _lastEvent.asStateFlow()

    // Callback para notificar eventos
    var onGeofenceEvent: ((GeofenceEventEntity) -> Unit)? = null

    /**
     * Carrega zonas do banco de dados
     */
    suspend fun loadZones() {
        try {
            zones = zoneDao.getActiveZones()
            AuraLog.Geofence.i("Loaded ${zones.size} active zones")

            // Inicializa estados das zonas
            zones.forEach { zone ->
                if (!zoneStates.containsKey(zone.id)) {
                    zoneStates[zone.id] = ZoneState()
                }
            }
        } catch (e: Exception) {
            AuraLog.Geofence.e("Failed to load zones: ${e.message}")
        }
    }

    /**
     * Recarrega zonas (após sync com Supabase)
     */
    fun reloadZones() {
        scope.launch {
            loadZones()
        }
    }

    /**
     * Verifica localização atual contra todas as zonas.
     * Deve ser chamado a cada update GPS (~1Hz).
     */
    fun checkLocation(gpsData: GpsData) {
        if (zones.isEmpty()) return

        scope.launch {
            val currentlyInside = mutableListOf<ZoneEntity>()

            zones.forEach { zone ->
                val isInside = isInsideZone(gpsData.latitude, gpsData.longitude, zone)
                val state = zoneStates.getOrPut(zone.id) { ZoneState() }

                processZoneState(zone, state, isInside, gpsData)

                if (state.isConfirmedInside) {
                    currentlyInside.add(zone)
                }
            }

            // Atualiza zona atual (prioridade: loading > unloading > outros)
            val priorityZone = currentlyInside
                .sortedBy { zonePriority(it.zoneType) }
                .firstOrNull()

            _currentZone.value = priorityZone
            _activeZones.value = currentlyInside
        }
    }

    /**
     * Processa mudança de estado para uma zona específica
     */
    private suspend fun processZoneState(
        zone: ZoneEntity,
        state: ZoneState,
        isCurrentlyInside: Boolean,
        gpsData: GpsData
    ) {
        val now = System.currentTimeMillis()

        when {
            // Caso 1: Entrou na zona (transição de fora para dentro)
            isCurrentlyInside && !state.isConfirmedInside -> {
                if (state.pendingEntryTime == null) {
                    // Primeira detecção - inicia timer de confirmação
                    state.pendingEntryTime = now
                    state.entryLocation = gpsData
                    AuraLog.Geofence.d("Pending entry to zone ${zone.name}")
                } else if (now - state.pendingEntryTime!! >= MIN_DWELL_TIME_MS) {
                    // Confirmou entrada (passou tempo mínimo)
                    state.isConfirmedInside = true
                    state.entryTimestamp = state.pendingEntryTime
                    state.pendingEntryTime = null

                    val event = createEvent(
                        zone = zone,
                        eventType = GeofenceEventType.ENTER,
                        gpsData = state.entryLocation ?: gpsData
                    )
                    saveAndNotifyEvent(event)

                    AuraLog.Geofence.i("ENTERED zone: ${zone.name} (${zone.zoneType})")
                }
            }

            // Caso 2: Saiu da zona (transição de dentro para fora)
            !isCurrentlyInside && state.isConfirmedInside -> {
                val durationSeconds = state.entryTimestamp?.let {
                    ((now - it) / 1000).toInt()
                } ?: 0

                val event = createEvent(
                    zone = zone,
                    eventType = GeofenceEventType.EXIT,
                    gpsData = gpsData,
                    durationSeconds = durationSeconds
                )
                saveAndNotifyEvent(event)

                // Reset estado
                state.isConfirmedInside = false
                state.entryTimestamp = null
                state.pendingEntryTime = null
                state.entryLocation = null

                AuraLog.Geofence.i("EXITED zone: ${zone.name} after ${durationSeconds}s")
            }

            // Caso 3: Saiu antes de confirmar entrada (cancelar pending)
            !isCurrentlyInside && state.pendingEntryTime != null -> {
                state.pendingEntryTime = null
                state.entryLocation = null
                AuraLog.Geofence.d("Cancelled pending entry to zone ${zone.name}")
            }
        }
    }

    /**
     * Cria entidade de evento de geofencing
     */
    private fun createEvent(
        zone: ZoneEntity,
        eventType: String,
        gpsData: GpsData,
        durationSeconds: Int = 0
    ): GeofenceEventEntity {
        return GeofenceEventEntity(
            zoneId = zone.id,
            zoneName = zone.name,
            zoneType = zone.zoneType,
            eventType = eventType,
            durationSeconds = durationSeconds,
            latitude = gpsData.latitude,
            longitude = gpsData.longitude,
            gpsAccuracy = gpsData.accuracy,
            speed = gpsData.speed,
            deviceId = deviceId,
            operatorId = operatorId
        )
    }

    /**
     * Salva evento e notifica listeners
     */
    private suspend fun saveAndNotifyEvent(event: GeofenceEventEntity) {
        try {
            val id = eventDao.insert(event)
            val savedEvent = event.copy(id = id)
            _lastEvent.value = savedEvent
            onGeofenceEvent?.invoke(savedEvent)
        } catch (e: Exception) {
            AuraLog.Geofence.e("Failed to save geofence event: ${e.message}")
        }
    }

    /**
     * Verifica se um ponto está dentro de uma zona
     */
    private fun isInsideZone(lat: Double, lon: Double, zone: ZoneEntity): Boolean {
        return when {
            zone.isCircular() -> isInsideCircle(lat, lon, zone)
            zone.isPolygon() -> isInsidePolygon(lat, lon, zone)
            else -> false
        }
    }

    /**
     * Verifica se ponto está dentro de círculo
     */
    private fun isInsideCircle(lat: Double, lon: Double, zone: ZoneEntity): Boolean {
        val centerLat = zone.centerLat ?: return false
        val centerLon = zone.centerLon ?: return false
        val radius = zone.radiusMeters ?: return false

        val distance = haversineDistance(lat, lon, centerLat, centerLon)
        return distance <= radius + HYSTERESIS_METERS
    }

    /**
     * Verifica se ponto está dentro de polígono usando ray casting
     */
    private fun isInsidePolygon(lat: Double, lon: Double, zone: ZoneEntity): Boolean {
        val polygon = parsePolygon(zone.polygonJson) ?: return false
        if (polygon.size < 3) return false

        var inside = false
        var j = polygon.size - 1

        for (i in polygon.indices) {
            val xi = polygon[i].first
            val yi = polygon[i].second
            val xj = polygon[j].first
            val yj = polygon[j].second

            if (((yi > lon) != (yj > lon)) &&
                (lat < (xj - xi) * (lon - yi) / (yj - yi) + xi)) {
                inside = !inside
            }
            j = i
        }

        return inside
    }

    /**
     * Parse JSON de polígono para lista de coordenadas
     */
    private fun parsePolygon(json: String?): List<Pair<Double, Double>>? {
        if (json.isNullOrEmpty()) return null

        return try {
            val coordinates = Json.decodeFromString<List<List<Double>>>(json)
            coordinates.map { Pair(it[0], it[1]) }
        } catch (e: Exception) {
            AuraLog.Geofence.e("Failed to parse polygon: ${e.message}")
            null
        }
    }

    /**
     * Calcula distância Haversine entre dois pontos (metros)
     */
    private fun haversineDistance(
        lat1: Double, lon1: Double,
        lat2: Double, lon2: Double
    ): Double {
        val dLat = Math.toRadians(lat2 - lat1)
        val dLon = Math.toRadians(lon2 - lon1)

        val a = sin(dLat / 2) * sin(dLat / 2) +
                cos(Math.toRadians(lat1)) * cos(Math.toRadians(lat2)) *
                sin(dLon / 2) * sin(dLon / 2)

        val c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return EARTH_RADIUS_METERS * c
    }

    /**
     * Prioridade de tipos de zona (menor = maior prioridade)
     */
    private fun zonePriority(type: String): Int {
        return when (type) {
            "loading_zone" -> 1
            "unloading_zone" -> 2
            "deposit" -> 3
            "maintenance" -> 4
            "fuel_station" -> 5
            "parking" -> 6
            else -> 10
        }
    }

    /**
     * Obtém contexto de geofencing para telemetria
     */
    fun getGeofenceContext(): GeofenceContext? {
        val zone = _currentZone.value ?: return null
        return GeofenceContext(
            zoneId = zone.id,
            zoneName = zone.name,
            zoneType = zone.zoneType
        )
    }

    /**
     * Limpa estado (ao parar tracking)
     */
    fun reset() {
        zoneStates.clear()
        _currentZone.value = null
        _activeZones.value = emptyList()
        _lastEvent.value = null
    }

    /**
     * Estado interno de uma zona
     */
    private class ZoneState {
        var isConfirmedInside: Boolean = false
        var entryTimestamp: Long? = null
        var pendingEntryTime: Long? = null
        var entryLocation: GpsData? = null
    }
}

/**
 * Contexto de geofencing para incluir na telemetria
 */
data class GeofenceContext(
    val zoneId: Long,
    val zoneName: String,
    val zoneType: String
)
