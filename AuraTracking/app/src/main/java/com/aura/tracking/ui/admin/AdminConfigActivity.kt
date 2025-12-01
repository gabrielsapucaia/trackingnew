package com.aura.tracking.ui.admin

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.aura.tracking.AuraTrackingApp
import com.aura.tracking.R
import com.aura.tracking.data.model.Equipment
import com.aura.tracking.data.model.EquipmentType
import com.aura.tracking.data.room.ConfigEntity
import android.util.Log
import com.aura.tracking.databinding.ActivityAdminConfigBinding
import com.aura.tracking.ui.dashboard.DashboardActivity
import kotlinx.coroutines.launch

/**
 * AdminConfigActivity - Configuration screen for MQTT and Fleet/Equipment.
 * First-time setup or accessed from Dashboard settings.
 */
class AdminConfigActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_FIRST_TIME = "extra_first_time"
    }

    private lateinit var binding: ActivityAdminConfigBinding
    private var isFirstTime = false

    private var equipmentTypes: List<EquipmentType> = emptyList()
    private var equipments: List<Equipment> = emptyList()
    private var selectedEquipmentType: EquipmentType? = null
    private var selectedEquipment: Equipment? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityAdminConfigBinding.inflate(layoutInflater)
        setContentView(binding.root)

        isFirstTime = intent.getBooleanExtra(EXTRA_FIRST_TIME, false)

        setupToolbar()
        setupClickListeners()
        loadExistingConfig()
        loadEquipmentTypes()
    }

    private fun setupToolbar() {
        binding.toolbar.setNavigationOnClickListener {
            if (isFirstTime) {
                // Can't go back on first time, must complete setup
                Toast.makeText(this, "Complete a configuração primeiro", Toast.LENGTH_SHORT).show()
            } else {
                finish()
            }
        }
    }

    private fun setupClickListeners() {
        binding.btnSave.setOnClickListener {
            saveConfig()
        }

        binding.btnCancel.setOnClickListener {
            if (isFirstTime) {
                Toast.makeText(this, "Complete a configuração primeiro", Toast.LENGTH_SHORT).show()
            } else {
                finish()
            }
        }

        // Equipment Type selection listener
        binding.actvFleet.setOnItemClickListener { _, _, position, _ ->
            selectedEquipmentType = equipmentTypes.getOrNull(position)
            selectedEquipmentType?.let { type ->
                loadEquipmentsByType(type.id)
            }
        }

        // Equipment selection listener
        binding.actvEquipment.setOnItemClickListener { _, _, position, _ ->
            selectedEquipment = equipments.getOrNull(position)
        }
    }

    /**
     * Load existing configuration from Room if available.
     */
    private fun loadExistingConfig() {
        lifecycleScope.launch {
            try {
                val config = AuraTrackingApp.database.configDao().getConfig()
                config?.let {
                    binding.etMqttHost.setText(it.mqttHost)
                    binding.etMqttPort.setText(it.mqttPort.toString())

                    // Equipment type and equipment will be set after loading lists
                }
            } catch (e: Exception) {
                // Use defaults
            }
        }
    }

    /**
     * Load equipment types from Supabase.
     */
    private fun loadEquipmentTypes() {
        setLoading(true)

        lifecycleScope.launch {
            try {
                val result = AuraTrackingApp.supabaseApi.getEquipmentTypes()

                result.fold(
                    onSuccess = { typeList ->
                        equipmentTypes = typeList
                        updateEquipmentTypeSpinner()
                        setLoading(false)
                    },
                    onFailure = { error ->
                        setLoading(false)
                        Toast.makeText(
                            this@AdminConfigActivity,
                            "Erro ao carregar tipos de equipamento: ${error.message}",
                            Toast.LENGTH_LONG
                        ).show()
                    }
                )
            } catch (e: Exception) {
                setLoading(false)
                Toast.makeText(
                    this@AdminConfigActivity,
                    "Erro ao carregar tipos de equipamento",
                    Toast.LENGTH_LONG
                ).show()
            }
        }
    }

    /**
     * Load equipments for a specific equipment type from Supabase.
     */
    private fun loadEquipmentsByType(typeId: Long) {
        setLoading(true)

        lifecycleScope.launch {
            try {
                val result = AuraTrackingApp.supabaseApi.getEquipmentByType(typeId)

                result.fold(
                    onSuccess = { equipmentList ->
                        equipments = equipmentList
                        updateEquipmentSpinner()
                        setLoading(false)
                    },
                    onFailure = { error ->
                        setLoading(false)
                        Toast.makeText(
                            this@AdminConfigActivity,
                            "Erro ao carregar equipamentos: ${error.message}",
                            Toast.LENGTH_LONG
                        ).show()
                    }
                )
            } catch (e: Exception) {
                setLoading(false)
                Toast.makeText(
                    this@AdminConfigActivity,
                    "Erro ao carregar equipamentos",
                    Toast.LENGTH_LONG
                ).show()
            }
        }
    }

    private fun updateEquipmentTypeSpinner() {
        val typeNames = equipmentTypes.map { "${it.name} (${it.description ?: ""})" }
        val adapter = ArrayAdapter(
            this,
            android.R.layout.simple_dropdown_item_1line,
            typeNames
        )
        binding.actvFleet.setAdapter(adapter)
    }

    private fun updateEquipmentSpinner() {
        val equipmentNames = equipments.map { it.tag }
        val adapter = ArrayAdapter(
            this,
            android.R.layout.simple_dropdown_item_1line,
            equipmentNames
        )
        binding.actvEquipment.setAdapter(adapter)
    }

    /**
     * Validate and save configuration to Room.
     */
    private fun saveConfig() {
        val mqttHost = binding.etMqttHost.text?.toString()?.trim() ?: ""
        val mqttPortStr = binding.etMqttPort.text?.toString()?.trim() ?: ""

        // Validation
        if (mqttHost.isEmpty()) {
            binding.tilMqttHost.error = "Informe o host MQTT"
            return
        }
        binding.tilMqttHost.error = null

        if (mqttPortStr.isEmpty()) {
            binding.tilMqttPort.error = "Informe a porta MQTT"
            return
        }
        binding.tilMqttPort.error = null

        val mqttPort = mqttPortStr.toIntOrNull() ?: 1883

        if (selectedEquipmentType == null) {
            Toast.makeText(this, "Selecione um tipo de equipamento", Toast.LENGTH_SHORT).show()
            return
        }

        if (selectedEquipment == null) {
            Toast.makeText(this, "Selecione um equipamento", Toast.LENGTH_SHORT).show()
            return
        }

        // Create config entity
        val config = ConfigEntity(
            id = 1,
            mqttHost = mqttHost,
            mqttPort = mqttPort,
            mqttTopic = "aura/tracking",
            fleetId = selectedEquipmentType!!.id.toString(),
            fleetName = selectedEquipmentType!!.name,
            equipmentId = selectedEquipment!!.id.toString(),
            equipmentName = selectedEquipment!!.tag,
            updatedAt = System.currentTimeMillis()
        )

        // Save to Room
        lifecycleScope.launch {
            try {
                // Usa updateConfig se já existe, senão insertConfig
                // Isso garante que o Room detecte a mudança
                val existingConfig = AuraTrackingApp.database.configDao().getConfig()
                if (existingConfig != null) {
                    AuraTrackingApp.database.configDao().updateConfig(config)
                } else {
                    AuraTrackingApp.database.configDao().insertConfig(config)
                }
                Toast.makeText(
                    this@AdminConfigActivity,
                    getString(R.string.admin_saved_success),
                    Toast.LENGTH_SHORT
                ).show()

                if (isFirstTime) {
                    navigateToDashboard()
                } else {
                    finish()
                }
            } catch (e: Exception) {
                Toast.makeText(
                    this@AdminConfigActivity,
                    "Erro ao salvar: ${e.message}",
                    Toast.LENGTH_LONG
                ).show()
            }
        }
    }

    private fun setLoading(loading: Boolean) {
        binding.progressBar.visibility = if (loading) View.VISIBLE else View.GONE
    }

    /**
     * Navigate to DashboardActivity after first-time setup.
     */
    private fun navigateToDashboard() {
        val intent = Intent(this, DashboardActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }
        startActivity(intent)
        finish()
    }
}
