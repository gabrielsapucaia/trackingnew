import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from datetime import datetime, timedelta
import os

# Carregar dados
print("Carregando dados...")
periods_df = pd.read_csv('amostra/periodos_vibracao_detalhado.csv')
df = pd.read_csv('amostra/telemetria_20251212_20251213.csv')

# Converter colunas de tempo
df['time'] = pd.to_datetime(df['time'])
df['speed_kmh'] = df['speed_kmh'].astype(float)
df['linear_accel_magnitude'] = df['linear_accel_magnitude'].astype(float)

# Adicionar categoria de duração se necessário
if 'duration_category' not in periods_df.columns:
    def categorize_duration(minutes):
        if minutes < 1:
            return 'Muito Curto (< 1 min)'
        elif minutes < 5:
            return 'Curto (1-5 min)'
        elif minutes < 15:
            return 'Médio (5-15 min)'
        elif minutes < 60:
            return 'Longo (15-60 min)'
        else:
            return 'Muito Longo (> 1h)'

    periods_df['duration_category'] = periods_df['duration_minutes'].apply(categorize_duration)

# Filtrar períodos para análise
target_periods = periods_df[
    ((periods_df['duration_category'] == 'Curto (1-5 min)') & (periods_df['vibration_level'] == 'Alta (0.01 - 0.1)')) |
    ((periods_df['duration_category'] == 'Médio (5-15 min)') & (periods_df['vibration_level'].isin(['Alta (0.01 - 0.1)', 'Média (0.001 - 0.01)'])))
]

# Função para identificar carregamento (mesma da análise final)
def is_loading_pattern(period_data, duration_minutes):
    """Identifica se um período é carregamento usando critérios finais"""
    vibration = period_data['linear_accel_magnitude'].values

    if duration_minutes < 5:
        height_threshold = np.mean(vibration) + 0.3 * np.std(vibration)
        min_distance = len(vibration) // 15
        prominence = 0.005
        min_peaks = 3
        min_peaks_per_min = 1.8
        min_regularity = 0.4
        max_variability = 1.2
    else:
        height_threshold = np.mean(vibration) + 0.25 * np.std(vibration)
        min_distance = len(vibration) // 25
        prominence = 0.004
        min_peaks = 5
        min_peaks_per_min = 1.2
        min_regularity = 0.5
        max_variability = 1.0

    peaks, properties = find_peaks(vibration,
                                 height=height_threshold,
                                 distance=min_distance,
                                 prominence=prominence,
                                 width=1)

    if len(peaks) < 2:
        return False

    peak_intervals = np.diff(peaks)
    regularity_score = 1 / (1 + np.std(peak_intervals) / np.mean(peak_intervals)) if np.mean(peak_intervals) > 0 else 0
    peak_heights = properties['peak_heights']
    peak_variability = np.std(peak_heights) / np.mean(peak_heights) if np.mean(peak_heights) > 0 else 999

    peak_positions = peaks / len(vibration)
    peak_distribution = np.std(peak_positions)
    interval_cv = np.std(peak_intervals) / np.mean(peak_intervals) if np.mean(peak_intervals) > 0 else 999

    return (
        len(peaks) >= min_peaks and
        len(peaks) / duration_minutes >= min_peaks_per_min and
        regularity_score >= min_regularity and
        peak_variability <= max_variability and
        peak_distribution >= 0.15 and
        interval_cv <= 0.6
    )

# Identificar períodos de carregamento
print("Identificando períodos de carregamento...")
loading_periods = []

for idx, period in target_periods.iterrows():
    start_time = pd.to_datetime(period['start_time'])
    end_time = pd.to_datetime(period['end_time'])
    duration_minutes = period['duration_minutes']

    period_data = df[(df['time'] >= start_time) & (df['time'] <= end_time) & (df['speed_kmh'] == 0.0)]

    if len(period_data) > 5:
        if is_loading_pattern(period_data, duration_minutes):
            loading_periods.append({
                'start_time': start_time,
                'end_time': end_time,
                'period_id': idx
            })

loading_df = pd.DataFrame(loading_periods)
print(f"Períodos de carregamento identificados: {len(loading_df)}")

# Determinar range de tempo dos dados
min_time = df['time'].min()
max_time = df['time'].max()

# Criar janelas de 1 hora
hour_windows = []
current_time = min_time.replace(minute=0, second=0, microsecond=0)

while current_time < max_time:
    window_end = current_time + timedelta(hours=1)
    if window_end > max_time:
        window_end = max_time
    
    # Verificar se há dados nesta janela
    window_data = df[(df['time'] >= current_time) & (df['time'] < window_end)]
    if len(window_data) > 0:
        hour_windows.append({
            'start': current_time,
            'end': window_end
        })
    
    current_time = window_end

print(f"Janelas de 1 hora criadas: {len(hour_windows)}")

