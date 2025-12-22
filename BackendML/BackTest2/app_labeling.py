"""
Aplicação Streamlit para rotulagem interativa de períodos de carregamento.
"""
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Backend não-interativo para Streamlit
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os
from pathlib import Path

# Configurar página
st.set_page_config(
    page_title="Rotulagem de Carregamento",
    page_icon="🏷️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Caminhos dos arquivos
DATA_FILE = 'amostra/telemetria_20251212_20251213.csv'
PERIODS_FILE = 'amostra/periodos_vibracao_detalhado.csv'
LABELS_FILE = 'amostra/rotulos_carregamento.csv'

# Inicializar estado da sessão
if 'periods_df' not in st.session_state:
    st.session_state.periods_df = None
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'labels_df' not in st.session_state:
    st.session_state.labels_df = None
if 'uncataloged_periods' not in st.session_state:
    st.session_state.uncataloged_periods = None

@st.cache_data
def load_telemetry_data():
    """Carrega dados de telemetria."""
    df = pd.read_csv(DATA_FILE)
    df['time'] = pd.to_datetime(df['time'])
    df['speed_kmh'] = df['speed_kmh'].astype(float)
    df['linear_accel_magnitude'] = df['linear_accel_magnitude'].astype(float)
    return df

def load_existing_labels():
    """Carrega rótulos existentes."""
    if os.path.exists(LABELS_FILE):
        return pd.read_csv(LABELS_FILE)
    return pd.DataFrame(columns=['period_id', 'start_time', 'end_time', 'duration_minutes', 'label', 'labeled_at'])

def save_label(period_id, start_time, end_time, duration_minutes, label):
    """Salva um rótulo no CSV."""
    labels_df = load_existing_labels()
    
    # Converter para datetime se necessário
    if isinstance(start_time, str):
        start_time = pd.to_datetime(start_time)
    if isinstance(end_time, str):
        end_time = pd.to_datetime(end_time)
    
    # Criar novo registro
    new_label = pd.DataFrame({
        'period_id': [period_id],
        'start_time': [start_time],
        'end_time': [end_time],
        'duration_minutes': [duration_minutes],
        'label': [label],
        'labeled_at': [datetime.now()]
    })
    
    # Remover rótulo existente para este período se houver
    labels_df = labels_df[labels_df['period_id'] != period_id]
    
    # Adicionar novo rótulo
    labels_df = pd.concat([labels_df, new_label], ignore_index=True)
    
    # Salvar
    labels_df.to_csv(LABELS_FILE, index=False)
    return labels_df

def detect_stop_periods(df, min_duration_minutes=1.0, max_speed=1.0):
    """Detecta períodos de parada >= min_duration_minutes com velocidade < max_speed."""
    periods = []
    start_idx = None
    
    for i in range(len(df)):
        speed = df.iloc[i]['speed_kmh']
        
        if speed < max_speed:
            if start_idx is None:
                start_idx = i
        else:
            if start_idx is not None:
                # Calcular duração
                start_time = df.iloc[start_idx]['time']
                end_time = df.iloc[i-1]['time']
                duration_seconds = (end_time - start_time).total_seconds()
                duration_minutes = duration_seconds / 60
                
                if duration_minutes >= min_duration_minutes:
                    periods.append({
                        'start_idx': start_idx,
                        'end_idx': i-1,
                        'start_time': start_time,
                        'end_time': end_time,
                        'duration_minutes': duration_minutes
                    })
                start_idx = None
    
    # Adicionar último período se terminar com velocidade baixa
    if start_idx is not None:
        start_time = df.iloc[start_idx]['time']
        end_time = df.iloc[len(df)-1]['time']
        duration_seconds = (end_time - start_time).total_seconds()
        duration_minutes = duration_seconds / 60
        
        if duration_minutes >= min_duration_minutes:
            periods.append({
                'start_idx': start_idx,
                'end_idx': len(df)-1,
                'start_time': start_time,
                'end_time': end_time,
                'duration_minutes': duration_minutes
            })
    
    return pd.DataFrame(periods)

def filter_uncataloged_periods(all_periods, cataloged_periods, labeled_periods):
    """Filtra períodos não catalogados e não rotulados."""
    uncataloged = []
    
    for idx, period in all_periods.iterrows():
        start_time = period['start_time']
        end_time = period['end_time']
        
        # Verificar se está catalogado
        is_cataloged = False
        if cataloged_periods is not None and len(cataloged_periods) > 0:
            cataloged_periods_copy = cataloged_periods.copy()
            cataloged_periods_copy['start_time'] = pd.to_datetime(cataloged_periods_copy['start_time'])
            cataloged_periods_copy['end_time'] = pd.to_datetime(cataloged_periods_copy['end_time'])
            
            overlap = cataloged_periods_copy[
                ((cataloged_periods_copy['start_time'] <= start_time) & (cataloged_periods_copy['end_time'] >= start_time)) |
                ((cataloged_periods_copy['start_time'] <= end_time) & (cataloged_periods_copy['end_time'] >= end_time)) |
                ((cataloged_periods_copy['start_time'] >= start_time) & (cataloged_periods_copy['end_time'] <= end_time))
            ]
            is_cataloged = len(overlap) > 0
        
        # Verificar se já está rotulado
        is_labeled = False
        if labeled_periods is not None and len(labeled_periods) > 0:
            labeled_periods_copy = labeled_periods.copy()
            labeled_periods_copy['start_time'] = pd.to_datetime(labeled_periods_copy['start_time'])
            labeled_periods_copy['end_time'] = pd.to_datetime(labeled_periods_copy['end_time'])
            
            overlap = labeled_periods_copy[
                ((labeled_periods_copy['start_time'] <= start_time) & (labeled_periods_copy['end_time'] >= start_time)) |
                ((labeled_periods_copy['start_time'] <= end_time) & (labeled_periods_copy['end_time'] >= end_time)) |
                ((labeled_periods_copy['start_time'] >= start_time) & (labeled_periods_copy['end_time'] <= end_time))
            ]
            is_labeled = len(overlap) > 0
        
        if not is_cataloged and not is_labeled:
            period_copy = period.copy()
            # Criar ID único baseado em timestamp
            period_copy['period_id'] = f"{start_time.strftime('%Y%m%d_%H%M%S')}_{end_time.strftime('%H%M%S')}"
            uncataloged.append(period_copy)
    
    result_df = pd.DataFrame(uncataloged)
    if len(result_df) > 0:
        result_df = result_df.reset_index(drop=True)
    return result_df

def plot_period_context(df, period, window_minutes=1):
    """Plota velocidade e vibração com contexto antes/depois."""
    try:
        start_time = period['start_time']
        end_time = period['end_time']
        
        # Definir janela
        window_start = start_time - timedelta(minutes=window_minutes)
        window_end = end_time + timedelta(minutes=window_minutes)
        
        # Extrair dados da janela
        mask = (df['time'] >= window_start) & (df['time'] <= window_end)
        window_data = df[mask].copy()
        
        if len(window_data) == 0:
            return None, None
        
        # Limpar figuras anteriores do matplotlib
        plt.close('all')
        
        # Criar figura
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        
        # Gráfico 1: Velocidade
        max_speed = window_data['speed_kmh'].max() if len(window_data) > 0 else 1.0
        ax1.plot(window_data['time'], window_data['speed_kmh'], 
                color='blue', linewidth=2, alpha=0.8, label='Velocidade')
        
        # Destacar período de parada
        stop_mask = (window_data['time'] >= start_time) & (window_data['time'] <= end_time)
        if stop_mask.any() and max_speed > 0:
            ax1.fill_between(window_data['time'], 0, max_speed,
                           where=stop_mask, alpha=0.3, color='red', label='Período de Parada')
        
        ax1.set_ylabel('Velocidade (km/h)', fontsize=12)
        ax1.set_title(f'Velocidade - Período {period.get("period_id", "N/A")}', fontsize=14, fontweight='bold')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Gráfico 2: Vibração
        max_vibration = window_data['linear_accel_magnitude'].max() if len(window_data) > 0 else 1.0
        ax2.plot(window_data['time'], window_data['linear_accel_magnitude'],
                color='green', linewidth=2, alpha=0.8, label='Vibração')
        
        if stop_mask.any() and max_vibration > 0:
            ax2.fill_between(window_data['time'], 0, max_vibration,
                           where=stop_mask, alpha=0.3, color='red', label='Período de Parada')
        
        ax2.set_ylabel('Vibração (linear_accel_magnitude)', fontsize=12)
        ax2.set_xlabel('Tempo', fontsize=12)
        ax2.set_title(f'Vibração - Período {period.get("period_id", "N/A")}', fontsize=14, fontweight='bold')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Formatação do eixo X
        ax2.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%H:%M:%S'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        return fig, window_data
    except Exception as e:
        st.error(f"Erro ao gerar gráfico: {str(e)}")
        plt.close('all')
        return None, None

# Carregar dados
st.title("🏷️ Sistema de Rotulagem de Carregamento")

# Sidebar
with st.sidebar:
    st.header("Configurações")
    
    min_duration = st.number_input(
        "Duração mínima (minutos)",
        min_value=0.5,
        max_value=60.0,
        value=1.0,
        step=0.5
    )
    
    max_speed = st.number_input(
        "Velocidade máxima (km/h)",
        min_value=0.0,
        max_value=10.0,
        value=1.0,
        step=0.1
    )
    
    if st.button("🔄 Carregar Períodos"):
        with st.spinner("Carregando dados..."):
            # Carregar dados
            df = load_telemetry_data()
            
            # Detectar períodos
            all_periods = detect_stop_periods(df, min_duration, max_speed)
            
            # Carregar períodos catalogados
            cataloged_periods = None
            if os.path.exists(PERIODS_FILE):
                cataloged_periods = pd.read_csv(PERIODS_FILE)
            
            # Carregar rótulos existentes
            labeled_periods = load_existing_labels()
            
            # Filtrar períodos não catalogados
            uncataloged = filter_uncataloged_periods(all_periods, cataloged_periods, labeled_periods)
            
            st.session_state.periods_df = df
            st.session_state.uncataloged_periods = uncataloged
            st.session_state.current_index = 0
            st.session_state.labels_df = labeled_periods
            
            st.success(f"Carregados {len(uncataloged)} períodos não catalogados!")
            st.rerun()

# Verificar se há períodos carregados
if st.session_state.uncataloged_periods is None or len(st.session_state.uncataloged_periods) == 0:
    st.info("👆 Clique em 'Carregar Períodos' na sidebar para começar.")
    st.stop()

uncataloged = st.session_state.uncataloged_periods
df = st.session_state.periods_df
current_idx = st.session_state.current_index

# Verificar limites e validar dados
if uncataloged is None or len(uncataloged) == 0:
    st.warning("Nenhum período não catalogado encontrado.")
    st.stop()

if current_idx >= len(uncataloged):
    current_idx = len(uncataloged) - 1
if current_idx < 0:
    current_idx = 0

st.session_state.current_index = current_idx

# Validar que o índice atual é válido
try:
    current_period = uncataloged.iloc[current_idx].copy()
except (IndexError, KeyError) as e:
    st.error(f"Erro ao acessar período {current_idx}: {str(e)}")
    st.session_state.current_index = 0
    st.rerun()

# Estatísticas
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total de Períodos", len(uncataloged))
with col2:
    labeled_count = len(load_existing_labels())
    st.metric("Já Rotulados", labeled_count)
with col3:
    remaining = len(uncataloged) - labeled_count
    st.metric("Restantes", remaining)
with col4:
    progress = (labeled_count / len(uncataloged) * 100) if len(uncataloged) > 0 else 0
    st.metric("Progresso", f"{progress:.1f}%")

st.progress(progress / 100)

st.divider()

# Período atual (já validado acima)
if 'period_id' not in current_period:
    # Criar ID se não existir
    try:
        start_time = pd.to_datetime(current_period['start_time'])
        end_time = pd.to_datetime(current_period['end_time'])
        current_period['period_id'] = f"{start_time.strftime('%Y%m%d_%H%M%S')}_{end_time.strftime('%H%M%S')}"
    except Exception as e:
        st.error(f"Erro ao criar ID do período: {str(e)}")
        st.stop()

# Informações do período
col1, col2, col3 = st.columns(3)
with col1:
    st.write(f"**Período {current_idx + 1} de {len(uncataloged)}**")
with col2:
    st.write(f"**Início:** {current_period['start_time'].strftime('%H:%M:%S')}")
with col3:
    st.write(f"**Duração:** {current_period['duration_minutes']:.2f} minutos")

# Verificar se já está rotulado
existing_labels = load_existing_labels()
existing_label = None
if len(existing_labels) > 0:
    period_labels = existing_labels[existing_labels['period_id'] == current_period['period_id']]
    if len(period_labels) > 0:
        existing_label = period_labels.iloc[0]['label']
        st.info(f"⚠️ Este período já está rotulado como: **{existing_label}**")

# Gráfico
try:
    fig, window_data = plot_period_context(df, current_period)
    if fig is not None:
        st.pyplot(fig, clear_figure=True)
        plt.close(fig)
        plt.close('all')  # Garantir que todas as figuras sejam fechadas
    else:
        st.warning("Não foi possível gerar gráfico para este período.")
except Exception as e:
    st.error(f"Erro ao exibir gráfico: {str(e)}")
    plt.close('all')

# Botões de ação
st.divider()
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    if st.button("⏮️ Primeiro", use_container_width=True):
        st.session_state.current_index = 0
        st.rerun()

with col2:
    if st.button("◀️ Anterior", use_container_width=True, disabled=(current_idx == 0)):
        st.session_state.current_index = max(0, current_idx - 1)
        st.rerun()

with col3:
    if st.button("✅ Carregamento", use_container_width=True, type="primary"):
        try:
            save_label(
                current_period['period_id'],
                current_period['start_time'],
                current_period['end_time'],
                current_period['duration_minutes'],
                'Carregamento'
            )
            st.session_state.labels_df = load_existing_labels()
            st.success("✅ Rotulado como Carregamento!")
            # Limpar figuras antes de avançar
            plt.close('all')
            # Avançar para próximo
            if current_idx < len(uncataloged) - 1:
                st.session_state.current_index = current_idx + 1
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar rótulo: {str(e)}")

with col4:
    if st.button("❌ Não Carregamento", use_container_width=True):
        try:
            save_label(
                current_period['period_id'],
                current_period['start_time'],
                current_period['end_time'],
                current_period['duration_minutes'],
                'Não Carregamento'
            )
            st.session_state.labels_df = load_existing_labels()
            st.success("❌ Rotulado como Não Carregamento!")
            # Limpar figuras antes de avançar
            plt.close('all')
            # Avançar para próximo
            if current_idx < len(uncataloged) - 1:
                st.session_state.current_index = current_idx + 1
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar rótulo: {str(e)}")

with col5:
    if st.button("▶️ Próximo", use_container_width=True, disabled=(current_idx == len(uncataloged) - 1)):
        st.session_state.current_index = min(len(uncataloged) - 1, current_idx + 1)
        st.rerun()

# Exportar rótulos
st.divider()
if st.button("💾 Exportar Rótulos"):
    labels_df = load_existing_labels()
    if len(labels_df) > 0:
        csv = labels_df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name="rotulos_carregamento.csv",
            mime="text/csv"
        )
    else:
        st.warning("Nenhum rótulo para exportar ainda.")
