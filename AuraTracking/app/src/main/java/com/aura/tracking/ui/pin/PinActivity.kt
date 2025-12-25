package com.aura.tracking.ui.pin

import android.content.Intent
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.KeyEvent
import android.view.View
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.aura.tracking.AuraTrackingApp
import com.aura.tracking.R
import com.aura.tracking.data.model.Operator
import com.aura.tracking.data.room.OperatorEntity
import com.aura.tracking.databinding.ActivityPinBinding
import com.aura.tracking.ui.admin.AdminConfigActivity
import com.aura.tracking.ui.dashboard.DashboardActivity
import kotlinx.coroutines.launch

/**
 * PinActivity - Operator enters their 4-digit PIN.
 * Authenticates against Supabase and saves session locally.
 */
class PinActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_REGISTRATION = "extra_registration"
    }

    private lateinit var binding: ActivityPinBinding
    private var registration: String = ""
    private var operatorData: Operator? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityPinBinding.inflate(layoutInflater)
        setContentView(binding.root)

        registration = intent.getStringExtra(EXTRA_REGISTRATION) ?: ""

        if (registration.isEmpty()) {
            finish()
            return
        }

        loadOperatorData()
        setupClickListeners()
    }

    private fun loadOperatorData() {
        setLoading(true)

        lifecycleScope.launch {
            try {
                // Tentar buscar dados do operador local primeiro
                val localOperator = AuraTrackingApp.database.operatorDao().getOperatorByRegistration(registration)

                if (localOperator != null) {
                    // Operador já existe localmente
                    operatorData = Operator(
                        id = localOperator.id,
                        registration = localOperator.registration,
                        name = localOperator.name,
                        pin = "" // Não temos o PIN salvo localmente
                    )
                    updateOperatorUI()
                    setLoading(false)
                } else {
                    // Buscar dados do Supabase
                    val result = AuraTrackingApp.supabaseApi.getOperatorByRegistration(registration)

                    result.fold(
                        onSuccess = { operator ->
                            operatorData = operator
                            updateOperatorUI()
                            setLoading(false)
                            // Abrir teclado automaticamente no primeiro campo
                            showKeyboard()
                        },
                        onFailure = { error ->
                            // Matrícula não encontrada - mostrar erro
                            setLoading(false)
                            showError(getString(R.string.pin_error_registration_not_found))
                            // Abrir teclado automaticamente
                            showKeyboard()
                        }
                    )
                }
            } catch (e: Exception) {
                // Em caso de erro de conexão, permitir tentativa de login
                operatorData = Operator(
                    id = 0,
                    registration = registration,
                    name = "Operador",
                    pin = ""
                )
                updateOperatorUI()
                setLoading(false)
            }
        }
    }

    private fun updateOperatorUI() {
        operatorData?.let { operator ->
            binding.tvOperator.text = "${operator.name} - ${operator.registration}"
        } ?: run {
            binding.tvOperator.text = "Matrícula: $registration"
        }
    }

    private fun setupClickListeners() {
        binding.btnBack.setOnClickListener {
            finish()
        }

        binding.btnLogin.setOnClickListener {
            attemptLogin()
        }

        setupPinFieldListeners()
    }

    private fun setupPinFieldListeners() {
        val pinFields = arrayOf(
            binding.etPin1,
            binding.etPin2,
            binding.etPin3,
            binding.etPin4
        )

        pinFields.forEachIndexed { index, editText ->
            editText.addTextChangedListener(object : TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}

                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}

                override fun afterTextChanged(s: Editable?) {
                    val length = s?.length ?: 0
                    if (length == 1 && index < pinFields.size - 1) {
                        // Move to next field
                        pinFields[index + 1].requestFocus()
                    } else if (length == 0 && index > 0) {
                        // Handle backspace - move to previous field
                        pinFields[index - 1].requestFocus()
                    }

                    // Check if all fields are filled
                    if (isPinComplete()) {
                        attemptLogin()
                    }
                }
            })

            // Handle backspace key
            editText.setOnKeyListener { _, keyCode, event ->
                if (keyCode == KeyEvent.KEYCODE_DEL && event.action == KeyEvent.ACTION_DOWN) {
                    if (editText.text.isNullOrEmpty() && index > 0) {
                        // Move to previous field on backspace when current is empty
                        pinFields[index - 1].requestFocus()
                        val prevField = pinFields[index - 1]
                        prevField.setSelection(prevField.text?.length ?: 0)
                        return@setOnKeyListener true
                    }
                }
                false
            }
        }
    }

    private fun isPinComplete(): Boolean {
        return binding.etPin1.text?.isNotEmpty() == true &&
               binding.etPin2.text?.isNotEmpty() == true &&
               binding.etPin3.text?.isNotEmpty() == true &&
               binding.etPin4.text?.isNotEmpty() == true
    }

    private fun getPinFromFields(): String {
        return "${binding.etPin1.text}${binding.etPin2.text}${binding.etPin3.text}${binding.etPin4.text}"
    }

    /**
     * Attempt to login with the provided PIN.
     */
    private fun attemptLogin() {
        val pin = getPinFromFields()

        // Validate PIN - permitir campo vazio
        if (pin.length != 4 && pin.isNotEmpty()) {
            showError(getString(R.string.pin_error_invalid))
            return
        }

        // Show loading
        setLoading(true)
        hideError()

        // Call Supabase API - usar PIN vazio se nenhum foi digitado
        val pinToUse = if (pin.isEmpty()) operatorData?.pin ?: "" else pin

        lifecycleScope.launch {
            try {
                val result = AuraTrackingApp.supabaseApi.login(registration, pinToUse)

                result.fold(
                    onSuccess = { operator ->
                        // Save operator to Room
                        val operatorEntity = OperatorEntity(
                            id = operator.id,
                            registration = operator.registration,
                            name = operator.name,
                            token = null, // Token can be added later if needed
                            isActive = true
                        )
                        AuraTrackingApp.database.operatorDao().insertOperator(operatorEntity)

                        // Set operator context for Firebase Crashlytics
                        AuraTrackingApp.getInstance().setOperatorContext(operator)

                        // Check if config exists
                        val hasConfig = AuraTrackingApp.database.configDao().hasConfig()

                        if (hasConfig) {
                            navigateToDashboard()
                        } else {
                            navigateToAdminConfig()
                        }
                    },
                    onFailure = { error ->
                        setLoading(false)
                        showError(getString(R.string.pin_error_login_failed))
                        // Limpar todos os campos PIN em caso de erro
                        clearAllPinFields()
                        // Abrir teclado automaticamente no primeiro campo
                        showKeyboard()
                    }
                )
            } catch (e: Exception) {
                setLoading(false)
                showError(getString(R.string.pin_error_login_failed))
            }
        }
    }

    private fun setLoading(loading: Boolean) {
        binding.progressBar.visibility = if (loading) View.VISIBLE else View.GONE
        binding.btnLogin.isEnabled = !loading

        // Enable/disable all PIN fields
        binding.etPin1.isEnabled = !loading
        binding.etPin2.isEnabled = !loading
        binding.etPin3.isEnabled = !loading
        binding.etPin4.isEnabled = !loading
    }

    private fun showError(message: String) {
        binding.tvError.text = message
        binding.tvError.visibility = View.VISIBLE
    }

    private fun hideError() {
        binding.tvError.visibility = View.GONE
    }

    /**
     * Navigate to DashboardActivity.
     */
    private fun navigateToDashboard() {
        val intent = Intent(this, DashboardActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }
        startActivity(intent)
        finish()
    }

    /**
     * Navigate to AdminConfigActivity for first-time setup.
     */
    private fun navigateToAdminConfig() {
        val intent = Intent(this, AdminConfigActivity::class.java).apply {
            putExtra(AdminConfigActivity.EXTRA_FIRST_TIME, true)
        }
        startActivity(intent)
        finish()
    }

    /**
     * Show keyboard automatically on the first PIN field.
     */
    private fun showKeyboard() {
        binding.etPin1.requestFocus()
        val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
        imm.showSoftInput(binding.etPin1, InputMethodManager.SHOW_IMPLICIT)
    }

    /**
     * Clear all PIN fields.
     */
    private fun clearAllPinFields() {
        binding.etPin1.text?.clear()
        binding.etPin2.text?.clear()
        binding.etPin3.text?.clear()
        binding.etPin4.text?.clear()
        // Focus no primeiro campo
        binding.etPin1.requestFocus()
    }
}
