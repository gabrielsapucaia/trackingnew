#!/usr/bin/env python3
"""Pipeline completo de rotulagem - extraído do notebook"""

import matplotlib
matplotlib.use('Agg')


# === CÉLULA 1 ===
import pandas as pd
import numpy as np
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

print("✅ Configuração concluída")
print(f"📁 Diretório de saída: {OUTPUT_DIR}")
print(f"📁 Diretório de gráficos: {PLOTS_DIR}")


# === CÉLULA 2 ===
# Carregar CSV
print("⏳ Carregando CSV...")
df = pd.read_csv(CSV_PATH, low_memory=False)

# Converter coluna time para datetime
df['time'] = pd.to_datetime(df['time'])

print(f"✅ Dados carregados: {len(df):,} registros, {len(df.columns)} colunas")
print(f"📅 Período: {df['time'].min()} até {df['time'].max()}")
print(f"⏱️ Duração total: {(df['time'].max() - df['time'].min()).total_seconds() / 3600:.2f} horas")
print(f"🚛 Devices únicos: {df['device_id'].nunique()}")
print(f"📊 Taxa de amostragem média: {len(df) / ((df['time'].max() - df['time'].min()).total_seconds() / 3600):.2f} Hz")


# === CÉLULA 3 ===
# Gerar Data Dictionary
print("📚 Gerando Data Dictionary...\n")

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
print(df_dict.to_string(index=False))

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


# === CÉLULA 4 ===
# Verificar qualidade dos sinais principais
print("📊 Qualidade dos Sinais Principais:\n")

for col in ['speed_kmh', 'linear_accel_magnitude', 'pitch', 'roll', 'battery_voltage']:
    if col in df.columns:
        missing = df[col].isna().sum()
        pct_missing = (missing / len(df)) * 100
        if pd.api.types.is_numeric_dtype(df[col]):
            valid = df[col].notna()
            if valid.sum() > 0:
                print(f"{col}:")
                print(f"  Missing: {missing} ({pct_missing:.2f}%)")
                print(f"  Range: [{df[col].min():.4f}, {df[col].max():.4f}]")
                print(f"  Mean: {df[col].mean():.4f}, Std: {df[col].std():.4f}")
                print()


# === CÉLULA 5 ===
# Ordenar por time e device_id
df = df.sort_values(['device_id', 'time']).reset_index(drop=True)

# Verificar duplicatas
duplicates = df.duplicated(subset=['device_id', 'time']).sum()
print(f"🔍 Duplicatas encontradas: {duplicates}")
if duplicates > 0:
    df = df.drop_duplicates(subset=['device_id', 'time'], keep='first')
    print(f"✅ Duplicatas removidas. Registros restantes: {len(df):,}")

# Verificar gaps de amostragem
df['time_diff'] = df.groupby('device_id')['time'].diff().dt.total_seconds()
gap_stats = df['time_diff'].describe()
print(f"\n📈 Estatísticas de intervalo entre amostras:")
print(f"  Média: {gap_stats['mean']:.2f}s")
print(f"  Mediana: {gap_stats['50%']:.2f}s")
print(f"  P95: {gap_stats.quantile(0.95):.2f}s")
print(f"  Max: {gap_stats['max']:.2f}s")

# Identificar outliers grosseiros em speed_kmh
if 'speed_kmh' in df.columns:
    # Remover valores negativos ou extremamente altos (>200 km/h para caminhão)
    outliers_speed = (df['speed_kmh'] < 0) | (df['speed_kmh'] > 200)
    print(f"\n🚨 Outliers em speed_kmh: {outliers_speed.sum()}")
    if outliers_speed.sum() > 0:
        df.loc[outliers_speed, 'speed_kmh'] = np.nan
        print(f"✅ Outliers substituídos por NaN")

# Identificar outliers em linear_accel_magnitude
if 'linear_accel_magnitude' in df.columns:
    # Valores muito altos (>50 m/s² são suspeitos para caminhão)
    outliers_accel = df['linear_accel_magnitude'].abs() > 50
    print(f"🚨 Outliers em linear_accel_magnitude: {outliers_accel.sum()}")
    if outliers_accel.sum() > 0:
        df.loc[outliers_accel, 'linear_accel_magnitude'] = np.nan
        print(f"✅ Outliers substituídos por NaN")

print(f"\n✅ Limpeza concluída. Registros finais: {len(df):,}")


# === CÉLULA 6 ===
# Gráficos de qualidade
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
plt.xticks(rotation=45)

plt.tight_layout()
plt.savefig(PLOTS_DIR / '01_data_quality.png', dpi=150, bbox_inches='tight')
print(f"✅ Gráfico salvo: {PLOTS_DIR / '01_data_quality.png'}")
plt.show()


