package com.aura.tracking.data.supabase

import android.util.Log
import com.aura.tracking.BuildConfig
import com.aura.tracking.data.model.Equipment
import com.aura.tracking.data.model.EquipmentType
import com.aura.tracking.data.model.Fleet
import com.aura.tracking.data.model.Geofence
import com.aura.tracking.data.model.Operator
import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.android.Android
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.client.plugins.logging.LogLevel
import io.ktor.client.plugins.logging.Logger
import io.ktor.client.plugins.logging.Logging
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.parameter
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json

/**
 * Implementation of SupabaseApi using Ktor HTTP Client.
 * Connects to Supabase REST API (PostgREST).
 * 
 * Supabase Tables:
 * - operators: id, name, registration, pin, status, created_at, updated_at
 * - equipment: id, tag, type_id, status, location, fleet, created_at, updated_at
 * - equipment_types: id, name, description, seq_id, status, created_at, updated_at
 */
class SupabaseApiImpl : SupabaseApi {

    companion object {
        private const val TAG = "SupabaseApi"

        // Supabase credentials from BuildConfig
        private val SUPABASE_URL = BuildConfig.SUPABASE_URL
        private val SUPABASE_ANON_KEY = BuildConfig.SUPABASE_ANON_KEY

        // REST API base URL (full path)
        private val BASE_URL = "$SUPABASE_URL/rest/v1"
    }

    // Ktor HTTP Client with JSON serialization
    private val client: HttpClient by lazy {
        HttpClient(Android) {
            // JSON serialization
            install(ContentNegotiation) {
                json(Json {
                    prettyPrint = true
                    isLenient = true
                    ignoreUnknownKeys = true
                    encodeDefaults = true
                })
            }

            // Logging for debug
            install(Logging) {
                logger = object : Logger {
                    override fun log(message: String) {
                        Log.d(TAG, message)
                    }
                }
                level = LogLevel.BODY
            }

            // Default headers for all requests
            defaultRequest {
                contentType(ContentType.Application.Json)
                header("apikey", SUPABASE_ANON_KEY)
                header("Authorization", "Bearer $SUPABASE_ANON_KEY")
            }
        }
    }

    /** Build full URL for a table endpoint */
    private fun tableUrl(table: String) = "$BASE_URL/$table"

