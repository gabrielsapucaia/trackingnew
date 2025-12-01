package com.aura.tracking.ui.admin

import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import com.aura.tracking.R
import com.aura.tracking.databinding.ActivitySupabasePinBinding

/**
 * SupabasePinActivity - PIN entry for accessing Supabase configuration.
 * PIN: 1234
 */
class SupabasePinActivity : AppCompatActivity() {

    companion object {
        private const val SUPABASE_PIN = "1234"
    }

    private lateinit var binding: ActivitySupabasePinBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySupabasePinBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupUI()
        setupClickListeners()
    }

    private fun setupUI() {
        binding.tvTitle.text = getString(R.string.supabase_pin_title)
        binding.tvSubtitle.text = getString(R.string.supabase_pin_subtitle)
    }

    private fun setupClickListeners() {
        binding.btnBack.setOnClickListener {
            finish()
        }

        binding.btnConfirm.setOnClickListener {
            validatePin()
        }
    }

    private fun validatePin() {
        val enteredPin = binding.etPin.text?.toString()?.trim() ?: ""

        if (enteredPin.isEmpty()) {
            binding.tvError.text = getString(R.string.supabase_pin_error_empty)
            binding.tvError.visibility = View.VISIBLE
            return
        }

        if (enteredPin != SUPABASE_PIN) {
            binding.tvError.text = getString(R.string.supabase_pin_error_invalid)
            binding.tvError.visibility = View.VISIBLE
            return
        }

        // PIN correto, navegar para SupabaseConfigActivity
        binding.tvError.visibility = View.GONE
        navigateToSupabaseConfig()
    }

    private fun navigateToSupabaseConfig() {
        val intent = Intent(this, SupabaseConfigActivity::class.java)
        startActivity(intent)
        finish()
    }
}

