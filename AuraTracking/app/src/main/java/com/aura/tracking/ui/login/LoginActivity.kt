package com.aura.tracking.ui.login

import android.content.Intent
import android.os.Bundle
import android.view.KeyEvent
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.aura.tracking.AuraTrackingApp
import com.aura.tracking.BuildConfig
import com.aura.tracking.data.room.ConfigEntity
import com.aura.tracking.data.room.OperatorEntity
import com.aura.tracking.databinding.ActivityLoginBinding
import com.aura.tracking.ui.dashboard.DashboardActivity
import com.aura.tracking.ui.pin.PinActivity
import kotlinx.coroutines.launch

/**
 * LoginActivity - Entry point of the application.
 * Operator enters their matricula (registration number).
 */
class LoginActivity : AppCompatActivity() {

    companion object {
        // Test mode: Use "TEST" as matricula to bypass Supabase authentication
        const val TEST_MODE_MATRICULA = "TEST"
    }

    private lateinit var binding: ActivityLoginBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)

        checkExistingSession()
        setupClickListeners()
        
        // Show test mode hint in debug builds
        if (BuildConfig.DEBUG) {
            binding.tilMatricula.helperText = "Modo teste: use 'TEST' como matrícula"
        }
    }

    /**
     * Check if there's an existing operator session.
     * If yes, navigate directly to Dashboard.
     */
    private fun checkExistingSession() {
        lifecycleScope.launch {
            try {
                val operator = AuraTrackingApp.database.operatorDao().getCurrentOperator()
                if (operator != null) {
                    // Operator already logged in, go to Dashboard
                    navigateToDashboard()
                }
            } catch (e: Exception) {
                // No session found, stay on login
            }
        }
    }

    private fun setupClickListeners() {
        binding.btnContinue.setOnClickListener {
            performLoginAction()
        }

        binding.btnSettings.setOnClickListener {
            navigateToSettings()
        }

        // Listener para o teclado (seta direita)
        binding.etMatricula.setOnEditorActionListener { _, actionId, event ->
            if (actionId == EditorInfo.IME_ACTION_GO ||
                (event?.keyCode == KeyEvent.KEYCODE_ENTER && event.action == KeyEvent.ACTION_DOWN)) {
                performLoginAction()
                true
            } else {
                false
            }
        }
    }

    private fun performLoginAction() {
        val matricula = binding.etMatricula.text?.toString()?.trim()

        if (matricula.isNullOrEmpty()) {
            binding.tilMatricula.error = getString(com.aura.tracking.R.string.login_error_empty)
            return
        }

        binding.tilMatricula.error = null

        // Test mode bypass: If DEBUG build and "TEST" matricula, skip Supabase
        if (BuildConfig.DEBUG && matricula.equals(TEST_MODE_MATRICULA, ignoreCase = true)) {
            setupTestModeAndNavigate()
        } else {
            navigateToPin(matricula)
        }
    }
    
    /**
     * Setup test mode with mock data and navigate to Dashboard.
     */
    private fun setupTestModeAndNavigate() {
        lifecycleScope.launch {
            try {
                // Insert test operator
                val testOperator = OperatorEntity(
                    id = 999999L,
                    registration = "TEST",
                    name = "Operador de Teste",
                    token = null,
                    isActive = true
                )
                AuraTrackingApp.database.operatorDao().insertOperator(testOperator)
                
                // Insert test config - AuraTracking Server (local intranet)
                val testConfig = ConfigEntity(
                    id = 1,
                    mqttHost = "192.168.0.113", // AuraTracking Server local
                    mqttPort = 1883,
                    mqttTopic = "aura/tracking/${android.os.Build.SERIAL}",
                    fleetId = "test-fleet-001",
                    fleetName = "Frota de Teste",
                    equipmentId = android.os.Build.SERIAL ?: "moto-g34",
                    equipmentName = "Moto G34 - Caminhão Teste",
                    updatedAt = System.currentTimeMillis()
                )
                AuraTrackingApp.database.configDao().insertConfig(testConfig)
                
                Toast.makeText(this@LoginActivity, "Modo de teste ativado!", Toast.LENGTH_SHORT).show()
                navigateToDashboard()
            } catch (e: Exception) {
                Toast.makeText(this@LoginActivity, "Erro: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    /**
     * Navigate to PinActivity with the registration number.
     */
    private fun navigateToPin(registration: String) {
        val intent = Intent(this, PinActivity::class.java).apply {
            putExtra(PinActivity.EXTRA_REGISTRATION, registration)
        }
        startActivity(intent)
    }

    /**
     * Navigate to Settings (AdminConfigActivity).
     */
    private fun navigateToSettings() {
        val intent = Intent(this, com.aura.tracking.ui.admin.AdminConfigActivity::class.java).apply {
            // Pass flag indicating this is accessed from login screen (not first time setup)
            putExtra(com.aura.tracking.ui.admin.AdminConfigActivity.EXTRA_FIRST_TIME, false)
        }
        startActivity(intent)
    }

    /**
     * Navigate to DashboardActivity and clear back stack.
     */
    private fun navigateToDashboard() {
        val intent = Intent(this, DashboardActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }
        startActivity(intent)
        finish()
    }
}
