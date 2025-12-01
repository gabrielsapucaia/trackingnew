package com.aura.tracking.data.room

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Entity representing the currently logged-in operator.
 * Stored locally for session persistence.
 * 
 * Maps to Supabase 'operators' table:
 * - id: bigint (primary key)
 * - name: text
 * - registration: text (matrícula)
 * - pin: char(4)
 * - status: text (active/inactive)
 */
@Entity(tableName = "operator")
data class OperatorEntity(
    @PrimaryKey
    @ColumnInfo(name = "id")
    val id: Long,

    @ColumnInfo(name = "registration")
    val registration: String,

    @ColumnInfo(name = "name")
    val name: String,

    @ColumnInfo(name = "token")
    val token: String? = null,

    @ColumnInfo(name = "logged_in_at")
    val loggedInAt: Long = System.currentTimeMillis(),

    @ColumnInfo(name = "is_active")
    val isActive: Boolean = true
)
