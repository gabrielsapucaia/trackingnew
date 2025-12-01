package com.aura.tracking.background

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.PowerManager
import com.aura.tracking.logging.AuraLog

/**
 * PowerSaveModeReceiver - Monitors power save mode changes.
 * Ensures service survives battery saver activation.
 */
class PowerSaveModeReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "PowerSaveReceiver"
    }

    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            PowerManager.ACTION_POWER_SAVE_MODE_CHANGED -> {
                handlePowerSaveModeChanged(context)
            }
            PowerManager.ACTION_DEVICE_IDLE_MODE_CHANGED -> {
                handleDeviceIdleModeChanged(context)
            }
        }
    }

    private fun handlePowerSaveModeChanged(context: Context) {
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        val isPowerSaveMode = powerManager.isPowerSaveMode

        AuraLog.Service.i("Power save mode changed: $isPowerSaveMode")

        if (isPowerSaveMode) {
            AuraLog.Service.w("Power save mode ENABLED - ensuring service continues")
            ensureServiceRunning(context)
        } else {
            AuraLog.Service.i("Power save mode DISABLED")
        }
    }

    private fun handleDeviceIdleModeChanged(context: Context) {
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        val isIdle = powerManager.isDeviceIdleMode

        AuraLog.Service.i("Device idle mode changed: $isIdle")

        if (isIdle) {
            AuraLog.Service.w("Device entering DOZE mode - service should continue with whitelist")
        } else {
            AuraLog.Service.i("Device exiting DOZE mode")
            ensureServiceRunning(context)
        }
    }

    private fun ensureServiceRunning(context: Context) {
        if (!TrackingForegroundService.isRunning) {
            AuraLog.Service.w("Service not running after power state change - restarting")
            try {
                val intent = Intent(context, TrackingForegroundService::class.java)
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                    context.startForegroundService(intent)
                } else {
                    context.startService(intent)
                }
            } catch (e: Exception) {
                AuraLog.Service.e("Failed to restart service after power state change", e)
            }
        }
    }
}
