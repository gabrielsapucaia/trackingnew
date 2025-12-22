import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Carregar os dados dos períodos
print("Carregando dados dos períodos de parada...")
df = pd.read_csv('amostra/periodos_vibracao_detalhado.csv')

print(f"Total de períodos carregados: {len(df)}")

# Verificar as colunas disponíveis
print(f"Colunas disponíveis: {list(df.columns)}")

# Definir as categorias de duração (5 categorias)
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

# Aplicar categorização de duração se não existir
if 'duration_category' not in df.columns:
    df['duration_category'] = df['duration_minutes'].apply(categorize_duration)

# Verificar as categorias de vibração presentes
print("\n=== CATEGORIAS DE VIBRAÇÃO PRESENTES ===")
vibration_categories = df['vibration_level'].value_counts()
print(vibration_categories)

# Filtrar apenas as 3 categorias principais que apareceram
main_vibration_categories = ['Alta (0.01 - 0.1)', 'Muito Alta (> 0.1)', 'Média (0.001 - 0.01)']
df_filtered = df[df['vibration_level'].isin(main_vibration_categories)]

print(f"\nPeríodos após filtro: {len(df_filtered)}")

# Criar a matriz de contingência 5x3
print("\n=== MATRIZ DE CONTINGÊNCIA: DURAÇÃO vs VIBRAÇÃO ===")

# Definir a ordem das categorias
duration_order = ['Muito Curto (< 1 min)', 'Curto (1-5 min)', 'Médio (5-15 min)', 'Longo (15-60 min)', 'Muito Longo (> 1h)']
vibration_order = ['Média (0.001 - 0.01)', 'Alta (0.01 - 0.1)', 'Muito Alta (> 0.1)']

# Criar a matriz
contingency_matrix = pd.crosstab(df_filtered['duration_category'], df_filtered['vibration_level'],
                                margins=True, margins_name='Total')

# Reordenar as colunas e linhas
contingency_matrix = contingency_matrix.reindex(duration_order + ['Total'])
contingency_matrix = contingency_matrix[vibration_order + ['Total']]

print(contingency_matrix)

# Calcular percentuais
print("\n=== PERCENTUAIS POR LINHA (DURAÇÃO) ===")
contingency_percent_row = pd.crosstab(df_filtered['duration_category'], df_filtered['vibration_level'],
                                     normalize='index') * 100
contingency_percent_row = contingency_percent_row[vibration_order]
print(contingency_percent_row.round(2))

print("\n=== PERCENTUAIS POR COLUNA (VIBRAÇÃO) ===")
contingency_percent_col = pd.crosstab(df_filtered['duration_category'], df_filtered['vibration_level'],
                                     normalize='columns') * 100
contingency_percent_col = contingency_percent_col[vibration_order]
print(contingency_percent_col.round(2))

# Estatísticas detalhadas por combinação
print("\n=== ESTATÍSTICAS DETALHADAS POR COMBINAÇÃO ===")
for duration_cat in duration_order:
    for vibration_cat in vibration_order:
        subset = df_filtered[(df_filtered['duration_category'] == duration_cat) &
                           (df_filtered['vibration_level'] == vibration_cat)]
        if len(subset) > 0:
            print(f"\n{duration_cat} + {vibration_cat}:")
            print(f"  Quantidade: {len(subset)} ocorrências")
            print(f"  Duração média: {subset['duration_minutes'].mean():.3f} minutos")
            print(f"  Vibração média: {subset['avg_vibration'].mean():.6f}")
            print(f"  Vibração máxima: {subset['max_vibration'].max():.6f}")
            print(f"  Vibração mínima: {subset['min_vibration'].min():.6f}")
        else:
            print(f"\n{duration_cat} + {vibration_cat}: 0 ocorrências")

# Criar visualização
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

# 1. Matriz de contingência como heatmap
im1 = ax1.imshow(contingency_matrix.iloc[:-1, :-1].values, cmap='Blues', aspect='auto')
ax1.set_title('Matriz Cruzada: Duração vs Vibração\n(Número de Ocorrências)')
ax1.set_xlabel('Categoria de Vibração')
ax1.set_ylabel('Categoria de Duração')
ax1.set_xticks(range(len(vibration_order)))
ax1.set_xticklabels(vibration_order, rotation=45, ha='right')
ax1.set_yticks(range(len(duration_order)))
ax1.set_yticklabels(duration_order)

# Adicionar valores nas células
for i in range(len(duration_order)):
    for j in range(len(vibration_order)):
        value = contingency_matrix.iloc[i, j]
        ax1.text(j, i, f'{value}', ha="center", va="center",
                color="white" if value > contingency_matrix.iloc[:-1, :-1].values.max() / 2 else "black",
                fontweight='bold', fontsize=12)

plt.colorbar(im1, ax=ax1, label='Número de Ocorrências')

# 2. Percentuais por linha (duração)
contingency_percent_row_plot = contingency_percent_row.reindex(duration_order)
im2 = ax2.imshow(contingency_percent_row_plot.values, cmap='Reds', aspect='auto')
ax2.set_title('Distribuição de Vibração por Categoria de Duração (%)')
ax2.set_xlabel('Categoria de Vibração')
ax2.set_ylabel('Categoria de Duração')
ax2.set_xticks(range(len(vibration_order)))
ax2.set_xticklabels(vibration_order, rotation=45, ha='right')
ax2.set_yticks(range(len(duration_order)))
ax2.set_yticklabels(duration_order)

