# Dashboard Streamlit Consolidado - AuraTracking
# Para executar: streamlit run dashboard_streamlit.py
# Consolida todas as funcionalidades dos dashboards anteriores em um único arquivo

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import numpy as np

# Configuração da página Streamlit
st.set_page_config(
    page_title="Dashboard AuraTracking",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Função para conectar ao banco e obter dados
@st.cache_data(ttl=60, show_spinner=False)  # Cache por 60 segundos
def get_data(start_time=None, end_time=None, hours_back=None, device_id=None):
    """
    Conecta ao banco PostgreSQL e retorna dados de telemetria.
    
    Args:
        start_time: Data/hora inicial (datetime ou timestamp)
        end_time: Data/hora final (datetime ou timestamp)
        hours_back: Número de horas para buscar dados (fallback se start_time/end_time não fornecidos)
        device_id: ID do dispositivo para filtrar (None = todos)
    
    Returns:
        DataFrame com dados de telemetria
    """
    try:
        # Converter timestamps para datetime se necessário
        if start_time is not None and not isinstance(start_time, datetime):
            if isinstance(start_time, (int, float)):
                start_time = datetime.fromtimestamp(start_time)
            elif isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
        
        if end_time is not None and not isinstance(end_time, datetime):
            if isinstance(end_time, (int, float)):
                end_time = datetime.fromtimestamp(end_time)
            elif isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time)
        
        conn = psycopg2.connect(
            host="10.135.22.3",
            port=5432,
            dbname="auratracking",
            user="aura",
            password="aura2025",
            connect_timeout=5,
        )
        cur = conn.cursor()

        # Obter todas as colunas da tabela
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'telemetry'
            ORDER BY ordinal_position;
        """)
        colunas = cur.fetchall()
        colunas_nomes = [col[0] for col in colunas]
        colunas_select = ', '.join(colunas_nomes)

        # Construir query com filtros
        if start_time is not None and end_time is not None:
            query = f"SELECT {colunas_select} FROM telemetry WHERE time >= %s AND time <= %s"
            params = [start_time, end_time]
        elif hours_back is not None:
            hora_atras = datetime.now() - timedelta(hours=hours_back)
            query = f"SELECT {colunas_select} FROM telemetry WHERE time >= %s"
            params = [hora_atras]
        else:
            # Fallback padrão: últimas 3 horas
            hora_atras = datetime.now() - timedelta(hours=3)
            query = f"SELECT {colunas_select} FROM telemetry WHERE time >= %s"
            params = [hora_atras]
        
        if device_id:
            query += " AND device_id = %s"
            params.append(device_id)
        
        query += " ORDER BY time ASC;"

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        cols = [c.name for c in cur.description]

        df = pd.DataFrame(rows, columns=cols)
        df['time'] = pd.to_datetime(df['time'])
        
        # Ordenar por tempo
        df = df.sort_values('time').reset_index(drop=True)

        cur.close()
        conn.close()
        
        return df
    
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return pd.DataFrame()

# Função para consultar TODO o banco de dados com cache
@st.cache_data(ttl=300, show_spinner=True)  # Cache por 5 minutos (300 segundos)
def get_all_data():
    """
    Conecta ao banco PostgreSQL e retorna TODOS os dados de telemetria.
    Os dados ficam em cache para melhor performance.
    
    Returns:
        DataFrame com todos os dados de telemetria do banco
    """
    try:
        conn = psycopg2.connect(
            host="10.135.22.3",
            port=5432,
            dbname="auratracking",
            user="aura",
            password="aura2025",
            connect_timeout=10,
        )
        cur = conn.cursor()

        # Obter todas as colunas da tabela telemetry
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'telemetry'
            ORDER BY ordinal_position;
        """)
        colunas = cur.fetchall()
        colunas_nomes = [col[0] for col in colunas]
        colunas_select = ', '.join(colunas_nomes)

        # Consultar TODOS os dados sem filtros
        query = f"SELECT {colunas_select} FROM telemetry ORDER BY time ASC;"
        
        cur.execute(query)
        rows = cur.fetchall()
        cols = [c.name for c in cur.description]

        df = pd.DataFrame(rows, columns=cols)
        df['time'] = pd.to_datetime(df['time'])
        
        # Ordenar por tempo
        df = df.sort_values('time').reset_index(drop=True)

        cur.close()
        conn.close()
        
        return df
    
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return pd.DataFrame()

