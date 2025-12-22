import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from datetime import datetime, timedelta
import os

# Carregar dados
print("Carregando dados para análise refinada...")
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

# Filtrar períodos Curto_Alta e Medio_Alta/Medio_Media (onde identificamos carregamento)
target_periods = periods_df[
    ((periods_df['duration_category'] == 'Curto (1-5 min)') & (periods_df['vibration_level'] == 'Alta (0.01 - 0.1)')) |
    ((periods_df['duration_category'] == 'Médio (5-15 min)') & (periods_df['vibration_level'].isin(['Alta (0.01 - 0.1)', 'Média (0.001 - 0.01)'])))
]

print(f"Encontrados {len(target_periods)} períodos para análise refinada:")
print(f"  - Curto_Alta: {len(target_periods[(target_periods['duration_category'] == 'Curto (1-5 min)')])}")
print(f"  - Medio_Alta: {len(target_periods[(target_periods['duration_category'] == 'Médio (5-15 min)') & (target_periods['vibration_level'] == 'Alta (0.01 - 0.1)')])}")
print(f"  - Medio_Media: {len(target_periods[(target_periods['duration_category'] == 'Médio (5-15 min)') & (target_periods['vibration_level'] == 'Média (0.001 - 0.01)')])}")

# Função refinada para extrair features de carregamento
def extract_loading_features_refined(period_data, duration_minutes):
    """Extrai features específicas para identificar padrões de carregamento (refinado)"""
    vibration = period_data['linear_accel_magnitude'].values

    # Ajustar parâmetros de detecção baseado na duração
    # Para períodos mais longos, ajustar threshold e distância mínima
    if duration_minutes < 5:
        # Períodos curtos: picos mais próximos
        height_threshold = np.mean(vibration) + 0.3 * np.std(vibration)
        min_distance = len(vibration) // 15
        prominence = 0.005
    else:
        # Períodos médios: picos podem estar mais espaçados
        height_threshold = np.mean(vibration) + 0.2 * np.std(vibration)
        min_distance = len(vibration) // 20
        prominence = 0.003

    # Detectar picos significativos
    peaks, properties = find_peaks(vibration,
                                 height=height_threshold,
                                 distance=min_distance,
                                 prominence=prominence,
                                 width=1)

    # Features básicas
    features = {
        'num_peaks': len(peaks),
        'peaks_per_minute': len(peaks) / duration_minutes if duration_minutes > 0 else 0,
        'duration_seconds': len(vibration),
        'duration_minutes': duration_minutes,
    }

    if len(peaks) >= 2:  # Pelo menos 2 picos para análise
        peak_heights = properties['peak_heights']
        peak_intervals = np.diff(peaks)

        features.update({
            'avg_peak_height': np.mean(peak_heights),
            'std_peak_height': np.std(peak_heights),
            'peak_variability': np.std(peak_heights) / np.mean(peak_heights) if np.mean(peak_heights) > 0 else 0,
            'avg_peak_interval': np.mean(peak_intervals),
            'std_peak_interval': np.std(peak_intervals),
            'regularity_score': 1 / (1 + np.std(peak_intervals) / np.mean(peak_intervals)) if np.mean(peak_intervals) > 0 else 0,
            'min_interval': np.min(peak_intervals),
            'max_interval': np.max(peak_intervals),
        })

        # Regras refinadas para carregamento
        # Ajustadas para períodos mais longos também
        min_peaks = 3 if duration_minutes < 5 else 4  # Períodos longos precisam de mais picos
        min_peaks_per_min = 1.5 if duration_minutes < 5 else 0.8  # Períodos longos podem ter frequência menor
        
        is_loading = (
            len(peaks) >= min_peaks and
            features['peaks_per_minute'] >= min_peaks_per_min and
            features['regularity_score'] >= 0.25 and  # Regularidade um pouco mais flexível
            features['peak_variability'] <= 2.0  # Variabilidade mais flexível para períodos longos
        )

        # Score de confiança ajustado
        base_score = min(1.0, len(peaks) / 10)  # Normalizar por número de picos
        regularity_bonus = features['regularity_score'] * 0.3
        frequency_bonus = min(0.3, features['peaks_per_minute'] / 5)
        variability_penalty = max(0, (2.0 - features['peak_variability']) / 2.0) * 0.2
        
        features['is_loading_pattern'] = is_loading
        features['confidence_score'] = min(1.0, base_score + regularity_bonus + frequency_bonus + variability_penalty)
    else:
        features.update({
            'avg_peak_height': 0,
            'std_peak_height': 0,
            'peak_variability': 0,
            'avg_peak_interval': 0,
            'std_peak_interval': 0,
            'regularity_score': 0,
            'min_interval': 0,
            'max_interval': 0,
            'is_loading_pattern': False,
            'confidence_score': 0,
        })

    return features, peaks, properties