# Adicionar valores percentuais
for i in range(len(duration_order)):
    for j in range(len(vibration_order)):
        value = contingency_percent_row_plot.iloc[i, j]
        ax2.text(j, i, f'{value:.1f}%', ha="center", va="center",
                color="white" if value > 50 else "black", fontsize=10)

plt.colorbar(im2, ax=ax2, label='Porcentagem (%)')

# 3. Box plot da vibração por combinação de categorias
category_combinations = []
vibration_values = []

for duration_cat in duration_order:
    for vibration_cat in vibration_order:
        subset = df_filtered[(df_filtered['duration_category'] == duration_cat) &
                           (df_filtered['vibration_level'] == vibration_cat)]
        if len(subset) > 0:
            category_combinations.extend([f'{duration_cat[:15]}...\n{vibration_cat}'] * len(subset))
            vibration_values.extend(subset['avg_vibration'].values)

# Criar box plot apenas se houver dados
if vibration_values:
    unique_combinations = list(set(category_combinations))
    box_data = [np.array(vibration_values)[np.array(category_combinations) == combo] for combo in unique_combinations]

    ax3.boxplot(box_data, tick_labels=unique_combinations)
    ax3.set_title('Vibração por Combinação de Categorias')
    ax3.set_ylabel('Vibração Média (linear_accel_magnitude)')
    ax3.set_xticklabels(unique_combinations, rotation=45, ha='right')
    ax3.set_yscale('log')
    ax3.grid(True, alpha=0.3)
else:
    ax3.text(0.5, 0.5, 'Sem dados suficientes para box plot',
             ha='center', va='center', transform=ax3.transAxes)
    ax3.set_title('Vibração por Combinação de Categorias')

# 4. Scatter plot: duração vs vibração com cores por combinação
colors = {'Média (0.001 - 0.01)': 'blue', 'Alta (0.01 - 0.1)': 'green', 'Muito Alta (> 0.1)': 'red'}
markers = {'Muito Curto (< 1 min)': 'o', 'Curto (1-5 min)': 's', 'Médio (5-15 min)': '^',
          'Longo (15-60 min)': 'D', 'Muito Longo (> 1h)': '*'}

for duration_cat in duration_order:
    for vibration_cat in vibration_order:
        subset = df_filtered[(df_filtered['duration_category'] == duration_cat) &
                           (df_filtered['vibration_level'] == vibration_cat)]
        if len(subset) > 0:
            ax4.scatter(subset['duration_minutes'], subset['avg_vibration'],
                       c=colors[vibration_cat], marker=markers[duration_cat],
                       label=f'{duration_cat[:10]}... + {vibration_cat}',
                       alpha=0.7, s=50)

ax4.set_title('Duração vs Vibração por Tipo de Parada')
ax4.set_xlabel('Duração (minutos)')
ax4.set_ylabel('Vibração Média')
ax4.set_yscale('log')
ax4.set_xscale('log')
ax4.grid(True, alpha=0.3)

# Criar legenda simplificada
legend_elements = []
for vib_cat, color in colors.items():
    legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=color,
                                     markersize=10, label=f'Vibração: {vib_cat}'))

for dur_cat, marker in markers.items():
    legend_elements.append(plt.Line2D([0], [0], marker=marker, color='w', markerfacecolor='gray',
                                     markersize=10, label=f'Duração: {dur_cat[:10]}...'))

ax4.legend(legend_elements, [elem.get_label() for elem in legend_elements],
          bbox_to_anchor=(1.05, 1), loc='upper left')

plt.tight_layout()

# Salvar gráfico
output_file = 'amostra/matriz_duracao_vibracao_15_tipos.png'
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"\nGráfico salvo em: {output_file}")

# Salvar dados detalhados
detailed_file = 'amostra/matriz_duracao_vibracao_detalhado.csv'
df_filtered.to_csv(detailed_file, index=False)
print(f"Dados detalhados salvos em: {detailed_file}")

# Salvar apenas a matriz
matrix_file = 'amostra/matriz_15_tipos_ocorrencias.csv'
contingency_matrix.to_csv(matrix_file)
print(f"Matriz de ocorrências salva em: {matrix_file}")

print("\n=== RESUMO DA ANÁLISE ===")
print(f"Total de combinações analisadas: {len(duration_order)} x {len(vibration_order)} = {len(duration_order) * len(vibration_order)}")
print(f"Total de períodos incluídos: {len(df_filtered)}")
print(f"Períodos excluídos (vibração baixa): {len(df) - len(df_filtered)}")

# Encontrar as combinações mais e menos frequentes
matrix_values = contingency_matrix.iloc[:-1, :-1].values
max_value = matrix_values.max()
min_value = matrix_values.min()

max_indices = np.where(matrix_values == max_value)
min_indices = np.where(matrix_values == min_value)

print("\nCombinação mais frequente:")
for i, j in zip(max_indices[0], max_indices[1]):
    print(f"  {duration_order[i]} + {vibration_order[j]}: {max_value} ocorrências")

print("\nCombinação menos frequente:")
for i, j in zip(min_indices[0], min_indices[1]):
    print(f"  {duration_order[i]} + {vibration_order[j]}: {min_value} ocorrências")

plt.show()