# === CÉLULA 7 ===
def find_stop_segments(df, speed_col='speed_kmh', v_stop=0.5, min_stop_sec=10, gap_sec=3):
    """
    Identifica segmentos contínuos onde o veículo está parado.
    
    Args:
        df: DataFrame com coluna time e speed_col
        speed_col: nome da coluna de velocidade
        v_stop: threshold de velocidade para considerar parado (km/h)
        min_stop_sec: duração mínima do segmento (segundos)
        gap_sec: tolerância a gaps dentro do segmento (segundos)
    
    Returns:
        DataFrame com colunas: device_id, t_start, t_end, duration_s, is_moving
    """
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
                
                if duration_s >= min_stop_sec:  # Movimento também precisa de duração mínima
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
print("⏳ Segmentando dados...")
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


# === CÉLULA 8 ===
# Visualizar segmentação
fig, axes = plt.subplots(2, 1, figsize=(16, 10))

# Timeline com segmentos coloridos
for device_id in df['device_id'].unique():
    device_df = df[df['device_id'] == device_id].copy()
    device_segments = segments_df[segments_df['device_id'] == device_id]
    
    # Plot velocidade
    axes[0].plot(device_df['time'], device_df['speed_kmh'], alpha=0.3, label=f'{device_id} - Velocidade', color='gray')
    
    # Colorir segmentos de parada
    for _, seg in device_segments[device_segments['is_moving'] == False].iterrows():
        axes[0].axvspan(seg['t_start'], seg['t_end'], alpha=0.3, color='red', label='PARADO' if seg.name == 0 else '')
    
    # Colorir segmentos de movimento
    for _, seg in device_segments[device_segments['is_moving'] == True].iterrows():
        axes[0].axvspan(seg['t_start'], seg['t_end'], alpha=0.3, color='green', label='MOVIMENTO' if seg.name == 0 else '')

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
print(f"✅ Gráfico salvo: {PLOTS_DIR / '02_segmentation.png'}")
plt.show()


# === CÉLULA 9 ===
def extract_features(seg_data, window_sec=10):
    """
    Extrai features de um segmento de dados.
    
    Args:
        seg_data: DataFrame com dados do segmento (deve ter time, linear_accel_magnitude, pitch, roll, etc.)
        window_sec: tamanho da janela para features deslizantes
    
    Returns:
        dict com features extraídas
    """
    features = {}
    
    # Features de aceleração linear
    if 'linear_accel_magnitude' in seg_data.columns:
        accel = seg_data['linear_accel_magnitude'].dropna()
        if len(accel) > 0:
            features['accel_mean'] = accel.mean()
            features['accel_std'] = accel.std()
            features['accel_rms'] = np.sqrt((accel**2).mean())
            features['accel_p50'] = accel.median()
            features['accel_p95'] = accel.quantile(0.95)
            features['accel_p99'] = accel.quantile(0.99)
            features['accel_iqr'] = accel.quantile(0.75) - accel.quantile(0.25)
            features['accel_energy'] = (accel**2).sum()
            features['accel_max'] = accel.max()
            features['accel_min'] = accel.min()
            
            # Detecção de picos
            peaks, properties = signal.find_peaks(
                accel.values,
                height=CONFIG['PEAK_HEIGHT'],
                distance=int(CONFIG['PEAK_DISTANCE'])
            )
            features['peak_count'] = len(peaks)
            if len(peaks) > 0:
                peak_heights = accel.iloc[peaks].values
                features['peak_height_mean'] = peak_heights.mean()
                features['peak_height_max'] = peak_heights.max()
                
                # Intervalos entre picos
                if len(peaks) > 1:
                    peak_intervals = np.diff(peaks)
                    features['peak_interval_mean'] = peak_intervals.mean()
                    features['peak_interval_std'] = peak_intervals.std()
                else:
                    features['peak_interval_mean'] = np.nan
                    features['peak_interval_std'] = np.nan
            else:
                features['peak_height_mean'] = 0
                features['peak_height_max'] = 0
                features['peak_interval_mean'] = np.nan
                features['peak_interval_std'] = np.nan
            
            # Análise espectral (FFT)
            if len(accel) >= 10:
                fft_vals = np.abs(fft(accel.values))
                freqs = fftfreq(len(accel), 1.0)  # 1 Hz sampling
                # Energia em diferentes bandas
                low_freq_energy = np.sum(fft_vals[freqs < 0.1])  # < 0.1 Hz
                mid_freq_energy = np.sum(fft_vals[(freqs >= 0.1) & (freqs < 0.5)])  # 0.1-0.5 Hz
                high_freq_energy = np.sum(fft_vals[freqs >= 0.5])  # >= 0.5 Hz
                features['spectral_low_energy'] = low_freq_energy
                features['spectral_mid_energy'] = mid_freq_energy
                features['spectral_high_energy'] = high_freq_energy
            else:
                features['spectral_low_energy'] = np.nan
                features['spectral_mid_energy'] = np.nan
                features['spectral_high_energy'] = np.nan
        else:
            # Preencher com NaN se não houver dados
            for key in ['accel_mean', 'accel_std', 'accel_rms', 'accel_p50', 'accel_p95', 'accel_p99',
                       'accel_iqr', 'accel_energy', 'accel_max', 'accel_min', 'peak_count',
                       'peak_height_mean', 'peak_height_max', 'peak_interval_mean', 'peak_interval_std',
                       'spectral_low_energy', 'spectral_mid_energy', 'spectral_high_energy']:
                features[key] = np.nan
    
    # Features de orientação (pitch e roll)
    if 'pitch' in seg_data.columns:
        pitch = seg_data['pitch'].dropna()
        if len(pitch) > 0:
            features['pitch_mean'] = pitch.mean()
            features['pitch_std'] = pitch.std()
            features['pitch_delta'] = pitch.max() - pitch.min()
            features['pitch_range'] = pitch.max() - pitch.min()
        else:
            features['pitch_mean'] = np.nan
            features['pitch_std'] = np.nan
            features['pitch_delta'] = np.nan
            features['pitch_range'] = np.nan
    
    if 'roll' in seg_data.columns:
        roll = seg_data['roll'].dropna()
        if len(roll) > 0:
            features['roll_mean'] = roll.mean()
            features['roll_std'] = roll.std()
            features['roll_delta'] = roll.max() - roll.min()
            features['roll_range'] = roll.max() - roll.min()
        else:
            features['roll_mean'] = np.nan
            features['roll_std'] = np.nan
            features['roll_delta'] = np.nan
            features['roll_range'] = np.nan
    
    # Features de bateria (proxy para motor ligado/desligado)
    if 'battery_voltage' in seg_data.columns:
        voltage = seg_data['battery_voltage'].dropna()
        if len(voltage) > 0:
            features['voltage_mean'] = voltage.mean()
            features['voltage_std'] = voltage.std()
        else:
            features['voltage_mean'] = np.nan
            features['voltage_std'] = np.nan
    
    if 'battery_status' in seg_data.columns:
        status = seg_data['battery_status'].dropna()
        if len(status) > 0:
            # Contar ocorrências de CHARGING (motor ligado)
            features['battery_charging_pct'] = (status == 'CHARGING').sum() / len(status) if len(status) > 0 else 0
        else:
            features['battery_charging_pct'] = np.nan
    
    return features

