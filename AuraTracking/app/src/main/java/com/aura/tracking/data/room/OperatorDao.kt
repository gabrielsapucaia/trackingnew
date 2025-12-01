package com.aura.tracking.data.room

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

/**
 * DAO for OperatorEntity operations.
 */
@Dao
interface OperatorDao {

    /**
     * Get the currently logged-in operator.
     */
    @Query("SELECT * FROM operator WHERE is_active = 1 LIMIT 1")
    suspend fun getCurrentOperator(): OperatorEntity?

    /**
     * Observe the current operator as a Flow.
     */
    @Query("SELECT * FROM operator WHERE is_active = 1 LIMIT 1")
    fun observeCurrentOperator(): Flow<OperatorEntity?>

    /**
     * Get operator by ID.
     */
    @Query("SELECT * FROM operator WHERE id = :id LIMIT 1")
    suspend fun getOperatorById(id: String): OperatorEntity?

    /**
     * Get operator by registration.
     */
    @Query("SELECT * FROM operator WHERE registration = :registration LIMIT 1")
    suspend fun getOperatorByRegistration(registration: String): OperatorEntity?

    /**
     * Insert or replace an operator.
     */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertOperator(operator: OperatorEntity)

    /**
     * Delete an operator.
     */
    @Delete
    suspend fun deleteOperator(operator: OperatorEntity)

    /**
     * Clear all operators (logout).
     */
    @Query("DELETE FROM operator")
    suspend fun clearAllOperators()

    /**
     * Check if any operator is logged in.
     */
    @Query("SELECT EXISTS(SELECT 1 FROM operator WHERE is_active = 1)")
    suspend fun hasLoggedInOperator(): Boolean
}
