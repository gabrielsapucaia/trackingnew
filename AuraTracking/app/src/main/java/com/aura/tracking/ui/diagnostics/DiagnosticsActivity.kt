package com.aura.tracking.ui.diagnostics

import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.work.WorkInfo
import androidx.work.WorkManager
import com.aura.tracking.AuraTrackingApp
import com.aura.tracking.R
import com.aura.tracking.background.TrackingForegroundService
import com.aura.tracking.data.room.AppDatabase
import com.aura.tracking.databinding.ActivityDiagnosticsBinding
import com.aura.tracking.diagnostics.LatencyDiagnostics
import com.aura.tracking.diagnostics.LatencyStatus
import com.aura.tracking.logging.AuraLog
import com.aura.tracking.logging.LogWriter
import com.aura.tracking.util.BatteryOptimizationHelper
import com.aura.tracking.util.ServiceStarter
import kotlinx.coroutines.launch
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * DiagnosticsActivity - Developer mode screen for real-time system monitoring.
 * Shows comprehensive telemetry system status.
 */
class DiagnosticsActivity : AppCompatActivity() {

    private lateinit var binding: ActivityDiagnosticsBinding
    private val handler = Handler(Looper.getMainLooper())
    private val updateInterval = 1000L // 1 second
    private val timeFormat = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
    private val dateTimeFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault())

    private var lastPublishTime: Long = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityDiagnosticsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupToolbar()
        setupButtons()
        loadStaticInfo()
        observeTelemetry()
        startPeriodicUpdates()
    }

    override fun onDestroy() {
        super.onDestroy()
        handler.removeCallbacksAndMessages(null)
    }

    private fun setupToolbar() {
        binding.toolbar.setNavigationOnClickListener {
            finish()
        }
    }

    private fun setupButtons() {
        binding.btnExportLogs.setOnClickListener {
            exportLogs()
        }

        binding.btnRestartService.setOnClickListener {
            restartService()
        }

        binding.btnCheckBattery.setOnClickListener {
            checkBatteryOptimization()
        }

        binding.btnRefresh.setOnClickListener {
            refreshAll()
        }
        
        // Latency Diagnostics buttons
        binding.btnRunDiagnosis.setOnClickListener {
            runLatencyDiagnosis()
        }
        
        binding.btnExportDiagnostics.setOnClickListener {
            exportDiagnosticsData()
        }
    }

    private fun loadStaticInfo() {
        lifecycleScope.launch {
            try {
                val database = AppDatabase.getInstance(this@DiagnosticsActivity)
                val config = database.configDao().getConfig()
                val operator = database.operatorDao().getCurrentOperator()

                binding.tvDeviceId.text = config?.deviceId ?: android.os.Build.MODEL
                binding.tvOperatorId.text = operator?.id?.toString() ?: "N/A"
                binding.tvEquipmentId.text = config?.equipmentId ?: "N/A"
                binding.tvMqttHost.text = "${config?.mqttHost ?: "localhost"}:${config?.mqttPort ?: 1883}"
                binding.tvFleet.text = config?.fleetName ?: "N/A"
                
                // Device info
                binding.tvDeviceModel.text = android.os.Build.MODEL
                binding.tvAndroidVersion.text = "Android ${android.os.Build.VERSION.RELEASE} (API ${android.os.Build.VERSION.SDK_INT})"
                
            } catch (e: Exception) {
                AuraLog.Service.e("Failed to load static info", e)
            }
        }
    }

    private fun observeTelemetry() {
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                // GPS Status
                launch {
                    TrackingForegroundService.lastGpsData.collect { gpsData ->
                        if (gpsData != null) {
                            binding.tvGpsStatus.text = "Active"
                            binding.tvGpsLat.text = String.format(Locale.US, "%.6f", gpsData.latitude)
                            binding.tvGpsLon.text = String.format(Locale.US, "%.6f", gpsData.longitude)
                            binding.tvGpsAccuracy.text = String.format(Locale.US, "%.1fm", gpsData.accuracy)
                            binding.tvGpsSpeed.text = String.format(Locale.US, "%.1f km/h", gpsData.speedKmh)
                            binding.tvGpsLastFix.text = timeFormat.format(Date(gpsData.timestamp))
                            
                            // Accuracy indicator
                            val accuracyColor = when {
                                gpsData.accuracy < 10 -> R.color.status_tracking
                                gpsData.accuracy < 25 -> R.color.status_warning
                                else -> R.color.status_stopped
                            }
                            binding.viewGpsAccuracyIndicator.setBackgroundColor(getColor(accuracyColor))
                        } else {
                            binding.tvGpsStatus.text = "No fix"
                        }
                    }
                }

                // IMU Status
                launch {
                    TrackingForegroundService.lastImuData.collect { imuData ->
                        if (imuData != null) {
                            binding.tvImuStatus.text = "Active"
                            binding.tvImuAccel.text = String.format(
                                Locale.US, "X:%.2f Y:%.2f Z:%.2f",
                                imuData.accelX, imuData.accelY, imuData.accelZ
                            )
                            binding.tvImuGyro.text = String.format(
                                Locale.US, "X:%.3f Y:%.3f Z:%.3f",
                                imuData.gyroX, imuData.gyroY, imuData.gyroZ
                            )
                            binding.tvImuLastSample.text = timeFormat.format(Date(imuData.timestamp))
                        } else {
                            binding.tvImuStatus.text = "Inactive"
                        }
                    }
                }

                // MQTT Status
                launch {
                    TrackingForegroundService.mqttConnected.collect { connected ->
                        binding.tvMqttStatus.text = if (connected) "Connected" else "Disconnected"
                        val color = if (connected) R.color.status_tracking else R.color.status_stopped
                        binding.viewMqttIndicator.setBackgroundColor(getColor(color))
                    }
                }

                // Queue Size
                launch {
                    TrackingForegroundService.queueSize.collect { size ->
                        binding.tvQueueSize.text = "$size messages"
                        val color = when {
                            size == 0 -> R.color.status_tracking
                            size < 100 -> R.color.status_warning
                            else -> R.color.status_stopped
                        }
                        binding.viewQueueIndicator.setBackgroundColor(getColor(color))
                    }
                }

                // Packets Sent
                launch {
                    TrackingForegroundService.packetsSent.collect { count ->
                        binding.tvPacketsSent.text = "$count"
                        if (count > 0) {
                            lastPublishTime = System.currentTimeMillis()
                        }
                    }
                }
            }
        }
    }

    private fun startPeriodicUpdates() {
        val updateRunnable = object : Runnable {
            override fun run() {
                updateDynamicInfo()
                updateLatencyDiagnostics()
                handler.postDelayed(this, updateInterval)
            }
        }
        handler.post(updateRunnable)
    }

    private fun updateDynamicInfo() {
        // Service Status
        val serviceRunning = TrackingForegroundService.isRunning
        binding.tvServiceStatus.text = if (serviceRunning) "Running" else "Stopped"
        val serviceColor = if (serviceRunning) R.color.status_tracking else R.color.status_stopped
        binding.viewServiceIndicator.setBackgroundColor(getColor(serviceColor))

        // WakeLock Status (inferred from service)
        binding.tvWakeLockStatus.text = if (serviceRunning) "Held" else "Released"

        // Time since last publish
        if (lastPublishTime > 0) {
            val elapsed = (System.currentTimeMillis() - lastPublishTime) / 1000
            binding.tvLastPublish.text = "${elapsed}s ago"
        } else {
            binding.tvLastPublish.text = "Never"
        }

        // Battery optimization status
        val ignoringOptimizations = BatteryOptimizationHelper.isIgnoringBatteryOptimizations(this)
        binding.tvBatteryOptStatus.text = if (ignoringOptimizations) "Disabled (good)" else "Enabled (bad)"
        val batteryColor = if (ignoringOptimizations) R.color.status_tracking else R.color.status_stopped
        binding.viewBatteryIndicator.setBackgroundColor(getColor(batteryColor))

        // Power save mode
        val powerSaveMode = BatteryOptimizationHelper.isPowerSaveMode(this)
        binding.tvPowerSaveMode.text = if (powerSaveMode) "Active" else "Inactive"

        // Update WorkManager status
        updateWorkerStatus()

        // Supabase connectivity
        updateSupabaseStatus()

        // Log file info
        updateLogInfo()
    }

    private fun updateWorkerStatus() {
        lifecycleScope.launch {
            try {
                val workManager = WorkManager.getInstance(this@DiagnosticsActivity)
                
                // Check queue flush worker
                val queueWorkInfos = workManager.getWorkInfosForUniqueWork("queue_flush_periodic").get()
                val queueStatus = queueWorkInfos.firstOrNull()?.state?.name ?: "Not scheduled"
                binding.tvFlushWorkerStatus.text = queueStatus

                // Check watchdog worker
                val watchdogWorkInfos = workManager.getWorkInfosForUniqueWork("service_watchdog_periodic").get()
                val watchdogStatus = watchdogWorkInfos.firstOrNull()?.state?.name ?: "Not scheduled"
                binding.tvWatchdogStatus.text = watchdogStatus

                // Check MQTT reconnect worker
                val mqttWorkInfos = workManager.getWorkInfosForUniqueWork("mqtt_reconnect_periodic").get()
                val mqttStatus = mqttWorkInfos.firstOrNull()?.state?.name ?: "Not scheduled"
                binding.tvReconnectWorkerStatus.text = mqttStatus

            } catch (e: Exception) {
                binding.tvFlushWorkerStatus.text = "Error"
                binding.tvWatchdogStatus.text = "Error"
                binding.tvReconnectWorkerStatus.text = "Error"
            }
        }
    }

    private fun updateSupabaseStatus() {
        // Simple connectivity check - could be enhanced
        binding.tvSupabaseStatus.text = "Configured"
    }

    private fun updateLogInfo() {
        lifecycleScope.launch {
            try {
                val logWriter = LogWriter.getInstance(this@DiagnosticsActivity)
                val logFiles = logWriter.getLogFiles()
                val totalSize = logFiles.sumOf { it.length() }
                binding.tvLogFilesCount.text = "${logFiles.size} files (${formatBytes(totalSize)})"
            } catch (e: Exception) {
                binding.tvLogFilesCount.text = "Error"
            }
        }
    }

    private fun formatBytes(bytes: Long): String {
        return when {
            bytes < 1024 -> "$bytes B"
            bytes < 1024 * 1024 -> "${bytes / 1024} KB"
            else -> "${bytes / (1024 * 1024)} MB"
        }
    }

    private fun exportLogs() {
        lifecycleScope.launch {
            try {
                binding.btnExportLogs.isEnabled = false
                binding.btnExportLogs.text = "Exporting..."

                val logWriter = LogWriter.getInstance(this@DiagnosticsActivity)
                val exportFile = logWriter.exportLogs()

                if (exportFile != null) {
                    Toast.makeText(
                        this@DiagnosticsActivity,
                        "Logs exported to:\n${exportFile.absolutePath}",
                        Toast.LENGTH_LONG
                    ).show()

                    // Offer to share
                    try {
                        val uri = FileProvider.getUriForFile(
                            this@DiagnosticsActivity,
                            "${packageName}.fileprovider",
                            exportFile
                        )
                        val shareIntent = Intent(Intent.ACTION_SEND).apply {
                            type = "text/plain"
                            putExtra(Intent.EXTRA_STREAM, uri)
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        }
                        startActivity(Intent.createChooser(shareIntent, "Share logs"))
                    } catch (e: Exception) {
                        AuraLog.Service.e("Failed to share logs", e)
                    }
                } else {
                    Toast.makeText(this@DiagnosticsActivity, "Failed to export logs", Toast.LENGTH_SHORT).show()
                }

            } catch (e: Exception) {
                Toast.makeText(this@DiagnosticsActivity, "Export failed: ${e.message}", Toast.LENGTH_SHORT).show()
                AuraLog.Service.e("Log export failed", e)
            } finally {
                binding.btnExportLogs.isEnabled = true
                binding.btnExportLogs.text = "Export Logs"
            }
        }
    }

    private fun restartService() {
        try {
            binding.btnRestartService.isEnabled = false
            binding.btnRestartService.text = "Restarting..."

            AuraLog.Service.i("User requested service restart from diagnostics")

            // Stop service
            ServiceStarter.stopTrackingService(this)

            // Wait and restart
            handler.postDelayed({
                ServiceStarter.startTrackingService(this)
                
                handler.postDelayed({
                    binding.btnRestartService.isEnabled = true
                    binding.btnRestartService.text = "Restart Service"
                    Toast.makeText(this, "Service restarted", Toast.LENGTH_SHORT).show()
                }, 1000)
            }, 2000)

        } catch (e: Exception) {
            binding.btnRestartService.isEnabled = true
            binding.btnRestartService.text = "Restart Service"
            Toast.makeText(this, "Restart failed: ${e.message}", Toast.LENGTH_SHORT).show()
            AuraLog.Service.e("Service restart failed", e)
        }
    }

    private fun checkBatteryOptimization() {
        val status = BatteryOptimizationHelper.getOptimizationStatus(this)
        
        val message = buildString {
            appendLine("Battery Optimization Status:")
            appendLine()
            appendLine("Ignoring optimizations: ${if (status.isIgnoringOptimizations) "YES ✓" else "NO ✗"}")
            appendLine("Power save mode: ${if (status.isPowerSaveMode) "ACTIVE" else "Inactive"}")
            appendLine("Device idle (Doze): ${if (status.isDeviceIdle) "YES" else "No"}")
            appendLine("Interactive: ${if (status.isInteractive) "Yes" else "No"}")
            appendLine()
            if (!status.isIgnoringOptimizations) {
                appendLine("⚠️ App should be exempted from battery optimization for reliable 24/7 operation.")
            }
        }

        androidx.appcompat.app.AlertDialog.Builder(this)
            .setTitle("Battery Status")
            .setMessage(message)
            .setPositiveButton("OK", null)
            .apply {
                if (!status.isIgnoringOptimizations) {
                    setNeutralButton("Fix") { _, _ ->
                        BatteryOptimizationHelper.requestIgnoreBatteryOptimizations(this@DiagnosticsActivity)
                    }
                }
            }
            .show()
    }

    private fun refreshAll() {
        loadStaticInfo()
        updateDynamicInfo()
        updateLatencyDiagnostics()
        Toast.makeText(this, "Refreshed", Toast.LENGTH_SHORT).show()
    }
    
    // ==================== Latency Diagnostics ====================
    
    private fun updateLatencyDiagnostics() {
        val stats = LatencyDiagnostics.stats.value
        
        // GPS Age stats
        binding.tvGpsAgeAvg.text = "avg: ${stats.avgGpsAge}ms"
        binding.tvGpsAgeP95.text = "P95: ${stats.p95GpsAge}ms"
        
        // Chipset and FusedLP latency
        binding.tvChipsetLatency.text = "~${stats.avgChipsetLatency}ms"
        binding.tvFusedLatency.text = "~${stats.avgHardwareLatency}ms"
        
        // Sample count
        binding.tvSampleCount.text = "(${stats.sampleCount} samples)"
        
        // Last diagnosis result
        val diagnosis = LatencyDiagnostics.lastDiagnosis.value
        if (diagnosis != null) {
            binding.tvLatencyStatus.text = diagnosis.status.name
            binding.tvCorrelationLag.text = "~${diagnosis.correlation.lagMs}ms (corr: ${"%.2f".format(diagnosis.correlation.correlation)})"
            binding.tvLatencyDiagnosis.text = diagnosis.conclusion
            
            // Status indicator color
            val statusColor = when (diagnosis.status) {
                LatencyStatus.EXCELLENT -> R.color.status_tracking
                LatencyStatus.NORMAL -> R.color.status_tracking
                LatencyStatus.ACCEPTABLE -> R.color.status_warning
                LatencyStatus.PROBLEMATIC -> R.color.status_stopped
            }
            binding.viewLatencyIndicator.setBackgroundColor(getColor(statusColor))
        } else {
            binding.tvLatencyStatus.text = "Collecting..."
            binding.tvCorrelationLag.text = "Waiting for data..."
            binding.tvLatencyDiagnosis.text = "Collecting samples. Run analysis after driving for 1-2 minutes."
        }
    }
    
    private fun runLatencyDiagnosis() {
        binding.btnRunDiagnosis.isEnabled = false
        binding.btnRunDiagnosis.text = "Analyzing..."
        
        lifecycleScope.launch {
            try {
                val diagnosis = LatencyDiagnostics.runFullDiagnosis()
                
                // Update UI
                updateLatencyDiagnostics()
                
                // Show detailed dialog
                val message = buildString {
                    appendLine("Status: ${diagnosis.status.name}")
                    appendLine()
                    appendLine("📊 Latency Stats:")
                    appendLine("  • GPS Age (avg): ${diagnosis.stats.avgGpsAge}ms")
                    appendLine("  • GPS Age (P95): ${diagnosis.stats.p95GpsAge}ms")
                    appendLine("  • Chipset: ${diagnosis.stats.avgChipsetLatency}ms")
                    appendLine("  • FusedLP: ${diagnosis.stats.avgHardwareLatency}ms")
                    appendLine()
                    appendLine("📈 IMU↔GPS Correlation:")
                    appendLine("  • Lag: ${diagnosis.correlation.lagMs}ms")
                    appendLine("  • Correlation: ${"%.3f".format(diagnosis.correlation.correlation)}")
                    appendLine("  • Samples: ${diagnosis.correlation.sampleCount}")
                    appendLine()
                    if (diagnosis.patterns.isNotEmpty()) {
                        appendLine("🔍 Patterns Detected:")
                        diagnosis.patterns.forEach { appendLine("  • $it") }
                        appendLine()
                    }
                    if (diagnosis.causes.isNotEmpty()) {
                        appendLine("⚠️ Possible Causes:")
                        diagnosis.causes.forEach { appendLine("  • $it") }
                        appendLine()
                    }
                    if (diagnosis.recommendations.isNotEmpty()) {
                        appendLine("💡 Recommendations:")
                        diagnosis.recommendations.forEach { appendLine("  • $it") }
                        appendLine()
                    }
                    appendLine("📝 Conclusion:")
                    appendLine(diagnosis.conclusion)
                }
                
                androidx.appcompat.app.AlertDialog.Builder(this@DiagnosticsActivity)
                    .setTitle("🛰️ GNSS Latency Analysis")
                    .setMessage(message)
                    .setPositiveButton("OK", null)
                    .setNeutralButton("Export") { _, _ ->
                        exportDiagnosticsData()
                    }
                    .show()
                    
            } catch (e: Exception) {
                Toast.makeText(this@DiagnosticsActivity, "Analysis failed: ${e.message}", Toast.LENGTH_SHORT).show()
                AuraLog.GPS.e("Latency diagnosis failed", e)
            } finally {
                binding.btnRunDiagnosis.isEnabled = true
                binding.btnRunDiagnosis.text = "Run Analysis"
            }
        }
    }
    
    private fun exportDiagnosticsData() {
        lifecycleScope.launch {
            try {
                binding.btnExportDiagnostics.isEnabled = false
                binding.btnExportDiagnostics.text = "Exporting..."
                
                val jsonData = LatencyDiagnostics.exportData()
                
                // Save to file
                val exportDir = File(getExternalFilesDir(null), "diagnostics")
                exportDir.mkdirs()
                
                val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
                val exportFile = File(exportDir, "latency_diagnostics_$timestamp.json")
                exportFile.writeText(jsonData)
                
                Toast.makeText(
                    this@DiagnosticsActivity,
                    "Exported to:\n${exportFile.absolutePath}",
                    Toast.LENGTH_LONG
                ).show()
                
                // Offer to share
                try {
                    val uri = FileProvider.getUriForFile(
                        this@DiagnosticsActivity,
                        "${packageName}.fileprovider",
                        exportFile
                    )
                    val shareIntent = Intent(Intent.ACTION_SEND).apply {
                        type = "application/json"
                        putExtra(Intent.EXTRA_STREAM, uri)
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }
                    startActivity(Intent.createChooser(shareIntent, "Share diagnostics"))
                } catch (e: Exception) {
                    AuraLog.GPS.e("Failed to share diagnostics", e)
                }
                
            } catch (e: Exception) {
                Toast.makeText(this@DiagnosticsActivity, "Export failed: ${e.message}", Toast.LENGTH_SHORT).show()
                AuraLog.GPS.e("Diagnostics export failed", e)
            } finally {
                binding.btnExportDiagnostics.isEnabled = true
                binding.btnExportDiagnostics.text = "Export Data"
            }
        }
    }
}
