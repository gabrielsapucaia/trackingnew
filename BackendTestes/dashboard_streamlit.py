# Dashboard Streamlit com Plotly - Telemetria AuraTracking
# Execute: streamlit run dashboard_streamlit.py
# Acesse: http://localhost:8501

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, time
import pytz

# Configurar página para usar modo wide
st.set_page_config(
    page_title="Dashboard Telemetria AuraTracking",
    page_icon="📊",
    layout="wide",  # Modo wide para usar toda a largura da tela
    initial_sidebar_state="expanded"
)

# Configuração da página
st.set_page_config(
    page_title="AuraTracking - Dashboard de Telemetria",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configurações de conexão com banco
DB_CONFIG = {
    "host": "10.135.22.3",
    "port": 5432,
    "dbname": "auratracking",
    "user": "aura",
    "password": "aura2025",
    "connect_timeout": 5,
}

# Timezone de Brasília (UTC-3)
TIMEZONE_BR = pytz.timezone("America/Sao_Paulo")
TIMEZONE_UTC = pytz.UTC

# Categorias de variáveis para organização
VARIABLE_CATEGORIES = {
    "📍 GPS": [
        ("latitude", "Latitude"),
        ("longitude", "Longitude"),
        ("altitude", "Altitude (m)"),
        ("speed", "Velocidade (m/s)"),
        ("speed_kmh", "Velocidade (km/h)"),
        ("bearing", "Direção (graus)"),
        ("gps_accuracy", "Precisão GPS (m)"),
        ("satellites", "Satélites"),
        ("h_acc", "Precisão Horizontal (m)"),
        ("v_acc", "Precisão Vertical (m)"),
        ("s_acc", "Precisão Velocidade (m/s)"),
        ("hdop", "HDOP"),
        ("vdop", "VDOP"),
        ("pdop", "PDOP"),
    ],
    "📊 Acelerômetro": [
        ("accel_x", "Aceleração X (m/s²)"),
        ("accel_y", "Aceleração Y (m/s²)"),
        ("accel_z", "Aceleração Z (m/s²)"),
        ("accel_magnitude", "Aceleração Magnitude (m/s²)"),
        ("linear_accel_x", "Aceleração Linear X (m/s²)"),
        ("linear_accel_y", "Aceleração Linear Y (m/s²)"),
        ("linear_accel_z", "Aceleração Linear Z (m/s²)"),
        ("linear_accel_magnitude", "Aceleração Linear Magnitude (m/s²)"),
    ],
    "🔄 Giroscópio": [
        ("gyro_x", "Velocidade Angular X (rad/s)"),
        ("gyro_y", "Velocidade Angular Y (rad/s)"),
        ("gyro_z", "Velocidade Angular Z (rad/s)"),
        ("gyro_magnitude", "Velocidade Angular Magnitude (rad/s)"),
    ],
    "🧲 Magnetômetro": [
        ("mag_x", "Campo Magnético X (μT)"),
        ("mag_y", "Campo Magnético Y (μT)"),
        ("mag_z", "Campo Magnético Z (μT)"),
        ("mag_magnitude", "Campo Magnético Magnitude (μT)"),
    ],
    "⚖️ Gravidade": [
        ("gravity_x", "Gravidade X (m/s²)"),
        ("gravity_y", "Gravidade Y (m/s²)"),
        ("gravity_z", "Gravidade Z (m/s²)"),
    ],
    "🔄 Rotação": [
        ("rotation_vector_x", "Vetor Rotação X"),
        ("rotation_vector_y", "Vetor Rotação Y"),
        ("rotation_vector_z", "Vetor Rotação Z"),
        ("rotation_vector_w", "Vetor Rotação W"),
    ],
    "📐 Orientação": [
        ("azimuth", "Azimute (graus)"),
        ("pitch", "Pitch (graus)"),
        ("roll", "Roll (graus)"),
    ],
    "🔋 Bateria": [
        ("battery_level", "Nível (%)"),
        ("battery_temperature", "Temperatura (°C)"),
        ("battery_voltage", "Voltagem (V)"),
        ("battery_charge_counter", "Contador de Carga"),
        ("battery_full_capacity", "Capacidade Total"),
    ],
    "📶 WiFi": [
        ("wifi_rssi", "RSSI (dBm)"),
        ("wifi_frequency", "Frequência (MHz)"),
        ("wifi_channel", "Canal"),
    ],
    "📱 Celular": [
        ("cellular_rsrp", "RSRP (dBm)"),
        ("cellular_rsrq", "RSRQ (dB)"),
        ("cellular_rssnr", "RSSNR (dB)"),
        ("cellular_ci", "Cell ID"),
        ("cellular_pci", "PCI"),
        ("cellular_tac", "TAC"),
        ("cellular_earfcn", "EARFCN"),
        ("cellular_bandwidth", "Largura de Banda (MHz)"),
    ],
}


@st.cache_data
def get_data_range():
    """Obtém o range de datas disponíveis no banco."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT MIN(time), MAX(time) FROM telemetry;")
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result and result[0] and result[1]:
            min_time_utc, max_time_utc = result
            # Garantir que são timezone-aware
            if min_time_utc.tzinfo is None:
                min_time_utc = TIMEZONE_UTC.localize(min_time_utc)
            if max_time_utc.tzinfo is None:
                max_time_utc = TIMEZONE_UTC.localize(max_time_utc)
            
            min_time_br = min_time_utc.astimezone(TIMEZONE_BR)
            max_time_br = max_time_utc.astimezone(TIMEZONE_BR)
            return min_time_br, max_time_br
        return None, None
    except psycopg2.OperationalError as e:
        st.error(f"❌ Erro de conexão com banco de dados: {e}")
        return None, None
    except Exception as e:
        st.error(f"❌ Erro ao obter range de datas: {e}")
        return None, None


@st.cache_data(ttl=3600, show_spinner="Carregando dados do banco...")
def load_all_telemetry_data(start_datetime_br, end_datetime_br):
    """
    Carrega TODAS as colunas numéricas da tabela telemetry para o período especificado.
    Usa cache para evitar múltiplas consultas ao banco.
    
    Args:
        start_datetime_br: datetime em UTC-3 (Brasília)
        end_datetime_br: datetime em UTC-3 (Brasília)
    
    Returns:
        DataFrame com dados convertidos para UTC-3
    """
    try:
        # Validar que os datetimes têm timezone
        if start_datetime_br.tzinfo is None:
            start_datetime_br = TIMEZONE_BR.localize(start_datetime_br)
        if end_datetime_br.tzinfo is None:
            end_datetime_br = TIMEZONE_BR.localize(end_datetime_br)
        
        # Converter para UTC para consulta no banco
        start_utc = start_datetime_br.astimezone(TIMEZONE_UTC)
        end_utc = end_datetime_br.astimezone(TIMEZONE_UTC)
        
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Obter todas as colunas numéricas
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'telemetry'
            AND data_type IN ('integer', 'bigint', 'double precision', 'real', 'numeric')
            ORDER BY ordinal_position;
        """)
        numeric_cols = [row[0] for row in cur.fetchall()]
        
        # Adicionar coluna time
        cols_to_select = ['time'] + numeric_cols
        cols_str = ', '.join(cols_to_select)
        
        # Query para buscar dados
        query = f"""
            SELECT {cols_str}
            FROM telemetry
            WHERE time >= %s AND time <= %s
            ORDER BY time ASC;
        """
        
        cur.execute(query, (start_utc, end_utc))
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]
        
        df = pd.DataFrame(rows, columns=col_names)
        
        # Converter time para timezone BR
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'], utc=True)
            # Se já tem timezone, converter; se não, assumir UTC e depois converter
            if df['time'].dt.tz is None:
                df['time'] = df['time'].dt.tz_localize(TIMEZONE_UTC)
            df['time'] = df['time'].dt.tz_convert(TIMEZONE_BR)
        
        cur.close()
        conn.close()
        
        return df
        
    except psycopg2.OperationalError as e:
        error_msg = str(e)
        if "No route to host" in error_msg or "Connection refused" in error_msg:
            st.error(f"❌ Erro de conexão: Não foi possível conectar ao servidor {DB_CONFIG['host']}:{DB_CONFIG['port']}. Verifique se o servidor está acessível na rede.")
        else:
            st.error(f"❌ Erro de conexão com banco de dados: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados: {e}")
        import traceback
        st.code(traceback.format_exc())
        return pd.DataFrame()