# Extrair features para cada segmento PARADO
print("⏳ Extraindo features dos segmentos PARADO...")
stop_segments = segments_df[segments_df['is_moving'] == False].copy()

features_list = []
for idx, seg in stop_segments.iterrows():
    # Obter dados do segmento
    seg_data = df[
        (df['device_id'] == seg['device_id']) &
        (df['time'] >= seg['t_start']) &
        (df['time'] <= seg['t_end'])
    ].copy()
    
    if len(seg_data) > 0:
        feat = extract_features(seg_data, window_sec=CONFIG['WINDOW_SEC'])
        feat['segment_idx'] = idx
        features_list.append(feat)

features_df = pd.DataFrame(features_list)
print(f"✅ Features extraídas para {len(features_df)} segmentos")
print(f"\n📊 Features disponíveis: {list(features_df.columns)}")
print(f"\n📈 Estatísticas das features principais:")
print(features_df[['accel_mean', 'accel_std', 'peak_count', 'pitch_delta', 'voltage_mean']].describe())


# === CÉLULA 10 ===
def classify_stop_segment(features, th_conf=0.5):
    """
    Classifica um segmento parado usando regras de weak supervision.
    
    Args:
        features: dict com features do segmento
        th_conf: threshold mínimo de confiança
    
    Returns:
        tuple: (label, confidence, evidence)
    """
    label = 'DESCONHECIDO'
    confidence = 0.0
    evidence_parts = []
    
    # Regra 1: CARREGANDO
    # Múltiplos picos intermitentes (alta variabilidade de intervalos)
    peak_count = features.get('peak_count', 0)
    peak_interval_std = features.get('peak_interval_std', np.nan)
    accel_std = features.get('accel_std', 0)
    
    if peak_count >= 5 and not np.isnan(peak_interval_std) and peak_interval_std > 3:
        conf_carregando = min(0.9, 0.5 + (peak_count / 20) * 0.4)
        if conf_carregando > confidence:
            label = 'CARREGANDO'
            confidence = conf_carregando
            evidence_parts.append(f"peak_count={peak_count}, interval_std={peak_interval_std:.2f}")
    
    # Regra 2: BASCULANDO
    # Mudança significativa de pitch OU padrão contínuo de aceleração
    pitch_delta = features.get('pitch_delta', 0)
    accel_rms = features.get('accel_rms', 0)
    accel_mean = features.get('accel_mean', 0)
    
    if not np.isnan(pitch_delta) and pitch_delta > 10:  # >10 graus de mudança
        conf_basculando = min(0.8, 0.5 + (pitch_delta / 30) * 0.3)
        if conf_basculando > confidence:
            label = 'BASCULANDO'
            confidence = conf_basculando
            evidence_parts.append(f"pitch_delta={pitch_delta:.2f}deg")
    elif accel_rms > 1.5 and accel_mean > 0.5:  # Padrão contínuo de vibração
        conf_basculando = min(0.7, 0.4 + (accel_rms / 3) * 0.3)
        if conf_basculando > confidence:
            label = 'BASCULANDO'
            confidence = conf_basculando
            evidence_parts.append(f"accel_rms={accel_rms:.2f}, accel_mean={accel_mean:.2f}")
    
    # Regra 3: MOTOR_DESLIGADO
    # Baixa voltagem E baixa variabilidade de aceleração
    voltage_mean = features.get('voltage_mean', np.nan)
    battery_charging_pct = features.get('battery_charging_pct', 0)
    
    if not np.isnan(voltage_mean) and voltage_mean < 4000:  # Threshold empírico
        if accel_std < 0.3 and accel_rms < 0.5:
            conf_motor_off = min(0.95, 0.7 + (1 - battery_charging_pct) * 0.25)
            if conf_motor_off > confidence:
                label = 'MOTOR_DESLIGADO'
                confidence = conf_motor_off
                evidence_parts.append(f"voltage={voltage_mean:.0f}mV, accel_std={accel_std:.2f}")
    
    # Regra 4: MOTOR_LIGADO_IDLE
    # Voltagem OK E aceleração moderada contínua (sem picos intermitentes)
    if not np.isnan(voltage_mean) and voltage_mean >= 4000:
        if accel_std > 0.3 and accel_std < 1.5 and peak_count < 3:
            conf_motor_on = min(0.7, 0.5 + (accel_std / 2) * 0.2)
            if conf_motor_on > confidence:
                label = 'MOTOR_LIGADO_IDLE'
                confidence = conf_motor_on
                evidence_parts.append(f"voltage={voltage_mean:.0f}mV, accel_std={accel_std:.2f}, peaks={peak_count}")
    
    # Se nenhuma regra atingiu threshold, manter DESCONHECIDO
    if confidence < th_conf:
        label = 'DESCONHECIDO'
        confidence = confidence  # Manter confiança calculada mesmo que baixa
        evidence_parts.append("nenhuma regra atingiu threshold")
    
    evidence = " | ".join(evidence_parts) if evidence_parts else "sem evidência"
    
    return label, confidence, evidence

