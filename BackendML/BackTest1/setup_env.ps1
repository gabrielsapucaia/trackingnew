# Script para criar e configurar ambiente virtual Python
# Execute: .\setup_env.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Configurando Ambiente Python" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar se Python está instalado
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python encontrado: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERRO: Python não encontrado!" -ForegroundColor Red
    Write-Host "Instale Python 3.8 ou superior de https://www.python.org/" -ForegroundColor Yellow
    exit 1
}

# Criar ambiente virtual se não existir
if (-not (Test-Path ".venv")) {
    Write-Host "Criando ambiente virtual..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "Ambiente virtual criado com sucesso!" -ForegroundColor Green
} else {
    Write-Host "Ambiente virtual já existe." -ForegroundColor Green
}

Write-Host ""
Write-Host "Ativando ambiente virtual..." -ForegroundColor Yellow

# Ativar ambiente virtual
if (Test-Path ".venv\Scripts\Activate.ps1") {
    .\.venv\Scripts\Activate.ps1
    Write-Host "Ambiente virtual ativado!" -ForegroundColor Green
} else {
    Write-Host "ERRO: Não foi possível ativar o ambiente virtual." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Atualizando pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet

Write-Host ""
Write-Host "Instalando dependências..." -ForegroundColor Yellow

# Verificar se requirements.txt existe
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt
    Write-Host ""
    Write-Host "Dependências instaladas com sucesso!" -ForegroundColor Green
} else {
    Write-Host "AVISO: requirements.txt não encontrado. Instalando dependências manualmente..." -ForegroundColor Yellow
    pip install streamlit plotly pandas psycopg2-binary numpy
    Write-Host ""
    Write-Host "Dependências instaladas com sucesso!" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Ambiente configurado com sucesso!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para executar o dashboard:" -ForegroundColor Yellow
Write-Host "  streamlit run dashboard_streamlit.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para ativar o ambiente virtual novamente:" -ForegroundColor Yellow
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host ""

