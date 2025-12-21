#!/usr/bin/env python3
"""
Script para executar o pipeline completo de rotulagem de telemetria.
Extrai e executa todas as células do notebook pipeline_rotulagem_telemetria.ipynb
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Backend não-interativo para salvar figuras
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import warnings
from pathlib import Path
import os
from scipy import signal
from scipy.fft import fft, fftfreq
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
try:
    import hdbscan
    HDBSCAN_AVAILABLE = True
except ImportError:
    HDBSCAN_AVAILABLE = False
    print("⚠️ HDBSCAN não disponível. Usando KMeans como fallback.")

warnings.filterwarnings('ignore')

# Configurações de visualização
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

# Configurações do pipeline
CONFIG = {
    'V_STOP': 0.5,              # km/h threshold para considerar parado
    'MIN_STOP_SEC': 10,          # duração mínima de parada (segundos)
    'GAP_SEC': 3,                # tolerância a gaps em segmentos (segundos)
    'PEAK_HEIGHT': 0.5,          # altura mínima de pico (m/s²)
    'PEAK_DISTANCE': 5,          # distância mínima entre picos (segundos)
    'TH_CONF': 0.5,              # threshold de confiança mínimo
    'MAX_SHORT_MOVE_SEC': 30,    # duração máxima de andadinha curta
    'MAX_SHORT_MOVE_SPEED': 5,   # velocidade máxima de andadinha curta (km/h)
    'WINDOW_SEC': 10,            # janela para features deslizantes
}

# Caminhos
CSV_PATH = '/Users/sapucaia/tracking/BackendTestes/telemetry_all_data_20251213_171617.csv'
OUTPUT_DIR = Path('/Users/sapucaia/tracking/BackendTestes/labeled_segments')
PLOTS_DIR = Path('/Users/sapucaia/tracking/BackendTestes/plots')

# Criar diretórios
OUTPUT_DIR.mkdir(exist_ok=True)
PLOTS_DIR.mkdir(exist_ok=True)

print("="*80)
print("PIPELINE DE ROTULAGEM AUTOMÁTICA - TELEMETRIA VEICULAR")
print("="*80)
print("\n✅ Configuração concluída")
print(f"📁 Diretório de saída: {OUTPUT_DIR}")
print(f"📁 Diretório de gráficos: {PLOTS_DIR}")

# ============================================================================
# CÉLULA 2: DATA DISCOVERY
# ============================================================================
print("\n" + "="*80)
print("CÉLULA 2: DATA DISCOVERY")
print("="*80)

# Carregar CSV
print("\n⏳ Carregando CSV...")
df = pd.read_csv(CSV_PATH, low_memory=False)

# Converter coluna time para datetime
df['time'] = pd.to_datetime(df['time'])

print(f"✅ Dados carregados: {len(df):,} registros, {len(df.columns)} colunas")
print(f"📅 Período: {df['time'].min()} até {df['time'].max()}")
print(f"⏱️ Duração total: {(df['time'].max() - df['time'].min()).total_seconds() / 3600:.2f} horas")
print(f"🚛 Devices únicos: {df['device_id'].nunique()}")
print(f"📊 Taxa de amostragem média: {len(df) / ((df['time'].max() - df['time'].min()).total_seconds() / 3600):.2f} Hz")

# Gerar Data Dictionary
print("\n📚 Gerando Data Dictionary...")

data_dict = []
for col in df.columns:
    dtype = str(df[col].dtype)
    missing_pct = (df[col].isna().sum() / len(df)) * 100
    
    if pd.api.types.is_numeric_dtype(df[col]):
        col_min = df[col].min()
        col_max = df[col].max()
        col_mean = df[col].mean()
        col_std = df[col].std()
        range_info = f"[{col_min:.4f}, {col_max:.4f}], mean={col_mean:.4f}, std={col_std:.4f}"
    else:
        unique_count = df[col].nunique()
        range_info = f"{unique_count} valores únicos"
    
    data_dict.append({
        'Coluna': col,
        'Tipo': dtype,
        'Missing (%)': f"{missing_pct:.2f}",
        'Range/Stats': range_info
    })

df_dict = pd.DataFrame(data_dict)
print(f"\n📊 Total de colunas: {len(df_dict)}")
print(f"📋 Colunas com missing > 50%: {len(df_dict[df_dict['Missing (%)'].astype(float) > 50])}")

# Identificar colunas-chave
print("\n🔑 Colunas-chave identificadas:")
key_cols = {
    'timestamp': 'time',
    'device_id': 'device_id',
    'speed': 'speed_kmh',
    'accel_linear': 'linear_accel_magnitude',
    'pitch': 'pitch',
    'roll': 'roll',
    'battery_status': 'battery_status',
    'battery_voltage': 'battery_voltage',
    'motion_stationary': 'motion_stationary_detect'
}

for key, col in key_cols.items():
    if col in df.columns:
        print(f"  ✅ {key}: {col}")
    else:
        print(f"  ❌ {key}: NÃO ENCONTRADO")

# Verificar qualidade dos sinais principais
print("\n📊 Qualidade dos Sinais Principais:")
for col in ['speed_kmh', 'linear_accel_magnitude', 'pitch', 'roll', 'battery_voltage']:
    if col in df.columns:
        missing = df[col].isna().sum()
        pct_missing = (missing / len(df)) * 100
        if pd.api.types.is_numeric_dtype(df[col]):
            valid = df[col].notna()
            if valid.sum() > 0:
                print(f"  {col}: Missing={pct_missing:.2f}%, Range=[{df[col].min():.4f}, {df[col].max():.4f}]")

# ============================================================================
# CÉLULA 3: LIMPEZA E QUALIDADE
# ============================================================================
print("\n" + "="*80)
print("CÉLULA 3: LIMPEZA E QUALIDADE")
print("="*80)

# Ordenar por time e device_id
df = df.sort_values(['device_id', 'time']).reset_index(drop=True)

# Verificar duplicatas
duplicates = df.duplicated(subset=['device_id', 'time']).sum()
print(f"\n🔍 Duplicatas encontradas: {duplicates}")
if duplicates > 0:
    df = df.drop_duplicates(subset=['device_id', 'time'], keep='first')
    print(f"✅ Duplicatas removidas. Registros restantes: {len(df):,}")

# Verificar gaps de amostragem
df['time_diff'] = df.groupby('device_id')['time'].diff().dt.total_seconds()
gap_stats = df['time_diff'].describe()
print(f"\n📈 Estatísticas de intervalo entre amostras:")
print(f"  Média: {gap_stats['mean']:.2f}s")
print(f"  Mediana: {gap_stats['50%']:.2f}s")
print(f"  P95: {gap_stats['95%']:.2f}s")

# Identificar outliers grosseiros em speed_kmh
if 'speed_kmh' in df.columns:
    outliers_speed = (df['speed_kmh'] < 0) | (df['speed_kmh'] > 200)
    print(f"\n🚨 Outliers em speed_kmh: {outliers_speed.sum()}")
    if outliers_speed.sum() > 0:
        df.loc[outliers_speed, 'speed_kmh'] = np.nan
        print(f"✅ Outliers substituídos por NaN")

# Identificar outliers em linear_accel_magnitude
if 'linear_accel_magnitude' in df.columns:
    outliers_accel = df['linear_accel_magnitude'].abs() > 50
    print(f"🚨 Outliers em linear_accel_magnitude: {outliers_accel.sum()}")
    if outliers_accel.sum() > 0:
        df.loc[outliers_accel, 'linear_accel_magnitude'] = np.nan
        print(f"✅ Outliers substituídos por NaN")

print(f"\n✅ Limpeza concluída. Registros finais: {len(df):,}")

# Gráficos de qualidade
print("\n⏳ Gerando gráficos de qualidade...")
fig, axes = plt.subplots(2, 2, figsize=(15, 10))

# 1. Missing por coluna (top 20)
missing_counts = df.isnull().sum().sort_values(ascending=False).head(20)
axes[0, 0].barh(range(len(missing_counts)), missing_counts.values)
axes[0, 0].set_yticks(range(len(missing_counts)))
axes[0, 0].set_yticklabels(missing_counts.index)
axes[0, 0].set_xlabel('Quantidade de Missing')
axes[0, 0].set_title('Top 20 Colunas com Missing Values')
axes[0, 0].grid(True, alpha=0.3)

# 2. Histograma de speed_kmh
if 'speed_kmh' in df.columns:
    valid_speed = df['speed_kmh'].dropna()
    axes[0, 1].hist(valid_speed, bins=100, edgecolor='black', alpha=0.7)
    axes[0, 1].axvline(CONFIG['V_STOP'], color='r', linestyle='--', label=f"V_STOP={CONFIG['V_STOP']} km/h")
    axes[0, 1].set_xlabel('Velocidade (km/h)')
    axes[0, 1].set_ylabel('Frequência')
    axes[0, 1].set_title('Distribuição de Velocidade')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)

# 3. Histograma de linear_accel_magnitude
if 'linear_accel_magnitude' in df.columns:
    valid_accel = df['linear_accel_magnitude'].dropna()
    axes[1, 0].hist(valid_accel, bins=100, edgecolor='black', alpha=0.7)
    axes[1, 0].axvline(CONFIG['PEAK_HEIGHT'], color='r', linestyle='--', label=f"PEAK_HEIGHT={CONFIG['PEAK_HEIGHT']} m/s²")
    axes[1, 0].set_xlabel('Aceleração Linear Magnitude (m/s²)')
    axes[1, 0].set_ylabel('Frequência')
    axes[1, 0].set_title('Distribuição de Aceleração Linear')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)

# 4. Timeline de amostragem (primeiras 1000 amostras)
sample_df = df.head(1000)
axes[1, 1].plot(sample_df['time'], range(len(sample_df)), marker='.', markersize=1)
axes[1, 1].set_xlabel('Tempo')
axes[1, 1].set_ylabel('Índice da Amostra')
axes[1, 1].set_title('Timeline de Amostragem (primeiras 1000)')
axes[1, 1].grid(True, alpha=0.3)
plt.setp(axes[1, 1].xaxis.get_majorticklabels(), rotation=45)

plt.tight_layout()
plt.savefig(PLOTS_DIR / '01_data_quality.png', dpi=150, bbox_inches='tight')
plt.close()
print(f"✅ Gráfico salvo: {PLOTS_DIR / '01_data_quality.png'}")

# ============================================================================
# CÉLULA 4: SEGMENTAÇÃO BASE
# ============================================================================
print("\n" + "="*80)
print("CÉLULA 4: SEGMENTAÇÃO BASE (PARADO vs MOVIMENTO)")
print("="*80)

def find_stop_segments(df, speed_col='speed_kmh', v_stop=0.5, min_stop_sec=10, gap_sec=3):
    """Identifica segmentos contínuos onde o veículo está parado."""
    segments = []
    
    for device_id in df['device_id'].unique():
        device_df = df[df['device_id'] == device_id].copy()
        device_df = device_df.sort_values('time').reset_index(drop=True)
        
        # Marcar pontos parados
        device_df['is_stopped'] = device_df[speed_col] <= v_stop
        
        # Criar grupos contínuos de parada
        device_df['group'] = (device_df['is_stopped'] != device_df['is_stopped'].shift()).cumsum()
        
        for group_id in device_df['group'].unique():
            group_data = device_df[device_df['group'] == group_id]
            
            if group_data['is_stopped'].iloc[0]:  # Apenas grupos de parada
                t_start = group_data['time'].iloc[0]
                t_end = group_data['time'].iloc[-1]
                duration_s = (t_end - t_start).total_seconds()
                
                # Verificar gaps dentro do segmento
                time_diffs = group_data['time'].diff().dt.total_seconds()
                max_gap = time_diffs.max() if len(time_diffs) > 1 else 0
                
                # Aplicar filtros
                if duration_s >= min_stop_sec and max_gap <= gap_sec:
                    segments.append({
                        'device_id': device_id,
                        't_start': t_start,
                        't_end': t_end,
                        'duration_s': duration_s,
                        'is_moving': False
                    })
        
        # Criar segmentos de movimento (complemento)
        device_df['is_moving'] = device_df[speed_col] > v_stop
        device_df['move_group'] = (device_df['is_moving'] != device_df['is_moving'].shift()).cumsum()
        
        for group_id in device_df['move_group'].unique():
            group_data = device_df[device_df['move_group'] == group_id]
            
            if group_data['is_moving'].iloc[0]:
                t_start = group_data['time'].iloc[0]
                t_end = group_data['time'].iloc[-1]
                duration_s = (t_end - t_start).total_seconds()
                
                if duration_s >= min_stop_sec:
                    segments.append({
                        'device_id': device_id,
                        't_start': t_start,
                        't_end': t_end,
                        'duration_s': duration_s,
                        'is_moving': True
                    })
    
    segments_df = pd.DataFrame(segments)
    if len(segments_df) > 0:
        segments_df = segments_df.sort_values(['device_id', 't_start']).reset_index(drop=True)
    
    return segments_df

# Aplicar segmentação
print("\n⏳ Segmentando dados...")
segments_df = find_stop_segments(
    df,
    speed_col='speed_kmh',
    v_stop=CONFIG['V_STOP'],
    min_stop_sec=CONFIG['MIN_STOP_SEC'],
    gap_sec=CONFIG['GAP_SEC']
)

print(f"✅ Segmentação concluída:")
print(f"  Total de segmentos: {len(segments_df)}")
print(f"  Segmentos PARADO: {len(segments_df[segments_df['is_moving'] == False])}")
print(f"  Segmentos MOVIMENTO: {len(segments_df[segments_df['is_moving'] == True])}")
print(f"\n📊 Estatísticas de duração:")
print(segments_df.groupby('is_moving')['duration_s'].describe())

# Visualizar segmentação
print("\n⏳ Gerando gráfico de segmentação...")
fig, axes = plt.subplots(2, 1, figsize=(16, 10))

# Timeline com segmentos coloridos
for device_id in df['device_id'].unique():
    device_df = df[df['device_id'] == device_id].copy()
    device_segments = segments_df[segments_df['device_id'] == device_id]
    
    # Plot velocidade
    axes[0].plot(device_df['time'], device_df['speed_kmh'], alpha=0.3, label=f'{device_id} - Velocidade', color='gray')
    
    # Colorir segmentos de parada
    for _, seg in device_segments[device_segments['is_moving'] == False].iterrows():
        axes[0].axvspan(seg['t_start'], seg['t_end'], alpha=0.3, color='red')
    
    # Colorir segmentos de movimento
    for _, seg in device_segments[device_segments['is_moving'] == True].iterrows():
        axes[0].axvspan(seg['t_start'], seg['t_end'], alpha=0.3, color='green')

axes[0].set_xlabel('Tempo')
axes[0].set_ylabel('Velocidade (km/h)')
axes[0].set_title('Timeline de Segmentação: PARADO vs MOVIMENTO')
axes[0].legend()
axes[0].grid(True, alpha=0.3)
axes[0].axhline(CONFIG['V_STOP'], color='r', linestyle='--', linewidth=2, label=f"V_STOP={CONFIG['V_STOP']} km/h")

# Distribuição de durações
axes[1].hist(segments_df[segments_df['is_moving'] == False]['duration_s'] / 60, bins=50, 
             alpha=0.7, label='PARADO', color='red', edgecolor='black')
axes[1].hist(segments_df[segments_df['is_moving'] == True]['duration_s'] / 60, bins=50, 
             alpha=0.7, label='MOVIMENTO', color='green', edgecolor='black')
axes[1].set_xlabel('Duração (minutos)')
axes[1].set_ylabel('Frequência')
axes[1].set_title('Distribuição de Duração dos Segmentos')
axes[1].legend()
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(PLOTS_DIR / '02_segmentation.png', dpi=150, bbox_inches='tight')
plt.close()
print(f"✅ Gráfico salvo: {PLOTS_DIR / '02_segmentation.png'}")

# Continuar no próximo arquivo devido ao limite de tamanho...
print("\n⏳ Continuando com Feature Engineering...")



