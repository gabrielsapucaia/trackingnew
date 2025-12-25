package com.aura.tracking.background

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.aura.tracking.AuraTrackingApp
import com.aura.tracking.R
import com.aura.tracking.data.room.AppDatabase
import com.aura.tracking.data.room.ZoneEntity
import com.aura.tracking.logging.AuraLog
import com.aura.tracking.mqtt.MqttClientManager
import com.aura.tracking.sensors.gps.GpsData
import com.aura.tracking.sensors.gps.GpsLocationProvider
import com.aura.tracking.sensors.imu.ImuData
import com.aura.tracking.sensors.imu.ImuSensorProvider
import com.aura.tracking.sensors.orientation.OrientationProvider
import com.aura.tracking.sensors.system.SystemDataProvider
import com.aura.tracking.sensors.motion.MotionDetectorProvider
import com.aura.tracking.geofence.GeofenceContext
import com.aura.tracking.geofence.GeofenceEventFlushWorker
import com.aura.tracking.geofence.GeofenceManager
import com.aura.tracking.geofence.ZoneSyncWorker
import com.aura.tracking.ui.dashboard.DashboardActivity
import com.google.firebase.crashlytics.ktx.crashlytics
import com.google.firebase.ktx.Firebase
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.concurrent.TimeUnit

/**
 * TrackingForegroundService - Foreground service 24/7 para coleta de telemetria.
 * Executa GPS a 1Hz, IMU a 1Hz, publicação MQTT e fila offline.
 * 
 * FASE 3: Integração com sistema de logging persistente, watchdog e recuperação de crash.
 * 
 * FASE 3 - BOOT RECOVERY:
 * - Persiste trackingEnabled=true no start, false no stop
 * - BootCompletedReceiver usa esta flag para reiniciar após reboot
 */
class TrackingForegroundService : Service() {

    companion object {
        private const val TAG = "TrackingService"
        private const val WAKELOCK_TAG = "AuraTracking:TelemetryWakeLock"

        // Estado global do serviço
        @Volatile
        var isRunning: Boolean = false
            private set

        // Timestamps para monitoramento do watchdog
        @Volatile
        var lastGpsTimestamp: Long = 0L

        @Volatile
        var lastImuTimestamp: Long = 0L

        @Volatile
        var lastMqttTimestamp: Long = 0L

        @Volatile
        var isWakeLockHeld: Boolean = false

        // Instância singleton para acesso externo
        @Volatile
        private var instance: TrackingForegroundService? = null

        fun getMqttClient(): MqttClientManager? = instance?.mqttClient
        
        fun getWakeLock(): PowerManager.WakeLock? = instance?.wakeLock

        // Estados reativos globais
        private val _lastGpsData = MutableStateFlow<GpsData?>(null)
        val lastGpsData: StateFlow<GpsData?> = _lastGpsData.asStateFlow()

        private val _lastImuData = MutableStateFlow<ImuData?>(null)
        val lastImuData: StateFlow<ImuData?> = _lastImuData.asStateFlow()

        private val _mqttConnected = MutableStateFlow(false)
        val mqttConnected: StateFlow<Boolean> = _mqttConnected.asStateFlow()

        private val _queueSize = MutableStateFlow(0)
        val queueSize: StateFlow<Int> = _queueSize.asStateFlow()
        
        private val _packetsSent = MutableStateFlow(0L)
        val packetsSent: StateFlow<Long> = _packetsSent.asStateFlow()

        // Geofencing
        private val _currentZone = MutableStateFlow<ZoneEntity?>(null)
        val currentZone: StateFlow<ZoneEntity?> = _currentZone.asStateFlow()

        fun getGeofenceContext(): GeofenceContext? = instance?.geofenceManager?.getGeofenceContext()
    }

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    // Componentes
    private var gpsProvider: GpsLocationProvider? = null
    private var imuProvider: ImuSensorProvider? = null
    private var orientationProvider: OrientationProvider? = null
    private var systemDataProvider: SystemDataProvider? = null
    private var motionDetectorProvider: MotionDetectorProvider? = null
    private var mqttClient: MqttClientManager? = null
    private var telemetryAggregator: TelemetryAggregator? = null
    private var geofenceManager: GeofenceManager? = null
    private var wakeLock: PowerManager.WakeLock? = null

