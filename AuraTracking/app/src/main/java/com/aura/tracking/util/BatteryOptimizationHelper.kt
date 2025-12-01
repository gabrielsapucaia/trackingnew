package com.aura.tracking.util

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.appcompat.app.AlertDialog
import com.aura.tracking.logging.AuraLog

/**
 * BatteryOptimizationHelper - Helps bypass Doze mode and battery optimizations.
 * Critical for 24/7 telemetry operation on Moto G34.
 */
object BatteryOptimizationHelper {

    private const val TAG = "BatteryOptHelper"

    /**
     * Check if app is ignoring battery optimizations (whitelisted from Doze)
     */
    fun isIgnoringBatteryOptimizations(context: Context): Boolean {
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        return powerManager.isIgnoringBatteryOptimizations(context.packageName)
    }

    /**
     * Request to be added to battery optimization whitelist.
     * Opens system settings if direct request not possible.
     */
    fun requestIgnoreBatteryOptimizations(context: Context): Boolean {
        if (isIgnoringBatteryOptimizations(context)) {
            AuraLog.i(TAG, "Already ignoring battery optimizations")
            return true
        }

        return try {
            val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                data = Uri.parse("package:${context.packageName}")
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
            AuraLog.i(TAG, "Requested ignore battery optimizations")
            true
        } catch (e: Exception) {
            AuraLog.e(TAG, "Failed to request battery optimization exemption: ${e.message}")
            // Fallback to settings page
            openBatteryOptimizationSettings(context)
            false
        }
    }

    /**
     * Open battery optimization settings page
     */
    fun openBatteryOptimizationSettings(context: Context) {
        try {
            val intent = Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            AuraLog.e(TAG, "Failed to open battery settings: ${e.message}")
            // Fallback to general settings
            try {
                val intent = Intent(Settings.ACTION_SETTINGS).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                context.startActivity(intent)
            } catch (e2: Exception) {
                AuraLog.e(TAG, "Failed to open settings: ${e2.message}")
            }
        }
    }

    /**
     * Check if power save mode is active
     */
    fun isPowerSaveMode(context: Context): Boolean {
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        return powerManager.isPowerSaveMode
    }

    /**
     * Check if device is in idle mode (Doze)
     */
    fun isDeviceIdleMode(context: Context): Boolean {
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        return powerManager.isDeviceIdleMode
    }

    /**
     * Get comprehensive battery optimization status
     */
    fun getOptimizationStatus(context: Context): OptimizationStatus {
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        
        return OptimizationStatus(
            isIgnoringOptimizations = powerManager.isIgnoringBatteryOptimizations(context.packageName),
            isPowerSaveMode = powerManager.isPowerSaveMode,
            isDeviceIdle = powerManager.isDeviceIdleMode,
            isInteractive = powerManager.isInteractive
        )
    }

    /**
     * Ensure all optimizations are disabled for reliable background operation
     */
    fun ensureOptimalConfiguration(context: Context): Boolean {
        val status = getOptimizationStatus(context)
        
        AuraLog.i(TAG, "Optimization status: $status")
        
        if (!status.isIgnoringOptimizations) {
            AuraLog.w(TAG, "App is NOT ignoring battery optimizations - requesting exemption")
            requestIgnoreBatteryOptimizations(context)
            return false
        }
        
        if (status.isPowerSaveMode) {
            AuraLog.w(TAG, "Power save mode is active - may affect telemetry")
        }
        
        if (status.isDeviceIdle) {
            AuraLog.w(TAG, "Device is in idle/Doze mode")
        }
        
        return status.isIgnoringOptimizations
    }

