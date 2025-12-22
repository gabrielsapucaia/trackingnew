import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from datetime import datetime, timedelta
import os

# Carregar dados
print("Carregando dados para análise final refinada...")
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

# Filtrar períodos Curto_Alta e Medio_Alta/Medio_Media
target_periods = periods_df[
    ((periods_df['duration_category'] == 'Curto (1-5 min)') & (periods_df['vibration_level'] == 'Alta (0.01 - 0.1)')) |
    ((periods_df['duration_category'] == 'Médio (5-15 min)') & (periods_df['vibration_level'].isin(['Alta (0.01 - 0.1)', 'Média (0.001 - 0.01)'])))
]

print(f"Encontrados {len(target_periods)} períodos para análise final")

# Função FINAL refinada para extrair features de carregamento
def extract_loading_features_final(period_data, duration_minutes):
    """Extrai features específicas para identificar padrões de carregamento (versão final rigorosa)"""
    vibration = period_data['linear_accel_magnitude'].values

    # Ajustar parâmetros de detecção baseado na duração
    if duration_minutes < 5:
        # Períodos curtos: picos mais próximos e frequentes
        height_threshold = np.mean(vibration) + 0.3 * np.std(vibration)
        min_distance = len(vibration) // 15
        prominence = 0.005
    else:
        # Períodos médios: picos devem ser mais frequentes e regulares
        height_threshold = np.mean(vibration) + 0.25 * np.std(vibration)
        min_distance = len(vibration) // 25  # Mais frequentes
        prominence = 0.004

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

    if len(peaks) >= 2:
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

        # NOVAS REGRAS MAIS RIGOROSAS PARA CARREGAMENTO
        # Baseadas no feedback do usuário sobre falsos positivos
        
        if duration_minutes < 5:
            # Períodos curtos: padrão mais claro
            min_peaks = 3
            min_peaks_per_min = 1.8  # Mais frequente
            min_regularity = 0.4  # Mais regular
            max_variability = 1.2  # Menos variável
        else:
            # Períodos médios: critérios MUITO mais rigorosos
            min_peaks = 5  # Mais picos necessários
            min_peaks_per_min = 1.2  # Frequência mínima maior
            min_regularity = 0.5  # Regularidade maior
            max_variability = 1.0  # Variabilidade muito baixa
        
        # Verificar distribuição temporal dos picos
        # Picos devem estar distribuídos ao longo do período, não concentrados
        if len(peaks) > 0:
            peak_positions = peaks / len(vibration)  # Posição relativa no período
            peak_distribution = np.std(peak_positions)  # Quanto mais distribuído, maior o std
            min_distribution = 0.15  # Picos devem estar bem distribuídos
        else:
            peak_distribution = 0
            min_distribution = 0

        # Verificar se há muitos picos muito próximos (ruído) vs picos bem espaçados (padrão)
        interval_cv = np.std(peak_intervals) / np.mean(peak_intervals) if np.mean(peak_intervals) > 0 else 999
        max_interval_cv = 0.6  # Coeficiente de variação dos intervalos deve ser baixo

        is_loading = (
            len(peaks) >= min_peaks and
            features['peaks_per_minute'] >= min_peaks_per_min and
            features['regularity_score'] >= min_regularity and
            features['peak_variability'] <= max_variability and
            peak_distribution >= min_distribution and
            interval_cv <= max_interval_cv
        )

        # Score de confiança ajustado
        base_score = min(1.0, len(peaks) / 10)
        regularity_bonus = features['regularity_score'] * 0.3
        frequency_bonus = min(0.3, features['peaks_per_minute'] / 5)
        variability_penalty = max(0, (max_variability - features['peak_variability']) / max_variability) * 0.2
        distribution_bonus = min(0.1, peak_distribution / 0.3) if peak_distribution >= min_distribution else 0
        
        features['is_loading_pattern'] = is_loading
        features['confidence_score'] = min(1.0, base_score + regularity_bonus + frequency_bonus + variability_penalty + distribution_bonus)
        features['peak_distribution'] = peak_distribution
        features['interval_cv'] = interval_cv
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
            'peak_distribution': 0,
            'interval_cv': 999,
        })

    return features, peaks, properties

# Analisar todos os períodos
print("Analisando padrões de carregamento (versão final rigorosa)...")
loading_candidates = []
all_features = []

