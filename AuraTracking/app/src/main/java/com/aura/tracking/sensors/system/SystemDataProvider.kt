package com.aura.tracking.sensors.system

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiInfo
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.telephony.CellInfo
import android.telephony.CellInfoLte
import android.telephony.TelephonyManager
import com.aura.tracking.logging.AuraLog
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale

/**
 * SystemDataProvider - Fornece dados de bateria e conectividade a 1Hz.
 */
class SystemDataProvider(private val context: Context) {

    companion object {
        private const val TAG = "SystemDataProvider"
        private const val UPDATE_INTERVAL_MS = 1000L // 1Hz
    }

    private var isRunning = false
    private var batteryReceiver: BroadcastReceiver? = null
    private val handlerThread: HandlerThread? = HandlerThread("SystemDataThread").apply { start() }
    private val handler: Handler? = Handler(handlerThread?.looper ?: android.os.Looper.getMainLooper())
    private var updateRunnable: Runnable? = null

    // Estado reativo do último dado de sistema
    private val _lastSystemData = kotlinx.coroutines.flow.MutableStateFlow<SystemData?>(null)
    val lastSystemData: kotlinx.coroutines.flow.StateFlow<SystemData?> = _lastSystemData.asStateFlow()

    // Listeners
    var onSystemDataUpdate: ((SystemData) -> Unit)? = null

