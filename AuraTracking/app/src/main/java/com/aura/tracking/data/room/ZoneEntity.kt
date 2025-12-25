package com.aura.tracking.data.room

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * ZoneEntity - Zona geográfica para geofencing.
 *
 * Representa áreas de interesse (carga, descarga, depósito, etc.)
 * para detecção de entrada/saída de equipamentos.
 *
 * Suporta dois tipos de geometria:
 * - Polígono: lista de coordenadas [(lat, lon), ...]
 * - Círculo: centro (lat, lon) + raio em metros
 */
@Entity(
    tableName = "zones",
    indices = [
        Index(name = "idx_zone_type", value = ["zoneType"]),
        Index(name = "idx_zone_active", value = ["isActive"])
    ]
)
data class ZoneEntity(
    @PrimaryKey
    val id: Long,

    val name: String,

    /**
     * Tipo da zona:
     * - loading_zone: Zona de carregamento (escavadeira/pá carregadeira)
     * - unloading_zone: Zona de descarga (basculamento)
     * - deposit: Depósito/pilha de material
     * - maintenance: Área de manutenção
     * - fuel_station: Posto de abastecimento
     * - parking: Estacionamento
     * - restricted: Área restrita
     */
    @ColumnInfo(name = "zoneType")
    val zoneType: String,

    /**
     * Coordenadas do polígono em formato JSON.
     * Exemplo: [[lat1,lon1],[lat2,lon2],[lat3,lon3],[lat4,lon4]]
     *
     * Deve formar um polígono fechado (primeiro = último ponto).
     * Null se usando geometria circular (centerLat/centerLon + radiusMeters).
     */
    @ColumnInfo(name = "polygonJson")
    val polygonJson: String? = null,

    /**
     * Centro do círculo - Latitude
     * Usado quando radiusMeters > 0
     */
    @ColumnInfo(name = "centerLat")
    val centerLat: Double? = null,

    /**
     * Centro do círculo - Longitude
     * Usado quando radiusMeters > 0
     */
    @ColumnInfo(name = "centerLon")
    val centerLon: Double? = null,

    /**
     * Raio em metros para geometria circular.
     * Se > 0, usa círculo ao invés de polígono.
     */
    @ColumnInfo(name = "radiusMeters")
    val radiusMeters: Float? = null,

    /**
     * Cor para visualização no mapa (hex: #RRGGBB ou #AARRGGBB)
     */
    val color: String = "#4CAF50",

    /**
     * Se a zona está ativa para detecção
     */
    @ColumnInfo(name = "isActive")
    val isActive: Boolean = true,

    /**
     * Timestamp da última atualização (sync com Supabase)
     */
    @ColumnInfo(name = "updatedAt")
    val updatedAt: Long = System.currentTimeMillis(),

    /**
     * Timestamp da criação no servidor
     */
    @ColumnInfo(name = "createdAt")
    val createdAt: Long = System.currentTimeMillis()
) {
    /**
     * Verifica se a zona usa geometria circular
     */
    fun isCircular(): Boolean = radiusMeters != null && radiusMeters > 0

    /**
     * Verifica se a zona usa geometria poligonal
     */
    fun isPolygon(): Boolean = !polygonJson.isNullOrEmpty()
}

/**
 * Tipos de zona suportados
 */
object ZoneType {
    const val LOADING_ZONE = "loading_zone"
    const val UNLOADING_ZONE = "unloading_zone"
    const val DEPOSIT = "deposit"
    const val MAINTENANCE = "maintenance"
    const val FUEL_STATION = "fuel_station"
    const val PARKING = "parking"
    const val RESTRICTED = "restricted"
    const val OTHER = "other"
}
