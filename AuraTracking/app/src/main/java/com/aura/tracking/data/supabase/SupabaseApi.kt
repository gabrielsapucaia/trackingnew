package com.aura.tracking.data.supabase

import com.aura.tracking.data.model.Equipment
import com.aura.tracking.data.model.EquipmentType
import com.aura.tracking.data.model.Fleet
import com.aura.tracking.data.model.Geofence
import com.aura.tracking.data.model.Operator

/**
 * Interface for Supabase API operations.
 * Defines all remote data operations for the app.
 */
interface SupabaseApi {

    /**
     * Authenticate an operator using registration and PIN.
     * @param registration The operator's registration number.
     * @param pin The operator's 4-digit PIN.
     * @return Result containing the Operator on success, or exception on failure.
     */
    suspend fun login(registration: String, pin: String): Result<Operator>

    /**
     * Fetch all unique fleets from equipment table.
     * @return Result containing list of Fleets on success.
     */
    suspend fun getFleets(): Result<List<Fleet>>

    /**
     * Fetch all active equipment for a specific fleet.
     * @param fleetName The name of the fleet to filter by.
     * @return Result containing list of Equipment on success.
     */
    suspend fun getEquipmentByFleet(fleetName: String): Result<List<Equipment>>

    /**
     * Fetch all active equipment (no filter).
     * @return Result containing list of all Equipment on success.
     */
    suspend fun getAllEquipment(): Result<List<Equipment>>

    /**
     * Fetch all equipment types.
     * @return Result containing list of EquipmentTypes on success.
     */
    suspend fun getEquipmentTypes(): Result<List<EquipmentType>>

    /**
     * Fetch all active equipment for a specific equipment type.
     * @param typeId The ID of the equipment type to filter by.
     * @return Result containing list of Equipment on success.
     */
    suspend fun getEquipmentByType(typeId: Long): Result<List<Equipment>>

    /**
     * Fetch all active operators.
     * @return Result containing list of Operators on success.
     */
    suspend fun getOperators(): Result<List<Operator>>

    /**
     * Fetch operator by registration number.
     * @param registration The operator's registration number.
     * @return Result containing the Operator on success.
     */
    suspend fun getOperatorByRegistration(registration: String): Result<Operator>

    /**
     * Fetch all active equipment (alias for getAllEquipment).
     * @return Result containing list of all Equipment on success.
     */
    suspend fun getEquipments(): Result<List<Equipment>> = getAllEquipment()

    /**
     * Validate if the operator session is still valid.
     * @param operatorId The operator's ID to validate.
     * @return Result containing Boolean (true if valid).
     */
    suspend fun validateSession(operatorId: Long): Result<Boolean>

    /**
     * Fetch all active geofence zones.
     * @return Result containing list of Geofences on success.
     */
    suspend fun getGeofences(): Result<List<Geofence>>
}