for idx, period in target_periods.iterrows():
    start_time = pd.to_datetime(period['start_time'])
    end_time = pd.to_datetime(period['end_time'])
    duration_minutes = period['duration_minutes']

    # Extrair dados do período
    period_data = df[(df['time'] >= start_time) & (df['time'] <= end_time) & (df['speed_kmh'] == 0.0)]

    if len(period_data) > 5:
        features, peaks, properties = extract_loading_features_final(period_data, duration_minutes)
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
    print("\n=== ESTATÍSTICAS DOS PADRÕES DE CARREGAMENTO (FINAL) ===")
    print(f"Picos por minuto médio: {loading_df['peaks_per_minute'].mean():.2f}")
    print(f"Regularidade média: {loading_df['regularity_score'].mean():.3f}")
    print(f"Variabilidade média: {loading_df['peak_variability'].mean():.3f}")
    print(f"Confiança média: {loading_df['confidence_score'].mean():.3f}")
    print(f"Duração média: {loading_df['duration_minutes'].mean():.2f} minutos")
    
    print("\nDistribuição por categoria:")
    print(loading_df.groupby(['duration_category', 'vibration_level']).size())

# Verificar se período 424 foi excluído
period_424 = features_df[features_df['period_id'] == 424]
if len(period_424) > 0:
    print(f"\nPeríodo 424:")
    print(f"  Identificado como carregamento: {period_424.iloc[0]['is_loading_pattern']}")
    print(f"  Picos: {period_424.iloc[0]['num_peaks']}")
    print(f"  Picos/min: {period_424.iloc[0]['peaks_per_minute']:.2f}")
    print(f"  Regularidade: {period_424.iloc[0]['regularity_score']:.3f}")
    print(f"  Variabilidade: {period_424.iloc[0]['peak_variability']:.3f}")
    print(f"  Distribuição: {period_424.iloc[0]['peak_distribution']:.3f}")

# Visualizações
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

# 1. Scatter: regularidade vs variabilidade
colors_map = {'Curto (1-5 min)': 'blue', 'Médio (5-15 min)': 'orange'}
for cat in features_df['duration_category'].unique():
    cat_data = features_df[features_df['duration_category'] == cat]
    ax1.scatter(cat_data['regularity_score'], cat_data['peak_variability'],
               c=colors_map.get(cat, 'gray'), label=cat, alpha=0.6, s=50)

if len(loading_df) > 0:
    for cat in loading_df['duration_category'].unique():
        loading_cat = loading_df[loading_df['duration_category'] == cat]
        ax1.scatter(loading_cat['regularity_score'], loading_cat['peak_variability'],
                   c=colors_map.get(cat, 'red'), s=100, marker='*',
                   label=f'{cat} - Carregamento', edgecolors='black', linewidths=1)

# Adicionar linha de corte
ax1.axhline(y=1.2, color='red', linestyle='--', alpha=0.5, label='Limite variabilidade (curto)')
ax1.axhline(y=1.0, color='orange', linestyle='--', alpha=0.5, label='Limite variabilidade (médio)')
ax1.axvline(x=0.4, color='blue', linestyle='--', alpha=0.5, label='Limite regularidade (curto)')
ax1.axvline(x=0.5, color='orange', linestyle='--', alpha=0.5, label='Limite regularidade (médio)')

ax1.set_xlabel('Regularidade')
ax1.set_ylabel('Variabilidade')
ax1.set_title('Regularidade vs Variabilidade (Critérios Finais)')
ax1.legend()
ax1.grid(True, alpha=0.3)

# 2. Scatter: picos por minuto vs distribuição
ax2.scatter(features_df['peaks_per_minute'], features_df['peak_distribution'],
           alpha=0.6, color='lightcoral', label='Todos', s=50)
if len(loading_df) > 0:
    ax2.scatter(loading_df['peaks_per_minute'], loading_df['peak_distribution'],
               color='red', s=100, label='Carregamento', marker='*', edgecolors='black')
ax2.axhline(y=0.15, color='red', linestyle='--', alpha=0.5, label='Limite distribuição')
ax2.set_xlabel('Picos por Minuto')
ax2.set_ylabel('Distribuição dos Picos')
ax2.set_title('Frequência vs Distribuição Temporal')
ax2.legend()
ax2.grid(True, alpha=0.3)

