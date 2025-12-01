package com.aura.tracking.util

import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import com.aura.tracking.background.TrackingForegroundService

/**
 * ServiceStarter - Utility class for starting and stopping the tracking service.
 */
object ServiceStarter {

    private const val TAG = "ServiceStarter"

    /**
     * Start the tracking foreground service.
     */
    fun startTrackingService(context: Context) {
        Log.d(TAG, "Starting tracking service")

        val intent = Intent(context, TrackingForegroundService::class.java)

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                // For Android 8.0+, use startForegroundService
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
            Log.d(TAG, "Tracking service start requested")
        } catch (e: Exception) {
            Log.e(TAG, "Error starting tracking service: ${e.message}", e)
        }
    }

    /**
     * Stop the tracking foreground service.
     */
    fun stopTrackingService(context: Context) {
        Log.d(TAG, "Stopping tracking service")

        val intent = Intent(context, TrackingForegroundService::class.java)

        try {
            context.stopService(intent)
            Log.d(TAG, "Tracking service stop requested")
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping tracking service: ${e.message}", e)
        }
    }

    /**
     * Check if the tracking service is currently running.
     */
    fun isTrackingServiceRunning(): Boolean {
        return TrackingForegroundService.isRunning
    }

    /**
     * Restart the tracking service.
     * Stops and then starts the service.
     */
    fun restartTrackingService(context: Context) {
        Log.d(TAG, "Restarting tracking service")
        stopTrackingService(context)

        // Small delay before restarting
        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
            startTrackingService(context)
        }, 500)
    }
}