# Aplicar rotulagem
print("⏳ Aplicando rotulagem aos segmentos PARADO...")

labeled_segments = []
for idx, seg in stop_segments.iterrows():
    seg_features = features_df[features_df['segment_idx'] == idx]
    
    if len(seg_features) > 0:
        feat_dict = seg_features.iloc[0].to_dict()
        label, confidence, evidence = classify_stop_segment(feat_dict, th_conf=CONFIG['TH_CONF'])
        
        labeled_segments.append({
            'device_id': seg['device_id'],
            't_start': seg['t_start'],
            't_end': seg['t_end'],
            'duration_s': seg['duration_s'],
            'is_moving': False,
            'label_operacional': label,
            'confidence': confidence,
            'evidence': evidence,
            **feat_dict
        })

# Adicionar segmentos de movimento
for idx, seg in segments_df[segments_df['is_moving'] == True].iterrows():
    labeled_segments.append({
        'device_id': seg['device_id'],
        't_start': seg['t_start'],
        't_end': seg['t_end'],
        'duration_s': seg['duration_s'],
        'is_moving': True,
        'label_operacional': 'EM_MOVIMENTO',
        'confidence': 1.0,
        'evidence': 'velocidade > V_STOP'
    })

labeled_df = pd.DataFrame(labeled_segments)

print(f"✅ Rotulagem concluída:")
print(f"\n📊 Distribuição de rótulos:")
print(labeled_df['label_operacional'].value_counts())
print(f"\n📈 Confiança média por rótulo:")
print(labeled_df.groupby('label_operacional')['confidence'].mean().sort_values(ascending=False))


