package com.aura.tracking.background

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.aura.tracking.data.room.AppDatabase
import com.aura.tracking.util.ServiceStarter
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * BootCompletedReceiver - Restarts the tracking service after device reboot.
 *
 * This receiver is triggered when:
 * - BOOT_COMPLETED: After full system boot
 * - QUICKBOOT_POWERON: After quick boot (some devices)
 *
 * FASE 3 - BOOT RECOVERY:
 * O serviço só é reiniciado se estava ativo antes do reboot (trackingEnabled=true).
 * Isso evita reiniciar o tracking se o usuário parou manualmente.
 * 
 * Compatibilidade: Android 12/13/14 (testado)
 */
class BootCompletedReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "BootCompletedReceiver"
        
        // Debounce para evitar múltiplos restarts em quick succession
        private const val DEBOUNCE_KEY = "last_boot_restart_time"
        private const val DEBOUNCE_MS = 30_000L  // 30 segundos
    }

    override fun onReceive(context: Context, intent: Intent) {
        Log.d(TAG, "Received broadcast: ${intent.action}")

        when (intent.action) {
            Intent.ACTION_BOOT_COMPLETED,
            "android.intent.action.QUICKBOOT_POWERON" -> {
                handleBootCompleted(context)
            }
        }
    }

    /**
     * Handle boot completed event.
     * Verifica no Room se o tracking estava ativo e reinicia se necessário.
     */
    private fun handleBootCompleted(context: Context) {
        Log.d(TAG, "Device boot completed, checking if service should restart")

        // Verifica debounce para evitar múltiplos restarts
        val prefs = context.getSharedPreferences("aura_boot", Context.MODE_PRIVATE)
        val lastRestart = prefs.getLong(DEBOUNCE_KEY, 0L)
        val now = System.currentTimeMillis()
        
        if (now - lastRestart < DEBOUNCE_MS) {
            Log.d(TAG, "Debounce active, skipping restart (last: ${now - lastRestart}ms ago)")
            return
        }

        // Use a coroutine to check database
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val shouldRestart = checkShouldRestartService(context)

                if (shouldRestart) {
                    Log.i(TAG, "✅ Restarting tracking service (was active before reboot)")
                    
                    // Atualiza timestamp de debounce
                    prefs.edit().putLong(DEBOUNCE_KEY, now).apply()
                    
                    // Inicia o serviço na main thread
                    CoroutineScope(Dispatchers.Main).launch {
                        ServiceStarter.startTrackingService(context)
                    }
                } else {
                    Log.d(TAG, "Not restarting service - tracking was not active before reboot")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error handling boot completed: ${e.message}", e)
            }
        }
    }

    /**
     * Verifica se o serviço de tracking deve ser reiniciado.
     * 
     * Condições para reiniciar:
     * 1. Existe configuração salva (operador logado)
     * 2. trackingEnabled == true (tracking estava ativo)
     * 
     * @return true se deve reiniciar, false caso contrário
     */
    private suspend fun checkShouldRestartService(context: Context): Boolean {
        val database = AppDatabase.getInstance(context)
        val configDao = database.configDao()
        
        // Verifica se existe configuração
        val hasConfig = configDao.hasConfig()
        if (!hasConfig) {
            Log.d(TAG, "No config found, not restarting")
            return false
        }
        
        // Verifica se tracking estava ativo
        val trackingEnabled = configDao.isTrackingEnabled() ?: false
        Log.d(TAG, "Config found, trackingEnabled=$trackingEnabled")
        
        return trackingEnabled
    }
}
