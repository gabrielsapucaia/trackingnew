package com.aura.tracking.ui.dashboard

import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.aura.tracking.AuraTrackingApp
import com.aura.tracking.R
import com.aura.tracking.background.TrackingForegroundService
import com.aura.tracking.data.room.OperatorEntity
import com.aura.tracking.databinding.ActivityDashboardBinding
import com.aura.tracking.ui.admin.AdminConfigActivity
import com.aura.tracking.ui.diagnostics.DiagnosticsActivity
import com.aura.tracking.ui.login.LoginActivity
import com.aura.tracking.util.BatteryOptimizationHelper
import com.aura.tracking.util.PermissionHelper
import com.aura.tracking.util.ServiceStarter
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * DashboardActivity - Main screen after login.
 * Shows operator info, tracking status, telemetry data, and control buttons.
 */
class DashboardActivity : AppCompatActivity() {

    private lateinit var binding: ActivityDashboardBinding
    private var currentOperator: OperatorEntity? = null
    private val timeFormat = SimpleDateFormat("HH:mm:ss", Locale.getDefault())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityDashboardBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupToolbar()
        setupClickListeners()
        observeOperator()
        loadEquipmentInfo()
        observeTelemetry()
        startTrackingAutomatically()
    }

    /**
     * Verifica se a otimização de bateria está desativada.
     * Se não estiver, força o usuário a configurar.
     */
    private fun checkBatteryOptimization() {
        if (!BatteryOptimizationHelper.isIgnoringBatteryOptimizations(this)) {
            BatteryOptimizationHelper.checkAndRequestOptimization(this)
        }
    }

    private fun setupToolbar() {
        binding.toolbar.setOnMenuItemClickListener { menuItem ->
            when (menuItem.itemId) {
                R.id.action_logout -> {
                    logout()
                    true
                }
                R.id.action_diagnostics -> {
                    navigateToDiagnostics()
                    true
                }
                else -> false
            }
        }
    }

    private fun setupClickListeners() {
        binding.btnConfig.setOnClickListener {
            navigateToConfig()
        }
    }

    /**
     * Start tracking automatically when dashboard opens.
     */
    private fun startTrackingAutomatically() {
        ServiceStarter.startTrackingService(this)
        updateTrackingUI(true)
    }

    /**
     * Observe the current operator from Room database.
     */
    private fun observeOperator() {
        lifecycleScope.launch {
            AuraTrackingApp.database.operatorDao()
                .observeCurrentOperator()
                .collectLatest { operator ->
                    currentOperator = operator
                    updateOperatorUI(operator)
                }
        }
    }

    /**
     * Load equipment info from ConfigEntity.
     */
    private fun loadEquipmentInfo() {
        lifecycleScope.launch {
            val config = AuraTrackingApp.database.configDao().getConfig()
            config?.let {
                binding.tvEquipmentType.text = if (it.fleetName.isNullOrEmpty()) "-" else it.fleetName
                binding.tvEquipmentName.text = if (it.equipmentName.isNullOrEmpty()) "-" else it.equipmentName
            } ?: run {
                binding.tvEquipmentType.text = "-"
                binding.tvEquipmentName.text = "-"
            }
        }
    }

    /**
     * Observa dados de telemetria em tempo real do serviço.
     */
    private fun observeTelemetry() {
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                // GPS Data
                launch {
                    TrackingForegroundService.lastGpsData.collect { gpsData ->
                        gpsData?.let {
                            binding.tvGpsLat.text = String.format(Locale.US, "%.6f", it.latitude)
                            binding.tvGpsLon.text = String.format(Locale.US, "%.6f", it.longitude)
                            binding.tvGpsSpeed.text = String.format(Locale.US, "%.1f km/h", it.speedKmh)
                            binding.tvGpsAccuracy.text = String.format(Locale.US, "±%.1fm", it.accuracy)
                            binding.tvGpsTime.text = timeFormat.format(Date(it.timestamp))
                            
                            // Indicador de qualidade GPS
                            val gpsColor = when {
                                it.accuracy < 10 -> R.color.status_tracking // Excelente
                                it.accuracy < 30 -> R.color.status_warning  // Bom
                                else -> R.color.status_stopped              // Ruim
                            }
                            binding.viewGpsIndicator.setBackgroundColor(ContextCompat.getColor(this@DashboardActivity, gpsColor))
                        }
                    }
                }

                // IMU Data
                launch {
                    TrackingForegroundService.lastImuData.collect { imuData ->
                        imuData?.let {
                            binding.tvImuAccel.text = String.format(
                                Locale.US, "X:%.2f Y:%.2f Z:%.2f",
                                it.accelX, it.accelY, it.accelZ
                            )
                            binding.tvImuGyro.text = String.format(
                                Locale.US, "X:%.2f Y:%.2f Z:%.2f",
                                it.gyroX, it.gyroY, it.gyroZ
                            )
                            binding.viewImuIndicator.setBackgroundColor(
                                ContextCompat.getColor(this@DashboardActivity, R.color.status_tracking)
                            )
                        }
                    }
                }

                // MQTT Status
                launch {
                    TrackingForegroundService.mqttConnected.collect { connected ->
                        binding.tvMqttStatus.text = if (connected) "Connected" else "Disconnected"
                        val color = if (connected) R.color.status_tracking else R.color.status_stopped
                        binding.viewMqttIndicator.setBackgroundColor(
                            ContextCompat.getColor(this@DashboardActivity, color)
                        )
                    }
                }

                // Queue Size
                launch {
                    TrackingForegroundService.queueSize.collect { size ->
                        binding.tvQueueSize.text = "$size pending"
                        val color = when {
                            size == 0 -> R.color.status_tracking
                            size < 100 -> R.color.status_warning
                            else -> R.color.status_stopped
                        }
                        binding.viewQueueIndicator.setBackgroundColor(
                            ContextCompat.getColor(this@DashboardActivity, color)
                        )
                    }
                }

                // Packets Sent
                launch {
                    TrackingForegroundService.packetsSent.collect { count ->
                        binding.tvPacketsSent.text = "$count sent"
                    }
                }
            }
        }
    }

    private fun updateOperatorUI(operator: OperatorEntity?) {
        if (operator != null) {
            binding.tvOperatorName.text = operator.name
            binding.tvOperatorMatricula.text = "Matrícula: ${operator.registration}"
        } else {
            navigateToLogin()
        }
    }

    private fun updateTrackingUI(isTracking: Boolean) {
        if (isTracking) {
            binding.tvStatus.text = getString(R.string.dashboard_status_tracking)
            binding.viewStatusIndicator.setBackgroundColor(
                ContextCompat.getColor(this, R.color.status_tracking)
            )
            binding.cardTelemetry.visibility = View.VISIBLE
        } else {
            binding.tvStatus.text = getString(R.string.dashboard_status_stopped)
            binding.viewStatusIndicator.setBackgroundColor(
                ContextCompat.getColor(this, R.color.status_stopped)
            )
            binding.cardTelemetry.visibility = View.GONE
        }
    }

    private fun navigateToConfig() {
        val intent = Intent(this, AdminConfigActivity::class.java)
        startActivity(intent)
    }
    
    private fun navigateToDiagnostics() {
        val intent = Intent(this, DiagnosticsActivity::class.java)
        startActivity(intent)
    }

    private fun logout() {
        // Para o tracking automaticamente no logout
        ServiceStarter.stopTrackingService(this)

        lifecycleScope.launch {
            AuraTrackingApp.database.operatorDao().clearAllOperators()
            navigateToLogin()
        }
    }

    private fun navigateToLogin() {
        val intent = Intent(this, LoginActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }
        startActivity(intent)
        finish()
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)

        when (requestCode) {
            PermissionHelper.REQUEST_LOCATION_PERMISSIONS -> {
                if (PermissionHelper.hasLocationPermissions(this)) {
                    // Permissões concedidas, tracking já foi iniciado automaticamente
                    updateTrackingUI(true)
                }
            }
            PermissionHelper.REQUEST_NOTIFICATION_PERMISSION -> {
                // Permissões concedidas, tracking já foi iniciado automaticamente
                updateTrackingUI(true)
            }
        }
    }
}