# Criar diretório de saída
output_dir = 'amostra/extratos_hora_carregamento'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Gerar gráficos para cada janela de 1 hora
print("\nGerando extratos de 1 hora...")
for i, window in enumerate(hour_windows):
    window_start = window['start']
    window_end = window['end']
    
    # Extrair dados da janela
    window_data = df[(df['time'] >= window_start) & (df['time'] < window_end)].copy()
    
    if len(window_data) == 0:
        continue
    
    # Identificar períodos de carregamento nesta janela
    window_loading = loading_df[
        ((loading_df['start_time'] >= window_start) & (loading_df['start_time'] < window_end)) |
        ((loading_df['end_time'] >= window_start) & (loading_df['end_time'] < window_end)) |
        ((loading_df['start_time'] <= window_start) & (loading_df['end_time'] >= window_end))
    ]
    
    # Criar gráfico
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), sharex=True)
    
    # Gráfico 1: Velocidade
    ax1.plot(window_data['time'], window_data['speed_kmh'], 
            color='blue', linewidth=1.5, alpha=0.8, label='Velocidade')
    
    # Hachurar períodos de carregamento
    for _, loading_period in window_loading.iterrows():
        load_start = max(loading_period['start_time'], window_start)
        load_end = min(loading_period['end_time'], window_end)
        
        mask = (window_data['time'] >= load_start) & (window_data['time'] <= load_end)
        if mask.any():
            ax1.fill_between(window_data['time'], 0, window_data['speed_kmh'].max(),
                           where=mask, alpha=0.4, color='red', hatch='///',
                           label='Carregamento' if window_loading.index[0] == loading_period.name else '')
    
    ax1.set_ylabel('Velocidade (km/h)', fontsize=12)
    ax1.set_title(f'Extrato de 1 Hora - Velocidade\n{window_start.strftime("%d/%m/%Y %H:%M")} - {window_end.strftime("%H:%M")}', 
                 fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)
    
    # Gráfico 2: Vibração
    ax2.plot(window_data['time'], window_data['linear_accel_magnitude'],
            color='green', linewidth=1.5, alpha=0.8, label='Vibração')
    
    # Hachurar períodos de carregamento
    for _, loading_period in window_loading.iterrows():
        load_start = max(loading_period['start_time'], window_start)
        load_end = min(loading_period['end_time'], window_end)
        
        mask = (window_data['time'] >= load_start) & (window_data['time'] <= load_end)
        if mask.any():
            ax2.fill_between(window_data['time'], 0, window_data['linear_accel_magnitude'].max(),
                           where=mask, alpha=0.4, color='red', hatch='///',
                           label='Carregamento' if window_loading.index[0] == loading_period.name else '')
    
    ax2.set_ylabel('Vibração (linear_accel_magnitude)', fontsize=12)
    ax2.set_xlabel('Tempo', fontsize=12)
    ax2.set_title(f'Extrato de 1 Hora - Vibração\n{window_start.strftime("%d/%m/%Y %H:%M")} - {window_end.strftime("%H:%M")}',
                 fontsize=14, fontweight='bold')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)
    
    # Formatação do eixo X
    ax2.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%H:%M'))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
    
    # Adicionar informações
    num_loading = len(window_loading)
    info_text = f"""
    Janela: {window_start.strftime('%H:%M')} - {window_end.strftime('%H:%M')}
    Períodos de carregamento: {num_loading}
    Total de pontos: {len(window_data)}
    """
    
    fig.text(0.02, 0.02, info_text, fontsize=10,
            bbox=dict(boxstyle='round,pad=0.5', facecolor='wheat', alpha=0.8),
            verticalalignment='bottom')
    
    plt.tight_layout()
    
    # Salvar gráfico
    filename = f"extrato_{window_start.strftime('%Y%m%d_%H%M')}_{window_end.strftime('%H%M')}.png"
    filepath = os.path.join(output_dir, filename)
    plt.savefig(filepath, dpi=200, bbox_inches='tight')
    plt.close()
    
    print(f"  Gerado: {filename} ({num_loading} períodos de carregamento)")

# Criar resumo
summary_file = os.path.join(output_dir, 'resumo_extratos.txt')
with open(summary_file, 'w', encoding='utf-8') as f:
    f.write("RESUMO DOS EXTRATOS DE 1 HORA COM PERÍODOS DE CARREGAMENTO\n")
    f.write("=" * 70 + "\n\n")
    f.write(f"Total de períodos de carregamento identificados: {len(loading_df)}\n")
    f.write(f"Total de janelas de 1 hora geradas: {len(hour_windows)}\n\n")
    
    f.write("Distribuição dos períodos de carregamento por hora:\n")
    for i, window in enumerate(hour_windows):
        window_loading = loading_df[
            ((loading_df['start_time'] >= window['start']) & (loading_df['start_time'] < window['end'])) |
            ((loading_df['end_time'] >= window['start']) & (loading_df['end_time'] < window['end'])) |
            ((loading_df['start_time'] <= window['start']) & (loading_df['end_time'] >= window['end']))
        ]
        f.write(f"  {window['start'].strftime('%H:%M')} - {window['end'].strftime('%H:%M')}: "
               f"{len(window_loading)} períodos\n")

print(f"\nExtratos gerados com sucesso!")
print(f"Total de gráficos criados: {len(hour_windows)}")
print(f"Diretório: {output_dir}")
print(f"Resumo: {summary_file}")