def filter_dataframe_by_columns(df, columns):
    """Filtra DataFrame mantendo apenas as colunas especificadas."""
    available_cols = ['time'] + [col for col in columns if col in df.columns]
    
    if 'time' not in available_cols:
        return pd.DataFrame()
    
    return df[available_cols].copy()


def create_multi_axis_plot(df, variables_dict):
    """
    Cria gráfico Plotly com múltiplos eixos Y dinâmicos.
    CADA variável tem seu próprio eixo Y individual, posicionado de forma espaçada.
    Eixo X é único e compartilhado por todas as variáveis.
    
    Args:
        df: DataFrame com dados
        variables_dict: dicionário {nome_coluna: label} com variáveis a plotar
    
    Returns:
        Figura Plotly
    """
    if not variables_dict:
        fig = go.Figure()
        fig.add_annotation(
            text="Selecione pelo menos uma variável para visualizar",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    fig = go.Figure()
    
    # Paleta de cores para múltiplas variáveis
    colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
        '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
        '#c49c94', '#f7b6d3', '#c7c7c7', '#dbdb8d', '#9edae5'
    ]
    
    # Filtrar variáveis válidas (que existem no DataFrame)
    valid_vars = []
    for var_name, var_label in variables_dict.items():
        if var_name in df.columns:
            valid_vars.append((var_name, var_label))
    
    if not valid_vars:
        fig.add_annotation(
            text="Nenhuma variável válida encontrada nos dados",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    # Configuração dos eixos Y - cada variável terá seu próprio eixo
    yaxis_configs = {}
    num_vars = len(valid_vars)
    
    # Espaçamento fixo de 5% por eixo adicional para suportar até 10 variáveis sem sobreposição
    # Com 10 variáveis: 0.05 + (9 * 0.05) = 0.50 (50% de espaço)
    axis_spacing = 0.05
    
    # Domain do eixo X - calcula espaço necessário baseado no número de variáveis
    # Cada eixo adicional precisa de 5% de espaço à esquerda
    # Para 10 variáveis: 0.05 + (9 * 0.05) = 0.50 (50% de espaço)
    left_margin_needed = max(0.05, 0.05 + ((num_vars - 1) * axis_spacing))
    x_domain_start = min(0.50, left_margin_needed)  # Máximo de 50% para acomodar até 10 eixos
    x_domain_end = 0.95  # 5% de margem à direita
    
    # Criar eixo Y individual para CADA variável
    for idx, (var_name, var_label) in enumerate(valid_vars):
        color = colors[idx % len(colors)]
        
        if idx == 0:
            # Primeira variável - eixo principal 'y' (ancorado na borda esquerda do gráfico)
            yaxis_name = 'y'
            layout_key = 'yaxis'
            yaxis_configs[layout_key] = dict(
                title=dict(text=var_label, font=dict(color=color, size=11)),
                showgrid=True,
                gridcolor='rgba(128, 128, 128, 0.2)',
                tickfont=dict(color=color, size=9),
                side='left',
                uirevision='telemetry_chart'  # Preservar estado de zoom/pan
                # Sem anchor='free' - fica ancorado ao domain do eixo X
            )
        else:
            # Variáveis adicionais - cada uma com seu próprio eixo posicionado
            yaxis_name = f'y{idx + 1}'  # y2, y3, y4...
            layout_key = f'yaxis{idx + 1}'  # yaxis2, yaxis3, yaxis4...
            
            # Posição do eixo: cada eixo adicional fica mais à esquerda
            # O segundo eixo (idx=1) fica em position = x_domain_start - axis_spacing
            # O terceiro eixo (idx=2) fica em position = x_domain_start - 2*axis_spacing
            # Espaçamento de 5% garante separação adequada para até 10 variáveis
            axis_position = x_domain_start - (idx * axis_spacing)
            
            yaxis_configs[layout_key] = dict(
                title=dict(text=var_label, font=dict(color=color, size=11)),
                showgrid=False,  # Apenas o primeiro eixo mostra grid
                tickfont=dict(color=color, size=9),
                overlaying='y',  # Sobrepõe o eixo principal (compartilha área do gráfico)
                side='left',
                anchor='free',  # Posição livre (não ancorado ao eixo X)
                position=max(0.0, axis_position),  # Posição em % da largura
                uirevision='telemetry_chart'  # Preservar estado de zoom/pan
            )
        
        # Adicionar trace (linha) para esta variável
        fig.add_trace(
            go.Scatter(
                x=df['time'],
                y=df[var_name],
                name=var_label,
                mode='lines',
                line=dict(color=color, width=1.5),
                yaxis=yaxis_name,
                hovertemplate=f"<b>{var_label}</b><br>" +
                             "Data/Hora: %{x|%d/%m/%Y %H:%M:%S}<br>" +
                             "Valor: %{y:.4f}<extra></extra>"
            )
        )
    
    # Calcular margem esquerda baseada no número de eixos
    # Cada eixo adicional precisa de ~45px de espaço para suportar até 10 variáveis
    # Para 10 variáveis: 100 + (10 * 45) = 550px
    left_margin = 100 + (num_vars * 45)  # Base aumentada + espaço por eixo
    
    # Layout do gráfico
    layout_config = dict(
        title=dict(
            text=f"<b>Telemetria AuraTracking - {num_vars} Variável(is)</b>",
            font=dict(size=18)
        ),
        xaxis=dict(
            title="Data/Hora (UTC-3)",
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)',
            tickformat="%d/%m %H:%M",
            hoverformat="%d/%m/%Y %H:%M:%S",
            # Domain calculado dinamicamente para deixar espaço para os eixos Y
            domain=[x_domain_start, x_domain_end],
            uirevision='telemetry_chart'  # Preservar estado de zoom/pan no eixo X
        ),
        # Preservar estado de zoom/pan quando variáveis são adicionadas/removidas
        # Valor constante garante que o estado seja preservado mesmo com mudanças estruturais
        uirevision='telemetry_chart',
        hovermode='x unified',
        # Legenda interativa - posicionada embaixo do gráfico
        legend=dict(
            orientation='h',  # Horizontal para ficar embaixo
            yanchor='top',
            y=-0.15,  # Abaixo do gráfico (valor negativo)
            xanchor='center',
            x=0.5,  # Centralizada
            font=dict(size=10),
            bgcolor='rgba(30, 30, 30, 0.9)',
            bordercolor='rgba(100, 100, 100, 0.5)',
            borderwidth=1,
            itemclick='toggle',  # Clique simples para toggle
            itemdoubleclick='toggleothers',  # Duplo clique para isolar
            itemsizing='constant',
            tracegroupgap=10  # Espaçamento entre itens na legenda horizontal
        ),
        margin=dict(l=left_margin, r=50, t=100, b=120),  # Margem inferior aumentada para legenda
        height=600,
        autosize=True,  # Permite que o gráfico se ajuste automaticamente à largura disponível
        template='plotly_dark'  # Tema escuro para combinar com Streamlit dark mode
    )
    
    # Adicionar configurações dos eixos Y
    layout_config.update(yaxis_configs)
    
    fig.update_layout(**layout_config)
    
    return fig