    @Volatile
    private var isStartingDataCollection: Boolean = false

    // Métricas de observabilidade GPS no serviço
    private var gpsAcceptedAfterAccuracy: Long = 0
    private var gpsDiscardedAccuracy: Long = 0

    // Database
    private val database by lazy { AppDatabase.getInstance(this) }

    override fun onCreate() {
        super.onCreate()
        AuraLog.Service.i("Service onCreate")
        instance = this

        // Instala handler de crash recovery
        CrashRecoveryHandler.install(this)

        // Inicializa WakeLock para manter CPU ativa
        val powerManager = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            WAKELOCK_TAG
        ).apply {
            setReferenceCounted(false)
        }

        // Inicializa providers
        gpsProvider = GpsLocationProvider(this)
        imuProvider = ImuSensorProvider(this)
        orientationProvider = OrientationProvider(this)
        systemDataProvider = SystemDataProvider(this)
        // REMOVIDO: motionDetectorProvider = MotionDetectorProvider(this)  // Sensores não disponíveis no dispositivo
        mqttClient = MqttClientManager(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        AuraLog.Service.i("Service onStartCommand (isRunning=$isRunning)")

        // Inicia como foreground
        startForegroundWithNotification()

        // GUARD: Se já está rodando, não reiniciar coleta
        if (isRunning && telemetryAggregator != null) {
            AuraLog.Service.i("Service already running, skipping data collection restart")
            return START_STICKY
        }

        // Adquire WakeLock
        wakeLock?.acquire(24 * 60 * 60 * 1000L) // 24 horas max
        isWakeLockHeld = wakeLock?.isHeld == true
        AuraLog.Service.i("WakeLock acquired: $isWakeLockHeld")

        isRunning = true
        
        // FASE 3 - BOOT RECOVERY: Persiste estado para BootCompletedReceiver
        serviceScope.launch {
            try {
                database.configDao().setTrackingEnabled(true)
                AuraLog.Service.i("TrackingEnabled persisted: true")
            } catch (e: Exception) {
                AuraLog.Service.e("Failed to persist trackingEnabled: ${e.message}")
            }
        }

        // Inicia coleta de dados
        startDataCollection()

        // Agenda workers
        scheduleWorkers()

        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        AuraLog.Service.w("Service onDestroy")
        
        // FASE 3 - BOOT RECOVERY: Persiste estado para BootCompletedReceiver
        // Usa runBlocking apenas aqui pois onDestroy é síncrono e curto
        kotlinx.coroutines.runBlocking {
            try {
                database.configDao().setTrackingEnabled(false)
                AuraLog.Service.i("TrackingEnabled persisted: false")
            } catch (e: Exception) {
                AuraLog.Service.e("Failed to persist trackingEnabled: ${e.message}")
            }
        }

        stopDataCollection()
        
        // Libera WakeLock
        wakeLock?.let {
            if (it.isHeld) it.release()
        }
        isWakeLockHeld = false
        wakeLock = null

        // Cancela workers
        QueueFlushWorker.cancel(this)
        cancelWorkers()

        // Limpa scope
        serviceScope.cancel()

        isRunning = false
        instance = null

        super.onDestroy()
    }

    /**
     * Agenda todos os workers periódicos para monitoramento
     */
    private fun scheduleWorkers() {
        AuraLog.Service.i("Scheduling periodic workers")

        val workManager = WorkManager.getInstance(this)

        // ServiceWatchdogWorker - a cada 15 minutos
        val watchdogWork = PeriodicWorkRequestBuilder<ServiceWatchdogWorker>(
            15, TimeUnit.MINUTES
        ).build()
        workManager.enqueueUniquePeriodicWork(
            ServiceWatchdogWorker.WORK_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            watchdogWork
        )

        // MqttReconnectWorker - a cada 15 minutos (network constrained)
        val mqttReconnectWork = PeriodicWorkRequestBuilder<MqttReconnectWorker>(
            15, TimeUnit.MINUTES
        ).build()
        workManager.enqueueUniquePeriodicWork(
            MqttReconnectWorker.WORK_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            mqttReconnectWork
        )

        // QueueFlushWorker
        QueueFlushWorker.schedule(this)

        // Geofence workers
        ZoneSyncWorker.schedule(this)
        GeofenceEventFlushWorker.schedule(this)

        AuraLog.Service.i("Workers scheduled: Watchdog, MQTT Reconnect, Queue Flush, Zone Sync, Geofence Flush")
    }

