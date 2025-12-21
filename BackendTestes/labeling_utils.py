"""
Utilitários para pipeline de rotulagem de estados operacionais de caminhões.
Funções reutilizáveis para segmentação, feature engineering e classificação.
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Dict, Optional
from datetime import datetime, timedelta
import psycopg2
from scipy import signal
from scipy.stats import entropy
import warnings
warnings.filterwarnings('ignore')


# Configuração do banco de dados
DB_CONFIG = {
    "host": "10.135.22.3",
    "port": 5432,
    "dbname": "auratracking",
    "user": "aura",
    "password": "aura2025",
    "connect_timeout": 5,
}


def get_db_connection():
    """Estabelece conexão com o banco de dados."""
    return psycopg2.connect(**DB_CONFIG)


def discover_schema() -> Dict[str, List[str]]:
    """
    Descobre automaticamente o schema do banco de dados.
    Retorna dicionário com colunas por categoria.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Listar todas as colunas da tabela telemetry
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'telemetry'
            ORDER BY ordinal_position;
        """)
        
        columns = {}
        for row in cur.fetchall():
            col_name, data_type = row
            if col_name not in columns:
                columns[col_name] = data_type
        
        # Categorizar colunas relevantes
        schema = {
            'timestamp': ['time'],
            'identifiers': ['device_id', 'operator_id'],
            'speed': ['speed', 'speed_kmh'],
            'acceleration': ['accel_x', 'accel_y', 'accel_z', 'accel_magnitude',
                           'linear_accel_x', 'linear_accel_y', 'linear_accel_z', 'linear_accel_magnitude'],
            'orientation': ['pitch', 'roll', 'azimuth'],
            'gyro': ['gyro_x', 'gyro_y', 'gyro_z', 'gyro_magnitude'],
            'gravity': ['gravity_x', 'gravity_y', 'gravity_z'],
            'gps': ['latitude', 'longitude', 'altitude', 'gps_accuracy'],
            'battery': ['battery_level', 'battery_voltage', 'battery_temperature'],
        }
        
        return schema
        
    finally:
        cur.close()
        conn.close()


def check_data_availability() -> Dict:
    """
    Verifica disponibilidade de dados no banco.
    Retorna dict com range de datas e lista de devices.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Range de datas
        cur.execute("SELECT MIN(time), MAX(time), COUNT(*) FROM telemetry;")
        min_time, max_time, count = cur.fetchone()
        
        # Lista de devices
        cur.execute("SELECT DISTINCT device_id FROM telemetry ORDER BY device_id;")
        devices = [row[0] for row in cur.fetchall()]
        
        # Verificar colunas disponíveis
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'telemetry'
            AND column_name IN ('linear_accel_magnitude', 'pitch', 'roll', 'speed_kmh')
            ORDER BY column_name;
        """)
        available_cols = [row[0] for row in cur.fetchall()]
        
        return {
            'min_time': min_time,
            'max_time': max_time,
            'total_records': count,
            'devices': devices,
            'available_columns': available_cols
        }
        
    finally:
        cur.close()
        conn.close()


def query_data(device_ids: List[str], t0: datetime, t1: datetime) -> pd.DataFrame:
    """
    Extrai dados ordenados e limpos para o período especificado.
    
    Args:
        device_ids: Lista de device_ids para filtrar
        t0: Data/hora inicial (timezone-aware ou UTC)
        t1: Data/hora final (timezone-aware ou UTC)
    
    Returns:
        DataFrame com time, device_id e colunas relevantes
    """
    conn = get_db_connection()
    
    # Garantir que datetimes são UTC
    if t0.tzinfo is None:
        t0 = t0.replace(tzinfo=None)
    if t1.tzinfo is None:
        t1 = t1.replace(tzinfo=None)
    
    # Colunas relevantes para análise
    cols = [
        'time', 'device_id',
        'speed_kmh',
        'linear_accel_x', 'linear_accel_y', 'linear_accel_z', 'linear_accel_magnitude',
        'accel_magnitude',
        'pitch', 'roll', 'azimuth',
        'gyro_magnitude',
        'gravity_x', 'gravity_y', 'gravity_z',
        'gps_accuracy',
        'battery_level', 'battery_voltage'
    ]
    
    cols_str = ', '.join(cols)
    placeholders = ', '.join(['%s'] * len(device_ids))
    
    query = f"""
        SELECT {cols_str}
        FROM telemetry
        WHERE device_id IN ({placeholders})
        AND time >= %s AND time <= %s
        ORDER BY device_id, time ASC;
    """
    
    params = list(device_ids) + [t0, t1]
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # Converter time para datetime
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
    
    # Ordenar por device e time
    df = df.sort_values(['device_id', 'time']).reset_index(drop=True)
    
    return df


def find_stop_segments(
    df: pd.DataFrame,
    speed_col: str = 'speed_kmh',
    v_stop: float = 0.5,
    min_stop_sec: float = 30.0,
    gap_sec: float = 5.0
) -> pd.DataFrame:
    """
    Identifica segmentos onde o veículo está parado.
    
    Args:
        df: DataFrame com coluna time e speed_col
        speed_col: Nome da coluna de velocidade
        v_stop: Threshold de velocidade para considerar parado (km/h)
        min_stop_sec: Duração mínima de parada (segundos)
        gap_sec: Tolerância para unir segmentos próximos (segundos)
    
    Returns:
        DataFrame com colunas: device_id, t_start, t_end, duration_s, is_stop
    """
    if df.empty:
        return pd.DataFrame(columns=['device_id', 't_start', 't_end', 'duration_s', 'is_stop'])
    
    segments = []
    
    for device_id in df['device_id'].unique():
        df_device = df[df['device_id'] == device_id].copy().sort_values('time')
        
        if len(df_device) < 2:
            continue
        
        # Calcular diferença de tempo entre registros
        df_device['dt'] = df_device['time'].diff().dt.total_seconds()
        df_device['is_stop'] = df_device[speed_col] <= v_stop
        
        # Encontrar transições
        df_device['transition'] = df_device['is_stop'].diff().fillna(False)
        
        # Identificar início e fim de segmentos
        starts = df_device[df_device['transition'] & df_device['is_stop']].index
        ends = df_device[df_device['transition'] & ~df_device['is_stop']].index
        
        # Tratar caso especial: começa parado
        if df_device.iloc[0]['is_stop']:
            starts = pd.Index([df_device.index[0]]).union(starts).sort_values()
        
        # Tratar caso especial: termina parado
        if df_device.iloc[-1]['is_stop']:
            ends = ends.union(pd.Index([df_device.index[-1]])).sort_values()
        
        # Criar segmentos iniciais
        for start_idx, end_idx in zip(starts, ends):
            if start_idx > end_idx:
                continue
            
            seg_df = df_device.loc[start_idx:end_idx]
            duration = (seg_df['time'].iloc[-1] - seg_df['time'].iloc[0]).total_seconds()
            
            if duration >= min_stop_sec:
                segments.append({
                    'device_id': device_id,
                    't_start': seg_df['time'].iloc[0],
                    't_end': seg_df['time'].iloc[-1],
                    'duration_s': duration,
                    'is_stop': True
                })
    
    if not segments:
        return pd.DataFrame(columns=['device_id', 't_start', 't_end', 'duration_s', 'is_stop'])
    
    segments_df = pd.DataFrame(segments)
    
    # Merge segmentos próximos (dentro de gap_sec)
    merged_segments = []
    for device_id in segments_df['device_id'].unique():
        device_segs = segments_df[segments_df['device_id'] == device_id].sort_values('t_start')
        
        current = device_segs.iloc[0].to_dict()
        
        for _, next_seg in device_segs.iloc[1:].iterrows():
            gap = (next_seg['t_start'] - current['t_end']).total_seconds()
            
            if gap <= gap_sec:
                # Merge
                current['t_end'] = next_seg['t_end']
                current['duration_s'] = (current['t_end'] - current['t_start']).total_seconds()
            else:
                # Finalizar segmento atual e começar novo
                merged_segments.append(current)
                current = next_seg.to_dict()
        
        merged_segments.append(current)
    
    return pd.DataFrame(merged_segments)


def find_moving_segments(
    df: pd.DataFrame,
    speed_col: str = 'speed_kmh',
    v_stop: float = 0.5
) -> pd.DataFrame:
    """
    Identifica segmentos onde o veículo está em movimento.
    Complementar aos segmentos de parada.
    """
    if df.empty:
        return pd.DataFrame(columns=['device_id', 't_start', 't_end', 'duration_s', 'is_stop'])
    
    segments = []
    
    for device_id in df['device_id'].unique():
        df_device = df[df['device_id'] == device_id].copy().sort_values('time')
        
        if len(df_device) < 2:
            continue
        
        df_device['is_moving'] = df_device[speed_col] > v_stop
        df_device['transition'] = df_device['is_moving'].diff().fillna(False)
        
        starts = df_device[df_device['transition'] & df_device['is_moving']].index
        ends = df_device[df_device['transition'] & ~df_device['is_moving']].index
        
        if df_device.iloc[0]['is_moving']:
            starts = pd.Index([df_device.index[0]]).union(starts).sort_values()
        
        if df_device.iloc[-1]['is_moving']:
            ends = ends.union(pd.Index([df_device.index[-1]])).sort_values()
        
        for start_idx, end_idx in zip(starts, ends):
            if start_idx > end_idx:
                continue
            
            seg_df = df_device.loc[start_idx:end_idx]
            duration = (seg_df['time'].iloc[-1] - seg_df['time'].iloc[0]).total_seconds()
            
            segments.append({
                'device_id': device_id,
                't_start': seg_df['time'].iloc[0],
                't_end': seg_df['time'].iloc[-1],
                'duration_s': duration,
                'is_stop': False
            })
    
    if not segments:
        return pd.DataFrame(columns=['device_id', 't_start', 't_end', 'duration_s', 'is_stop'])
    
    return pd.DataFrame(segments)


def merge_basculamento_segments(
    stop_segments: pd.DataFrame,
    moving_segments: pd.DataFrame,
    df: pd.DataFrame,
    max_short_move_sec: float = 30.0,
    max_short_move_speed: float = 5.0
) -> pd.DataFrame:
    """
    Mescla segmentos de parada com movimento curto adjacente para formar episódios de basculamento.
    
    Args:
        stop_segments: Segmentos de parada
        moving_segments: Segmentos de movimento
        df: DataFrame completo com dados
        max_short_move_sec: Duração máxima de movimento curto para considerar basculamento
        max_short_move_speed: Velocidade máxima para considerar movimento curto
    
    Returns:
        DataFrame de segmentos atualizado com merges aplicados
    """
    merged_stops = stop_segments.copy()
    merged_moving = moving_segments.copy()
    
    # Para cada segmento de parada, verificar se há movimento curto adjacente
    for idx, stop_seg in stop_segments.iterrows():
        device_id = stop_seg['device_id']
        stop_end = stop_seg['t_end']
        
        # Procurar movimento curto logo após a parada
        next_moves = moving_segments[
            (moving_segments['device_id'] == device_id) &
            (moving_segments['t_start'] >= stop_end) &
            (moving_segments['t_start'] <= stop_end + timedelta(seconds=max_short_move_sec * 2))
        ]
        
        for _, move_seg in next_moves.iterrows():
            # Verificar se é movimento curto
            if move_seg['duration_s'] <= max_short_move_sec:
                # Verificar velocidade média
                move_data = df[
                    (df['device_id'] == device_id) &
                    (df['time'] >= move_seg['t_start']) &
                    (df['time'] <= move_seg['t_end'])
                ]
                
                if not move_data.empty and move_data['speed_kmh'].mean() <= max_short_move_speed:
                    # Verificar se há parada logo após
                    next_stops = stop_segments[
                        (stop_segments['device_id'] == device_id) &
                        (stop_segments['t_start'] >= move_seg['t_end']) &
                        (stop_segments['t_start'] <= move_seg['t_end'] + timedelta(seconds=max_short_move_sec * 2))
                    ]
                    
                    if not next_stops.empty:
                        # Merge: parada + movimento curto + parada = episódio de basculamento
                        # Marcar para merge (será processado depois)
                        merged_stops.loc[idx, 'basculamento_merge'] = True
                        merged_stops.loc[idx, 'merge_t_end'] = next_stops.iloc[0]['t_end']
    
    return merged_stops


def extract_features(
    df_segment: pd.DataFrame,
    window_sec: float = 10.0
) -> Dict[str, float]:
    """
    Extrai features de um segmento de dados.
    
    Args:
        df_segment: DataFrame com dados do segmento (deve ter coluna 'time')
        window_sec: Tamanho da janela deslizante para algumas features
    
    Returns:
        Dicionário com features extraídas
    """
    features = {}
    
    if df_segment.empty or len(df_segment) < 2:
        return features
    
    # Garantir ordenação por tempo
    df_segment = df_segment.sort_values('time').reset_index(drop=True)
    
    # Calcular dt médio
    dt_mean = df_segment['time'].diff().dt.total_seconds().mean()
    fs = 1.0 / dt_mean if dt_mean > 0 else 1.0  # Frequência de amostragem
    
    # ===== FEATURES DE ACELERAÇÃO LINEAR =====
    if 'linear_accel_magnitude' in df_segment.columns:
        accel_mag = df_segment['linear_accel_magnitude'].dropna()
        
        if len(accel_mag) > 0:
            features['accel_mean'] = accel_mag.mean()
            features['accel_std'] = accel_mag.std()
            features['accel_rms'] = np.sqrt((accel_mag ** 2).mean())
            features['accel_p95'] = accel_mag.quantile(0.95)
            features['accel_p99'] = accel_mag.quantile(0.99)
            features['accel_iqr'] = accel_mag.quantile(0.75) - accel_mag.quantile(0.25)
            features['accel_energy'] = (accel_mag ** 2).sum()
            features['accel_min'] = accel_mag.min()
            features['accel_max'] = accel_mag.max()
            
            # Detecção de picos
            if len(accel_mag) >= 3:
                peaks, properties = signal.find_peaks(
                    accel_mag.values,
                    height=accel_mag.mean() + accel_mag.std(),
                    distance=int(fs * 0.5)  # Mínimo 0.5s entre picos
                )
                
                features['peak_count'] = len(peaks)
                if len(peaks) > 0:
                    peak_heights = accel_mag.iloc[peaks].values
                    features['peak_height_mean'] = peak_heights.mean()
                    features['peak_height_max'] = peak_heights.max()
                    
                    # Intervalos entre picos
                    if len(peaks) > 1:
                        inter_peaks = np.diff(peaks) * dt_mean
                        features['inter_peak_interval_mean'] = inter_peaks.mean()
                        features['inter_peak_interval_std'] = inter_peaks.std()
                    else:
                        features['inter_peak_interval_mean'] = 0.0
                        features['inter_peak_interval_std'] = 0.0
                else:
                    features['peak_count'] = 0
                    features['peak_height_mean'] = 0.0
                    features['peak_height_max'] = 0.0
                    features['inter_peak_interval_mean'] = 0.0
                    features['inter_peak_interval_std'] = 0.0
    
    # ===== FEATURES DE ORIENTAÇÃO =====
    if 'pitch' in df_segment.columns:
        pitch = df_segment['pitch'].dropna()
        if len(pitch) > 0:
            features['pitch_mean'] = pitch.mean()
            features['pitch_std'] = pitch.std()
            features['pitch_delta_total'] = abs(pitch.iloc[-1] - pitch.iloc[0])
            features['pitch_range'] = pitch.max() - pitch.min()
            
            # Monotonicidade (útil para basculamento)
            pitch_diff = pitch.diff().dropna()
            if len(pitch_diff) > 0:
                features['pitch_monotonic'] = 1.0 if (pitch_diff >= 0).all() or (pitch_diff <= 0).all() else 0.0
    
    if 'roll' in df_segment.columns:
        roll = df_segment['roll'].dropna()
        if len(roll) > 0:
            features['roll_mean'] = roll.mean()
            features['roll_std'] = roll.std()
            features['roll_delta_total'] = abs(roll.iloc[-1] - roll.iloc[0])
            features['roll_range'] = roll.max() - roll.min()
    
    # ===== FEATURES ESPECTRAIS =====
    if 'linear_accel_magnitude' in df_segment.columns:
        accel_mag = df_segment['linear_accel_magnitude'].dropna()
        
        if len(accel_mag) >= 10:  # Mínimo para FFT
            # FFT
            fft_vals = np.fft.rfft(accel_mag.values)
            freqs = np.fft.rfftfreq(len(accel_mag), dt_mean)
            power = np.abs(fft_vals) ** 2
            
            # Energia em bandas
            low_band = (freqs >= 0.1) & (freqs <= 1.0)
            high_band = (freqs > 1.0) & (freqs <= 5.0)
            
            features['energy_low_band'] = power[low_band].sum() if low_band.any() else 0.0
            features['energy_high_band'] = power[high_band].sum() if high_band.any() else 0.0
            features['energy_total'] = power.sum()
            
            if features['energy_total'] > 0:
                features['energy_ratio_low'] = features['energy_low_band'] / features['energy_total']
                features['energy_ratio_high'] = features['energy_high_band'] / features['energy_total']
    
    # ===== FEATURES DE ESTABILIDADE =====
    if 'linear_accel_magnitude' in df_segment.columns:
        accel_mag = df_segment['linear_accel_magnitude'].dropna()
        
        if len(accel_mag) >= 3:
            # Change points simples (variação significativa)
            accel_diff = accel_mag.diff().abs()
            threshold = accel_mag.std() * 2
            change_points = (accel_diff > threshold).sum()
            features['n_changepoints'] = change_points
            
            # Variance ratio (primeira metade vs segunda metade)
            mid = len(accel_mag) // 2
            var_first = accel_mag.iloc[:mid].var()
            var_second = accel_mag.iloc[mid:].var()
            
            if var_first > 0:
                features['variance_ratio'] = var_second / var_first
            else:
                features['variance_ratio'] = 1.0
    
    # ===== FEATURES DE GYRO (se disponível) =====
    if 'gyro_magnitude' in df_segment.columns:
        gyro = df_segment['gyro_magnitude'].dropna()
        if len(gyro) > 0:
            features['gyro_mean'] = gyro.mean()
            features['gyro_std'] = gyro.std()
            features['gyro_max'] = gyro.max()
    
    return features


def classify_stop_segment(
    features: Dict[str, float],
    th_conf: float = 0.6
) -> Tuple[str, float, str]:
    """
    Classifica um segmento de parada usando regras heurísticas.
    
    Args:
        features: Dicionário com features extraídas
        th_conf: Threshold mínimo de confiança
    
    Returns:
        (label, confidence, rule_trace)
    """
    scores = {
        'CARREGAMENTO': 0.0,
        'BASCULAMENTO': 0.0,
        'MOTOR_LIGADO': 0.0,
        'MOTOR_DESLIGADO': 0.0
    }
    
    rule_trace = []
    
    # ===== REGRA 1: MOTOR DESLIGADO =====
    # Sinal muito flat, baixa energia e variância
    if features.get('accel_std', 1.0) < 0.1 and features.get('accel_energy', 1000.0) < 10.0:
        scores['MOTOR_DESLIGADO'] += 0.8
        rule_trace.append("Motor desligado: baixa variância e energia")
    
    # ===== REGRA 2: MOTOR LIGADO =====
    # Vibração contínua, energia espectral em banda baixa
    if (features.get('accel_std', 0.0) > 0.2 and 
        features.get('accel_std', 0.0) < 1.0 and
        features.get('energy_ratio_low', 0.0) > 0.6):
        scores['MOTOR_LIGADO'] += 0.7
        rule_trace.append("Motor ligado: vibração contínua, energia banda baixa")
    
    # ===== REGRA 3: CARREGAMENTO =====
    # Picos intermitentes de aceleração (conchadas)
    if (features.get('peak_count', 0) >= 3 and
        features.get('peak_height_mean', 0.0) > 0.5 and
        features.get('inter_peak_interval_mean', 1000.0) > 2.0 and
        features.get('inter_peak_interval_mean', 1000.0) < 30.0):
        scores['CARREGAMENTO'] += 0.8
        rule_trace.append(f"Carregamento: {features.get('peak_count', 0)} picos intermitentes")
    
    # Pitch relativamente estável durante carregamento
    if (features.get('pitch_std', 100.0) < 5.0 and
        features.get('peak_count', 0) >= 2):
        scores['CARREGAMENTO'] += 0.3
        rule_trace.append("Carregamento: pitch estável com picos")
    
    # ===== REGRA 4: BASCULAMENTO =====
    # Variação monótona de pitch (inclinação da caçamba)
    if (features.get('pitch_monotonic', 0.0) == 1.0 and
        features.get('pitch_delta_total', 0.0) > 5.0):
        scores['BASCULAMENTO'] += 0.9
        rule_trace.append(f"Basculamento: pitch monótono, delta={features.get('pitch_delta_total', 0.0):.1f}°")
    
    # Roll também pode variar durante basculamento
    if (features.get('roll_delta_total', 0.0) > 3.0 and
        features.get('pitch_delta_total', 0.0) > 3.0):
        scores['BASCULAMENTO'] += 0.4
        rule_trace.append("Basculamento: variação significativa de pitch e roll")
    
    # ===== NORMALIZAR SCORES =====
    total_score = sum(scores.values())
    if total_score > 0:
        for key in scores:
            scores[key] = scores[key] / total_score
    
    # Selecionar label com maior score
    best_label = max(scores.items(), key=lambda x: x[1])
    label, confidence = best_label
    
    # Se confiança muito baixa, marcar como DESCONHECIDO
    if confidence < th_conf:
        label = 'DESCONHECIDO'
        rule_trace.append(f"Confiança baixa ({confidence:.2f} < {th_conf}), marcado como DESCONHECIDO")
    
    rule_trace_str = " | ".join(rule_trace) if rule_trace else "Nenhuma regra aplicada"
    
    return label, confidence, rule_trace_str