# Analisar todos os períodos
print("\nAnalisando padrões de carregamento (análise refinada)...")
loading_candidates = []
all_features = []

for idx, period in target_periods.iterrows():
    start_time = pd.to_datetime(period['start_time'])
    end_time = pd.to_datetime(period['end_time'])
    duration_minutes = period['duration_minutes']

    # Extrair dados do período
    period_data = df[(df['time'] >= start_time) & (df['time'] <= end_time) & (df['speed_kmh'] == 0.0)]

    if len(period_data) > 5:
        features, peaks, properties = extract_loading_features_refined(period_data, duration_minutes)
        features.update({
            'period_id': idx,
            'start_time': start_time,
            'end_time': end_time,
            'duration_category': period['duration_category'],
            'vibration_level': period['vibration_level'],
            'peaks_indices': peaks.tolist() if len(peaks) > 0 else []
        })

        all_features.append(features)

        if features['is_loading_pattern']:
            loading_candidates.append(features)

features_df = pd.DataFrame(all_features)
loading_df = pd.DataFrame(loading_candidates)

print(f"\nTotal de períodos analisados: {len(features_df)}")
print(f"Períodos identificados como carregamento: {len(loading_df)}")
print(f"Taxa de identificação: {len(loading_df)/len(features_df)*100:.1f}%")

if len(loading_df) > 0:
    print("\n=== ESTATÍSTICAS DOS PADRÕES DE CARREGAMENTO (REFINADO) ===")
    print(f"Picos por minuto médio: {loading_df['peaks_per_minute'].mean():.2f}")
    print(f"Regularidade média: {loading_df['regularity_score'].mean():.3f}")
    print(f"Variabilidade média: {loading_df['peak_variability'].mean():.3f}")
    print(f"Confiança média: {loading_df['confidence_score'].mean():.3f}")
    print(f"Duração média: {loading_df['duration_minutes'].mean():.2f} minutos")
    
    print("\nDistribuição por categoria:")
    print(loading_df.groupby(['duration_category', 'vibration_level']).size())

# Visualizações refinadas
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

# 1. Scatter: duração vs picos por minuto
colors_map = {'Curto (1-5 min)': 'blue', 'Médio (5-15 min)': 'orange'}
for cat in features_df['duration_category'].unique():
    cat_data = features_df[features_df['duration_category'] == cat]
    ax1.scatter(cat_data['duration_minutes'], cat_data['peaks_per_minute'],
               c=colors_map.get(cat, 'gray'), label=cat, alpha=0.6, s=50)

if len(loading_df) > 0:
    for cat in loading_df['duration_category'].unique():
        loading_cat = loading_df[loading_df['duration_category'] == cat]
        ax1.scatter(loading_cat['duration_minutes'], loading_cat['peaks_per_minute'],
                   c=colors_map.get(cat, 'red'), s=100, marker='*',
                   label=f'{cat} - Carregamento', edgecolors='black', linewidths=1)

ax1.set_xlabel('Duração (minutos)')
ax1.set_ylabel('Picos por Minuto')
ax1.set_title('Duração vs Frequência de Picos (Refinado)')
ax1.legend()
ax1.grid(True, alpha=0.3)

# 2. Box plot: regularidade por categoria
regularity_data = []
labels = []
for cat in ['Curto (1-5 min)', 'Médio (5-15 min)']:
    cat_data = features_df[features_df['duration_category'] == cat]
    if len(cat_data) > 0:
        regularity_data.append(cat_data['regularity_score'])
        labels.append(cat)

if len(regularity_data) > 0:
    ax2.boxplot(regularity_data, labels=labels)
    ax2.set_ylabel('Regularidade dos Picos')
    ax2.set_title('Regularidade por Categoria de Duração')
    ax2.grid(True, alpha=0.3)

# 3. Histograma: número de picos
ax3.hist(features_df['num_peaks'], bins=20, alpha=0.7, color='skyblue', edgecolor='black', label='Todos')
if len(loading_df) > 0:
    ax3.hist(loading_df['num_peaks'], bins=20, alpha=0.7, color='red', edgecolor='black', label='Carregamento')