# === CÉLULA 11 ===
def merge_basculamento_episodes(labeled_df, max_short_move_sec=30, max_short_move_speed=5):
    """
    Mescla segmentos de basculamento com andadinhas curtas adjacentes.
    
    Args:
        labeled_df: DataFrame com segmentos rotulados
        max_short_move_sec: duração máxima da andadinha
        max_short_move_speed: velocidade máxima da andadinha
    
    Returns:
        DataFrame com episódios mesclados
    """
    merged_segments = []
    i = 0
    
    while i < len(labeled_df):
        seg = labeled_df.iloc[i]
        
        # Se é um segmento de basculamento
        if seg['label_operacional'] == 'BASCULANDO' and not seg['is_moving']:
            episode_segments = [seg]
            episode_start = seg['t_start']
            episode_end = seg['t_end']
            episode_device = seg['device_id']
            
            # Verificar próximo segmento (movimento curto)
            if i + 1 < len(labeled_df):
                next_seg = labeled_df.iloc[i + 1]
                
                # Se é movimento curto adjacente
                if (next_seg['device_id'] == episode_device and
                    next_seg['is_moving'] and
                    next_seg['duration_s'] <= max_short_move_sec):
                    
                    # Verificar velocidade média do movimento
                    move_data = df[
                        (df['device_id'] == next_seg['device_id']) &
                        (df['time'] >= next_seg['t_start']) &
                        (df['time'] <= next_seg['t_end'])
                    ]
                    
                    if len(move_data) > 0 and move_data['speed_kmh'].mean() <= max_short_move_speed:
                        episode_segments.append(next_seg)
                        episode_end = next_seg['t_end']
                        i += 1  # Pular o segmento de movimento
                        
                        # Verificar se há outro segmento parado após (fim do basculamento)
                        if i + 1 < len(labeled_df):
                            after_seg = labeled_df.iloc[i + 1]
                            if (after_seg['device_id'] == episode_device and
                                not after_seg['is_moving'] and
                                (after_seg['t_start'] - episode_end).total_seconds() < 10):
                                episode_segments.append(after_seg)
                                episode_end = after_seg['t_end']
                                i += 1
            
            # Criar episódio mesclado
            episode_duration = (episode_end - episode_start).total_seconds()
            merged_segments.append({
                'device_id': episode_device,
                't_start': episode_start,
                't_end': episode_end,
                'duration_s': episode_duration,
                'is_moving': False,
                'label_operacional': 'BASCULANDO',
                'confidence': seg['confidence'],
                'evidence': f"{seg['evidence']} + andadinha curta mesclada",
                'has_short_move': len(episode_segments) > 1
            })
        else:
            # Manter segmento original
            merged_segments.append(seg.to_dict())
        
        i += 1
    
    return pd.DataFrame(merged_segments)

# Aplicar merge
print("⏳ Mesclando episódios de basculamento com andadinhas...")
merged_df = merge_basculamento_episodes(
    labeled_df,
    max_short_move_sec=CONFIG['MAX_SHORT_MOVE_SEC'],
    max_short_move_speed=CONFIG['MAX_SHORT_MOVE_SPEED']
)

print(f"✅ Merge concluído:")
print(f"  Segmentos antes: {len(labeled_df)}")
print(f"  Segmentos depois: {len(merged_df)}")
print(f"  Episódios mesclados: {len(merged_df[merged_df.get('has_short_move', False) == True])}")


# === CÉLULA 12 ===
# Preparar dados para clustering (apenas segmentos PARADO)
stop_labeled = merged_df[merged_df['is_moving'] == False].copy()

# Selecionar features numéricas relevantes
feature_cols = [
    'accel_mean', 'accel_std', 'accel_rms', 'accel_p95', 'accel_p99',
    'peak_count', 'peak_height_mean', 'peak_interval_mean', 'peak_interval_std',
    'pitch_delta', 'roll_delta', 'voltage_mean', 'spectral_low_energy',
    'spectral_mid_energy', 'spectral_high_energy'
]

# Filtrar colunas que existem
available_features = [col for col in feature_cols if col in stop_labeled.columns]
print(f"📊 Features disponíveis para clustering: {len(available_features)}")

# Preparar matriz de features
X = stop_labeled[available_features].copy()

# Remover linhas com muitos NaN
X = X.dropna(thresh=len(available_features) * 0.5)  # Pelo menos 50% das features preenchidas

# Preencher NaN restantes com mediana
X = X.fillna(X.median())

print(f"✅ Dados preparados: {len(X)} segmentos com {len(available_features)} features")

# Normalizar
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Aplicar clustering
print("\n⏳ Aplicando clustering...")

if HDBSCAN_AVAILABLE and len(X_scaled) > 10:
    clusterer = hdbscan.HDBSCAN(min_cluster_size=max(3, len(X_scaled) // 20), min_samples=2)
    cluster_labels = clusterer.fit_predict(X_scaled)
    n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
    n_noise = list(cluster_labels).count(-1)
    print(f"✅ HDBSCAN concluído: {n_clusters} clusters, {n_noise} pontos de ruído")
else:
    # Fallback para KMeans
    n_clusters = min(5, len(X_scaled) // 3)  # Máximo 5 clusters
    if n_clusters < 2:
        n_clusters = 2
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(X_scaled)
    print(f"✅ KMeans concluído: {n_clusters} clusters")

# Adicionar labels de cluster ao DataFrame
stop_labeled_clustered = stop_labeled.iloc[X.index].copy()
stop_labeled_clustered['cluster'] = cluster_labels

# Comparar clusters com rótulos de regras
print("\n📊 Comparação Clusters vs Rótulos de Regras:")
comparison = pd.crosstab(stop_labeled_clustered['cluster'], stop_labeled_clustered['label_operacional'])
print(comparison)

# PCA para visualização 2D
pca = PCA(n_components=2)
X_pca = pca.fit_transform(X_scaled)
print(f"\n📈 PCA: Variância explicada: {pca.explained_variance_ratio_.sum():.2%}")


# === CÉLULA 13 ===
# Visualizar clusters vs rótulos
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# PCA com cores por cluster
scatter1 = axes[0].scatter(X_pca[:, 0], X_pca[:, 1], c=cluster_labels, cmap='tab10', alpha=0.6, s=50)
axes[0].set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%} var)')
axes[0].set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%} var)')
axes[0].set_title('Clusters (HDBSCAN/KMeans)')
axes[0].grid(True, alpha=0.3)
plt.colorbar(scatter1, ax=axes[0])

