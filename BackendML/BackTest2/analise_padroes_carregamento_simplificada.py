import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from datetime import datetime, timedelta
import os

# Carregar dados dos períodos Curto_Alta
print("Carregando dados da classificação Curto_Alta...")
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

# Filtrar apenas períodos Curto_Alta
curto_alta_periods = periods_df[(periods_df['duration_category'] == 'Curto (1-5 min)') &
                               (periods_df['vibration_level'] == 'Alta (0.01 - 0.1)')]

print(f"Encontrados {len(curto_alta_periods)} períodos Curto_Alta")

# Função para extrair features de carregamento
def extract_loading_features(period_data):
    """Extrai features específicas para identificar padrões de carregamento"""
    vibration = period_data['linear_accel_magnitude'].values

    # Detectar picos significativos (conchadas)
    peaks, properties = find_peaks(vibration,
                                 height=np.mean(vibration) + 0.3 * np.std(vibration),
                                 distance=len(vibration)//15,  # mínimo 6.67% da duração entre picos
                                 prominence=0.005,
                                 width=1)

    # Features básicas
    features = {
        'num_peaks': len(peaks),
        'peaks_per_minute': len(peaks) / (len(vibration) / 60),
        'duration_seconds': len(vibration),
    }

    if len(peaks) > 1:
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

        # Classificação baseada em regras
        is_loading = (
            len(peaks) >= 3 and  # Pelo menos 3 picos
            features['peaks_per_minute'] >= 2 and  # Pelo menos 2 picos por minuto
            features['regularity_score'] >= 0.3 and  # Regularidade moderada
            features['peak_variability'] <= 1.5  # Variabilidade controlada
        )

        features['is_loading_pattern'] = is_loading
        features['confidence_score'] = min(1.0, (len(peaks) * features['regularity_score'] * (1/features['peak_variability'])) / 10)
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
print("Analisando padrões de carregamento...")
loading_candidates = []
all_features = []

for idx, period in curto_alta_periods.iterrows():
    start_time = pd.to_datetime(period['start_time'])
    end_time = pd.to_datetime(period['end_time'])

    # Extrair dados do período
    period_data = df[(df['time'] >= start_time) & (df['time'] <= end_time) & (df['speed_kmh'] == 0.0)]

    if len(period_data) > 5:  # Mínimo de pontos para análise
        features, peaks, properties = extract_loading_features(period_data)
        features.update({
            'period_id': idx,
            'start_time': start_time,
            'end_time': end_time,
            'duration_minutes': period['duration_minutes'],
            'peaks_indices': peaks.tolist() if len(peaks) > 0 else []
        })

        all_features.append(features)

        if features['is_loading_pattern']:
            loading_candidates.append(features)

features_df = pd.DataFrame(all_features)
loading_df = pd.DataFrame(loading_candidates)

print(f"\nTotal de períodos analisados: {len(features_df)}")
print(f"Períodos identificados como carregamento: {len(loading_df)}")
print(".1f")

if len(loading_df) > 0:
    print("\n=== ESTATÍSTICAS DOS PADRÕES DE CARREGAMENTO ===")
    print(f"Picos por minuto médio: {loading_df['peaks_per_minute'].mean():.2f}")
    print(f"Regularidade média: {loading_df['regularity_score'].mean():.3f}")
    print(f"Variabilidade média: {loading_df['peak_variability'].mean():.3f}")
    print(f"Confiança média: {loading_df['confidence_score'].mean():.3f}")

# Visualizações
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

# 1. Distribuição de picos por período
ax1.hist(features_df['num_peaks'], bins=20, alpha=0.7, color='skyblue', edgecolor='black')
ax1.axvline(loading_df['num_peaks'].mean() if len(loading_df) > 0 else 0,
           color='red', linestyle='--', label='Média Carregamento')
