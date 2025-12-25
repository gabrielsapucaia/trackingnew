package com.aura.tracking.sync

import com.aura.tracking.data.model.Geofence
import com.aura.tracking.data.model.Operator
import com.aura.tracking.logging.AuraLog
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray

/**
 * SyncValidator - Validações/Guardrails para dados sincronizados.
 *
 * Garante integridade dos dados antes de commit no banco local.
 */
object SyncValidator {

    private val json = Json { ignoreUnknownKeys = true }

    /**
     * Valida lista de operadores.
     * @throws SyncValidationException se validação falhar
     */
    fun validateOperators(operators: List<Operator>) {
        // Guardrail 1: Deve ter pelo menos 1 operador
        if (operators.size < SyncConfig.MIN_OPERATORS) {
            throw SyncValidationException(
                "Operators validation failed: expected at least ${SyncConfig.MIN_OPERATORS}, got ${operators.size}"
            )
        }

        // Guardrail 2: Todos devem ter ID válido
        operators.forEach { operator ->
            if (operator.id <= 0) {
                throw SyncValidationException("Operator has invalid ID: ${operator.id}")
            }
            if (operator.name.isBlank()) {
                throw SyncValidationException("Operator ${operator.id} has blank name")
            }
            if (operator.registration.isBlank()) {
                throw SyncValidationException("Operator ${operator.id} has blank registration")
            }
        }

        AuraLog.Sync.d("Operators validation passed: ${operators.size} valid operators")
    }

    /**
     * Valida lista de geofences.
     * @throws SyncValidationException se validação falhar
     */
    fun validateGeofences(geofences: List<Geofence>) {
        // Geofences podem ser vazias (nenhuma zona configurada)
        if (geofences.isEmpty()) {
            AuraLog.Sync.d("Geofences validation passed: empty list (no zones configured)")
            return
        }

        geofences.forEach { geofence ->
            validateGeofence(geofence)
        }

        AuraLog.Sync.d("Geofences validation passed: ${geofences.size} valid zones")
    }

    /**
     * Valida uma geofence individual.
     */
    private fun validateGeofence(geofence: Geofence) {
        // Guardrail 1: ID válido
        if (geofence.id <= 0) {
            throw SyncValidationException("Geofence has invalid ID: ${geofence.id}")
        }

        // Guardrail 2: Nome não vazio
        if (geofence.name.isBlank()) {
            throw SyncValidationException("Geofence ${geofence.id} has blank name")
        }

        // Guardrail 3: Tipo de zona válido
        if (geofence.zoneType !in listOf("carregamento", "basculamento", "manutencao", "abastecimento")) {
            AuraLog.Sync.w("Geofence ${geofence.id} has unknown zone type: ${geofence.zoneType}")
            // Não falha, apenas avisa - pode ser um novo tipo
        }

        // Guardrail 4: Polígono válido
        validatePolygon(geofence.id, geofence.polygonJson)
    }

    /**
     * Valida JSON do polígono.
     */
    private fun validatePolygon(geofenceId: Long, polygonJson: String) {
        if (polygonJson.isBlank()) {
            throw SyncValidationException("Geofence $geofenceId has blank polygon")
        }

        try {
            val coordinates = json.parseToJsonElement(polygonJson).jsonArray

            // Guardrail: Mínimo de pontos para formar um polígono
            if (coordinates.size < SyncConfig.MIN_POLYGON_POINTS) {
                throw SyncValidationException(
                    "Geofence $geofenceId polygon has ${coordinates.size} points, " +
                    "minimum is ${SyncConfig.MIN_POLYGON_POINTS}"
                )
            }

            // Valida cada coordenada
            coordinates.forEachIndexed { index, coord ->
                val point = coord.jsonArray
                if (point.size != 2) {
                    throw SyncValidationException(
                        "Geofence $geofenceId point $index has ${point.size} values, expected 2 [lat,lon]"
                    )
                }
            }
        } catch (e: SyncValidationException) {
            throw e
        } catch (e: Exception) {
            throw SyncValidationException(
                "Geofence $geofenceId has invalid polygon JSON: ${e.message}"
            )
        }
    }

    /**
     * Valida todos os dados de uma vez.
     * @throws SyncValidationException se qualquer validação falhar
     */
    fun validateAll(operators: List<Operator>, geofences: List<Geofence>) {
        validateOperators(operators)
        validateGeofences(geofences)
    }
}

/**
 * Exceção de validação de sync.
 */
class SyncValidationException(message: String) : Exception(message)
