# Dashboard AuraTracking - Streamlit

Dashboard consolidado para visualização de dados de telemetria do AuraTracking.

## 📋 Pré-requisitos

- Python 3.8 ou superior
- Acesso ao banco de dados PostgreSQL (10.135.22.3:5432)

## 🚀 Instalação

### Opção 1: Usando ambiente virtual (Recomendado)

```powershell
# Criar ambiente virtual
python -m venv .venv

# Ativar ambiente virtual (Windows)
.\.venv\Scripts\Activate.ps1

# Instalar dependências
pip install -r requirements.txt
```

### Opção 2: Usando script PowerShell

```powershell
# Executar script de instalação
.\instalar_dependencias.ps1
```

### Opção 3: Instalação manual

```bash
pip install streamlit plotly pandas psycopg2-binary numpy
```

## ▶️ Executar o Dashboard

```bash
streamlit run dashboard_streamlit.py
```

O dashboard será aberto automaticamente no navegador em `http://localhost:8501`

## 📊 Funcionalidades

- **GPS/Localização**: Mapa interativo, velocidade, altitude, precisão GPS
- **Acelerômetro**: Séries temporais XYZ, visualização 3D, comparação bruto vs linear
- **Giroscópio**: Dados XYZ e magnitude
- **Bateria**: Nível, temperatura, voltagem, status
- **Redes**: WiFi RSSI, celular (RSRP, RSRQ, RSSNR)
- **Orientação**: Azimuth, pitch, roll, rotation vector
- **Movimento**: Detecção de movimento

## ⚙️ Configuração

As credenciais do banco de dados estão configuradas no arquivo `dashboard_streamlit.py`:

```python
host="10.135.22.3"
port=5432
dbname="auratracking"
user="aura"
password="aura2025"
```

Para alterar, edite a função `get_data()` no arquivo `dashboard_streamlit.py`.

## 📁 Estrutura de Arquivos

```
BackendTestes/
├── dashboard_streamlit.py    # Dashboard principal
├── requirements.txt          # Dependências Python
├── instalar_dependencias.ps1 # Script de instalação
└── README.md                 # Este arquivo
```

## 🔧 Troubleshooting

### Erro de conexão com banco
- Verifique se o banco está acessível na rede
- Confirme as credenciais no código

### Erro ao instalar dependências
- Certifique-se de estar usando Python 3.8+
- Tente atualizar o pip: `python -m pip install --upgrade pip`

### Porta 8501 já em uso
- O Streamlit tentará usar outra porta automaticamente
- Ou especifique outra porta: `streamlit run dashboard_streamlit.py --server.port 8502`

## 📝 Notas

- Os dados são cacheados por 60 segundos para melhor performance
- Use o botão "Atualizar Dados" na sidebar para forçar atualização
- O período padrão é de 3 horas, ajustável na sidebar

