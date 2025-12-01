package com.aura.tracking.ui.admin

import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.aura.tracking.AuraTrackingApp
import com.aura.tracking.R
import com.aura.tracking.data.model.Equipment
import com.aura.tracking.data.model.EquipmentType
import com.aura.tracking.data.model.Operator
import com.aura.tracking.databinding.ActivitySupabaseConfigBinding
import kotlinx.coroutines.launch

/**
 * SupabaseConfigActivity - Configuration screen for loading Supabase tables.
 * Allows loading operators, equipment types, and equipment from Supabase.
 */
class SupabaseConfigActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "SupabaseConfigActivity"
    }

    private lateinit var binding: ActivitySupabaseConfigBinding

    // Dados carregados
    private var operators: List<Operator> = emptyList()
    private var equipmentTypes: List<EquipmentType> = emptyList()
    private var equipments: List<Equipment> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySupabaseConfigBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupToolbar()
        setupClickListeners()
        updateUI()
    }

    private fun setupToolbar() {
        binding.toolbar.setNavigationOnClickListener {
            finish()
        }
    }

    private fun setupClickListeners() {
        binding.btnLoadOperators.setOnClickListener {
            loadOperators()
        }

        binding.btnLoadEquipmentTypes.setOnClickListener {
            loadEquipmentTypes()
        }

        binding.btnLoadEquipments.setOnClickListener {
            loadEquipments()
        }

        binding.btnLoadAll.setOnClickListener {
            loadAllData()
        }
    }

    private fun setLoading(loading: Boolean) {
        binding.progressBar.visibility = if (loading) View.VISIBLE else View.GONE
        binding.btnLoadOperators.isEnabled = !loading
        binding.btnLoadEquipmentTypes.isEnabled = !loading
        binding.btnLoadEquipments.isEnabled = !loading
        binding.btnLoadAll.isEnabled = !loading
    }

    private fun updateUI() {
        binding.tvOperatorsCount.text = getString(R.string.supabase_operators_count, operators.size)
        binding.tvEquipmentTypesCount.text = getString(R.string.supabase_equipment_types_count, equipmentTypes.size)
        binding.tvEquipmentsCount.text = getString(R.string.supabase_equipments_count, equipments.size)

        binding.tvOperatorsStatus.text = if (operators.isNotEmpty())
            getString(R.string.supabase_status_loaded) else getString(R.string.supabase_status_not_loaded)
        binding.tvEquipmentTypesStatus.text = if (equipmentTypes.isNotEmpty())
            getString(R.string.supabase_status_loaded) else getString(R.string.supabase_status_not_loaded)
        binding.tvEquipmentsStatus.text = if (equipments.isNotEmpty())
            getString(R.string.supabase_status_loaded) else getString(R.string.supabase_status_not_loaded)
    }

    private fun loadOperators() {
        setLoading(true)
        Log.d(TAG, "Loading operators from Supabase...")

        lifecycleScope.launch {
            try {
                val result = AuraTrackingApp.supabaseApi.getOperators()
                result.fold(
                    onSuccess = { operatorList ->
                        operators = operatorList
                        Log.i(TAG, "Loaded ${operatorList.size} operators")
                        updateUI()
                        Toast.makeText(
                            this@SupabaseConfigActivity,
                            getString(R.string.supabase_operators_loaded, operatorList.size),
                            Toast.LENGTH_SHORT
                        ).show()
                    },
                    onFailure = { error ->
                        Log.e(TAG, "Failed to load operators: ${error.message}")
                        Toast.makeText(
                            this@SupabaseConfigActivity,
                            getString(R.string.supabase_error_load_failed, error.message),
                            Toast.LENGTH_LONG
                        ).show()
                    }
                )
            } catch (e: Exception) {
                Log.e(TAG, "Exception loading operators: ${e.message}")
                Toast.makeText(
                    this@SupabaseConfigActivity,
                    getString(R.string.supabase_error_load_failed, e.message),
                    Toast.LENGTH_LONG
                ).show()
            } finally {
                setLoading(false)
            }
        }
    }

    private fun loadEquipmentTypes() {
        setLoading(true)
        Log.d(TAG, "Loading equipment types from Supabase...")

        lifecycleScope.launch {
            try {
                val result = AuraTrackingApp.supabaseApi.getEquipmentTypes()
                result.fold(
                    onSuccess = { typeList ->
                        equipmentTypes = typeList
                        Log.i(TAG, "Loaded ${typeList.size} equipment types")
                        updateUI()
                        Toast.makeText(
                            this@SupabaseConfigActivity,
                            getString(R.string.supabase_equipment_types_loaded, typeList.size),
                            Toast.LENGTH_SHORT
                        ).show()
                    },
                    onFailure = { error ->
                        Log.e(TAG, "Failed to load equipment types: ${error.message}")
                        Toast.makeText(
                            this@SupabaseConfigActivity,
                            getString(R.string.supabase_error_load_failed, error.message),
                            Toast.LENGTH_LONG
                        ).show()
                    }
                )
            } catch (e: Exception) {
                Log.e(TAG, "Exception loading equipment types: ${e.message}")
                Toast.makeText(
                    this@SupabaseConfigActivity,
                    getString(R.string.supabase_error_load_failed, e.message),
                    Toast.LENGTH_LONG
                ).show()
            } finally {
                setLoading(false)
            }
        }
    }

    private fun loadEquipments() {
        setLoading(true)
        Log.d(TAG, "Loading equipments from Supabase...")

        lifecycleScope.launch {
            try {
                val result = AuraTrackingApp.supabaseApi.getEquipments()
                result.fold(
                    onSuccess = { equipmentList ->
                        equipments = equipmentList
                        Log.i(TAG, "Loaded ${equipmentList.size} equipments")
                        updateUI()
                        Toast.makeText(
                            this@SupabaseConfigActivity,
                            getString(R.string.supabase_equipments_loaded, equipmentList.size),
                            Toast.LENGTH_SHORT
                        ).show()
                    },
                    onFailure = { error ->
                        Log.e(TAG, "Failed to load equipments: ${error.message}")
                        Toast.makeText(
                            this@SupabaseConfigActivity,
                            getString(R.string.supabase_error_load_failed, error.message),
                            Toast.LENGTH_LONG
                        ).show()
                    }
                )
            } catch (e: Exception) {
                Log.e(TAG, "Exception loading equipments: ${e.message}")
                Toast.makeText(
                    this@SupabaseConfigActivity,
                    getString(R.string.supabase_error_load_failed, e.message),
                    Toast.LENGTH_LONG
                ).show()
            } finally {
                setLoading(false)
            }
        }
    }

    private fun loadAllData() {
        setLoading(true)
        Log.d(TAG, "Loading all data from Supabase...")

        lifecycleScope.launch {
            try {
                // Carregar operadores
                val operatorsResult = AuraTrackingApp.supabaseApi.getOperators()
                operatorsResult.fold(
                    onSuccess = { operatorList -> operators = operatorList },
                    onFailure = { Log.w(TAG, "Failed to load operators: ${it.message}") }
                )

                // Carregar tipos de equipamento
                val typesResult = AuraTrackingApp.supabaseApi.getEquipmentTypes()
                typesResult.fold(
                    onSuccess = { typeList -> equipmentTypes = typeList },
                    onFailure = { Log.w(TAG, "Failed to load equipment types: ${it.message}") }
                )

                // Carregar equipamentos
                val equipmentsResult = AuraTrackingApp.supabaseApi.getEquipments()
                equipmentsResult.fold(
                    onSuccess = { equipmentList -> equipments = equipmentList },
                    onFailure = { Log.w(TAG, "Failed to load equipments: ${it.message}") }
                )

                updateUI()
                Log.i(TAG, "Loaded all data: ${operators.size} operators, ${equipmentTypes.size} types, ${equipments.size} equipments")
                Toast.makeText(
                    this@SupabaseConfigActivity,
                    getString(R.string.supabase_all_loaded, operators.size, equipmentTypes.size, equipments.size),
                    Toast.LENGTH_SHORT
                ).show()

            } catch (e: Exception) {
                Log.e(TAG, "Exception loading all data: ${e.message}")
                Toast.makeText(
                    this@SupabaseConfigActivity,
                    getString(R.string.supabase_error_load_failed, e.message),
                    Toast.LENGTH_LONG
                ).show()
            } finally {
                setLoading(false)
            }
        }
    }
}

