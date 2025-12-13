package com.aura.tracking.sensors.system

import kotlinx.serialization.Serializable

/**
 * Modelo de dados para informações de sistema (bateria e conectividade)
 */
@Serializable
data class BatteryData(
    val level: Int? = null,                  // 0-100% (null se não disponível)
    val temperature: Float? = null,          // Celsius
    val status: String,                      // CHARGING, DISCHARGING, FULL, etc.
    val voltage: Int? = null,                // millivolts
    val health: String? = null,              // GOOD, OVERHEAT, etc.
    val technology: String? = null,          // Li-ion, etc.
    val chargeCounter: Long? = null,         // microampere-hours
    val fullCapacity: Long? = null           // microampere-hours
)

@Serializable
data class WifiData(
    val rssi: Int? = null,                   // dBm
    val ssid: String? = null,
    val bssid: String? = null,
    val frequency: Int? = null,              // MHz
    val channel: Int? = null
)

@Serializable
data class SignalStrengthData(
    val rsrp: Int? = null,                   // dBm (LTE)
    val rsrq: Int? = null,                   // dB (LTE)
    val rssnr: Int? = null,                  // dB (LTE)
    val rssi: Int? = null,                   // dBm
    val level: Int? = null                    // 0-4 scale
)

@Serializable
data class CellInfoData(
    val ci: Long? = null,                    // Cell Identity
    val pci: Int? = null,                     // Physical Cell Identity
    val tac: Int? = null,                     // Tracking Area Code
    val earfcn: Int? = null,                  // E-UTRAN Absolute Radio Frequency Channel Number
    val band: List<Int>? = null,             // LTE Band
    val bandwidth: Int? = null                // kHz
)

@Serializable
data class CellularData(
    val networkType: String? = null,         // LTE, 5G, etc.
    val operator: String? = null,
    val signalStrength: SignalStrengthData? = null,
    val cellInfo: CellInfoData? = null
)

@Serializable
data class ConnectivityData(
    val wifi: WifiData? = null,
    val cellular: CellularData? = null
)

@Serializable
data class SystemData(
    val battery: BatteryData? = null,
    val connectivity: ConnectivityData? = null,
    val timestamp: Long = System.currentTimeMillis()
)