    // Managers
    private val batteryManager: BatteryManager? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
        context.getSystemService(Context.BATTERY_SERVICE) as? BatteryManager
    } else null

    private val connectivityManager: ConnectivityManager? =
        context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager

    private val telephonyManager: TelephonyManager? =
        context.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager

    private val wifiManager: WifiManager? =
        context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager

    /**
     * Start receiving system data updates at 1Hz.
     */
    fun startSystemUpdates() {
        if (isRunning) {
            AuraLog.Service.d("System data updates already running")
            return
        }

        AuraLog.Service.i("Starting system data updates at 1Hz")

        // Registra receiver de bateria
        batteryReceiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                // Bateria atualizada - será coletada no próximo ciclo
            }
        }
        context.registerReceiver(batteryReceiver, IntentFilter(Intent.ACTION_BATTERY_CHANGED))

        // Inicia thread para atualizações periódicas
        updateRunnable = object : Runnable {
            override fun run() {
                emitSystemData()
                handler?.postDelayed(this, UPDATE_INTERVAL_MS)
            }
        }

        handler?.postDelayed(updateRunnable!!, UPDATE_INTERVAL_MS)
        isRunning = true
    }

    /**
     * Stop receiving system data updates.
     */
    fun stopSystemUpdates() {
        if (!isRunning) {
            AuraLog.Service.d("System data updates not running")
            return
        }

        AuraLog.Service.i("Stopping system data updates")

        updateRunnable?.let { handler?.removeCallbacks(it) }
        batteryReceiver?.let { context.unregisterReceiver(it) }
        batteryReceiver = null

        handlerThread?.quitSafely()

        isRunning = false
    }

    /**
     * Emite dados de sistema a 1Hz.
     */
    private fun emitSystemData() {
        val batteryData = collectBatteryData()
        val connectivityData = collectConnectivityData()

        val systemData = SystemData(
            battery = batteryData,
            connectivity = connectivityData
        )

        _lastSystemData.value = systemData
        onSystemDataUpdate?.invoke(systemData)
    }

    /**
     * Coleta dados de bateria.
     */
    private fun collectBatteryData(): BatteryData? {
        val batteryStatus = context.registerReceiver(
            null,
            IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        ) ?: return null

        val level = batteryStatus.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        val scale = batteryStatus.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
        val batteryLevel = if (level >= 0 && scale > 0) {
            (level * 100) / scale
        } else null

        val temperature = batteryStatus.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1)
        val batteryTemperature = if (temperature > 0) temperature / 10f else null // Em décimos de grau

        val status = batteryStatus.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
        val batteryStatusStr = when (status) {
            BatteryManager.BATTERY_STATUS_CHARGING -> "CHARGING"
            BatteryManager.BATTERY_STATUS_DISCHARGING -> "DISCHARGING"
            BatteryManager.BATTERY_STATUS_FULL -> "FULL"
            BatteryManager.BATTERY_STATUS_NOT_CHARGING -> "NOT_CHARGING"
            else -> "UNKNOWN"
        }

        val voltage = batteryStatus.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1)
        val batteryVoltage = if (voltage > 0) voltage else null

        val health = batteryStatus.getIntExtra(BatteryManager.EXTRA_HEALTH, -1)
        val batteryHealth = when (health) {
            BatteryManager.BATTERY_HEALTH_GOOD -> "GOOD"
            BatteryManager.BATTERY_HEALTH_OVERHEAT -> "OVERHEAT"
            BatteryManager.BATTERY_HEALTH_DEAD -> "DEAD"
            BatteryManager.BATTERY_HEALTH_OVER_VOLTAGE -> "OVER_VOLTAGE"
            BatteryManager.BATTERY_HEALTH_UNSPECIFIED_FAILURE -> "UNSPECIFIED_FAILURE"
            BatteryManager.BATTERY_HEALTH_COLD -> "COLD"
            else -> null
        }

        val technology = batteryStatus.getStringExtra(BatteryManager.EXTRA_TECHNOLOGY)

        val chargeCounter = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            batteryManager?.getLongProperty(BatteryManager.BATTERY_PROPERTY_CHARGE_COUNTER)
        } else null

        val fullCapacity = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            batteryManager?.getLongProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        } else null

        return BatteryData(
            level = batteryLevel,  // null se não disponível (em vez de 0)
            temperature = batteryTemperature,
            status = batteryStatusStr,
            voltage = batteryVoltage,
            health = batteryHealth,
            technology = technology,
            chargeCounter = chargeCounter,
            fullCapacity = fullCapacity
        )
    }

    /**
     * Coleta dados de conectividade.
     */
    private fun collectConnectivityData(): ConnectivityData? {
        val wifiData = collectWifiData()
        val cellularData = collectCellularData()

        return ConnectivityData(
            wifi = wifiData,
            cellular = cellularData
        )
    }

    /**
     * Coleta dados WiFi.
     */
    private fun collectWifiData(): WifiData? {
        if (wifiManager == null) return null

        return try {
            val wifiInfo: WifiInfo? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                connectivityManager?.getNetworkCapabilities(
                    connectivityManager.activeNetwork
                )?.let { capabilities ->
                    if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
                        wifiManager.connectionInfo
                    } else null
                }
            } else {
                @Suppress("DEPRECATION")
                wifiManager.connectionInfo
            }

            if (wifiInfo == null) return null

            val rssi = wifiInfo.rssi
            val ssid = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                wifiInfo.ssid?.replace("\"", "")
            } else {
                @Suppress("DEPRECATION")
                wifiInfo.ssid?.replace("\"", "")
            }
            val bssid = wifiInfo.bssid

            val frequency = wifiInfo.frequency
            val channel = if (frequency > 0) {
                when {
                    frequency in 2412..2484 -> (frequency - 2412) / 5 + 1 // 2.4 GHz
                    frequency in 5170..5825 -> (frequency - 5000) / 5 // 5 GHz
                    else -> null
                }
            } else null

            WifiData(
                rssi = if (rssi != Int.MIN_VALUE) rssi else null,
                ssid = ssid,
                bssid = bssid,
                frequency = if (frequency > 0) frequency else null,
                channel = channel
            )
        } catch (e: SecurityException) {
            AuraLog.Service.w("WiFi permission not granted: ${e.message}")
            null
        } catch (e: Exception) {
            AuraLog.Service.e("Error collecting WiFi data: ${e.message}", e)
            null
        }
    }

    /**
     * Coleta dados celulares.
     */
    private fun collectCellularData(): CellularData? {
        if (telephonyManager == null) return null

        return try {
            val networkType = try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                    when (telephonyManager.dataNetworkType) {
                        TelephonyManager.NETWORK_TYPE_LTE -> "LTE"
                        TelephonyManager.NETWORK_TYPE_NR -> "5G"
                        TelephonyManager.NETWORK_TYPE_HSPAP -> "HSPA+"
                        TelephonyManager.NETWORK_TYPE_HSPA -> "HSPA"
                        TelephonyManager.NETWORK_TYPE_EDGE -> "EDGE"
                        TelephonyManager.NETWORK_TYPE_GPRS -> "GPRS"
                        else -> "UNKNOWN"
                    }
                } else {
                    @Suppress("DEPRECATION")
                    when (telephonyManager.networkType) {
                        TelephonyManager.NETWORK_TYPE_LTE -> "LTE"
                        TelephonyManager.NETWORK_TYPE_HSPAP -> "HSPA+"
                        TelephonyManager.NETWORK_TYPE_HSPA -> "HSPA"
                        TelephonyManager.NETWORK_TYPE_EDGE -> "EDGE"
                        TelephonyManager.NETWORK_TYPE_GPRS -> "GPRS"
                        else -> "UNKNOWN"
                    }
                }
            } catch (e: SecurityException) {
                AuraLog.Service.w("Telephony permission not granted for network type: ${e.message}")
                null
            }

            val operator = try {
                telephonyManager.networkOperatorName
            } catch (e: SecurityException) {
                AuraLog.Service.w("Telephony permission not granted for networkOperatorName: ${e.message}")
                null
            }

            // Coleta informações de célula LTE
            val cellInfo = collectCellInfo()
            val signalStrength = collectSignalStrength()

            CellularData(
                networkType = networkType,
                operator = operator,
                signalStrength = signalStrength,
                cellInfo = cellInfo
            )
        } catch (e: SecurityException) {
            AuraLog.Service.w("Telephony permission not granted: ${e.message}")
            null
        } catch (e: Exception) {
            AuraLog.Service.e("Error collecting cellular data: ${e.message}", e)
            null
        }
    }

    /**
     * Coleta informações de célula.
     */
    private fun collectCellInfo(): CellInfoData? {
        if (telephonyManager == null) return null

        return try {
            val cellInfos = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                telephonyManager.allCellInfo
            } else {
                @Suppress("DEPRECATION")
                telephonyManager.allCellInfo
            }

            val lteCellInfo = cellInfos?.firstOrNull { it is CellInfoLte } as? CellInfoLte
                ?: return null

            val cellIdentity = lteCellInfo.cellIdentity
            val cellSignalStrength = lteCellInfo.cellSignalStrength

            val ci = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                cellIdentity.ci
            } else {
                @Suppress("DEPRECATION")
                cellIdentity.ci
            }

            val pci = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                cellIdentity.pci
            } else {
                @Suppress("DEPRECATION")
                cellIdentity.pci
            }

            val tac = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                cellIdentity.tac
            } else {
                @Suppress("DEPRECATION")
                cellIdentity.tac
            }

            val earfcn = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                cellIdentity.earfcn
            } else {
                @Suppress("DEPRECATION")
                cellIdentity.earfcn
            }

            val bands = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                cellIdentity.bands?.toList()
            } else {
                null
            }

            val bandwidth = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                cellIdentity.bandwidth
            } else {
                @Suppress("DEPRECATION")
                cellIdentity.bandwidth
            }

            CellInfoData(
                ci = ci.takeIf { it != Int.MAX_VALUE }?.toLong(),
                pci = pci.takeIf { it != Int.MAX_VALUE },
                tac = tac.takeIf { it != Int.MAX_VALUE },
                earfcn = earfcn.takeIf { it != Int.MAX_VALUE },
                band = bands,
                bandwidth = bandwidth.takeIf { it != Int.MAX_VALUE }
            )
        } catch (e: SecurityException) {
            AuraLog.Service.w("Telephony permission not granted for cell info: ${e.message}")
            null
        } catch (e: Exception) {
            AuraLog.Service.e("Error collecting cell info: ${e.message}", e)
            null
        }
    }

    /**
     * Coleta força do sinal celular.
     */
    private fun collectSignalStrength(): SignalStrengthData? {
        if (telephonyManager == null) return null

        return try {
            val cellInfos = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                telephonyManager.allCellInfo
            } else {
                @Suppress("DEPRECATION")
                telephonyManager.allCellInfo
            }

            val lteCellInfo = cellInfos?.firstOrNull { it is CellInfoLte } as? CellInfoLte
                ?: return null

            val cellSignalStrength = lteCellInfo.cellSignalStrength

            val rsrp = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                cellSignalStrength.rsrp
            } else {
                @Suppress("DEPRECATION")
                cellSignalStrength.dbm
            }

            val rsrq = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                cellSignalStrength.rsrq
            } else {
                null
            }

            val rssnr = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                cellSignalStrength.rssnr
            } else {
                null
            }

            val rssi = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                cellSignalStrength.rssi
            } else {
                null
            }

            val level = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                cellSignalStrength.level
            } else {
                @Suppress("DEPRECATION")
                cellSignalStrength.level
            }

            SignalStrengthData(
                rsrp = rsrp.takeIf { it != Int.MAX_VALUE },
                rsrq = rsrq.takeIf { it != Int.MAX_VALUE },
                rssnr = rssnr.takeIf { it != Int.MAX_VALUE },
                rssi = rssi.takeIf { it != Int.MAX_VALUE },
                level = level.takeIf { it >= 0 }
            )
        } catch (e: SecurityException) {
            AuraLog.Service.w("Telephony permission not granted for signal strength: ${e.message}")
            null
        } catch (e: Exception) {
            AuraLog.Service.e("Error collecting signal strength: ${e.message}", e)
            null
        }
    }

    fun isRunning(): Boolean = isRunning
}