ax3.set_xlabel('Número de Picos')
ax3.set_ylabel('Frequência')
ax3.set_title('Distribuição do Número de Picos')
ax3.legend()
ax3.grid(True, alpha=0.3)

# 4. Scatter: confiança vs regularidade
ax4.scatter(features_df['regularity_score'], features_df['confidence_score'],
           alpha=0.6, color='lightcoral', label='Todos', s=50)
if len(loading_df) > 0:
    ax4.scatter(loading_df['regularity_score'], loading_df['confidence_score'],
               color='red', s=100, label='Carregamento', marker='*', edgecolors='black')
ax4.set_xlabel('Regularidade')
ax4.set_ylabel('Confiança')
ax4.set_title('Regularidade vs Confiança na Identificação')
ax4.legend()
ax4.grid(True, alpha=0.3)

plt.tight_layout()

# Criar diretório de saída
output_dir = 'amostra/analise_carregamento_refinada'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

plt.savefig(os.path.join(output_dir, 'analise_refinada_carregamento.png'), dpi=300, bbox_inches='tight')

# Salvar dados
features_df.to_csv(os.path.join(output_dir, 'features_refinados_todos.csv'), index=False)
if len(loading_df) > 0:
    loading_df.to_csv(os.path.join(output_dir, 'padroes_carregamento_refinados.csv'), index=False)

# Criar exemplos detalhados dos períodos identificados
if len(loading_df) > 0:
    # Exemplo de cada categoria
    for cat in loading_df['duration_category'].unique():
        cat_examples = loading_df[loading_df['duration_category'] == cat]
        if len(cat_examples) > 0:
            # Pegar o exemplo com maior confiança
            best_example = cat_examples.loc[cat_examples['confidence_score'].idxmax()]
            period_id = int(best_example['period_id'])
            start_time = best_example['start_time']
            end_time = best_example['end_time']

            # Extrair dados do período
            period_data = df[(df['time'] >= start_time) & (df['time'] <= end_time) & (df['speed_kmh'] == 0.0)]

            if len(period_data) > 0:
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

                # Gráfico de velocidade
                ax1.plot(period_data['time'], period_data['speed_kmh'], color='blue', linewidth=2, alpha=0.8)
                ax1.fill_between(period_data['time'], 0, period_data['speed_kmh'].max(), alpha=0.3, color='red')
                ax1.set_ylabel('Velocidade (km/h)', fontsize=12)
                ax1.set_title(f'Padrão de Carregamento Refinado - {cat} (Período {period_id})', fontsize=14, fontweight='bold')
                ax1.grid(True, alpha=0.3)

                # Gráfico de vibração com picos destacados
                ax2.plot(period_data['time'], period_data['linear_accel_magnitude'],
                        color='green', linewidth=2, alpha=0.8, label='Vibração')

                # Detectar picos
                vibration = period_data['linear_accel_magnitude'].values
                duration_minutes = best_example['duration_minutes']
                
                if duration_minutes < 5:
                    height_threshold = np.mean(vibration) + 0.3 * np.std(vibration)
                    min_distance = len(vibration) // 15
                else:
                    height_threshold = np.mean(vibration) + 0.2 * np.std(vibration)
                    min_distance = len(vibration) // 20

                peaks, properties = find_peaks(vibration,
                                            height=height_threshold,
                                            distance=min_distance,
                                            prominence=0.003)

                if len(peaks) > 0:
                    peak_times = period_data['time'].iloc[peaks]
                    peak_values = vibration[peaks]
                    ax2.scatter(peak_times, peak_values, color='red', s=80, zorder=5,
                               label=f'Picos ({len(peaks)} detectados)')

                    for peak_time in peak_times:
                        ax2.axvline(x=peak_time, color='red', alpha=0.3, linestyle='--', linewidth=1)

                ax2.fill_between(period_data['time'], 0, period_data['linear_accel_magnitude'].max(),
                                alpha=0.2, color='red')
                ax2.set_ylabel('Vibração (linear_accel_magnitude)', fontsize=12)
                ax2.set_xlabel('Tempo', fontsize=12)
                ax2.legend()
                ax2.grid(True, alpha=0.3)

                # Informações
                info_text = f"""
                PADRÃO DE CARREGAMENTO REFINADO - {cat}
                • {len(peaks)} picos detectados
                • {best_example['peaks_per_minute']:.1f} picos por minuto
                • Regularidade: {best_example['regularity_score']:.3f}
                • Confiança: {best_example['confidence_score']:.3f}
                • Duração: {best_example['duration_minutes']:.1f} minutos
                • Variabilidade: {best_example['peak_variability']:.3f}

                REGRAS REFINADAS APLICADAS:
                • Períodos curtos: ≥3 picos, ≥1.5 p/min
                • Períodos médios: ≥4 picos, ≥0.8 p/min
                • Regularidade ≥0.25, Variabilidade ≤2.0
                """

                fig.text(0.02, 0.02, info_text, fontsize=9,
                        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.9),
                        verticalalignment='bottom')

                plt.tight_layout()
                plt.savefig(os.path.join(output_dir, f'exemplo_refinado_{cat.replace(" ", "_")}_{period_id}.png'),
                           dpi=300, bbox_inches='tight')
                plt.close()

