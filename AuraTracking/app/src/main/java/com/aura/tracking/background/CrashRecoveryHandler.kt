package com.aura.tracking.background

import android.app.Application
import android.content.Context
import com.aura.tracking.logging.AuraLog
import java.io.PrintWriter
import java.io.StringWriter

/**
 * CrashRecoveryHandler - Global uncaught exception handler.
 * Logs crash and attempts to restart service before app dies.
 */
class CrashRecoveryHandler private constructor(
    private val context: Context,
    private val defaultHandler: Thread.UncaughtExceptionHandler?
) : Thread.UncaughtExceptionHandler {

    companion object {
        private const val TAG = "CrashRecovery"

        fun install(context: Context) {
            val appContext = context.applicationContext
            val defaultHandler = Thread.getDefaultUncaughtExceptionHandler()
            val handler = CrashRecoveryHandler(appContext, defaultHandler)
            Thread.setDefaultUncaughtExceptionHandler(handler)
            AuraLog.Service.i("Crash recovery handler installed")
        }
    }

    override fun uncaughtException(thread: Thread, throwable: Throwable) {
        try {
            // Log the crash
            val stackTrace = StringWriter().apply {
                throwable.printStackTrace(PrintWriter(this))
            }.toString()

            AuraLog.Service.e("UNCAUGHT EXCEPTION in thread ${thread.name}: ${throwable.message}")
            AuraLog.Service.e("Stack trace:\n$stackTrace")

            // Try to flush logs
            try {
                com.aura.tracking.logging.LogWriter.getInstance(context).flush()
            } catch (e: Exception) {
                // Ignore
            }

            // Schedule service restart via AlarmManager if possible
            scheduleServiceRestart()

        } catch (e: Exception) {
            // Last resort - just log to system
            android.util.Log.e(TAG, "Error in crash handler", e)
        } finally {
            // Call default handler (will kill the app)
            defaultHandler?.uncaughtException(thread, throwable)
        }
    }

    private fun scheduleServiceRestart() {
        try {
            val intent = android.content.Intent(context, TrackingForegroundService::class.java)
            val pendingIntent = android.app.PendingIntent.getService(
                context,
                0,
                intent,
                android.app.PendingIntent.FLAG_IMMUTABLE or android.app.PendingIntent.FLAG_ONE_SHOT
            )

            val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as android.app.AlarmManager
            
            // Schedule restart in 2 seconds
            val triggerTime = System.currentTimeMillis() + 2000

            alarmManager.setExactAndAllowWhileIdle(
                android.app.AlarmManager.RTC_WAKEUP,
                triggerTime,
                pendingIntent
            )

            AuraLog.Service.i("Service restart scheduled for 2 seconds after crash")
        } catch (e: Exception) {
            AuraLog.Service.e("Failed to schedule service restart: ${e.message}")
        }
    }
}