# PCA com cores por rótulo
label_map = {label: i for i, label in enumerate(stop_labeled_clustered['label_operacional'].unique())}
label_colors = stop_labeled_clustered['label_operacional'].map(label_map)
scatter2 = axes[1].scatter(X_pca[:, 0], X_pca[:, 1], c=label_colors, cmap='Set2', alpha=0.6, s=50)
axes[1].set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%} var)')
axes[1].set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%} var)')
axes[1].set_title('Rótulos de Regras')
axes[1].grid(True, alpha=0.3)
plt.colorbar(scatter2, ax=axes[1], ticks=range(len(label_map)), label='Rótulo')

plt.tight_layout()
plt.savefig(PLOTS_DIR / '03_clustering.png', dpi=150, bbox_inches='tight')
print(f"✅ Gráfico salvo: {PLOTS_DIR / '03_clustering.png'}")
plt.show()


# === CÉLULA 14 ===
# 1. Scatter Speed vs Aceleração (hexbin)
fig, ax = plt.subplots(figsize=(12, 8))

# Filtrar dados válidos
valid_data = df[(df['speed_kmh'].notna()) & (df['linear_accel_magnitude'].notna())].copy()

# Hexbin plot
hb = ax.hexbin(valid_data['speed_kmh'], valid_data['linear_accel_magnitude'], 
               gridsize=50, cmap='YlOrRd', mincnt=1)
ax.axvline(CONFIG['V_STOP'], color='r', linestyle='--', linewidth=2, label=f"V_STOP={CONFIG['V_STOP']} km/h")
ax.set_xlabel('Velocidade (km/h)')
ax.set_ylabel('Aceleração Linear Magnitude (m/s²)')
ax.set_title('Speed vs Aceleração Linear (Hexbin)')
ax.legend()
ax.grid(True, alpha=0.3)
plt.colorbar(hb, ax=ax, label='Densidade')

plt.tight_layout()
plt.savefig(PLOTS_DIR / '04_speed_vs_accel.png', dpi=150, bbox_inches='tight')
print(f"✅ Gráfico salvo: {PLOTS_DIR / '04_speed_vs_accel.png'}")
plt.show()


# === CÉLULA 15 ===
# 2. Timeline com segmentos coloridos por rótulo
fig, axes = plt.subplots(3, 1, figsize=(16, 12))

for device_id in df['device_id'].unique():
    device_df = df[df['device_id'] == device_id].copy()
    device_segments = merged_df[merged_df['device_id'] == device_id]
    
    # Plot velocidade
    axes[0].plot(device_df['time'], device_df['speed_kmh'], alpha=0.3, color='gray', linewidth=0.5)
    
    # Colorir segmentos por rótulo
    color_map = {
        'CARREGANDO': 'orange',
        'BASCULANDO': 'purple',
        'MOTOR_LIGADO_IDLE': 'blue',
        'MOTOR_DESLIGADO': 'darkgreen',
        'EM_MOVIMENTO': 'green',
        'DESCONHECIDO': 'gray'
    }
    
    for _, seg in device_segments.iterrows():
        color = color_map.get(seg['label_operacional'], 'gray')
        axes[0].axvspan(seg['t_start'], seg['t_end'], alpha=0.4, color=color)
    
    axes[0].set_xlabel('Tempo')
    axes[0].set_ylabel('Velocidade (km/h)')
    axes[0].set_title(f'Timeline de Segmentos Rotulados - {device_id}')
    axes[0].grid(True, alpha=0.3)
    axes[0].axhline(CONFIG['V_STOP'], color='r', linestyle='--', linewidth=1)
    
    # Plot aceleração linear
    axes[1].plot(device_df['time'], device_df['linear_accel_magnitude'], alpha=0.5, color='blue', linewidth=0.5)
    axes[1].set_xlabel('Tempo')
    axes[1].set_ylabel('Aceleração Linear (m/s²)')
    axes[1].set_title('Aceleração Linear ao Longo do Tempo')
    axes[1].grid(True, alpha=0.3)
    
    # Plot pitch
    if 'pitch' in device_df.columns:
        axes[2].plot(device_df['time'], device_df['pitch'], alpha=0.5, color='green', linewidth=0.5)
        axes[2].set_xlabel('Tempo')
        axes[2].set_ylabel('Pitch (graus)')
        axes[2].set_title('Pitch ao Longo do Tempo')
        axes[2].grid(True, alpha=0.3)

