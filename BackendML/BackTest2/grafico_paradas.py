import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import numpy as np

# Carregar os dados
print("Carregando dados...")
df = pd.read_csv('amostra/telemetria_20251212_20251213.csv')

# Converter coluna de tempo para datetime
df['time'] = pd.to_datetime(df['time'])

# Converter velocidade para float (alguns valores estão em notação científica)
df['speed_kmh'] = df['speed_kmh'].astype(float)

print(f"Total de registros: {len(df)}")
print(f"Pontos com velocidade zero: {(df['speed_kmh'] == 0.0).sum()}")

# Criar a figura
fig, ax = plt.subplots(figsize=(15, 8))

# Plotar a velocidade ao longo do tempo
ax.plot(df['time'], df['speed_kmh'], color='blue', linewidth=1, alpha=0.7, label='Velocidade (km/h)')

# Identificar períodos com velocidade zero
zero_speed_mask = df['speed_kmh'] == 0.0

# Hachurar as áreas com velocidade zero
if zero_speed_mask.any():
    # Criar patches para hachurar
    from matplotlib.patches import Rectangle
    import matplotlib.transforms as mtransforms

    # Agrupar períodos consecutivos de velocidade zero
    zero_groups = []
    start_idx = None

    for i, is_zero in enumerate(zero_speed_mask):
        if is_zero and start_idx is None:
            start_idx = i
        elif not is_zero and start_idx is not None:
            zero_groups.append((start_idx, i-1))
            start_idx = None

    # Adicionar o último grupo se terminar com velocidade zero
    if start_idx is not None:
        zero_groups.append((start_idx, len(df)-1))

    print(f"Número de períodos de parada: {len(zero_groups)}")

    # Hachurar cada período
    for start_idx, end_idx in zero_groups:
        start_time = df['time'].iloc[start_idx]
        end_time = df['time'].iloc[end_idx]

        # Calcular duração em horas
        duration_hours = (end_time - start_time).total_seconds() / 3600

        # Criar retângulo hachurado
        width = (end_time - start_time).total_seconds() / 3600 / 24  # em dias para matplotlib
        height = ax.get_ylim()[1] - ax.get_ylim()[0]

        rect = Rectangle((mdates.date2num(start_time), ax.get_ylim()[0]),
                        width, height,
                        facecolor='red', alpha=0.3,
                        hatch='///', edgecolor='red', linewidth=0.5)
        ax.add_patch(rect)

# Configurar o gráfico
ax.set_title('Velocidade do Veículo - Períodos de Parada Hachurados\n(Dados: 12/12/2025 - 13/12/2025)',
             fontsize=14, fontweight='bold', pad=20)
ax.set_xlabel('Tempo', fontsize=12)
ax.set_ylabel('Velocidade (km/h)', fontsize=12)

# Formatação do eixo X (tempo)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

# Grade
ax.grid(True, alpha=0.3)

# Legenda
ax.legend()

# Estatísticas no gráfico
total_points = len(df)
zero_points = (df['speed_kmh'] == 0.0).sum()
zero_percentage = (zero_points / total_points) * 100

stats_text = f"""
Total de pontos: {total_points:,}
Pontos com velocidade zero: {zero_points:,}
Porcentagem parada: {zero_percentage:.1f}%
"""

ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
        verticalalignment='top', fontsize=10,
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

# Ajustar layout
plt.tight_layout()

# Salvar o gráfico
output_file = 'amostra/grafico_paradas_hachurado.png'
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"Gráfico salvo em: {output_file}")

# Mostrar o gráfico
plt.show()

print("\nAnálise concluída!")
print(f"Arquivo salvo: {output_file}")