# Função auxiliar para criar gráfico vazio
def empty_figure(title="Sem dados"):
    fig = go.Figure()
    fig.add_annotation(
        text="Nenhum dado disponível",
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=16)
    )
    fig.update_layout(title=title, height=400)
    return fig

# Função para filtrar dados por dispositivo
def filter_by_device(df, device_id):
    if device_id and device_id != "Todos":
        return df[df['device_id'] == device_id].copy()
    return df.copy()

# Função auxiliar para organizar variáveis por categoria
def get_variables_by_category():
    """
    Retorna dicionário com variáveis organizadas por categoria.
    """
    return {
        'GPS': ['speed_kmh', 'altitude', 'gps_accuracy', 'satellites', 'bearing'],
        'Acelerômetro': [
            'accel_x', 'accel_y', 'accel_z', 'accel_magnitude',
            'linear_accel_x', 'linear_accel_y', 'linear_accel_z', 'linear_accel_magnitude'
        ],
        'Giroscópio': ['gyro_x', 'gyro_y', 'gyro_z', 'gyro_magnitude'],
        'Bateria': ['battery_level', 'battery_temperature', 'battery_voltage', 'battery_status', 'battery_health'],
        'Redes': ['wifi_rssi', 'cellular_rsrp', 'cellular_rsrq', 'cellular_rssnr', 'cellular_network_type'],
        'Orientação': [
            'azimuth', 'pitch', 'roll',
            'rotation_vector_x', 'rotation_vector_y', 'rotation_vector_z', 'rotation_vector_w'
        ],
        'Movimento': [
            'motion_significant_motion', 'motion_stationary_detect', 'motion_motion_detect',
            'motion_flat_up', 'motion_flat_down', 'motion_stowed', 'motion_display_rotate'
        ]
    }

# Função para renderizar gráfico customizado
def render_custom_chart(df, selected_vars, secondary_y_var=None):
    """
    Cria gráfico único com variáveis selecionadas, cada uma em seu próprio eixo Y.
    
    Args:
        df: DataFrame com dados filtrados
        selected_vars: Lista de variáveis selecionadas para exibir
        secondary_y_var: Não utilizado mais (mantido para compatibilidade)
    """
    if not selected_vars:
        st.info("Selecione pelo menos uma variável no sidebar para visualizar o gráfico.")
        return
    
    # Filtrar variáveis que existem no DataFrame e têm dados
    available_vars = []
    for var in selected_vars:
        if var in df.columns and not df[var].isna().all():
            available_vars.append(var)
    
    if not available_vars:
        st.warning("Nenhuma das variáveis selecionadas está disponível nos dados.")
        return
    
    # Criar figura base
    fig = go.Figure()
    
    # Cores para as variáveis
    colors = px.colors.qualitative.Set3 + px.colors.qualitative.Pastel + px.colors.qualitative.Dark2
    
    # Adicionar cada variável em seu próprio eixo Y
    for i, var in enumerate(available_vars):
        color = colors[i % len(colors)]
        
        if i == 0:
            # Primeira variável no eixo Y primário
            fig.add_trace(
                go.Scatter(
                    x=df['time'],
                    y=df[var],
                    name=var,
                    mode='lines',
                    line=dict(color=color, width=2),
                    yaxis='y'
                )
            )
        else:
            # Demais variáveis em eixos Y secundários (y2, y3, y4, etc.)
            yaxis_ref = f'y{i+1}'
            
            fig.add_trace(
                go.Scatter(
                    x=df['time'],
                    y=df[var],
                    name=var,
                    mode='lines',
                    line=dict(color=color, width=2),
                    yaxis=yaxis_ref
                )
            )
    
    # Configurar layout com múltiplos eixos Y
    layout_dict = {
        'title': "Gráfico Personalizado - Múltiplas Variáveis",
        'height': 600,
        'hovermode': 'x unified',
        'showlegend': True,
        'legend': dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
        'xaxis': dict(title="Tempo", tickformat='%Y-%m-%d %H:%M:%S', tickangle=45),
        'yaxis': dict(title=available_vars[0] if available_vars else "Valor", side='left')
    }
    
    # Adicionar configurações para cada eixo Y secundário
    for i in range(1, len(available_vars)):
        yaxis_key = f'yaxis{i+1}'
        # Posicionar eixos à direita, espaçados (começando em 1.0 e diminuindo)
        position = 1.0 - (i - 1) * 0.12 if i > 1 else 1.0
        
        layout_dict[yaxis_key] = dict(
            title=available_vars[i],
            overlaying='y',
            side='right',
            position=position
        )
    
    fig.update_layout(**layout_dict)
    
    st.plotly_chart(fig, use_container_width=True)

