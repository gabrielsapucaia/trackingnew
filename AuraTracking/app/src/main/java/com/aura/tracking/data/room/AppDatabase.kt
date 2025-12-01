package com.aura.tracking.data.room

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

/**
 * Room database for AuraTracking.
 * Stores local configuration, operator data, and offline telemetry queue.
 * 
 * FASE 3 - QUEUE 30 DIAS (versão 4):
 * - Suporte para até 3.000.000 registros (~1.2 GB)
 * - Índice otimizado em createdAt para queries eficientes
 * - Campo message_id para deduplicação server-side
 * - Campo tracking_enabled para boot recovery
 * - PRAGMAs otimizados para performance com grande volume
 */
@Database(
    entities = [ConfigEntity::class, OperatorEntity::class, TelemetryQueueEntity::class],
    version = 4,
    exportSchema = true
)
abstract class AppDatabase : RoomDatabase() {

    abstract fun configDao(): ConfigDao
    abstract fun operatorDao(): OperatorDao
    abstract fun telemetryQueueDao(): TelemetryQueueDao

    companion object {
        private const val DATABASE_NAME = "aura_tracking_db"

        @Volatile
        private var instance: AppDatabase? = null

        fun getInstance(context: Context): AppDatabase {
            return instance ?: synchronized(this) {
                instance ?: buildDatabase(context).also { instance = it }
            }
        }

        /**
         * Migration 3 → 4: Queue 30 dias + Boot Recovery
         * 
         * Mudanças:
         * 1. Adiciona coluna message_id (UUID) na telemetry_queue
         * 2. Cria índice idx_queue_created_at para performance
         * 3. Adiciona coluna tracking_enabled na config
         */
        private val MIGRATION_3_4 = object : Migration(3, 4) {
            override fun migrate(database: SupportSQLiteDatabase) {
                // 1. Adicionar coluna message_id com valor default vazio
                database.execSQL(
                    "ALTER TABLE telemetry_queue ADD COLUMN message_id TEXT NOT NULL DEFAULT ''"
                )
                
                // 2. Gerar UUIDs para registros existentes (SQLite não tem UUID nativo,
                //    então usamos hex(randomblob) para criar um UUID v4 válido)
                database.execSQL("""
                    UPDATE telemetry_queue 
                    SET message_id = lower(
                        hex(randomblob(4)) || '-' || 
                        hex(randomblob(2)) || '-4' || 
                        substr(hex(randomblob(2)), 2) || '-' || 
                        substr('89ab', abs(random()) % 4 + 1, 1) || 
                        substr(hex(randomblob(2)), 2) || '-' || 
                        hex(randomblob(6))
                    ) 
                    WHERE message_id = ''
                """)
                
                // 3. Criar índice em createdAt para acelerar ORDER BY e purge
                //    CRÍTICO: sem este índice, queries em 3M registros levariam 30s+
                database.execSQL(
                    "CREATE INDEX IF NOT EXISTS idx_queue_created_at ON telemetry_queue(createdAt)"
                )
                
                // 4. Adicionar coluna tracking_enabled na config para boot recovery
                database.execSQL(
                    "ALTER TABLE config ADD COLUMN tracking_enabled INTEGER NOT NULL DEFAULT 0"
                )
            }
        }

        private fun buildDatabase(context: Context): AppDatabase {
            return Room.databaseBuilder(
                context.applicationContext,
                AppDatabase::class.java,
                DATABASE_NAME
            )
                .addMigrations(MIGRATION_3_4)
                // Callback para otimizações SQLite
                .addCallback(object : Callback() {
                    override fun onOpen(db: SupportSQLiteDatabase) {
                        super.onOpen(db)
                        // Otimizações para queue de 30 dias (~3M registros, ~1.2 GB)
                        // Nota: usamos query() para PRAGMAs pois execSQL pode ter problemas
                        // em algumas versões do Room/SQLite
                        try {
                            db.query("PRAGMA cache_size = -8000").close()
                            db.query("PRAGMA temp_store = MEMORY").close()
                            db.query("PRAGMA wal_autocheckpoint = 1000").close()
                            db.query("PRAGMA synchronous = NORMAL").close()
                        } catch (e: Exception) {
                            // Falha silenciosa - PRAGMAs são otimizações opcionais
                            android.util.Log.w("AppDatabase", "Failed to set PRAGMAs: ${e.message}")
                        }
                    }
                })
                .fallbackToDestructiveMigration()
                .build()
        }
    }
}