    /**
     * Get Motorola-specific battery optimization intent (for Moto G34)
     */
    fun getMotorolaOptimizationIntent(): Intent? {
        return try {
            Intent().apply {
                component = android.content.ComponentName(
                    "com.motorola.ccc.mainplm",
                    "com.motorola.ccc.mainplm.PlmActivity"
                )
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
        } catch (e: Exception) {
            null
        }
    }

    /**
     * Open Motorola-specific battery settings if available
     */
    fun openMotorolaBatterySettings(context: Context): Boolean {
        return try {
            getMotorolaOptimizationIntent()?.let { intent ->
                context.startActivity(intent)
                true
            } ?: false
        } catch (e: Exception) {
            AuraLog.w(TAG, "Motorola battery settings not available: ${e.message}")
            false
        }
    }

    data class OptimizationStatus(
        val isIgnoringOptimizations: Boolean,
        val isPowerSaveMode: Boolean,
        val isDeviceIdle: Boolean,
        val isInteractive: Boolean
    ) {
        val isOptimal: Boolean
            get() = isIgnoringOptimizations && !isPowerSaveMode && !isDeviceIdle
    }

    /**
     * Mostra dialog explicando a necessidade de desativar otimização
     * e leva o usuário para a configuração.
     */
    fun showBatteryOptimizationDialog(context: Context, onConfigured: (() -> Unit)? = null) {
        AlertDialog.Builder(context)
            .setTitle("⚠️ Otimização de Bateria Ativa")
            .setMessage(
                "Para garantir que o rastreamento funcione continuamente sem interrupções, " +
                "é OBRIGATÓRIO desativar a otimização de bateria para este app.\n\n" +
                "⚠️ Sem esta configuração, o Android IRÁ pausar a coleta de dados!\n\n" +
                "Na próxima tela:\n" +
                "• Selecione \"Permitir\" ou \"Não otimizar\""
            )
            .setPositiveButton("Configurar Agora") { dialog, _ ->
                requestIgnoreBatteryOptimizations(context)
                dialog.dismiss()
                onConfigured?.invoke()
            }
            .setCancelable(false)
            .show()
    }

    /**
     * Mostra dialog para configurações adicionais de economia de bateria
     * específicas de fabricantes (Motorola, Samsung, Xiaomi, etc.)
     */
    fun showManufacturerBatteryDialog(context: Context, onDismiss: (() -> Unit)? = null) {
        val manufacturer = Build.MANUFACTURER.lowercase()
        
        val message = when {
            manufacturer.contains("motorola") -> {
                "📱 Dispositivo Motorola detectado.\n\n" +
                "Configuração adicional IMPORTANTE:\n\n" +
                "1. Toque em \"Abrir Configurações\"\n" +
                "2. Toque em \"Bateria\"\n" +
                "3. Selecione \"Sem restrições\"\n\n" +
                "Isso garante que o app não será pausado."
            }
            manufacturer.contains("samsung") -> {
                "📱 Dispositivo Samsung detectado.\n\n" +
                "Configuração adicional:\n\n" +
                "1. Toque em \"Abrir Configurações\"\n" +
                "2. Bateria → Uso em segundo plano\n" +
                "3. Selecione \"Irrestrito\""
            }
            manufacturer.contains("xiaomi") || manufacturer.contains("redmi") -> {
                "📱 Dispositivo Xiaomi/Redmi detectado.\n\n" +
                "Configuração adicional:\n\n" +
                "1. Toque em \"Abrir Configurações\"\n" +
                "2. Economia de bateria → Sem restrições\n" +
                "3. Também desative \"MIUI Optimization\""
            }
            else -> {
                "📱 Configuração adicional recomendada:\n\n" +
                "1. Toque em \"Abrir Configurações\"\n" +
                "2. Vá em Bateria\n" +
                "3. Selecione \"Sem restrições\" ou \"Irrestrito\""
            }
        }

        AlertDialog.Builder(context)
            .setTitle("🔋 Configuração de Bateria do App")
            .setMessage(message)
            .setPositiveButton("Abrir Configurações") { dialog, _ ->
                openAppSettings(context)
                dialog.dismiss()
                onDismiss?.invoke()
            }
            .setNegativeButton("Já Configurei") { dialog, _ ->
                dialog.dismiss()
                onDismiss?.invoke()
            }
            .setCancelable(false)
            .show()
    }

    /**
     * Abre configurações do app diretamente.
     */
    fun openAppSettings(context: Context) {
        try {
            val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                data = Uri.parse("package:${context.packageName}")
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            AuraLog.e(TAG, "Failed to open app settings: ${e.message}")
        }
    }

    /**
     * Verifica e solicita desativação de otimização de bateria.
     * Mostra dialogs apropriados se necessário.
     * 
     * @return true se já está configurado corretamente
     */
    fun checkAndRequestOptimization(
        context: Context,
        onComplete: ((isConfigured: Boolean) -> Unit)? = null
    ): Boolean {
        if (isIgnoringBatteryOptimizations(context)) {
            AuraLog.i(TAG, "Battery optimization already disabled - OK")
            onComplete?.invoke(true)
            return true
        }

        AuraLog.w(TAG, "Battery optimization is ACTIVE - showing dialog")
        showBatteryOptimizationDialog(context) {
            // Após configurar, mostra dicas do fabricante
            showManufacturerBatteryDialog(context) {
                onComplete?.invoke(isIgnoringBatteryOptimizations(context))
            }
        }
        return false
    }
}
