"""
Aplicação Streamlit para visualização de dados de telemetria.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date, time
import pytz

from database import init_database, get_db
from config import DB_CONFIG, POOL_CONFIG
from streamlit_config import APP_TITLE, SIDEBAR_TITLE, TIMESTAMP_COLUMN, TO_TIMEZONE, CACHE_DIR
from data_loader import (
    load_all_parquet_files,
    check_cache_up_to_date,
    update_cache_if_needed,
    convert_timezone,
    get_non_null_columns,
    filter_by_date_range,
    get_last_update_time
)

# Configurar página
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar banco de dados (apenas uma vez)
@st.cache_resource
def init_db():
    """Inicializa conexão com banco de dados."""
    init_database(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        dbname=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        min_conn=POOL_CONFIG["min_conn"],
        max_conn=POOL_CONFIG["max_conn"],
        cache_dir=CACHE_DIR
    )
    return get_db()

# Cache de dados carregados
@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_data():
    """Carrega dados do cache Parquet."""
    df = load_all_parquet_files(CACHE_DIR)
    if not df.empty:
        df = convert_timezone(df)
    return df

# Inicializar sessão state
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
if 'last_update_time' not in st.session_state:
    st.session_state.last_update_time = None
if 'force_refresh' not in st.session_state:
    st.session_state.force_refresh = False

# Inicializar banco
db = init_db()

# Sidebar
with st.sidebar:
    st.title(SIDEBAR_TITLE)
    
    # Botão de atualização (opcional - apenas se quiser atualizar do banco)
    if st.button("🔄 Atualizar Dados do Banco", width='stretch'):
        st.session_state.force_refresh = True
        with st.spinner("Atualizando dados do banco..."):
            try:
                from streamlit_config import TELEMETRY_QUERY
                update_cache_if_needed(db, TELEMETRY_QUERY, TIMESTAMP_COLUMN, force=True)
                st.session_state.data_loaded = False
                st.session_state.last_update_time = get_last_update_time()
                st.session_state.force_refresh = False
                st.success("Dados atualizados!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao atualizar: {e}")
                st.info("Usando dados do cache Parquet existente.")
    
    st.divider()
    
    # Informação sobre última atualização
    last_update = get_last_update_time()
    if last_update:
        st.info(f"**Última atualização:**\n{last_update.strftime('%d/%m/%Y %H:%M:%S')}")
    else:
        st.warning("Nenhum dado encontrado no cache")
    
    st.divider()
    
    # Filtros de data/hora
    st.subheader("Período")
    
    # Data/hora inicial
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Data Inicial",
            value=date.today(),
            key="start_date"
        )
    with col2:
        start_time = st.time_input(
            "Hora Inicial",
            value=time(0, 0),
            key="start_time"
        )
    
    # Data/hora final
    col3, col4 = st.columns(2)
    with col3:
        end_date = st.date_input(
            "Data Final",
            value=date.today(),
            key="end_date"
        )
    with col4:
        end_time = st.time_input(
            "Hora Final",
            value=time(23, 59),
            key="end_time"
        )
    
    # Combinar data e hora
    start_datetime = datetime.combine(start_date, start_time)
    end_datetime = datetime.combine(end_date, end_time)
    
    # Localizar com timezone
    tz = pytz.timezone(TO_TIMEZONE)
    start_datetime = tz.localize(start_datetime)
    end_datetime = tz.localize(end_datetime)

# Área principal
st.title(APP_TITLE)

# Carregar dados diretamente do cache Parquet (sem check de atualização)
# Os dados já estão no cache Parquet
if not st.session_state.data_loaded or st.session_state.force_refresh:
    st.session_state.data_loaded = True

# Carregar dados
df = load_data()

if df.empty:
    st.error("Nenhum dado encontrado no cache. Clique em 'Atualizar Dados' para carregar dados do banco.")
    st.stop()

# Detectar coluna de timestamp automaticamente se não estiver definida
timestamp_col = TIMESTAMP_COLUMN
if TIMESTAMP_COLUMN not in df.columns:
    # Tenta encontrar coluna de timestamp automaticamente
    timestamp_cols = [col for col in df.columns 
                     if any(keyword in col.lower() for keyword in ['timestamp', 'time', 'datetime', 'date'])]
    if timestamp_cols:
        timestamp_col = timestamp_cols[0]
        st.info(f"Usando coluna '{timestamp_col}' como timestamp")
    else:
        st.warning("Coluna de timestamp não encontrada. Mostrando todos os dados sem filtro de data.")
        df_filtered = df.copy()
        timestamp_col = None  # Marca que não há timestamp
else:
    # Filtrar por período
    try:
        df_filtered = filter_by_date_range(df, timestamp_col, start_datetime, end_datetime)
    except Exception as e:
        st.error(f"Erro ao filtrar por data: {e}")
        df_filtered = df.copy()

if df_filtered.empty:
    if timestamp_col:
        st.warning(f"Nenhum dado encontrado no período selecionado ({start_datetime.strftime('%d/%m/%Y %H:%M')} - {end_datetime.strftime('%d/%m/%Y %H:%M')})")
    else:
        st.warning("Nenhum dado encontrado no cache.")
    st.stop()

# Informações sobre dados carregados
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Registros", len(df_filtered))
with col2:
    if timestamp_col and timestamp_col in df_filtered.columns:
        try:
            min_time = df_filtered[timestamp_col].min()
            if hasattr(min_time, 'strftime'):
                st.metric("Início", min_time.strftime('%d/%m/%Y %H:%M'))
            else:
                st.metric("Início", str(min_time))
        except:
            st.metric("Início", "N/A")
    else:
        st.metric("Início", "N/A")
with col3:
    if timestamp_col and timestamp_col in df_filtered.columns:
        try:
            max_time = df_filtered[timestamp_col].max()
            if hasattr(max_time, 'strftime'):
                st.metric("Fim", max_time.strftime('%d/%m/%Y %H:%M'))
            else:
                st.metric("Fim", str(max_time))
        except:
            st.metric("Fim", "N/A")
    else:
        st.metric("Fim", "N/A")

st.divider()

# Detectar colunas disponíveis (não-null, excluindo timestamp)
available_columns = get_non_null_columns(df_filtered, exclude_cols=[timestamp_col])

if not available_columns:
    st.error("Nenhuma coluna de dados disponível para visualização.")
    st.stop()

# Multiselect para escolher variáveis
selected_variables = st.multiselect(
    "Selecione as variáveis para visualizar:",
    options=available_columns,
    default=available_columns[:min(3, len(available_columns))],  # Seleciona até 3 por padrão
    key="variables"
)

if not selected_variables:
    st.warning("Selecione pelo menos uma variável para visualizar.")
    st.stop()

# Criar gráfico com múltiplos eixos Y
st.subheader("Gráfico de Telemetria")

# Mostrar indicador de progresso enquanto cria o gráfico
with st.spinner("Gerando gráfico..."):
    # Plotly suporta até 2 eixos Y (1 principal + 1 secundário) por subplot
    # Para mais variáveis, vamos criar subplots verticais ou usar cores diferentes
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
    
    # Verificar se temos coluna de timestamp para usar no eixo X
    has_timestamp = timestamp_col and timestamp_col in df_filtered.columns
    
    # Preparar dados do eixo X uma vez
    x_data = df_filtered[timestamp_col] if has_timestamp else df_filtered.index
    
    if len(selected_variables) <= 2:
        # Para 1-2 variáveis: usar eixos Y separados
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Primeira variável no eixo Y principal
        fig.add_trace(
            go.Scatter(
                x=x_data,
                y=df_filtered[selected_variables[0]],
                name=selected_variables[0],
                mode='lines',
                line=dict(color=colors[0], width=2),
                hovertemplate=f'<b>{selected_variables[0]}</b><br>' +
                            ('Tempo: %{x}<br>' if has_timestamp else 'Index: %{x}<br>') +
                            'Valor: %{y}<extra></extra>'
            ),
            secondary_y=False
        )
        
        # Segunda variável no eixo Y secundário (se houver)
        if len(selected_variables) > 1:
            fig.add_trace(
                go.Scatter(
                    x=x_data,
                    y=df_filtered[selected_variables[1]],
                    name=selected_variables[1],
                    mode='lines',
                    line=dict(color=colors[1], width=2),
                    hovertemplate=f'<b>{selected_variables[1]}</b><br>' +
                                ('Tempo: %{x}<br>' if has_timestamp else 'Index: %{x}<br>') +
                                'Valor: %{y}<extra></extra>'
                ),
                secondary_y=True
            )
        
        # Configurar eixos
        fig.update_xaxes(title_text="Tempo" if has_timestamp else "Index")
        fig.update_yaxes(title_text=selected_variables[0], secondary_y=False)
        if len(selected_variables) > 1:
            fig.update_yaxes(title_text=selected_variables[1], secondary_y=True)
    
    elif len(selected_variables) <= 4:
        # Para 3-4 variáveis: criar subplots verticais (uma variável por linha)
        fig = make_subplots(
            rows=len(selected_variables),
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=selected_variables
        )
        
        for i, var in enumerate(selected_variables):
            fig.add_trace(
                go.Scatter(
                    x=x_data,
                    y=df_filtered[var],
                    name=var,
                    mode='lines',
                    line=dict(color=colors[i % len(colors)], width=2),
                    showlegend=False,
                    hovertemplate=f'<b>{var}</b><br>' +
                                ('Tempo: %{x}<br>' if has_timestamp else 'Index: %{x}<br>') +
                                'Valor: %{y}<extra></extra>'
                ),
                row=i+1,
                col=1
            )
            fig.update_yaxes(title_text=var, row=i+1, col=1)
        
        fig.update_xaxes(title_text="Tempo" if has_timestamp else "Index", row=len(selected_variables), col=1)
    
    else:
        # Para muitas variáveis: usar mesmo eixo Y com cores diferentes
        fig = go.Figure()
        
        for i, var in enumerate(selected_variables):
            fig.add_trace(
                go.Scatter(
                    x=x_data,
                    y=df_filtered[var],
                    name=var,
                    mode='lines',
                    line=dict(color=colors[i % len(colors)], width=2),
                    hovertemplate=f'<b>{var}</b><br>' +
                                ('Tempo: %{x}<br>' if has_timestamp else 'Index: %{x}<br>') +
                                'Valor: %{y}<extra></extra>'
                )
            )
        
        fig.update_xaxes(title_text="Tempo" if has_timestamp else "Index")
        fig.update_yaxes(title_text="Valor")
    
    # Configurações do layout
fig.update_layout(
    height=600,
    hovermode='x unified',
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    ),
    xaxis=dict(
        showspikes=True,
        spikecolor="orange",
        spikesnap="cursor",
        spikemode="across"
    )
)

# Mostrar gráfico
st.plotly_chart(fig, width='stretch')

# Botão de exportação CSV
st.divider()

# Preparar dados para exportação
if timestamp_col and timestamp_col in df_filtered.columns:
    export_cols = [timestamp_col] + selected_variables
else:
    export_cols = selected_variables
export_df = df_filtered[export_cols].copy()

# Converter timestamps para string para CSV
if timestamp_col and timestamp_col in export_df.columns:
    try:
        export_df[timestamp_col] = pd.to_datetime(export_df[timestamp_col])
        export_df[timestamp_col] = export_df[timestamp_col].dt.strftime('%Y-%m-%d %H:%M:%S%z')
    except:
        pass  # Se não conseguir converter, mantém como está

csv = export_df.to_csv(index=False).encode('utf-8-sig')

st.download_button(
    label="📥 Exportar Dados como CSV",
    data=csv,
    file_name=f"telemetria_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv",
    mime="text/csv",
    width='stretch'
)