# Criar relatório refinado
report_file = os.path.join(output_dir, 'relatorio_refinado.txt')
with open(report_file, 'w', encoding='utf-8') as f:
    f.write("ANÁLISE REFINADA DE PADRÕES DE CARREGAMENTO\n")
    f.write("=" * 60 + "\n\n")
    f.write(f"Total de períodos analisados: {len(features_df)}\n")
    f.write(f"Períodos identificados como carregamento: {len(loading_df)}\n")
    f.write(f"Taxa de identificação: {len(loading_df)/len(features_df)*100:.1f}%\n\n")

    f.write("CRITÉRIOS REFINADOS PARA IDENTIFICAÇÃO:\n")
    f.write("Períodos Curtos (1-5 min):\n")
    f.write("  • Pelo menos 3 picos significativos\n")
    f.write("  • Pelo menos 1.5 picos por minuto\n")
    f.write("  • Regularidade >= 0.25\n")
    f.write("  • Variabilidade <= 2.0\n\n")
    
    f.write("Períodos Médios (5-15 min):\n")
    f.write("  • Pelo menos 4 picos significativos\n")
    f.write("  • Pelo menos 0.8 picos por minuto\n")
    f.write("  • Regularidade >= 0.25\n")
    f.write("  • Variabilidade <= 2.0\n\n")

    if len(loading_df) > 0:
        f.write("ESTATÍSTICAS DOS PADRÕES IDENTIFICADOS:\n")
        f.write(f"• Picos por minuto médio: {loading_df['peaks_per_minute'].mean():.2f}\n")
        f.write(f"• Regularidade média: {loading_df['regularity_score'].mean():.3f}\n")
        f.write(f"• Variabilidade média: {loading_df['peak_variability'].mean():.3f}\n")
        f.write(f"• Confiança média: {loading_df['confidence_score'].mean():.3f}\n")
        f.write(f"• Duração média: {loading_df['duration_minutes'].mean():.2f} minutos\n\n")

        f.write("DISTRIBUIÇÃO POR CATEGORIA:\n")
        dist = loading_df.groupby(['duration_category', 'vibration_level']).size()
        for (cat, vib), count in dist.items():
            f.write(f"  {cat} + {vib}: {count} períodos\n")

        f.write("\nPERÍODOS IDENTIFICADOS:\n")
        for _, row in loading_df.sort_values('confidence_score', ascending=False).iterrows():
            f.write(f"• Período {int(row['period_id'])} ({row['duration_category']}): "
                   f"{row['num_peaks']} picos, {row['peaks_per_minute']:.1f} p/min, "
                   f"confiança {row['confidence_score']:.3f}\n")

print(f"\nAnálise refinada concluída! Resultados salvos em: {output_dir}")
print(f"- Análise geral: analise_refinada_carregamento.png")
print(f"- Todos os features: features_refinados_todos.csv")
if len(loading_df) > 0:
    print(f"- Padrões identificados: padroes_carregamento_refinados.csv")
print(f"- Relatório: relatorio_refinado.txt")

print("\nREGRAS REFINADAS:")
print("Periodos Curtos (1-5 min): >=3 picos, >=1.5 p/min")
print("Periodos Medios (5-15 min): >=4 picos, >=0.8 p/min")
print("Ambos: Regularidade >=0.25, Variabilidade <=2.0")
print(f"\nTotal identificado: {len(loading_df)} periodos de carregamento!")

plt.show()
