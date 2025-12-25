package com.aura.tracking.sync

/**
 * SyncResult - Resultado da sincronização.
 */
sealed class SyncResult {
    /** Sync completado com sucesso (download + upload) */
    data class Success(
        val downloadedCount: Int,
        val uploadedCount: Int
    ) : SyncResult()

    /** Sync parcial - uma fase falhou */
    data class Partial(
        val downloadResult: SyncPhaseResult,
        val uploadResult: SyncPhaseResult
    ) : SyncResult()

    /** Sem rede - sync pulado */
    data object NoNetwork : SyncResult()

    /** Erro geral */
    data class Error(val message: String) : SyncResult()

    companion object {
        fun fromPhases(download: SyncPhaseResult, upload: SyncPhaseResult): SyncResult {
            return when {
                download is SyncPhaseResult.Success && upload is SyncPhaseResult.Success -> {
                    Success(
                        downloadedCount = download.count,
                        uploadedCount = upload.count
                    )
                }
                download is SyncPhaseResult.Skipped && upload is SyncPhaseResult.Skipped -> {
                    NoNetwork
                }
                else -> Partial(download, upload)
            }
        }
    }
}

/**
 * SyncPhaseResult - Resultado de uma fase do sync (download ou upload).
 */
sealed class SyncPhaseResult {
    /** Fase completada com sucesso */
    data class Success(val count: Int) : SyncPhaseResult()

    /** Fase pulada (sem rede, MQTT offline, etc) */
    data class Skipped(val reason: String) : SyncPhaseResult()

    /** Fase falhou */
    data class Failed(val error: String) : SyncPhaseResult()

    val isSuccess: Boolean get() = this is Success
    val isFailed: Boolean get() = this is Failed
}