ax1.set_xlabel('Número de Picos')
ax1.set_ylabel('Frequência')
ax1.set_title('Distribuição do Número de Picos por Período')
ax1.legend()
ax1.grid(True, alpha=0.3)

# 2. Scatter: picos vs regularidade
ax2.scatter(features_df['num_peaks'], features_df['regularity_score'],
           alpha=0.6, color='lightcoral', label='Todos')
if len(loading_df) > 0:
    ax2.scatter(loading_df['num_peaks'], loading_df['regularity_score'],
               color='red', s=80, label='Carregamento')
ax2.set_xlabel('Número de Picos')
ax2.set_ylabel('Regularidade dos Picos')
ax2.set_title('Número de Picos vs Regularidade')
ax2.legend()
ax2.grid(True, alpha=0.3)

# 3. Distribuição de picos por minuto
ax3.hist(features_df['peaks_per_minute'], bins=15, alpha=0.7, color='lightgreen', edgecolor='black')
if len(loading_df) > 0:
    ax3.axvline(loading_df['peaks_per_minute'].mean(),
               color='red', linestyle='--', label='Média Carregamento')
ax3.set_xlabel('Picos por Minuto')
ax3.set_ylabel('Frequência')
ax3.set_title('Distribuição de Picos por Minuto')
ax3.legend()
ax3.grid(True, alpha=0.3)

# 4. Box plot da variabilidade
variability_data = [features_df['peak_variability']]
if len(loading_df) > 0:
    variability_data.append(loading_df['peak_variability'])

ax4.boxplot(variability_data, labels=['Todos', 'Carregamento'] if len(loading_df) > 0 else ['Todos'])
ax4.set_ylabel('Variabilidade dos Picos')
ax4.set_title('Variabilidade dos Picos por Grupo')
ax4.grid(True, alpha=0.3)

plt.tight_layout()

# Criar diretório de saída
output_dir = 'amostra/analise_carregamento_simplificada'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

plt.savefig(os.path.join(output_dir, 'analise_padroes_carregamento.png'), dpi=300, bbox_inches='tight')

# Salvar dados
features_df.to_csv(os.path.join(output_dir, 'features_carregamento_todos.csv'), index=False)
if len(loading_df) > 0:
    loading_df.to_csv(os.path.join(output_dir, 'padroes_carregamento_identificados.csv'), index=False)

# Criar exemplo detalhado de carregamento
if len(loading_df) > 0:
    # Pegar o exemplo com maior confiança
    best_example = loading_df.loc[loading_df['confidence_score'].idxmax()]
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
        ax1.set_title(f'Padrão de Carregamento Identificado - Período {period_id}', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)

        # Gráfico de vibração com picos destacados
        ax2.plot(period_data['time'], period_data['linear_accel_magnitude'],
                color='green', linewidth=2, alpha=0.8, label='Vibração')

        # Detectar e destacar picos
        vibration = period_data['linear_accel_magnitude'].values
        peaks, properties = find_peaks(vibration,
                                     height=np.mean(vibration) + 0.3 * np.std(vibration),
                                     distance=len(vibration)//15)

        if len(peaks) > 0:
            peak_times = period_data['time'].iloc[peaks]
            peak_values = vibration[peaks]
            ax2.scatter(peak_times, peak_values, color='red', s=80, zorder=5,
                       label=f'Picos ({len(peaks)} detectados)')

            # Adicionar linhas verticais nos picos
            for peak_time in peak_times:
                ax2.axvline(x=peak_time, color='red', alpha=0.3, linestyle='--', linewidth=1)

        ax2.fill_between(period_data['time'], 0, period_data['linear_accel_magnitude'].max(),
                        alpha=0.2, color='red')
        ax2.set_ylabel('Vibração (linear_accel_magnitude)', fontsize=12)
        ax2.set_xlabel('Tempo', fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # Adicionar informações do padrão
        info_text = f"""
        PADRÃO DE CARREGAMENTO IDENTIFICADO
        • {len(peaks)} picos detectados
        • {best_example['peaks_per_minute']:.1f} picos por minuto
        • Regularidade: {best_example['regularity_score']:.3f}
        • Confiança: {best_example['confidence_score']:.3f}
        • Duração: {best_example['duration_minutes']:.1f} minutos

        INTERPRETAÇÃO: Padrão característico de carregamento
        com ciclos regulares (conchadas de escavadeira)
        """

        fig.text(0.02, 0.02, info_text, fontsize=10,
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.9),
                verticalalignment='bottom')

        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f'exemplo_detalhado_carregamento_{period_id}.png'),
                   dpi=300, bbox_inches='tight')
        plt.close()