    /**
     * Authenticate operator using registration and PIN.
     * Queries the 'operators' table and validates credentials.
     */
    override suspend fun login(registration: String, pin: String): Result<Operator> {
        return try {
            Log.d(TAG, "Attempting login for registration: $registration")

            // Query operators table with registration and pin filters
            val operators: List<Operator> = client.get(tableUrl("operators")) {
                parameter("registration", "eq.$registration")
                parameter("pin", "eq.$pin")
                parameter("status", "eq.active")
                parameter("select", "*")
            }.body()

            if (operators.isNotEmpty()) {
                Log.d(TAG, "Login successful for: ${operators.first().name}")
                Result.success(operators.first())
            } else {
                Log.w(TAG, "Login failed: Invalid credentials")
                Result.failure(Exception("Credenciais inválidas"))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Login error: ${e.message}", e)
            Result.failure(e)
        }
    }

    /**
     * Fetch all unique fleets from equipment table.
     * Since there's no fleets table, we extract unique fleet names from equipment.
     */
    override suspend fun getFleets(): Result<List<Fleet>> {
        return try {
            Log.d(TAG, "Fetching fleets from equipment")

            // Get all equipment and extract unique fleets
            val equipment: List<Equipment> = client.get(tableUrl("equipment")) {
                parameter("status", "eq.active")
                parameter("select", "fleet")
            }.body()

            // Group by fleet name and count
            val fleets = equipment
                .mapNotNull { it.fleet }
                .groupBy { it }
                .map { (name, items) -> Fleet(name = name, equipmentCount = items.size) }
                .sortedBy { it.name }

            Log.d(TAG, "Fetched ${fleets.size} unique fleets")
            Result.success(fleets)
        } catch (e: Exception) {
            Log.e(TAG, "Error fetching fleets: ${e.message}", e)
            Result.failure(e)
        }
    }

    /**
     * Fetch equipment for a specific fleet.
     */
    override suspend fun getEquipmentByFleet(fleetName: String): Result<List<Equipment>> {
        return try {
            Log.d(TAG, "Fetching equipment for fleet: $fleetName")

            val equipment: List<Equipment> = client.get(tableUrl("equipment")) {
                parameter("fleet", "eq.$fleetName")
                parameter("status", "eq.active")
                parameter("select", "*")
                parameter("order", "tag.asc")
            }.body()

            Log.d(TAG, "Fetched ${equipment.size} equipment")
            Result.success(equipment)
        } catch (e: Exception) {
            Log.e(TAG, "Error fetching equipment: ${e.message}", e)
            Result.failure(e)
        }
    }

    /**
     * Fetch all active equipment.
     */
    override suspend fun getAllEquipment(): Result<List<Equipment>> {
        return try {
            Log.d(TAG, "Fetching all equipment")

            val equipment: List<Equipment> = client.get(tableUrl("equipment")) {
                parameter("status", "eq.active")
                parameter("select", "*")
                parameter("order", "tag.asc")
            }.body()

            Log.d(TAG, "Fetched ${equipment.size} equipment")
            Result.success(equipment)
        } catch (e: Exception) {
            Log.e(TAG, "Error fetching equipment: ${e.message}", e)
            Result.failure(e)
        }
    }

    /**
     * Fetch all equipment types.
     */
    override suspend fun getEquipmentTypes(): Result<List<EquipmentType>> {
        return try {
            Log.d(TAG, "Fetching equipment types")

            val types: List<EquipmentType> = client.get(tableUrl("equipment_types")) {
                parameter("status", "eq.active")
                parameter("select", "*")
                parameter("order", "seq_id.asc")
            }.body()

            Log.d(TAG, "Fetched ${types.size} equipment types")
            Result.success(types)
        } catch (e: Exception) {
            Log.e(TAG, "Error fetching equipment types: ${e.message}", e)
            Result.failure(e)
        }
    }

    /**
     * Fetch equipment for a specific equipment type.
     */
    override suspend fun getEquipmentByType(typeId: Long): Result<List<Equipment>> {
        return try {
            Log.d(TAG, "Fetching equipment for type: $typeId")

            val equipment: List<Equipment> = client.get(tableUrl("equipment")) {
                parameter("type_id", "eq.$typeId")
                parameter("status", "eq.active")
                parameter("select", "*")
                parameter("order", "tag.asc")
            }.body()

            Log.d(TAG, "Fetched ${equipment.size} equipment for type $typeId")
            Result.success(equipment)
        } catch (e: Exception) {
            Log.e(TAG, "Error fetching equipment by type: ${e.message}", e)
            Result.failure(e)
        }
    }

    /**
     * Fetch all active operators.
     */
    override suspend fun getOperators(): Result<List<Operator>> {
        return try {
            Log.d(TAG, "Fetching all operators")

            val operators: List<Operator> = client.get(tableUrl("operators")) {
                parameter("status", "eq.active")
                parameter("select", "*")
                parameter("order", "name.asc")
            }.body()

            Log.d(TAG, "Fetched ${operators.size} operators")
            Result.success(operators)
        } catch (e: Exception) {
            Log.e(TAG, "Error fetching operators: ${e.message}", e)
            Result.failure(e)
        }
    }

    /**
     * Fetch operator by registration number.
     */
    override suspend fun getOperatorByRegistration(registration: String): Result<Operator> {
        return try {
            Log.d(TAG, "Fetching operator by registration: $registration")

            val operators: List<Operator> = client.get(tableUrl("operators")) {
                parameter("registration", "eq.$registration")
                parameter("status", "eq.active")
                parameter("select", "*")
            }.body()

            if (operators.isNotEmpty()) {
                Log.d(TAG, "Found operator: ${operators[0].name}")
                Result.success(operators[0])
            } else {
                Result.failure(Exception("Operator not found"))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error fetching operator by registration: ${e.message}", e)
            Result.failure(e)
        }
    }

    /**
     * Validate if an operator session is still valid.
     */
    override suspend fun validateSession(operatorId: Long): Result<Boolean> {
        return try {
            Log.d(TAG, "Validating session for operator: $operatorId")

            val operators: List<Operator> = client.get(tableUrl("operators")) {
                parameter("id", "eq.$operatorId")
                parameter("status", "eq.active")
                parameter("select", "id")
            }.body()

            val isValid = operators.isNotEmpty()
            Log.d(TAG, "Session valid: $isValid")
            Result.success(isValid)
        } catch (e: Exception) {
            Log.e(TAG, "Error validating session: ${e.message}", e)
            Result.failure(e)
        }
    }

    /**
     * Fetch all active geofence zones.
     */
    override suspend fun getGeofences(): Result<List<Geofence>> {
        return try {
            Log.d(TAG, "Fetching geofences")

            val geofences: List<Geofence> = client.get(tableUrl("geofence")) {
                parameter("is_active", "eq.true")
                parameter("select", "*")
                parameter("order", "id.asc")
            }.body()

            Log.d(TAG, "Fetched ${geofences.size} geofences")
            Result.success(geofences)
        } catch (e: Exception) {
            Log.e(TAG, "Error fetching geofences: ${e.message}", e)
            Result.failure(e)
        }
    }
}