# Criar legenda
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor=color, alpha=0.4, label=label) 
                   for label, color in color_map.items()]
axes[0].legend(handles=legend_elements, loc='upper right')

plt.tight_layout()
plt.savefig(PLOTS_DIR / '05_timeline_labeled.png', dpi=150, bbox_inches='tight')
print(f"✅ Gráfico salvo: {PLOTS_DIR / '05_timeline_labeled.png'}")
plt.show()


# === CÉLULA 16 ===
# 3. Exemplos por classe (séries temporais com picos marcados)
stop_labeled_examples = merged_df[merged_df['is_moving'] == False].copy()

# Selecionar até 10 exemplos por classe
n_examples_per_class = 10
classes = stop_labeled_examples['label_operacional'].unique()

fig, axes = plt.subplots(len(classes), 1, figsize=(16, 4 * len(classes)))

if len(classes) == 1:
    axes = [axes]

for class_idx, label_class in enumerate(classes):
    class_segments = stop_labeled_examples[stop_labeled_examples['label_operacional'] == label_class]
    n_examples = min(n_examples_per_class, len(class_segments))
    
    for i in range(n_examples):
        seg = class_segments.iloc[i]
        
        # Obter dados do segmento
        seg_data = df[
            (df['device_id'] == seg['device_id']) &
            (df['time'] >= seg['t_start']) &
            (df['time'] <= seg['t_end'])
        ].copy()
        
        if len(seg_data) > 0:
            # Plot aceleração
            time_rel = (seg_data['time'] - seg_data['time'].iloc[0]).dt.total_seconds()
            axes[class_idx].plot(time_rel, seg_data['linear_accel_magnitude'], 
                                 alpha=0.6, linewidth=1, label=f"Exemplo {i+1}")
            
            # Marcar picos
            accel = seg_data['linear_accel_magnitude'].dropna().values
            if len(accel) > CONFIG['PEAK_DISTANCE']:
                peaks, _ = signal.find_peaks(
                    accel,
                    height=CONFIG['PEAK_HEIGHT'],
                    distance=int(CONFIG['PEAK_DISTANCE'])
                )
                if len(peaks) > 0:
                    peak_times = time_rel.iloc[peaks]
                    peak_values = accel[peaks]
                    axes[class_idx].scatter(peak_times, peak_values, color='red', 
                                           marker='v', s=50, zorder=5, alpha=0.7)
    
    axes[class_idx].set_xlabel('Tempo (segundos)')
    axes[class_idx].set_ylabel('Aceleração Linear (m/s²)')
    axes[class_idx].set_title(f'{label_class} - Exemplos com Picos Marcados (confiança média: {class_segments["confidence"].mean():.2f})')
    axes[class_idx].grid(True, alpha=0.3)
    axes[class_idx].legend(loc='upper right', fontsize=8)

plt.tight_layout()
plt.savefig(PLOTS_DIR / '06_examples_by_class.png', dpi=150, bbox_inches='tight')
print(f"✅ Gráfico salvo: {PLOTS_DIR / '06_examples_by_class.png'}")
plt.show()


# === CÉLULA 17 ===
# 4. Distribuição de features por classe (boxplots)
feature_cols_viz = ['accel_mean', 'accel_std', 'accel_rms', 'peak_count', 'pitch_delta', 'voltage_mean']
available_viz_features = [col for col in feature_cols_viz if col in stop_labeled_examples.columns]

n_features = len(available_viz_features)
n_cols = 3
n_rows = (n_features + n_cols - 1) // n_cols

fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 6 * n_rows))
axes = axes.flatten() if n_features > 1 else [axes]

for idx, feat in enumerate(available_viz_features):
    data_to_plot = []
    labels = []
    
    for label_class in stop_labeled_examples['label_operacional'].unique():
        class_data = stop_labeled_examples[
            (stop_labeled_examples['label_operacional'] == label_class) &
            (stop_labeled_examples[feat].notna())
        ][feat].values
        
        if len(class_data) > 0:
            data_to_plot.append(class_data)
            labels.append(label_class)
    
    if len(data_to_plot) > 0:
        bp = axes[idx].boxplot(data_to_plot, labels=labels, patch_artist=True)
        for patch in bp['boxes']:
            patch.set_facecolor('lightblue')
            patch.set_alpha(0.7)
        axes[idx].set_ylabel(feat)
        axes[idx].set_title(f'Distribuição de {feat} por Classe')
        axes[idx].grid(True, alpha=0.3)
        axes[idx].tick_params(axis='x', rotation=45)

# Remover eixos extras
for idx in range(len(available_viz_features), len(axes)):
    fig.delaxes(axes[idx])

