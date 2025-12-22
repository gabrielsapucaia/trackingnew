import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
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

# Função para extrair features de um período de parada
def extract_vibration_features(period_data):
    """Extrai features da vibração durante um período de parada"""
    vibration = period_data['linear_accel_magnitude'].values

    # Features básicas
    features = {
        'mean_vibration': np.mean(vibration),
        'std_vibration': np.std(vibration),
        'max_vibration': np.max(vibration),
        'min_vibration': np.min(vibration),
        'range_vibration': np.max(vibration) - np.min(vibration),
        'duration_seconds': len(vibration),
    }

    # Detectar picos (padrão de carregamento)
    peaks, properties = find_peaks(vibration,
                                 height=np.mean(vibration) + 0.5 * np.std(vibration),
                                 distance=len(vibration)//20,  # mínimo 5% da duração entre picos
                                 prominence=0.01)

    features.update({
        'num_peaks': len(peaks),
        'peaks_per_minute': len(peaks) / (len(vibration) / 60),  # picos por minuto
        'avg_peak_height': np.mean(properties['peak_heights']) if len(peaks) > 0 else 0,
        'std_peak_height': np.std(properties['peak_heights']) if len(peaks) > 0 else 0,
        'peak_variability': np.std(properties['peak_heights']) / np.mean(properties['peak_heights']) if len(peaks) > 1 else 0,
    })

    # Análise de frequência dos picos
    if len(peaks) > 1:
        peak_intervals = np.diff(peaks)  # intervalos entre picos
        features.update({
            'avg_peak_interval': np.mean(peak_intervals),
            'std_peak_interval': np.std(peak_intervals),
            'regularity_score': 1 / (1 + np.std(peak_intervals) / np.mean(peak_intervals)),  # quanto mais regular, mais próximo de 1
        })
    else:
        features.update({
            'avg_peak_interval': 0,
            'std_peak_interval': 0,
            'regularity_score': 0,
        })

    # Análise de burst (rajadas de atividade)
    rolling_std = pd.Series(vibration).rolling(window=max(1, len(vibration)//10)).std()
    high_activity_periods = (rolling_std > np.mean(rolling_std) + np.std(rolling_std)).sum()

    features.update({
        'high_activity_periods': high_activity_periods,
        'activity_ratio': high_activity_periods / len(vibration),
    })

    return features

# Extrair features de todos os períodos Curto_Alta
print("Extraindo features de vibração...")
all_features = []

for idx, period in curto_alta_periods.iterrows():
    start_time = pd.to_datetime(period['start_time'])
    end_time = pd.to_datetime(period['end_time'])

    # Extrair dados do período
    period_data = df[(df['time'] >= start_time) & (df['time'] <= end_time) & (df['speed_kmh'] == 0.0)]

    if len(period_data) > 0:
        features = extract_vibration_features(period_data)
        features['period_id'] = idx
        features['start_time'] = start_time
        features['end_time'] = end_time
        features['duration_minutes'] = period['duration_minutes']
        all_features.append(features)

features_df = pd.DataFrame(all_features)
print(f"Features extraídas de {len(features_df)} períodos")

# Preparar dados para clustering
feature_cols = ['mean_vibration', 'std_vibration', 'num_peaks', 'peaks_per_minute',
               'peak_variability', 'regularity_score', 'activity_ratio', 'high_activity_periods']

X = features_df[feature_cols].fillna(0)

# Normalizar dados
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Aplicar K-means clustering
print("Aplicando clustering K-means...")
kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
clusters = kmeans.fit_predict(X_scaled)

features_df['cluster'] = clusters

# Avaliar qualidade do clustering
silhouette_avg = silhouette_score(X_scaled, clusters)
print(f"Coeficiente de Silhouette: {silhouette_avg:.3f}")

# Análise dos clusters
print("\n=== ANÁLISE DOS CLUSTERS ===")
cluster_summary = features_df.groupby('cluster').agg({
    'num_peaks': ['count', 'mean', 'std'],
    'peaks_per_minute': ['mean', 'std'],
    'regularity_score': ['mean', 'std'],
    'activity_ratio': ['mean', 'std'],
    'peak_variability': ['mean', 'std'],
    'duration_minutes': ['mean', 'std']
}).round(3)

print(cluster_summary)

# Identificar cluster de carregamento (baseado nos critérios mencionados)
cluster_stats = features_df.groupby('cluster').agg({
    'num_peaks': 'mean',
    'peaks_per_minute': 'mean',
    'regularity_score': 'mean',
    'peak_variability': 'mean'
}).round(3)

print("\n=== IDENTIFICAÇÃO DO CLUSTER DE CARREGAMENTO ===")
print("Critérios para carregamento: muitos picos, alta regularidade, variabilidade moderada")
print(cluster_stats)

# Cluster com maior número de picos e boa regularidade é provável de carregamento
loading_cluster = cluster_stats['num_peaks'].idxmax()
print(f"\nCluster identificado como 'CARREGAMENTO': {loading_cluster}")

# Análise detalhada do cluster de carregamento
loading_periods = features_df[features_df['cluster'] == loading_cluster]
print(f"\nPeríodos no cluster de carregamento: {len(loading_periods)}")

if len(loading_periods) > 0:
    print("Estatísticas do cluster de carregamento:")
    print(f"  Média de picos: {loading_periods['num_peaks'].mean():.1f}")
    print(f"  Picos por minuto: {loading_periods['peaks_per_minute'].mean():.2f}")
    print(f"  Regularidade: {loading_periods['regularity_score'].mean():.3f}")
    print(f"  Variabilidade de picos: {loading_periods['peak_variability'].mean():.3f}")

# Visualizações
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

# 1. Scatter plot: picos vs regularidade por cluster
colors = ['red', 'blue', 'green']
for cluster_id in range(3):
    cluster_data = features_df[features_df['cluster'] == cluster_id]
    ax1.scatter(cluster_data['num_peaks'], cluster_data['regularity_score'],
               c=colors[cluster_id], label=f'Cluster {cluster_id}', alpha=0.7, s=50)

ax1.set_xlabel('Número de Picos')
ax1.set_ylabel('Regularidade dos Picos')
ax1.set_title('Clusters: Número de Picos vs Regularidade')
ax1.legend()
ax1.grid(True, alpha=0.3)

# 2. Distribuição de picos por minuto por cluster
for cluster_id in range(3):
    cluster_data = features_df[features_df['cluster'] == cluster_id]
    ax2.hist(cluster_data['peaks_per_minute'], bins=10, alpha=0.7,
            label=f'Cluster {cluster_id}', color=colors[cluster_id])

ax2.set_xlabel('Picos por Minuto')
ax2.set_ylabel('Frequência')
ax2.set_title('Distribuição de Picos por Minuto por Cluster')
ax2.legend()
ax2.grid(True, alpha=0.3)

# 3. Box plot da variabilidade por cluster
variability_data = [features_df[features_df['cluster'] == i]['peak_variability'] for i in range(3)]
ax3.boxplot(variability_data, labels=[f'Cluster {i}' for i in range(3)])
ax3.set_ylabel('Variabilidade dos Picos')
ax3.set_title('Variabilidade dos Picos por Cluster')
ax3.grid(True, alpha=0.3)

# 4. Scatter plot: atividade vs duração por cluster
for cluster_id in range(3):
    cluster_data = features_df[features_df['cluster'] == cluster_id]
    ax4.scatter(cluster_data['activity_ratio'], cluster_data['duration_minutes'],
               c=colors[cluster_id], label=f'Cluster {cluster_id}', alpha=0.7, s=50)

ax4.set_xlabel('Razão de Atividade')
ax4.set_ylabel('Duração (minutos)')
ax4.set_title('Atividade vs Duração por Cluster')
ax4.legend()
ax4.grid(True, alpha=0.3)

plt.tight_layout()

# Salvar análise
output_dir = 'amostra/analise_ml_carregamento'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

plt.savefig(os.path.join(output_dir, 'clusters_carregamento.png'), dpi=300, bbox_inches='tight')

# Salvar dados dos clusters
features_df.to_csv(os.path.join(output_dir, 'features_clusters_carregamento.csv'), index=False)

# Criar exemplo de padrão de carregamento
if len(loading_periods) > 0:
    # Pegar um exemplo do cluster de carregamento
    example_period = loading_periods.iloc[0]
    period_id = int(example_period['period_id'])
    start_time = example_period['start_time']
    end_time = example_period['end_time']

    # Extrair dados do período
    period_data = df[(df['time'] >= start_time) & (df['time'] <= end_time) & (df['speed_kmh'] == 0.0)]

    if len(period_data) > 0:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        # Gráfico de velocidade
        ax1.plot(period_data['time'], period_data['speed_kmh'], color='blue', linewidth=2)
        ax1.fill_between(period_data['time'], 0, period_data['speed_kmh'].max(), alpha=0.3, color='red')
        ax1.set_ylabel('Velocidade (km/h)')
        ax1.set_title(f'Exemplo de Padrão de Carregamento - Período {period_id}')
        ax1.grid(True, alpha=0.3)

        # Gráfico de vibração com picos destacados
        ax2.plot(period_data['time'], period_data['linear_accel_magnitude'], color='green', linewidth=2)

        # Detectar e destacar picos
        vibration = period_data['linear_accel_magnitude'].values
        peaks, properties = find_peaks(vibration,
                                     height=np.mean(vibration) + 0.5 * np.std(vibration),
                                     distance=len(vibration)//20)

        if len(peaks) > 0:
            ax2.scatter(period_data['time'].iloc[peaks], vibration[peaks],
                       color='red', s=50, zorder=5, label='Picos Detectados')

        ax2.fill_between(period_data['time'], 0, period_data['linear_accel_magnitude'].max(), alpha=0.3, color='red')
        ax2.set_ylabel('Vibração (linear_accel_magnitude)')
        ax2.set_xlabel('Tempo')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f'exemplo_carregamento_periodo_{period_id}.png'), dpi=300, bbox_inches='tight')
        plt.close()

# Criar relatório final
report_file = os.path.join(output_dir, 'relatorio_ml_carregamento.txt')
with open(report_file, 'w', encoding='utf-8') as f:
    f.write("ANÁLISE DE MACHINE LEARNING - PADRÕES DE CARREGAMENTO\n")
    f.write("=" * 60 + "\n\n")
    f.write(f"Total de períodos analisados: {len(features_df)}\n")
    f.write(f"Coeficiente de Silhouette: {silhouette_avg:.3f}\n\n")

    f.write("CLUSTERS IDENTIFICADOS:\n")
    for cluster_id in range(3):
        cluster_data = features_df[features_df['cluster'] == cluster_id]
        f.write(f"\nCluster {cluster_id}: {len(cluster_data)} períodos\n")
        f.write(f"  Média de picos: {cluster_data['num_peaks'].mean():.1f}\n")
        f.write(f"  Picos por minuto: {cluster_data['peaks_per_minute'].mean():.2f}\n")
        f.write(f"  Regularidade: {cluster_data['regularity_score'].mean():.3f}\n")
        f.write(f"  Variabilidade: {cluster_data['peak_variability'].mean():.3f}\n")

    f.write(f"\n\nCLUSTER DE CARREGAMENTO IDENTIFICADO: {loading_cluster}\n")
    f.write("Características típicas:\n")
    f.write("- Múltiplos picos de vibração\n")
    f.write("- Padrão relativamente regular\n")
    f.write("- Atividade intermitente\n")
    f.write("- Vibração moderada a alta\n\n")

    f.write("INTERPRETAÇÃO:\n")
    f.write("- Picos representam 'conchadas' ou ciclos de carregamento\n")
    f.write("- Regularidade indica processo mecânico controlado\n")
    f.write("- Pausas entre picos sugerem tempo de posicionamento/carga\n")

print(f"\nAnálise concluída! Resultados salvos em: {output_dir}")
print(f"- Visualizações dos clusters: clusters_carregamento.png")
print(f"- Dados detalhados: features_clusters_carregamento.csv")
print(f"- Exemplo de carregamento: exemplo_carregamento_periodo_{period_id}.png")
print(f"- Relatório: relatorio_ml_carregamento.txt")

plt.show()