# ========== MAIN APP ==========
def main():
    st.title("📊 Dashboard de Telemetria - AuraTracking")
    st.markdown("---")
    
    # Sidebar com controles
    with st.sidebar:
        st.header("⚙️ Controles")
        
        # Seleção de período - Data e Hora
        st.subheader("📅 Período")
        col_date1, col_date2 = st.columns(2)
        
        with col_date1:
            date_start = st.date_input(
                "Data Inicial",
                value=datetime.now().date() - timedelta(days=1),
                help="Data inicial para buscar dados"
            )
        
        with col_date2:
            date_end = st.date_input(
                "Data Final",
                value=datetime.now().date(),
                help="Data final para buscar dados"
            )
        
        col_time1, col_time2 = st.columns(2)
        
        with col_time1:
            time_start = st.time_input(
                "Hora Inicial",
                value=datetime.now().time().replace(hour=0, minute=0, second=0),
                help="Hora inicial"
            )
        
        with col_time2:
            time_end = st.time_input(
                "Hora Final",
                value=datetime.now().time(),
                help="Hora final"
            )
        
        # Combinar data e hora
        start_datetime = datetime.combine(date_start, time_start)
        end_datetime = datetime.combine(date_end, time_end)
        
        # Validar período
        if start_datetime >= end_datetime:
            st.error("⚠️ Data/hora inicial deve ser anterior à data/hora final!")
            st.stop()
        
        # Botão para atualizar dados
        if st.button("🔄 Atualizar Dados", type="primary"):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        
        # Carregar dados
        with st.spinner("Carregando dados..."):
            # Converter datetime para string ISO para compatibilidade com cache
            start_str = start_datetime.isoformat() if start_datetime else None
            end_str = end_datetime.isoformat() if end_datetime else None
            df = get_data(start_time=start_str, end_time=end_str)
        
        if df.empty:
            st.error("Nenhum dado encontrado. Verifique a conexão com o banco.")
            return
        
        # Seleção de dispositivo
        devices = ["Todos"] + sorted(df['device_id'].unique().tolist())
        selected_device = st.selectbox(
            "Dispositivo",
            devices,
            index=0
        )
        
        # Filtrar por dispositivo
        df_filtered = filter_by_device(df, selected_device)
        
        st.markdown("---")
        
        # Seleção de variáveis para gráfico personalizado
        st.subheader("📊 Variáveis")
        
        # Obter variáveis por categoria
        vars_by_category = get_variables_by_category()
        
        # Obter todas as colunas do DataFrame (exceto colunas de controle)
        all_columns = [col for col in df_filtered.columns if col not in ['time', 'device_id', 'latitude', 'longitude']]
        
        # Filtrar variáveis disponíveis no DataFrame
        # Excluir apenas variáveis que são completamente null OU têm apenas um valor único
        def is_valid_variable(col):
            if col not in df_filtered.columns:
                return False
            # Verificar se não é completamente null
            if df_filtered[col].isna().all():
                return False
            # Verificar se tem mais de um valor único (excluindo NaN)
            non_null_values = df_filtered[col].dropna()
            if len(non_null_values) == 0:
                return False
            if non_null_values.nunique() <= 1:
                return False
            return True
        
        available_vars_dict = {}
        categorized_vars = set()
        
        # Adicionar variáveis categorizadas
        for category, vars_list in vars_by_category.items():
            available_vars = [v for v in vars_list if is_valid_variable(v)]
            if available_vars:
                available_vars_dict[category] = available_vars
                categorized_vars.update(available_vars)
        
        # Adicionar variáveis não categorizadas em "Outras"
        other_vars = [v for v in all_columns if v not in categorized_vars and is_valid_variable(v)]
        if other_vars:
            available_vars_dict['Outras'] = sorted(other_vars)
        
        # Criar checkboxes por categoria sempre visíveis
        selected_variables = []
        for category, vars_list in available_vars_dict.items():
            st.markdown(f"**{category}**")
            for var in vars_list:
                checkbox_value = st.checkbox(var, key=f"var_{var}", value=False)
                if checkbox_value:
                    selected_variables.append(var)
    
    # Verificar se há dados
    if df_filtered.empty:
        st.warning("Nenhum dado disponível para os filtros selecionados.")
        return
    
    # Mostrar gráfico personalizado diretamente na página principal
    # Cada variável terá seu próprio eixo Y automaticamente
    render_custom_chart(df_filtered, selected_variables)

if __name__ == "__main__":
    main()