# 3. Histograma: coeficiente de variação dos intervalos
ax3.hist(features_df['interval_cv'], bins=20, alpha=0.7, color='skyblue', edgecolor='black', label='Todos')
if len(loading_df) > 0:
    ax3.hist(loading_df['interval_cv'], bins=20, alpha=0.7, color='red', edgecolor='black', label='Carregamento')
ax3.axvline(x=0.6, color='red', linestyle='--', alpha=0.5, label='Limite CV intervalos')
ax3.set_xlabel('Coeficiente de Variação dos Intervalos')
ax3.set_ylabel('Frequência')
ax3.set_title('Distribuição do CV dos Intervalos')
ax3.legend()
ax3.grid(True, alpha=0.3)

# 4. Comparação: antes vs depois da refinagem
if len(loading_df) > 0:
    ax4.bar(['Curto', 'Médio'], 
           [len(loading_df[loading_df['duration_category'] == 'Curto (1-5 min)']),
            len(loading_df[loading_df['duration_category'] == 'Médio (5-15 min)'])],
           color=['blue', 'orange'], alpha=0.7)
    ax4.set_ylabel('Número de Períodos')
    ax4.set_title('Períodos Identificados por Categoria (Final)')
    ax4.grid(True, alpha=0.3, axis='y')

plt.tight_layout()

# Criar diretório de saída
output_dir = 'amostra/analise_carregamento_final'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

plt.savefig(os.path.join(output_dir, 'analise_final_carregamento.png'), dpi=300, bbox_inches='tight')

# Salvar dados
features_df.to_csv(os.path.join(output_dir, 'features_final_todos.csv'), index=False)
if len(loading_df) > 0:
    loading_df.to_csv(os.path.join(output_dir, 'padroes_carregamento_final.csv'), index=False)

# Criar relatório final
report_file = os.path.join(output_dir, 'relatorio_final.txt')
with open(report_file, 'w', encoding='utf-8') as f:
    f.write("ANÁLISE FINAL DE PADRÕES DE CARREGAMENTO (VERSÃO RIGOROSA)\n")
    f.write("=" * 70 + "\n\n")
    f.write(f"Total de períodos analisados: {len(features_df)}\n")
    f.write(f"Períodos identificados como carregamento: {len(loading_df)}\n")
    f.write(f"Taxa de identificação: {len(loading_df)/len(features_df)*100:.1f}%\n\n")

    f.write("CRITÉRIOS FINAIS RIGOROSOS PARA IDENTIFICAÇÃO:\n")
    f.write("Períodos Curtos (1-5 min):\n")
    f.write("  • Pelo menos 3 picos significativos\n")
    f.write("  • Pelo menos 1.8 picos por minuto\n")
    f.write("  • Regularidade >= 0.4\n")
    f.write("  • Variabilidade <= 1.2\n")
    f.write("  • Distribuição temporal >= 0.15\n")
    f.write("  • CV dos intervalos <= 0.6\n\n")
    
    f.write("Períodos Médios (5-15 min):\n")
    f.write("  • Pelo menos 5 picos significativos\n")
    f.write("  • Pelo menos 1.2 picos por minuto\n")
    f.write("  • Regularidade >= 0.5\n")
    f.write("  • Variabilidade <= 1.0\n")
    f.write("  • Distribuição temporal >= 0.15\n")
    f.write("  • CV dos intervalos <= 0.6\n\n")

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
                   f"regularidade {row['regularity_score']:.3f}, variabilidade {row['peak_variability']:.3f}\n")

print(f"\nAnálise final concluída! Resultados salvos em: {output_dir}")
print(f"- Análise geral: analise_final_carregamento.png")
print(f"- Todos os features: features_final_todos.csv")
if len(loading_df) > 0:
    print(f"- Padrões identificados: padroes_carregamento_final.csv")
print(f"- Relatório: relatorio_final.txt")

print("\nREGRAS FINAIS RIGOROSAS:")
print("Periodos Curtos: >=3 picos, >=1.8 p/min, regularidade >=0.4, variabilidade <=1.2")
print("Periodos Medios: >=5 picos, >=1.2 p/min, regularidade >=0.5, variabilidade <=1.0")
print("Ambos: distribuicao >=0.15, CV intervalos <=0.6")
print(f"\nTotal identificado: {len(loading_df)} periodos de carregamento!")

plt.show()