plt.tight_layout()
plt.savefig(PLOTS_DIR / '07_features_by_class.png', dpi=150, bbox_inches='tight')
print(f"✅ Gráfico salvo: {PLOTS_DIR / '07_features_by_class.png'}")
plt.show()


# === CÉLULA 18 ===
# 5. Episódios específicos de basculamento com andadinha
basculamento_episodes = merged_df[
    (merged_df['label_operacional'] == 'BASCULANDO') &
    (merged_df.get('has_short_move', False) == True)
]

if len(basculamento_episodes) > 0:
    n_episodes = min(5, len(basculamento_episodes))
    fig, axes = plt.subplots(n_episodes, 1, figsize=(16, 4 * n_episodes))
    
    if n_episodes == 1:
        axes = [axes]
    
    for ep_idx, episode in basculamento_episodes.head(n_episodes).iterrows():
        # Obter dados do episódio completo
        episode_data = df[
            (df['device_id'] == episode['device_id']) &
            (df['time'] >= episode['t_start'] - pd.Timedelta(seconds=30)) &
            (df['time'] <= episode['t_end'] + pd.Timedelta(seconds=30))
        ].copy()
        
        if len(episode_data) > 0:
            time_rel = (episode_data['time'] - episode['t_start']).dt.total_seconds()
            
            # Plot velocidade
            axes[ep_idx].plot(time_rel, episode_data['speed_kmh'], label='Velocidade', color='blue', linewidth=2)
            axes[ep_idx].axvspan(0, episode['duration_s'], alpha=0.2, color='purple', label='Episódio Basculamento')
            axes[ep_idx].axhline(CONFIG['V_STOP'], color='r', linestyle='--', label=f"V_STOP={CONFIG['V_STOP']} km/h")
            
            # Plot aceleração (eixo secundário)
            ax2 = axes[ep_idx].twinx()
            ax2.plot(time_rel, episode_data['linear_accel_magnitude'], 
                    label='Aceleração', color='orange', linewidth=1, alpha=0.7)
            
            axes[ep_idx].set_xlabel('Tempo (segundos)')
            axes[ep_idx].set_ylabel('Velocidade (km/h)', color='blue')
            ax2.set_ylabel('Aceleração Linear (m/s²)', color='orange')
            axes[ep_idx].set_title(f'Episódio Basculamento com Andadinha - Duração: {episode["duration_s"]:.0f}s')
            axes[ep_idx].grid(True, alpha=0.3)
            axes[ep_idx].legend(loc='upper left')
            ax2.legend(loc='upper right')
    
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / '08_basculamento_episodes.png', dpi=150, bbox_inches='tight')
    print(f"✅ Gráfico salvo: {PLOTS_DIR / '08_basculamento_episodes.png'}")
    plt.show()
else:
    print("⚠️ Nenhum episódio de basculamento com andadinha encontrado para visualizar")


# === CÉLULA 19 ===
# Preparar tabela final para exportação
timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')

# Selecionar colunas principais para exportação
export_cols = [
    'device_id', 't_start', 't_end', 'duration_s', 'is_moving',
    'label_operacional', 'confidence', 'evidence',
    'accel_mean', 'accel_std', 'accel_rms', 'accel_p95', 'accel_p99',
    'peak_count', 'peak_height_mean', 'peak_interval_mean',
    'pitch_delta', 'roll_delta', 'voltage_mean'
]

# Filtrar colunas que existem
available_export_cols = [col for col in export_cols if col in merged_df.columns]
final_df = merged_df[available_export_cols].copy()

# Adicionar colunas faltantes com NaN se necessário
for col in export_cols:
    if col not in final_df.columns:
        final_df[col] = np.nan

# Reordenar colunas
final_df = final_df[export_cols]

# Exportar CSV
csv_filename = OUTPUT_DIR / f'labeled_segments_{timestamp_str}.csv'
final_df.to_csv(csv_filename, index=False)
print(f"✅ CSV exportado: {csv_filename}")
print(f"   Registros: {len(final_df):,}")

# Exportar Parquet
parquet_filename = OUTPUT_DIR / f'labeled_segments_{timestamp_str}.parquet'
final_df.to_parquet(parquet_filename, index=False, engine='pyarrow')
print(f"✅ Parquet exportado: {parquet_filename}")

# Estatísticas finais
print(f"\n📊 Estatísticas Finais:")
print(f"   Total de segmentos: {len(final_df)}")
print(f"   Segmentos PARADO: {len(final_df[final_df['is_moving'] == False])}")
print(f"   Segmentos MOVIMENTO: {len(final_df[final_df['is_moving'] == True])}")
print(f"\n📈 Distribuição de rótulos:")
print(final_df['label_operacional'].value_counts())
print(f"\n📊 Confiança média por rótulo:")
print(final_df.groupby('label_operacional')['confidence'].agg(['mean', 'std', 'min', 'max']))

