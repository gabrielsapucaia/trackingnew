import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# Carregar os dados
print("Carregando dados...")
df = pd.read_csv('amostra/telemetria_20251212_20251213.csv')

# Converter colunas
df['time'] = pd.to_datetime(df['time'])
df['speed_kmh'] = df['speed_kmh'].astype(float)
df['linear_accel_magnitude'] = df['linear_accel_magnitude'].astype(float)

print(f"Total de registros: {len(df)}")

# Identificar períodos com velocidade zero
zero_speed_mask = df['speed_kmh'] == 0.0
print(f"Pontos com velocidade zero: {zero_speed_mask.sum()}")

# Adicionar coluna de status de parada
df['is_stopped'] = zero_speed_mask

# Estatísticas da vibração geral
print("\n=== ESTATÍSTICAS DA VIBRAÇÃO ===")
print(f"Vibração média geral: {df['linear_accel_magnitude'].mean():.6f}")
print(f"Vibração mediana geral: {df['linear_accel_magnitude'].median():.6f}")
print(f"Vibração máxima: {df['linear_accel_magnitude'].max():.6f}")
print(f"Vibração mínima: {df['linear_accel_magnitude'].min():.6f}")

# Estatísticas da vibração durante paradas
stopped_vibration = df[df['is_stopped']]['linear_accel_magnitude']
print("\n=== VIBRAÇÃO DURANTE PARADAS (VELOCIDADE = 0) ===")
print(f"Média da vibração em paradas: {stopped_vibration.mean():.6f}")
print(f"Mediana da vibração em paradas: {stopped_vibration.median():.6f}")
print(f"Desvio padrão da vibração em paradas: {stopped_vibration.std():.6f}")
print(f"Vibração máxima em paradas: {stopped_vibration.max():.6f}")
print(f"Vibração mínima em paradas: {stopped_vibration.min():.6f}")

# Estatísticas da vibração durante movimento
moving_vibration = df[~df['is_stopped']]['linear_accel_magnitude']
print("\n=== VIBRAÇÃO DURANTE MOVIMENTO (VELOCIDADE > 0) ===")
print(f"Média da vibração em movimento: {moving_vibration.mean():.6f}")
print(f"Mediana da vibração em movimento: {moving_vibration.median():.6f}")
print(f"Desvio padrão da vibração em movimento: {moving_vibration.std():.6f}")

# Categorizar vibração durante paradas
def categorize_vibration(accel):
    if accel < 0.0001:
        return 'Muito Baixa (< 0.0001)'
    elif accel < 0.001:
        return 'Baixa (0.0001 - 0.001)'
    elif accel < 0.01:
        return 'Média (0.001 - 0.01)'
    elif accel < 0.1:
        return 'Alta (0.01 - 0.1)'
    else:
        return 'Muito Alta (> 0.1)'

df['vibration_category'] = df['linear_accel_magnitude'].apply(categorize_vibration)

# Criar matriz de contingência
print("\n=== MATRIZ DE CONTINGÊNCIA: VELOCIDADE vs VIBRAÇÃO ===")
contingency_matrix = pd.crosstab(df['is_stopped'], df['vibration_category'],
                                margins=True, margins_name='Total')

# Reordenar colunas
vibration_order = ['Muito Baixa (< 0.0001)', 'Baixa (0.0001 - 0.001)',
                  'Média (0.001 - 0.01)', 'Alta (0.01 - 0.1)', 'Muito Alta (> 0.1)']
contingency_matrix = contingency_matrix[vibration_order]

print(contingency_matrix)

# Calcular percentuais
print("\n=== PERCENTUAIS POR STATUS DE VELOCIDADE ===")
contingency_percent = pd.crosstab(df['is_stopped'], df['vibration_category'],
                                 normalize='index') * 100
contingency_percent = contingency_percent[vibration_order]
print(contingency_percent.round(2))

# Análise específica dos períodos de parada
print("\n=== ANÁLISE DETALHADA DOS PERÍODOS DE PARADA ===")

# Agrupar períodos consecutivos de parada
stop_periods = []
start_idx = None

for i, is_stopped in enumerate(df['is_stopped']):
    if is_stopped and start_idx is None:
        start_idx = i
    elif not is_stopped and start_idx is not None:
        stop_periods.append({
            'start_idx': start_idx,
            'end_idx': i-1,
            'start_time': df['time'].iloc[start_idx],
            'end_time': df['time'].iloc[i-1],
            'duration_seconds': (df['time'].iloc[i-1] - df['time'].iloc[start_idx]).total_seconds(),
            'avg_vibration': df['linear_accel_magnitude'].iloc[start_idx:i].mean(),
            'max_vibration': df['linear_accel_magnitude'].iloc[start_idx:i].max(),
            'min_vibration': df['linear_accel_magnitude'].iloc[start_idx:i].min(),
            'std_vibration': df['linear_accel_magnitude'].iloc[start_idx:i].std()
        })
        start_idx = None

# Adicionar último período se necessário
if start_idx is not None:
    stop_periods.append({
        'start_idx': start_idx,
        'end_idx': len(df)-1,
        'start_time': df['time'].iloc[start_idx],
        'end_time': df['time'].iloc[len(df)-1],
        'duration_seconds': (df['time'].iloc[len(df)-1] - df['time'].iloc[start_idx]).total_seconds(),
        'avg_vibration': df['linear_accel_magnitude'].iloc[start_idx:].mean(),
        'max_vibration': df['linear_accel_magnitude'].iloc[start_idx:].max(),
        'min_vibration': df['linear_accel_magnitude'].iloc[start_idx:].min(),
        'std_vibration': df['linear_accel_magnitude'].iloc[start_idx:].std()
    })

