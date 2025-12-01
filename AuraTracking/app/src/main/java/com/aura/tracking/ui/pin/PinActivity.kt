package com.aura.tracking.ui.pin

import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.aura.tracking.AuraTrackingApp
import com.aura.tracking.R
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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityPinBinding.inflate(layoutInflater)
        setContentView(binding.root)

        registration = intent.getStringExtra(EXTRA_REGISTRATION) ?: ""

        if (registration.isEmpty()) {
            finish()
            return
        }

        setupUI()
        setupClickListeners()
    }

    private fun setupUI() {
        binding.tvOperator.text = getString(R.string.pin_subtitle, registration)
    }

    private fun setupClickListeners() {
        binding.btnBack.setOnClickListener {
            finish()
        }

        binding.btnLogin.setOnClickListener {
            attemptLogin()
        }
    }

    /**
     * Attempt to login with the provided PIN.
     */
    private fun attemptLogin() {
        val pin = binding.etPin.text?.toString()?.trim() ?: ""

        // Validate PIN
        if (pin.isEmpty()) {
            showError(getString(R.string.pin_error_empty))
            return
        }

        if (pin.length != 4) {
            showError(getString(R.string.pin_error_invalid))
            return
        }

        // Show loading
        setLoading(true)
        hideError()

        // Call Supabase API
        lifecycleScope.launch {
            try {
                val result = AuraTrackingApp.supabaseApi.login(registration, pin)

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
        binding.etPin.isEnabled = !loading
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
}