def get_variable_options():
    """Retorna lista de opções de variáveis para o dropdown."""
    options = [("", "-- Selecione uma variável --")]
    
    for category, variables in VARIABLE_CATEGORIES.items():
        for col_name, col_label in variables:
            options.append((col_name, f"{category} {col_label}"))
    
    return options


def filter_variables_with_variation(df, variable_categories):
    """
    Filtra variáveis que têm dados válidos e variação (não são constantes ou null).
    
    Args:
        df: DataFrame com os dados
        variable_categories: Dicionário com categorias e variáveis
    
    Returns:
        Dicionário filtrado {categoria: [(col_name, col_label), ...]}
    """
    filtered_categories = {}
    
    for category, variables in variable_categories.items():
        filtered_vars = []
        for col_name, col_label in variables:
            if col_name not in df.columns:
                continue
            
            # Verificar se a coluna tem dados válidos e variação
            col_data = df[col_name].dropna()
            
            if len(col_data) == 0:
                # Sem dados válidos
                continue
            
            # Verificar se há variação (não é constante)
            if col_data.nunique() > 1:
                # Tem variação - incluir
                filtered_vars.append((col_name, col_label))
            # Se nunique == 1, é constante - não incluir
        
        if filtered_vars:
            filtered_categories[category] = filtered_vars
    
    return filtered_categories


