package com.aura.tracking

import android.app.Activity
import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.WindowManager
import androidx.work.Configuration
import androidx.work.WorkManager
import com.aura.tracking.background.SyncDataWorker
import com.aura.tracking.data.model.Operator
import com.aura.tracking.data.room.AppDatabase
import com.aura.tracking.data.supabase.SupabaseApi
import com.aura.tracking.analytics.TelemetryAnalytics
import com.aura.tracking.data.supabase.SupabaseApiImpl
import com.aura.tracking.logging.LogWriter
import com.google.firebase.crashlytics.ktx.crashlytics
import com.google.firebase.ktx.Firebase

/**
 * Application class for AuraTracking.
 * Initializes core dependencies using Manual DI pattern.
 *
 * FASE 3: Inicialização do sistema de logging persistente.
 */
class AuraTrackingApp : Application() {

    // Database instance (lazy initialization)
    val database: AppDatabase by lazy {
        AppDatabase.getInstance(this)
    }

    // Supabase API instance (lazy initialization)
    val supabaseApi: SupabaseApi by lazy {
        SupabaseApiImpl()
    }

    override fun onCreate() {
        super.onCreate()
        instance = this

        // Inicializa sistema de logging persistente
        LogWriter.getInstance(this)
        keepScreenAwake()

        // Inicializa Firebase Crashlytics
        initializeCrashlytics()

        // Inicializa TelemetryAnalytics (métricas de qualidade)
        TelemetryAnalytics.initialize()

        createNotificationChannel()
        createWatchdogNotificationChannel()

        // Inicializa WorkManager
        val config = Configuration.Builder()
            .setMinimumLoggingLevel(android.util.Log.INFO)
            .build()
        WorkManager.initialize(this, config)

        // Agenda sincronização automática de dados
        SyncDataWorker.schedule(this)
    }

    /**
     * Inicializa Firebase Crashlytics com contexto do dispositivo.
     * Permite identificar crashes por device e versão do app.
     */
    private fun initializeCrashlytics() {
        val deviceId = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID)

        Firebase.crashlytics.apply {
            setCrashlyticsCollectionEnabled(true)

            // Contexto para identificar device
            setCustomKey("device_id", deviceId ?: "unknown")
            setCustomKey("app_version", BuildConfig.VERSION_NAME)
            setCustomKey("build_type", BuildConfig.BUILD_TYPE)

            // Device info
            setCustomKey("device_model", Build.MODEL)
            setCustomKey("device_manufacturer", Build.MANUFACTURER)
            setCustomKey("android_version", Build.VERSION.RELEASE)
            setCustomKey("sdk_version", Build.VERSION.SDK_INT)
        }
    }

    /**
     * Atualiza contexto do Crashlytics quando operador faz login.
     * Permite correlacionar crashes com operadores específicos.
     */
    fun setOperatorContext(operator: Operator) {
        Firebase.crashlytics.apply {
            setUserId(operator.id.toString())
            setCustomKey("operator_name", operator.name)
            setCustomKey("operator_registration", operator.registration)
        }
    }

    /**
     * Limpa contexto do operador no logout.
     */
    fun clearOperatorContext() {
        Firebase.crashlytics.apply {
            setUserId("")
            setCustomKey("operator_name", "")
            setCustomKey("operator_registration", "")
        }
    }

    /**
     * Creates the notification channel for the foreground service.
     * Required for Android 8.0 (API 26) and above.
     */
    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                getString(R.string.notification_channel_name),
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = getString(R.string.notification_channel_description)
                setShowBadge(false)
            }

            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannel(channel)
        }
    }
    
    /**
     * Mantém a tela ligada enquanto qualquer Activity do app estiver visível.
     */
    private fun keepScreenAwake() {
        registerActivityLifecycleCallbacks(object : ActivityLifecycleCallbacks {
            override fun onActivityCreated(activity: Activity, savedInstanceState: Bundle?) {
                activity.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            }

            override fun onActivityResumed(activity: Activity) {
                activity.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            }

            override fun onActivityDestroyed(activity: Activity) {
                activity.window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            }

            override fun onActivityStarted(activity: Activity) {}
            override fun onActivityPaused(activity: Activity) {}
            override fun onActivityStopped(activity: Activity) {}
            override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) {}
        })
    }
    
    /**
     * Creates notification channel for watchdog alerts.
     */
    private fun createWatchdogNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                WATCHDOG_CHANNEL_ID,
                "Watchdog Alerts",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Silent notifications for service recovery"
                setShowBadge(false)
                setSound(null, null)
            }

            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannel(channel)
        }
    }

    companion object {
        const val NOTIFICATION_CHANNEL_ID = "aura_tracking_channel"
        const val WATCHDOG_CHANNEL_ID = "aura_watchdog_channel"
        const val NOTIFICATION_ID = 1001
        const val WATCHDOG_NOTIFICATION_ID = 1002

        @Volatile
        private var instance: AuraTrackingApp? = null

        fun getInstance(): AuraTrackingApp {
            return instance ?: throw IllegalStateException(
                "AuraTrackingApp has not been initialized yet"
            )
        }

        // Convenience accessors for dependencies
        val database: AppDatabase
            get() = getInstance().database

        val supabaseApi: SupabaseApi
            get() = getInstance().supabaseApi
    }
}
