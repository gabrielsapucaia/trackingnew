# Script para recriar banco TimescaleDB do zero
# ATENÇÃO: Isso apagará TODOS os dados existentes!

param(
    [switch]$SkipBackup = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================="
Write-Host "Recriar Banco TimescaleDB"
Write-Host "=========================================="
Write-Host ""

# 1. Backup opcional
if (-not $SkipBackup) {
    Write-Host "1. Fazendo backup..." -ForegroundColor Yellow
    $backupFile = "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"
    docker compose exec timescaledb pg_dump -U aura auratracking > $backupFile
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   Backup salvo em: $backupFile" -ForegroundColor Green
    } else {
        Write-Host "   Erro ao fazer backup, continuando mesmo assim..." -ForegroundColor Yellow
    }
} else {
    Write-Host "1. Pulando backup (--SkipBackup)" -ForegroundColor Yellow
}

# 2. Parar serviços dependentes
Write-Host "2. Parando serviços..." -ForegroundColor Yellow
docker compose stop ingest
docker compose stop timescaledb

# 3. Remover container
Write-Host "3. Removendo container..." -ForegroundColor Yellow
docker compose rm -f timescaledb

# 4. Remover volume
Write-Host "4. Removendo volume do banco..." -ForegroundColor Yellow
$volumeName = (docker volume ls --format "{{.Name}}" | Select-String "timescale_data" | Select-Object -First 1)
if ($volumeName) {
    docker volume rm $volumeName
    Write-Host "   Volume removido: $volumeName" -ForegroundColor Green
} else {
    Write-Host "   Volume não encontrado (pode já ter sido removido)" -ForegroundColor Yellow
}

# 5. Recriar container
Write-Host "5. Recriando container..." -ForegroundColor Yellow
docker compose up -d timescaledb

# 6. Aguardar inicialização
Write-Host "6. Aguardando inicialização do banco..." -ForegroundColor Yellow
$maxWait = 90
$waited = 0
$healthy = $false
while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 3
    $waited += 3
    $status = docker compose ps timescaledb --format json 2>$null | ConvertFrom-Json
    if ($status -and $status.Health -eq "healthy") {
        $healthy = $true
        Write-Host "   Banco inicializado e saudável!" -ForegroundColor Green
        break
    }
    Write-Host "   Aguardando... ($waited/$maxWait segundos)" -ForegroundColor Gray
}

if (-not $healthy) {
    Write-Host "   AVISO: Banco pode não estar totalmente inicializado" -ForegroundColor Yellow
}

# 7. Validar schema
Write-Host "7. Validando schema..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
docker compose exec timescaledb psql -U aura -d auratracking -c "
SELECT 
    COUNT(*) as total_columns,
    COUNT(CASE WHEN column_name LIKE 'wifi_%' THEN 1 END) as wifi_columns,
    COUNT(CASE WHEN column_name LIKE 'cellular_%' THEN 1 END) as cellular_columns,
    COUNT(CASE WHEN column_name LIKE 'battery_%' THEN 1 END) as battery_columns,
    COUNT(CASE WHEN column_name LIKE 'motion_%' THEN 1 END) as motion_columns
FROM information_schema.columns 
WHERE table_name = 'telemetry';
"

# 8. Verificar ordem das colunas (primeiras 15)
Write-Host "8. Verificando ordem das colunas..." -ForegroundColor Yellow
docker compose exec timescaledb psql -U aura -d auratracking -c "
SELECT column_name, ordinal_position 
FROM information_schema.columns 
WHERE table_name = 'telemetry' 
ORDER BY ordinal_position 
LIMIT 15;
"

# 9. Reiniciar ingest
Write-Host "9. Reiniciando serviço de ingest..." -ForegroundColor Yellow
docker compose up -d ingest
Start-Sleep -Seconds 10

# 10. Verificar logs e saúde
Write-Host "10. Verificando saúde dos serviços..." -ForegroundColor Yellow
docker compose ps

Write-Host ""
Write-Host "=========================================="
Write-Host "Recriação concluída!" -ForegroundColor Green
Write-Host "=========================================="
Write-Host ""
Write-Host "Próximos passos:"
Write-Host "1. Verificar logs: docker compose logs -f ingest"
Write-Host "2. Verificar dados: docker compose exec timescaledb psql -U aura -d auratracking -c 'SELECT COUNT(*) FROM telemetry;'"
Write-Host "3. Verificar stats: curl http://localhost:8080/stats"



