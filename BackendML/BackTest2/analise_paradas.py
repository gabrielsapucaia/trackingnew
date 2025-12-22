import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta

# Carregar os dados
print("Carregando dados...")
df = pd.read_csv('amostra/telemetria_20251212_20251213.csv')

# Converter coluna de tempo para datetime
df['time'] = pd.to_datetime(df['time'])

# Converter velocidade para float
df['speed_kmh'] = df['speed_kmh'].astype(float)

print(f"Total de registros: {len(df)}")

# Identificar períodos com velocidade zero
zero_speed_mask = df['speed_kmh'] == 0.0
print(f"Pontos com velocidade zero: {zero_speed_mask.sum()}")

# Agrupar períodos consecutivos de velocidade zero
stop_periods = []
start_idx = None
current_period = []

for i, is_zero in enumerate(zero_speed_mask):
    if is_zero:
        if start_idx is None:
            start_idx = i
        current_period.append(i)
    else:
        if start_idx is not None:
            stop_periods.append({
                'start_idx': start_idx,
                'end_idx': i-1,
                'start_time': df['time'].iloc[start_idx],
                'end_time': df['time'].iloc[i-1],
                'duration_seconds': (df['time'].iloc[i-1] - df['time'].iloc[start_idx]).total_seconds(),
                'num_points': len(current_period)
            })
            start_idx = None
            current_period = []

# Adicionar o último período se terminar com velocidade zero
if start_idx is not None:
    stop_periods.append({
        'start_idx': start_idx,
        'end_idx': len(df)-1,
        'start_time': df['time'].iloc[start_idx],
        'end_time': df['time'].iloc[len(df)-1],
        'duration_seconds': (df['time'].iloc[len(df)-1] - df['time'].iloc[start_idx]).total_seconds(),
        'num_points': len(current_period)
    })

print(f"Número total de períodos de parada: {len(stop_periods)}")

# Converter para DataFrame para análise
periods_df = pd.DataFrame(stop_periods)

# Adicionar colunas calculadas
periods_df['duration_minutes'] = periods_df['duration_seconds'] / 60
periods_df['duration_hours'] = periods_df['duration_seconds'] / 3600

# Classificar os períodos por duração
def classify_stop_duration(minutes):
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

periods_df['category'] = periods_df['duration_minutes'].apply(classify_stop_duration)

# Estatísticas gerais
print("\n=== ESTATÍSTICAS GERAIS DOS PERÍODOS DE PARADA ===")
print(f"Total de períodos: {len(periods_df)}")
print(f"Duração média: {periods_df['duration_minutes'].mean():.1f} minutos")
print(f"Duração mediana: {periods_df['duration_minutes'].median():.1f} minutos")
print(f"Duração máxima: {periods_df['duration_minutes'].max():.1f} minutos")
print(f"Duração mínima: {periods_df['duration_minutes'].min():.1f} minutos")

# Distribuição por categoria
print("\n=== DISTRIBUIÇÃO POR CATEGORIA ===")
category_counts = periods_df['category'].value_counts().sort_index()
for category, count in category_counts.items():
    percentage = (count / len(periods_df)) * 100
    print(f"{category}: {count} períodos ({percentage:.1f}%)")

# Análise temporal - distribuição ao longo do dia
periods_df['hour'] = periods_df['start_time'].dt.hour
hourly_distribution = periods_df.groupby('hour').size()

# Criar visualizações
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

# 1. Distribuição de durações
bins = [0, 1, 5, 15, 60, periods_df['duration_minutes'].max()]
labels = ['< 1 min', '1-5 min', '5-15 min', '15-60 min', '> 1h']
periods_df['duration_bins'] = pd.cut(periods_df['duration_minutes'], bins=bins, labels=labels)

duration_counts = periods_df['duration_bins'].value_counts().sort_index()
ax1.bar(range(len(duration_counts)), duration_counts.values)
ax1.set_xticks(range(len(duration_counts)))
ax1.set_xticklabels(duration_counts.index, rotation=45)
ax1.set_title('Distribuição dos Períodos de Parada por Duração')
ax1.set_ylabel('Número de Períodos')
ax1.grid(True, alpha=0.3)

# 2. Histograma de durações
ax2.hist(periods_df['duration_minutes'], bins=50, alpha=0.7, color='skyblue', edgecolor='black')
ax2.set_title('Histograma das Durações dos Períodos de Parada')
ax2.set_xlabel('Duração (minutos)')
ax2.set_ylabel('Frequência')
ax2.axvline(periods_df['duration_minutes'].mean(), color='red', linestyle='--',
           label=f'Média: {periods_df["duration_minutes"].mean():.1f} min')
ax2.axvline(periods_df['duration_minutes'].median(), color='green', linestyle='--',
           label=f'Mediana: {periods_df["duration_minutes"].median():.1f} min')
ax2.legend()
ax2.grid(True, alpha=0.3)

# 3. Distribuição horária
ax3.bar(hourly_distribution.index, hourly_distribution.values, alpha=0.7, color='orange')
ax3.set_title('Distribuição dos Períodos de Parada por Hora do Dia')
ax3.set_xlabel('Hora do Dia')
ax3.set_ylabel('Número de Períodos')
ax3.set_xticks(range(0, 24, 2))
ax3.grid(True, alpha=0.3)

# 4. Box plot por categoria
categories_order = ['Muito Curto (< 1 min)', 'Curto (1-5 min)', 'Médio (5-15 min)', 'Longo (15-60 min)', 'Muito Longo (> 1h)']
box_data = [periods_df[periods_df['category'] == cat]['duration_minutes'] for cat in categories_order if cat in periods_df['category'].values]

ax4.boxplot(box_data, labels=[cat for cat in categories_order if cat in periods_df['category'].values])
ax4.set_title('Box Plot das Durações por Categoria')
ax4.set_ylabel('Duração (minutos)')
ax4.grid(True, alpha=0.3)

plt.tight_layout()

# Salvar gráfico
output_file = 'amostra/analise_grupos_paradas.png'
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"\nGráfico salvo em: {output_file}")

# Salvar dados dos períodos
periods_summary_file = 'amostra/periodos_parada_detalhado.csv'
periods_df.to_csv(periods_summary_file, index=False)
print(f"Dados detalhados salvos em: {periods_summary_file}")

# Mostrar estatísticas detalhadas por categoria
print("\n=== ESTATÍSTICAS DETALHADAS POR CATEGORIA ===")
for category in categories_order:
    if category in periods_df['category'].values:
        cat_data = periods_df[periods_df['category'] == category]
        print(f"\n{category}:")
        print(f"  Quantidade: {len(cat_data)} períodos")
        print(f"  Duração média: {cat_data['duration_minutes'].mean():.1f} minutos")
        print(f"  Duração mediana: {cat_data['duration_minutes'].median():.1f} minutos")
        print(f"  Duração máxima: {cat_data['duration_minutes'].max():.1f} minutos")
        print(f"  Duração mínima: {cat_data['duration_minutes'].min():.1f} minutos")

print(f"\n=== ANÁLISE CONCLUÍDA ===")
print(f"Total de períodos analisados: {len(periods_df)}")
print(f"Arquivo de análise visual: {output_file}")
print(f"Arquivo de dados detalhados: {periods_summary_file}")

# Mostrar o gráfico
plt.show()