periods_df = pd.DataFrame(stop_periods)
periods_df['duration_minutes'] = periods_df['duration_seconds'] / 60

# Classificar vibração média dos períodos
periods_df['vibration_level'] = periods_df['avg_vibration'].apply(categorize_vibration)

print(f"Total de períodos de parada analisados: {len(periods_df)}")

# Estatísticas de vibração por categoria de duração
vibration_by_duration = periods_df.groupby('vibration_level').agg({
    'duration_minutes': ['count', 'mean', 'median', 'min', 'max'],
    'avg_vibration': ['mean', 'std']
}).round(4)

print("\n=== VIBRAÇÃO POR CATEGORIA DE PERÍODO ===")
print(vibration_by_duration)

# Criar visualizações
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

# 1. Distribuição de vibração por status
vibration_data = [df[df['is_stopped']]['linear_accel_magnitude'],
                  df[~df['is_stopped']]['linear_accel_magnitude']]

ax1.hist(vibration_data, bins=50, alpha=0.7, label=['Parado', 'Em Movimento'],
         color=['red', 'blue'], density=True)
ax1.set_title('Distribuição da Vibração: Parado vs Em Movimento')
ax1.set_xlabel('Vibração (linear_accel_magnitude)')
ax1.set_ylabel('Densidade')
ax1.legend()
ax1.set_yscale('log')
ax1.grid(True, alpha=0.3)

# 2. Box plot da vibração por status
ax2.boxplot(vibration_data, labels=['Parado', 'Em Movimento'])
ax2.set_title('Box Plot da Vibração por Status')
ax2.set_ylabel('Vibração (linear_accel_magnitude)')
ax2.set_yscale('log')
ax2.grid(True, alpha=0.3)

# 3. Matriz de contingência como heatmap
contingency_percent_plot = pd.crosstab(df['is_stopped'], df['vibration_category'],
                                      normalize='index') * 100
contingency_percent_plot = contingency_percent_plot[vibration_order]

# Criar heatmap manualmente com matplotlib
im = ax3.imshow(contingency_percent_plot.values, cmap='YlOrRd', aspect='auto')
ax3.set_title('Matriz Cruzada: Status vs Vibração (%)')
ax3.set_xlabel('Categoria de Vibração')
ax3.set_ylabel('Status do Veículo')
ax3.set_xticks(range(len(vibration_order)))
ax3.set_xticklabels(vibration_order, rotation=45, ha='right')
ax3.set_yticks(range(len(contingency_percent_plot.index)))
ax3.set_yticklabels(['Em Movimento', 'Parado'])

# Adicionar valores nas células
for i in range(len(contingency_percent_plot.index)):
    for j in range(len(vibration_order)):
        text = ax3.text(j, i, f'{contingency_percent_plot.values[i, j]:.1f}',
                       ha="center", va="center", color="black", fontsize=10)

# Adicionar colorbar
plt.colorbar(im, ax=ax3, label='Porcentagem (%)')

# 4. Scatter plot: duração vs vibração média dos períodos
colors = {'Muito Baixa (< 0.0001)': 'blue',
          'Baixa (0.0001 - 0.001)': 'green',
          'Média (0.001 - 0.01)': 'orange',
          'Alta (0.01 - 0.1)': 'red',
          'Muito Alta (> 0.1)': 'purple'}

for level in vibration_order:
    subset = periods_df[periods_df['vibration_level'] == level]
    if not subset.empty:
        ax4.scatter(subset['duration_minutes'], subset['avg_vibration'],
                   c=colors[level], label=level, alpha=0.7, s=50)

ax4.set_title('Duração vs Vibração Média dos Períodos de Parada')
ax4.set_xlabel('Duração do Período (minutos)')
ax4.set_ylabel('Vibração Média')
ax4.set_yscale('log')
ax4.legend()
ax4.grid(True, alpha=0.3)

plt.tight_layout()

# Salvar gráfico
output_file = 'amostra/matriz_vibracao_paradas.png'
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"\nGráfico salvo em: {output_file}")

# Salvar dados detalhados
detailed_file = 'amostra/vibracao_paradas_detalhado.csv'
df[['time', 'speed_kmh', 'is_stopped', 'linear_accel_magnitude', 'vibration_category']].to_csv(detailed_file, index=False)
print(f"Dados detalhados salvos em: {detailed_file}")

# Salvar análise dos períodos
periods_file = 'amostra/periodos_vibracao_detalhado.csv'
periods_df.to_csv(periods_file, index=False)
print(f"Análise dos períodos salva em: {periods_file}")

print("\n=== RESUMO DA ANÁLISE ===")
print(f"Total de pontos analisados: {len(df)}")
print(f"Pontos com velocidade zero: {zero_speed_mask.sum()}")
print(f"Porcentagem de parada: {(zero_speed_mask.sum() / len(df) * 100):.1f}%")
print(f"Vibração média geral: {df['linear_accel_magnitude'].mean():.6f}")
print(f"Vibração média em paradas: {stopped_vibration.mean():.6f}")
print("\nMatriz cruzada mostra que durante paradas, a vibração tende a ser mais baixa,")
print("sugerindo diferentes tipos de parada baseada na atividade/vibração do veículo.")

plt.show()
