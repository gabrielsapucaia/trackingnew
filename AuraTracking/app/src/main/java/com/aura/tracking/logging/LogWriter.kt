package com.aura.tracking.logging

import android.content.Context
import android.os.Environment
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import java.io.File
import java.io.FileWriter
import java.io.PrintWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean

/**
 * LogWriter - Persistent file logging for industrial telemetry.
 * Thread-safe with buffered async writing.
 */
class LogWriter private constructor(private val context: Context) {

    companion object {
        private const val TAG = "LogWriter"
        private const val LOG_DIR = "logs"
        private const val MAX_LOG_SIZE_BYTES = 10 * 1024 * 1024 // 10MB per file
        private const val MAX_LOG_FILES = 7 // Keep 7 days

        @Volatile
        private var instance: LogWriter? = null

        fun getInstance(context: Context): LogWriter {
            return instance ?: synchronized(this) {
                instance ?: LogWriter(context.applicationContext).also { instance = it }
            }
        }

        const val LEVEL_DEBUG = "D"
        const val LEVEL_INFO = "I"
        const val LEVEL_WARN = "W"
        const val LEVEL_ERROR = "E"
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val logChannel = Channel<LogEntry>(Channel.BUFFERED)
    private val dateFormat = SimpleDateFormat("yyyy-MM-dd", Locale.US)
    private val timeFormat = SimpleDateFormat("HH:mm:ss.SSS", Locale.US)
    private val isRunning = AtomicBoolean(false)

    private var currentLogFile: File? = null
    private var currentWriter: PrintWriter? = null
    private var currentDate: String = ""

    init {
        startLogProcessor()
    }

    private fun startLogProcessor() {
        if (isRunning.compareAndSet(false, true)) {
            scope.launch {
                for (entry in logChannel) {
                    writeEntry(entry)
                }
            }
        }
    }

    fun getLogDirectory(): File {
        val externalDir = context.getExternalFilesDir(null)
        return File(externalDir, LOG_DIR).apply {
            if (!exists()) mkdirs()
        }
    }

    fun log(level: String, component: String, message: String, throwable: Throwable? = null) {
        val entry = LogEntry(
            timestamp = System.currentTimeMillis(),
            level = level,
            component = component,
            message = message,
            throwable = throwable
        )
        
        val fullMessage = "[$component] $message"
        when (level) {
            LEVEL_DEBUG -> Log.d(TAG, fullMessage, throwable)
            LEVEL_INFO -> Log.i(TAG, fullMessage, throwable)
            LEVEL_WARN -> Log.w(TAG, fullMessage, throwable)
            LEVEL_ERROR -> Log.e(TAG, fullMessage, throwable)
        }

        scope.launch {
            try {
                logChannel.send(entry)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to queue log entry", e)
            }
        }
    }

    fun d(component: String, message: String) = log(LEVEL_DEBUG, component, message)
    fun i(component: String, message: String) = log(LEVEL_INFO, component, message)
    fun w(component: String, message: String) = log(LEVEL_WARN, component, message)
    fun e(component: String, message: String, throwable: Throwable? = null) = 
        log(LEVEL_ERROR, component, message, throwable)

    private fun writeEntry(entry: LogEntry) {
        try {
            ensureWriter(entry.timestamp)
            
            val time = timeFormat.format(Date(entry.timestamp))
            val line = "$time ${entry.level}/${entry.component}: ${entry.message}"
            
            currentWriter?.println(line)
            
            entry.throwable?.let { throwable ->
                currentWriter?.println("    Exception: ${throwable.javaClass.simpleName}: ${throwable.message}")
                throwable.stackTrace.take(10).forEach { element ->
                    currentWriter?.println("        at $element")
                }
            }
            
            currentWriter?.flush()
            
            currentLogFile?.let { file ->
                if (file.length() > MAX_LOG_SIZE_BYTES) {
                    rotateLogFile()
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to write log entry", e)
        }
    }

    private fun ensureWriter(timestamp: Long) {
        val date = dateFormat.format(Date(timestamp))
        
        if (date != currentDate || currentWriter == null) {
            closeCurrentWriter()
            currentDate = date
            currentLogFile = File(getLogDirectory(), "aura_$date.log")
            currentWriter = PrintWriter(FileWriter(currentLogFile, true), true)
            cleanOldLogs()
        }
    }

    private fun rotateLogFile() {
        closeCurrentWriter()
        currentLogFile?.let { file ->
            val rotatedName = "${file.nameWithoutExtension}_${System.currentTimeMillis()}.log"
            file.renameTo(File(file.parentFile, rotatedName))
        }
        currentDate = ""
    }

    private fun cleanOldLogs() {
        try {
            val logDir = getLogDirectory()
            val logFiles = logDir.listFiles { file -> 
                file.isFile && file.name.endsWith(".log") 
            }?.sortedByDescending { it.lastModified() } ?: return

            logFiles.drop(MAX_LOG_FILES).forEach { file ->
                file.delete()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to clean old logs", e)
        }
    }

    private fun closeCurrentWriter() {
        try {
            currentWriter?.close()
        } catch (e: Exception) {
            Log.e(TAG, "Error closing writer", e)
        }
        currentWriter = null
    }

    fun getLogFiles(): List<File> {
        return getLogDirectory().listFiles { file -> 
            file.isFile && file.name.endsWith(".log") 
        }?.sortedByDescending { it.lastModified() } ?: emptyList()
    }

    fun readLogFile(file: File): String {
        return try {
            file.readText()
        } catch (e: Exception) {
            "Error reading log: ${e.message}"
        }
    }

    fun exportLogs(): File? {
        return try {
            val exportDir = File(
                Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS),
                "AuraTracking/logs"
            ).apply { mkdirs() }

            val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            val exportFile = File(exportDir, "aura_export_$timestamp.txt")

            PrintWriter(FileWriter(exportFile)).use { writer ->
                writer.println("=== AuraTracking Log Export ===")
                writer.println("Exported: ${Date()}")
                writer.println("Device: ${android.os.Build.MODEL}")
                writer.println("Android: ${android.os.Build.VERSION.RELEASE}")
                writer.println("=".repeat(40))
                writer.println()

                getLogFiles().forEach { logFile ->
                    writer.println("--- ${logFile.name} ---")
                    writer.println(logFile.readText())
                    writer.println()
                }
            }

            exportFile
        } catch (e: Exception) {
            Log.e(TAG, "Failed to export logs", e)
            null
        }
    }

    fun flush() {
        currentWriter?.flush()
    }

    fun shutdown() {
        isRunning.set(false)
        logChannel.close()
        closeCurrentWriter()
    }

    data class LogEntry(
        val timestamp: Long,
        val level: String,
        val component: String,
        val message: String,
        val throwable: Throwable? = null
    )
}

object AuraLog {
    private fun writer() = LogWriter.getInstance(
        com.aura.tracking.AuraTrackingApp.getInstance()
    )

    fun d(component: String, message: String) = writer().d(component, message)
    fun i(component: String, message: String) = writer().i(component, message)
    fun w(component: String, message: String) = writer().w(component, message)
    fun e(component: String, message: String, t: Throwable? = null) = writer().e(component, message, t)

    object GPS {
        private const val TAG = "GPS"
        fun d(msg: String) = d(TAG, msg)
        fun i(msg: String) = i(TAG, msg)
        fun w(msg: String) = w(TAG, msg)
        fun e(msg: String, t: Throwable? = null) = e(TAG, msg, t)
    }

    object IMU {
        private const val TAG = "IMU"
        fun d(msg: String) = d(TAG, msg)
        fun i(msg: String) = i(TAG, msg)
        fun w(msg: String) = w(TAG, msg)
        fun e(msg: String, t: Throwable? = null) = e(TAG, msg, t)
    }

    object MQTT {
        private const val TAG = "MQTT"
        fun d(msg: String) = d(TAG, msg)
        fun i(msg: String) = i(TAG, msg)
        fun w(msg: String) = w(TAG, msg)
        fun e(msg: String, t: Throwable? = null) = e(TAG, msg, t)
    }

    object Service {
        private const val TAG = "Service"
        fun d(msg: String) = d(TAG, msg)
        fun i(msg: String) = i(TAG, msg)
        fun w(msg: String) = w(TAG, msg)
        fun e(msg: String, t: Throwable? = null) = e(TAG, msg, t)
    }

    object Queue {
        private const val TAG = "Queue"
        fun d(msg: String) = d(TAG, msg)
        fun i(msg: String) = i(TAG, msg)
        fun w(msg: String) = w(TAG, msg)
        fun e(msg: String, t: Throwable? = null) = e(TAG, msg, t)
    }

    object Watchdog {
        private const val TAG = "Watchdog"
        fun d(msg: String) = d(TAG, msg)
        fun i(msg: String) = i(TAG, msg)
        fun w(msg: String) = w(TAG, msg)
        fun e(msg: String, t: Throwable? = null) = e(TAG, msg, t)
    }

    object Analytics {
        private const val TAG = "Analytics"
        fun d(msg: String) = d(TAG, msg)
        fun i(msg: String) = i(TAG, msg)
        fun w(msg: String) = w(TAG, msg)
        fun e(msg: String, t: Throwable? = null) = e(TAG, msg, t)
    }
}