    /**
     * Cancela workers periódicos
     */
    private fun cancelWorkers() {
        val workManager = WorkManager.getInstance(this)
        workManager.cancelUniqueWork(ServiceWatchdogWorker.WORK_NAME)
        workManager.cancelUniqueWork(MqttReconnectWorker.WORK_NAME)
        ZoneSyncWorker.cancel(this)
        GeofenceEventFlushWorker.cancel(this)
    }

    private fun startForegroundWithNotification() {
        val notification = createNotification()

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                // Android 14+: Verificar permissões de localização antes de usar FOREGROUND_SERVICE_TYPE_LOCATION
                if (hasLocationPermissions()) {
                    ServiceCompat.startForeground(
                        this,
                        AuraTrackingApp.NOTIFICATION_ID,
                        notification,
                        ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
                    )
                } else {
                    // Fallback: iniciar sem tipo específico (funciona mas não pode acessar localização)
                    AuraLog.Service.w("Starting foreground without location type - missing permissions")
                    startForeground(AuraTrackingApp.NOTIFICATION_ID, notification)
                }
            } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                // Android 10-13: Usar ServiceCompat com tipo location
                ServiceCompat.startForeground(
                    this,
                    AuraTrackingApp.NOTIFICATION_ID,
                    notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
                )
            } else {
                startForeground(AuraTrackingApp.NOTIFICATION_ID, notification)
            }
        } catch (e: Exception) {
            AuraLog.Service.e("Failed to start foreground with location type: ${e.message}", e)
            // Fallback: tentar iniciar sem tipo específico
            try {
                startForeground(AuraTrackingApp.NOTIFICATION_ID, notification)
                AuraLog.Service.w("Started foreground without location type (fallback)")
            } catch (fallbackError: Exception) {
                AuraLog.Service.e("Failed to start foreground service: ${fallbackError.message}", fallbackError)
                // Reportar para Crashlytics mas não crashar
                Firebase.crashlytics.recordException(fallbackError)
            }
        }
    }

    /**
     * Verifica se as permissões de localização foram concedidas.
     */
    private fun hasLocationPermissions(): Boolean {
        return androidx.core.content.ContextCompat.checkSelfPermission(
            this,
            android.Manifest.permission.ACCESS_FINE_LOCATION
        ) == android.content.pm.PackageManager.PERMISSION_GRANTED
    }

    private fun createNotification(): Notification {
        val intent = Intent(this, DashboardActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
        }

        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return NotificationCompat.Builder(this, AuraTrackingApp.NOTIFICATION_CHANNEL_ID)
            .setContentTitle(getString(R.string.notification_title))
            .setContentText(getString(R.string.notification_text))
            .setSmallIcon(R.drawable.ic_notification)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setSilent(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }

    /**
     * Inicia coleta de telemetria GPS 1Hz + IMU 1Hz
     */
    private fun startDataCollection() {
        // GUARD: Evita criar múltiplas instâncias
        if (telemetryAggregator != null) {
            AuraLog.Service.w("Data collection already active, skipping")
            return
        }

        // GUARD: Evita corrida de inicialização (duplo start após crash/restart)
        if (isStartingDataCollection) {
            AuraLog.Service.w("Data collection start already in progress, skipping")
            return
        }
        isStartingDataCollection = true
        
        AuraLog.Service.i("Starting telemetry collection")

        serviceScope.launch {
            try {
                // Carrega configuração inicial
                val config = database.configDao().getConfig()
                // Usa equipmentName como deviceId (tag do equipamento, ex: TRK-101)
                val deviceId = config?.equipmentName ?: android.os.Build.MODEL
                // Obtém operatorId da matrícula do operador logado
                val currentOperator = database.operatorDao().getCurrentOperator()
                val operatorId = currentOperator?.registration?.takeIf { it.isNotEmpty() } ?: "TEST"
                var currentMqttHost = config?.mqttHost ?: "localhost"
                var currentMqttPort = config?.mqttPort ?: 1883

                AuraLog.Service.i("Config loaded: device=$deviceId, operator=$operatorId, mqtt=$currentMqttHost:$currentMqttPort")

                // Configura MQTT inicial
                mqttClient?.configure(currentMqttHost, currentMqttPort)
                mqttClient?.onConnectionStatusChange = { connected ->
                    _mqttConnected.value = connected
                    if (connected) {
                        lastMqttTimestamp = System.currentTimeMillis()
                    }
                    AuraLog.MQTT.i("Connection status changed: $connected")
                }
                mqttClient?.connect()

                // Observa mudanças na configuração e reconecta quando IP mudar
                launch {
                    AuraLog.Service.i("Starting config observer")
                    var isFirstConfig = true
                    try {
                        database.configDao().observeConfig().collect { newConfig ->
                            AuraLog.Service.d("Config observer received update: ${newConfig != null}")
                            
                            if (newConfig == null) {
                                AuraLog.Service.d("Config is null, skipping")
                                return@collect
                            }
                            
                            val newMqttHost = newConfig.mqttHost ?: "localhost"
                            val newMqttPort = newConfig.mqttPort ?: 1883
                            
                            AuraLog.Service.d("Config observed: mqtt=$newMqttHost:$newMqttPort (first=$isFirstConfig)")
                            
                            // Ignora a primeira emissão (configuração inicial)
                            if (isFirstConfig) {
                                isFirstConfig = false
                                currentMqttHost = newMqttHost
                                currentMqttPort = newMqttPort
                                AuraLog.Service.i("Initial config observed: mqtt=$newMqttHost:$newMqttPort")
                                return@collect
                            }
                            
                            // Verifica se houve mudança no host ou porta
                            if (newMqttHost != currentMqttHost || newMqttPort != currentMqttPort) {
                                AuraLog.Service.i("MQTT config changed: $currentMqttHost:$currentMqttPort -> $newMqttHost:$newMqttPort")
                                
                                // Atualiza valores antes de reconectar
                                currentMqttHost = newMqttHost
                                currentMqttPort = newMqttPort
                                
                                // Reconecta com nova configuração
                                AuraLog.MQTT.i("Reconnecting with new config: $newMqttHost:$newMqttPort")
                                
                                // Desconecta do broker atual (aguarda conclusão)
                                mqttClient?.disconnect()
                                
                                // Delay maior para garantir que desconexão termine completamente
                                kotlinx.coroutines.delay(1000)
                                
                                // Reconfigura e reconecta
                                mqttClient?.configure(newMqttHost, newMqttPort)
                                mqttClient?.connect()
                            } else {
                                AuraLog.Service.d("Config unchanged: mqtt=$newMqttHost:$newMqttPort")
                            }
                        }
                    } catch (e: Exception) {
                        AuraLog.Service.e("Error in config observer: ${e.message}", e)
                    }
                }

                // Inicializa agregador
                telemetryAggregator = TelemetryAggregator(
                    mqttClient = mqttClient!!,
                    queueDao = database.telemetryQueueDao(),
                    deviceId = deviceId,
                    operatorId = operatorId
                )

                AuraLog.Service.i("TelemetryAggregator instance created (hashCode=${telemetryAggregator.hashCode()})")

                // Inicializa GeofenceManager
                geofenceManager = GeofenceManager(
                    zoneDao = database.zoneDao(),
                    eventDao = database.geofenceEventDao(),
                    deviceId = deviceId,
                    operatorId = operatorId
                )
                geofenceManager?.loadZones()
                AuraLog.Service.i("GeofenceManager initialized")

                // Observa zona atual
                launch {
                    geofenceManager?.currentZone?.collect { zone ->
                        _currentZone.value = zone
                    }
                }
                
                // IMPORTANTE: Inicia o timer de 1Hz do agregador
                telemetryAggregator?.start()
                AuraLog.Service.i("TelemetryAggregator 1Hz timer started")

                // Observa estatísticas
                launch {
                    telemetryAggregator?.packetsSent?.collect { count ->
                        _packetsSent.value = count
                    }
                }

                // Observa tamanho da fila
                launch {
                    database.telemetryQueueDao().getCountFlow().collect { count ->
                        _queueSize.value = count
                        if (count > 1000) {
                            AuraLog.Queue.w("Queue size high: $count messages")
                        }
                    }
                }

                // Observa conexão MQTT e drena fila quando reconectar
                launch {
                    var wasConnected = false
                    mqttClient?.isConnected?.collect { connected ->
                        _mqttConnected.value = connected
                        
                        // Dispara drenagem quando (re)conectar e há itens na fila
                        if (connected && !wasConnected) {
                            val queueCount = database.telemetryQueueDao().getCount()
                            if (queueCount > 0) {
                                AuraLog.Queue.i("MQTT connected, triggering immediate queue flush ($queueCount items)")
                                drainQueueImmediately()
                            }
                        }
                        wasConnected = connected
                    }
                }

                // Verificador periódico de fila (backup para garantir drenagem)
                launch {
                    AuraLog.Queue.i("Starting periodic queue checker (every 10s)")
                    while (true) {
                        kotlinx.coroutines.delay(10_000) // A cada 10 segundos
                        val isConnected = mqttClient?.isConnected?.value ?: false
                        val queueCount = database.telemetryQueueDao().getCount()
                        AuraLog.Queue.d("Periodic tick: mqtt=$isConnected, queue=$queueCount")
                        if (isConnected && queueCount > 0) {
                            AuraLog.Queue.i("Periodic check: draining $queueCount queued items")
                            drainQueueImmediately()
                        }
                    }
                }

                // Verificador periódico de configuração (fallback caso observer não funcione)
                launch {
                    AuraLog.Service.i("Starting periodic config checker (every 5s)")
                    while (true) {
                        kotlinx.coroutines.delay(5_000) // A cada 5 segundos
                        try {
                            val latestConfig = database.configDao().getConfig()
                            val latestHost = latestConfig?.mqttHost ?: "localhost"
                            val latestPort = latestConfig?.mqttPort ?: 1883
                            
                            AuraLog.Service.d("Periodic config check: current=$currentMqttHost:$currentMqttPort, latest=$latestHost:$latestPort")
                            
                            if (latestHost != currentMqttHost || latestPort != currentMqttPort) {
                                AuraLog.Service.i("Periodic check: MQTT config changed: $currentMqttHost:$currentMqttPort -> $latestHost:$latestPort")
                                currentMqttHost = latestHost
                                currentMqttPort = latestPort
                                
                                // Reconecta com nova configuração
                                AuraLog.MQTT.i("Reconnecting with new config: $latestHost:$latestPort")
                                mqttClient?.disconnect()
                                kotlinx.coroutines.delay(1000)
                                mqttClient?.configure(latestHost, latestPort)
                                mqttClient?.connect()
                            }
                        } catch (e: Exception) {
                            AuraLog.Service.e("Error in periodic config check: ${e.message}", e)
                        }
                    }
                }
            } finally {
                isStartingDataCollection = false
            }
        }

        // Configura callbacks GPS
        gpsProvider?.onGpsDataUpdate = { gpsData ->
            _lastGpsData.value = gpsData
            lastGpsTimestamp = System.currentTimeMillis()

            // Valida precisão - descarta se >25m (Moto G34 optimization)
            if (gpsData.accuracy <= 25f) {
                gpsAcceptedAfterAccuracy++
                telemetryAggregator?.updateGps(gpsData)

                // Verifica geofencing a cada update GPS válido
                geofenceManager?.checkLocation(gpsData)

                if (gpsAcceptedAfterAccuracy % 50L == 0L) {
                    AuraLog.GPS.d("GPS accepted (acc<=25m) count=$gpsAcceptedAfterAccuracy discarded_acc=$gpsDiscardedAccuracy")
                }
                AuraLog.GPS.d("GPS: lat=${gpsData.latitude}, lon=${gpsData.longitude}, acc=${gpsData.accuracy}m")
            } else {
                gpsDiscardedAccuracy++
                if (gpsDiscardedAccuracy % 10L == 0L) {
                    AuraLog.GPS.w("GPS discarded by accuracy (>${25}m): count=$gpsDiscardedAccuracy accepted=$gpsAcceptedAfterAccuracy lastAcc=${gpsData.accuracy}m")
                } else {
                    AuraLog.GPS.w("GPS discarded: accuracy ${gpsData.accuracy}m > 25m threshold")
                }
            }
        }

        // Configura callbacks IMU
        imuProvider?.onImuDataUpdate = { imuData ->
            _lastImuData.value = imuData
            lastImuTimestamp = System.currentTimeMillis()
            telemetryAggregator?.updateImu(imuData)
        }

        // Configura callbacks Orientation
        orientationProvider?.onOrientationDataUpdate = { orientationData ->
            telemetryAggregator?.updateOrientation(orientationData)
        }

        // Configura callbacks System
        systemDataProvider?.onSystemDataUpdate = { systemData ->
            telemetryAggregator?.updateSystemData(systemData)
        }

        // REMOVIDO: Configura callbacks Motion Detection - sensores não disponíveis no dispositivo
        // motionDetectorProvider?.onMotionDetected = { motionData ->
        //     telemetryAggregator?.updateMotionDetection(motionData)
        // }

        // Inicia sensores a 1Hz
        gpsProvider?.startLocationUpdates(1000) // 1Hz
        imuProvider?.startSensorUpdates() // 1Hz averaged output
        orientationProvider?.startOrientationUpdates() // 1Hz
        systemDataProvider?.startSystemUpdates() // 1Hz
        // REMOVIDO: motionDetectorProvider?.startMotionDetection() // Event-based - sensores não disponíveis

        AuraLog.Service.i("Telemetry collection started: GPS 1Hz, IMU 1Hz, Orientation 1Hz, System 1Hz")
    }

    /**
     * Drena a fila imediatamente quando MQTT reconectar
     */
    private fun drainQueueImmediately() {
        serviceScope.launch {
            try {
                val aggregator = telemetryAggregator ?: return@launch
                val acquired = QueueFlushWorker.tryFlushWithLock {
                    var totalSent = 0
                    var iterations = 0
                    val maxIterations = 100 // Limite de segurança

                    while (mqttClient?.isConnected?.value == true && iterations < maxIterations) {
                        val result = aggregator.flushQueue(batchSize = 50)
                        totalSent += result.sent

                        if (result.remaining == 0) {
                            break
                        }

                        if (result.sent == 0 && result.failed > 0) {
                            AuraLog.Queue.w("Queue flush stopped: all failed in batch")
                            break
                        }

                        iterations++
                        // Pequena pausa entre batches
                        kotlinx.coroutines.delay(100)
                    }

                    AuraLog.Queue.i("Immediate queue drain complete: $totalSent messages sent")
                }

                if (!acquired) {
                    AuraLog.Queue.d("Skip immediate drain: another flush is in progress")
                }
            } catch (e: Exception) {
                AuraLog.Queue.e("Failed to drain queue: ${e.message}")
            }
        }
    }

    /**
     * Para coleta de telemetria
     */
    private fun stopDataCollection() {
        AuraLog.Service.i("Stopping telemetry collection")
        isStartingDataCollection = false

        // Para o timer de 1Hz do agregador
        telemetryAggregator?.stop()
        
        gpsProvider?.stopLocationUpdates()
        imuProvider?.stopSensorUpdates()
        orientationProvider?.stopOrientationUpdates()
        systemDataProvider?.stopSystemUpdates()
        // REMOVIDO: motionDetectorProvider?.stopMotionDetection()  // Sensores não disponíveis
        mqttClient?.disconnect()
        geofenceManager?.reset()

        gpsProvider = null
        imuProvider = null
        orientationProvider = null
        systemDataProvider = null
        // REMOVIDO: motionDetectorProvider = null  // Sensores não disponíveis
        mqttClient = null
        telemetryAggregator = null
        geofenceManager = null
    }

    /**
     * Atualiza notificação com status atual
     */
    fun updateNotification(text: String) {
        val notification = NotificationCompat.Builder(this, AuraTrackingApp.NOTIFICATION_CHANNEL_ID)
            .setContentTitle(getString(R.string.notification_title))
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_notification)
            .setOngoing(true)
            .setSilent(true)
            .build()

        val notificationManager = getSystemService(NOTIFICATION_SERVICE) as android.app.NotificationManager
        notificationManager.notify(AuraTrackingApp.NOTIFICATION_ID, notification)
    }
}