# Criar relatório
report_file = os.path.join(output_dir, 'relatorio_carregamento.txt')
with open(report_file, 'w', encoding='utf-8') as f:
    f.write("ANÁLISE DE PADRÕES DE CARREGAMENTO - CURTO_ALTA\n")
    f.write("=" * 60 + "\n\n")
    f.write(f"Total de períodos analisados: {len(features_df)}\n")
    f.write(f"Períodos identificados como carregamento: {len(loading_df)}\n")
    f.write(".1f")

    if len(loading_df) > 0:
        f.write("\n\nCRITÉRIOS PARA IDENTIFICAÇÃO DE CARREGAMENTO:\n")
        f.write("• Pelo menos 3 picos significativos\n")
        f.write("• Pelo menos 2 picos por minuto\n")
        f.write("• Regularidade moderada (score >= 0.3)\n")
        f.write("• Variabilidade controlada (<= 1.5)\n\n")

        f.write("ESTATÍSTICAS DOS PADRÕES IDENTIFICADOS:\n")
        f.write(f"• Picos por minuto médio: {loading_df['peaks_per_minute'].mean():.2f}\n")
        f.write(f"• Regularidade média: {loading_df['regularity_score'].mean():.3f}\n")
        f.write(f"• Variabilidade média: {loading_df['peak_variability'].mean():.3f}\n")
        f.write(f"• Confiança média: {loading_df['confidence_score'].mean():.3f}\n\n")

        f.write("INTERPRETAÇÃO DO PADRÃO:\n")
        f.write("Os picos identificados representam ciclos de carregamento,\n")
        f.write("provavelmente 'conchadas' de uma escavadeira ou similar.\n")
        f.write("A regularidade indica um processo mecânico controlado,\n")
        f.write("enquanto as pausas entre picos sugerem tempo de\n")
        f.write("posicionamento ou deslocamento do equipamento.\n\n")

        f.write("PERÍODOS IDENTIFICADOS:\n")
        for _, row in loading_df.iterrows():
            f.write(f"• Período {int(row['period_id'])}: {row['num_peaks']} picos, "
                   f"{row['peaks_per_minute']:.1f} p/min, "
                   f"regularidade {row['regularity_score']:.3f}\n")

print(f"\nAnálise concluída! Resultados salvos em: {output_dir}")
print(f"- Análise geral: analise_padroes_carregamento.png")
print(f"- Todos os features: features_carregamento_todos.csv")
if len(loading_df) > 0:
    print(f"- Padrões identificados: padroes_carregamento_identificados.csv")
    print(f"- Exemplo detalhado: exemplo_detalhado_carregamento_{period_id}.png")
print(f"- Relatório: relatorio_carregamento.txt")

print("\nREGRAS EXTRAÍDAS:")
print("1. Padrão de carregamento identificado quando:")
print("   - Pelo menos 3 picos de vibração significativos")
print("   - Frequência >= 2 picos por minuto")
print("   - Regularidade dos intervalos >= 0.3")
print("   - Variabilidade dos picos <= 1.5")
print(f"\n2. {len(loading_df)} dos {len(features_df)} períodos Curto_Alta seguem este padrão!")

plt.show()