def main():
    """Função principal do dashboard."""
    
    # Título
    st.title("📊 Dashboard de Telemetria - AuraTracking")
    st.markdown("---")
    
    # Obter range de datas disponíveis
    min_date, max_date = get_data_range()
    
    if not min_date or not max_date:
        st.error("❌ Não foi possível conectar ao banco de dados ou não há dados disponíveis.")
        return
    
    # Sidebar para configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        st.subheader("📅 Período de Consulta")
        st.caption(f"Dados disponíveis: {min_date.strftime('%d/%m/%Y %H:%M')} até {max_date.strftime('%d/%m/%Y %H:%M')}")
        
        # Seleção de data/hora início
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Data Início",
                value=min_date.date(),
                min_value=min_date.date(),
                max_value=max_date.date(),
                key='start_date'
            )
        with col2:
            start_time = st.time_input(
                "Hora Início",
                value=min_date.time(),
                key='start_time'
            )
        
        # Seleção de data/hora fim
        col3, col4 = st.columns(2)
        with col3:
            end_date = st.date_input(
                "Data Fim",
                value=max_date.date(),
                min_value=min_date.date(),
                max_value=max_date.date(),
                key='end_date'
            )
        with col4:
            end_time = st.time_input(
                "Hora Fim",
                value=max_date.time(),
                key='end_time'
            )
        
        # Combinar data e hora
        start_datetime_br = TIMEZONE_BR.localize(
            datetime.combine(start_date, start_time)
        )
        end_datetime_br = TIMEZONE_BR.localize(
            datetime.combine(end_date, end_time)
        )
        
        # Validar período
        if start_datetime_br >= end_datetime_br:
            st.error("⚠️ Data/hora de início deve ser anterior à data/hora de fim.")
            return
        
        # Validar que o período está dentro do range disponível
        # Arredondar para minutos para evitar problemas de precisão com microsegundos
        start_datetime_rounded = start_datetime_br.replace(second=0, microsecond=0)
        end_datetime_rounded = end_datetime_br.replace(second=0, microsecond=0)
        min_date_rounded = min_date.replace(second=0, microsecond=0)
        max_date_rounded = max_date.replace(second=0, microsecond=0)
        
        if start_datetime_rounded < min_date_rounded:
            st.error(f"⚠️ Data/hora de início ({start_datetime_br.strftime('%d/%m/%Y %H:%M')}) é anterior à data mínima disponível ({min_date.strftime('%d/%m/%Y %H:%M')}).")
            return
        
        if end_datetime_rounded > max_date_rounded:
            st.error(f"⚠️ Data/hora de fim ({end_datetime_br.strftime('%d/%m/%Y %H:%M')}) é posterior à data máxima disponível ({max_date.strftime('%d/%m/%Y %H:%M')}).")
            return
        
        st.markdown("---")
        
        st.subheader("📊 Variáveis")
        st.caption("Selecione as variáveis para comparar em eixos Y separados")
        
        # Verificar se há dados carregados para filtrar variáveis
        df_for_filtering = None
        
        # Tentar obter dados do cache atual primeiro
        cache_key_for_filter = f"df_{start_datetime_br}_{end_datetime_br}"
        if cache_key_for_filter in st.session_state:
            df_for_filtering = st.session_state[cache_key_for_filter]
        # Se não encontrou, tentar usar dados já carregados
        elif st.session_state.get('df_full') is not None:
            df_for_filtering = st.session_state['df_full']
        # Se ainda não encontrou, tentar qualquer cache disponível (para pré-filtro)
        else:
            cache_keys = [key for key in st.session_state.keys() if key.startswith('df_')]
            if cache_keys:
                # Usar o primeiro cache disponível para pré-filtrar variáveis
                df_for_filtering = st.session_state[cache_keys[0]]
        
        # Filtrar variáveis que têm variação
        if df_for_filtering is not None and not df_for_filtering.empty:
            filtered_categories = filter_variables_with_variation(df_for_filtering, VARIABLE_CATEGORIES)
            if filtered_categories:
                st.caption(f"💡 Mostrando apenas variáveis com dados válidos e variação ({sum(len(v) for v in filtered_categories.values())} variáveis)")
            else:
                filtered_categories = VARIABLE_CATEGORIES
                st.caption("⚠️ Nenhuma variável com variação encontrada. Mostrando todas.")
        else:
            # Se não há dados carregados, mostrar todas as variáveis
            filtered_categories = VARIABLE_CATEGORIES
            st.caption("💡 Selecione o período e carregue os dados para filtrar variáveis automaticamente")
        
        # Inicializar selected_vars no session_state se não existir
        if 'selected_vars' not in st.session_state:
            st.session_state['selected_vars'] = {}
        
        # Criar checkboxes organizados por categoria
        selected_vars = {}
        
        # Usar expander para cada categoria para melhor organização
        for category, variables in filtered_categories.items():
            with st.expander(f"{category} ({len(variables)} variáveis)", expanded=True):
                # Criar checkboxes para cada variável nesta categoria
                for col_name, col_label in variables:
                    checkbox_key = f"var_checkbox_{col_name}"
                    full_label = f"{col_label}"
                    
                    # Verificar se já estava selecionado
                    is_checked = col_name in st.session_state.get('selected_vars', {})
                    
                    if st.checkbox(
                        full_label,
                        value=is_checked,
                        key=checkbox_key
                    ):
                        selected_vars[col_name] = f"{category} {col_label}"
        
        # Salvar variáveis selecionadas em session_state
        st.session_state['selected_vars'] = selected_vars
        
        st.markdown("---")
        
        # Botão para carregar dados
        if st.button("📥 Carregar Dados do Banco", type="primary", use_container_width=True):
            # Validar que variáveis foram selecionadas antes de carregar
            if not selected_vars:
                st.error("⚠️ Selecione pelo menos uma variável antes de carregar dados.")
            else:
                st.session_state['load_data'] = True
                st.session_state['start_datetime'] = start_datetime_br
                st.session_state['end_datetime'] = end_datetime_br
                st.session_state['selected_vars'] = selected_vars
        
        # Botão para limpar cache
        if st.button("🗑️ Limpar Cache", use_container_width=True):
            st.cache_data.clear()
            # Limpar também cache do session_state
            keys_to_remove = [key for key in st.session_state.keys() if key.startswith('df_')]
            for key in keys_to_remove:
                del st.session_state[key]
            if 'df_full' in st.session_state:
                del st.session_state['df_full']
            if 'last_cache_key' in st.session_state:
                del st.session_state['last_cache_key']
            st.success("✅ Cache limpo com sucesso!")
            st.rerun()
        
        # Mostrar informações sobre cache
        cache_keys = [key for key in st.session_state.keys() if key.startswith('df_')]
        if cache_keys:
            st.caption(f"💾 Cache ativo: {len(cache_keys)} período(s) em memória")
    
    # Verificar se deve carregar dados
    if not st.session_state.get('load_data', False):
        st.info("👈 Selecione as variáveis e clique em 'Carregar Dados do Banco' para visualizar o gráfico.")
        return
    
    # Obter variáveis selecionadas do session_state
    selected_vars = st.session_state.get('selected_vars', {})
    
    # Validar que variáveis foram selecionadas
    if not selected_vars:
        st.warning("⚠️ Selecione pelo menos uma variável para visualizar.")
        return
    
    # Carregar dados do cache ou banco
    start_dt = st.session_state.get('start_datetime')
    end_dt = st.session_state.get('end_datetime')
    
    # Validar que as datas foram definidas
    if start_dt is None or end_dt is None:
        st.error("⚠️ Erro: Período de datas não foi definido. Por favor, selecione o período novamente.")
        return
    
    # Validar período antes de consultar banco
    if start_dt >= end_dt:
        st.error("⚠️ Data/hora de início deve ser anterior à data/hora de fim.")
        return
    
    # Verificar se os dados já estão em cache no session_state
    cache_key = f"df_{start_dt}_{end_dt}"
    if cache_key in st.session_state:
        df_full = st.session_state[cache_key]
        st.info(f"✅ Dados carregados do cache ({len(df_full):,} registros)")
    else:
        try:
            with st.spinner("Carregando dados do banco de dados..."):
                df_full = load_all_telemetry_data(start_dt, end_dt)
                # Armazenar no session_state para acesso rápido
                st.session_state[cache_key] = df_full
                st.success(f"✅ Dados carregados do banco ({len(df_full):,} registros)")
        except Exception as e:
            st.error(f"❌ Erro ao carregar dados do banco: {e}")
            return
    
    if df_full.empty:
        st.warning("⚠️ Nenhum dado encontrado para o período selecionado.")
        return
    
    try:
        df = filter_dataframe_by_columns(df_full, selected_vars.keys())
    except Exception as e:
        st.error(f"❌ Erro ao filtrar dados: {e}")
        return
    
    if df.empty or len(df) == 0:
        st.warning("⚠️ Nenhum dado disponível para as variáveis selecionadas.")
        return
    
    # Validar que a coluna 'time' existe
    if 'time' not in df.columns:
        st.error("❌ Erro: Coluna 'time' não encontrada nos dados.")
        return
    
    # Armazenar variáveis selecionadas e dados completos
    st.session_state['selected_vars'] = selected_vars
    st.session_state['df_full'] = df_full  # Armazenar dados completos para cache metric
    st.session_state['last_cache_key'] = cache_key  # Armazenar chave do cache atual
    
    # Informações sobre os dados
    try:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📊 Registros Exibidos", f"{len(df):,}")
        with col2:
            time_min = df['time'].min()
            time_max = df['time'].max()
            st.metric("📅 Período", f"{time_min.strftime('%d/%m %H:%M')} - {time_max.strftime('%d/%m %H:%M')}")
        with col3:
            duration = time_max - time_min
            hours = duration.total_seconds() / 3600
            st.metric("⏱️ Duração", f"{hours:.1f} horas")
        with col4:
            total_cached = len(df_full)
            st.metric("💾 Cache Total", f"{total_cached:,} registros")
    except Exception as e:
        st.warning(f"⚠️ Erro ao exibir métricas: {e}")
    
    # Mostrar variáveis selecionadas
    st.info(f"📈 Visualizando {len(selected_vars)} variável(is): {', '.join(selected_vars.values())}")
    
    # Criar e exibir gráfico com múltiplos eixos Y
    try:
        fig = create_multi_axis_plot(df, selected_vars)
    except Exception as e:
        st.error(f"❌ Erro ao criar gráfico: {e}")
        import traceback
        st.code(traceback.format_exc())
        return
    
    # Configuração do Plotly para interatividade completa
    plotly_config = {
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        'scrollZoom': True,  # Permite zoom com scroll
        'doubleClick': 'reset',  # Duplo clique reseta o zoom
    }
    
    st.plotly_chart(
        fig, 
        use_container_width=True,
        config=plotly_config,
        key='main_telemetry_chart'  # Chave fixa para manter identidade do gráfico
    )
    
    # Estatísticas para todas as variáveis
    st.markdown("### 📊 Estatísticas")
    
    try:
        # Criar colunas dinamicamente (máximo 3 por linha)
        num_vars = len(selected_vars)
        num_cols = min(num_vars, 3) if num_vars > 0 else 1
        
        cols = None
        for idx, (var_name, var_label) in enumerate(selected_vars.items()):
            if var_name not in df.columns:
                continue
            
            col_idx = idx % num_cols
            if col_idx == 0:
                cols = st.columns(num_cols)
            
            if cols:
                with cols[col_idx]:
                    st.markdown(f"#### {var_label}")
                    var_data = df[var_name].dropna()
                    
                    if len(var_data) > 0:
                        try:
                            col_stat1, col_stat2 = st.columns(2)
                            with col_stat1:
                                st.metric("Mínimo", f"{var_data.min():.4f}")
                                st.metric("Média", f"{var_data.mean():.4f}")
                            with col_stat2:
                                st.metric("Máximo", f"{var_data.max():.4f}")
                                st.metric("Desvio Padrão", f"{var_data.std():.4f}")
                        except Exception as e:
                            st.warning(f"Erro ao calcular estatísticas: {e}")
                    else:
                        st.warning("Sem dados válidos")
    except Exception as e:
        st.warning(f"⚠️ Erro ao exibir estatísticas: {e}")
    
    # Botão para exportar dados
    st.markdown("---")
    try:
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"telemetry_{start_dt.strftime('%Y%m%d_%H%M%S')}_to_{end_dt.strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.error(f"❌ Erro ao gerar CSV: {e}")


if __name__ == "__main__":
    main()
