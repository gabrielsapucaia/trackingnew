# Script para instalar dependências no ambiente virtual
# Execute: .\instalar_dependencias.ps1

Write-Host "Instalando dependencias no ambiente virtual..." -ForegroundColor Green

# Verificar se o ambiente virtual existe
if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host "Ambiente virtual encontrado!" -ForegroundColor Green
    .\.venv\Scripts\python.exe -m pip install dash plotly pandas psycopg2-binary
    Write-Host "`nDependencias instaladas com sucesso!" -ForegroundColor Green
} else {
    Write-Host "Ambiente virtual nao encontrado. Instalando no Python global..." -ForegroundColor Yellow
    python -m pip install dash plotly pandas psycopg2-binary
    Write-Host "`nDependencias instaladas no Python global!" -ForegroundColor Green
}

Write-Host "`nAgora voce pode executar: python dashboard_acelerometro_web.py" -ForegroundColor Cyan


