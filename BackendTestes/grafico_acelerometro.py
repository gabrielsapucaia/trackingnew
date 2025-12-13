# Gráfico simples do Acelerômetro usando matplotlib (nativo do Python)
# Para executar: python grafico_acelerometro.py
# Ou copie o código para uma célula do Jupyter Notebook

import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Conectar ao banco
print("Conectando ao banco de dados...")
conn = psycopg2.connect(
    host="10.135.22.3",
    port=5432,
    dbname="auratracking",
    user="aura",
    password="aura2025",
    connect_timeout=5,
)
cur = conn.cursor()

# Buscar dados das últimas 3 horas
hora_atras = datetime.now() - timedelta(hours=3)
print(f"Buscando dados a partir de: {hora_atras}")

query = """
    SELECT time, device_id, accel_x, accel_y, accel_z, accel_magnitude
    FROM telemetry
    WHERE time >= %s
    ORDER BY time ASC;
"""

cur.execute(query, (hora_atras,))
rows = cur.fetchall()

# Criar DataFrame
df = pd.DataFrame(rows, columns=['time', 'device_id', 'accel_x', 'accel_y', 'accel_z', 'accel_magnitude'])
df['time'] = pd.to_datetime(df['time'])

print(f"\nDados carregados: {len(df)} registros")
print(f"Período: {df['time'].min()} até {df['time'].max()}")
print(f"Dispositivo: {df['device_id'].unique()}")

cur.close()
conn.close()

# Criar gráfico
print("\nCriando gráfico...")

# Criar figura com 2 subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
fig.suptitle('Dados do Acelerômetro - Últimas 3 Horas', fontsize=16, fontweight='bold')

# Gráfico 1: Aceleração X, Y, Z
ax1.plot(df['time'], df['accel_x'], label='X', linewidth=1.5, color='red', alpha=0.7)
ax1.plot(df['time'], df['accel_y'], label='Y', linewidth=1.5, color='green', alpha=0.7)
ax1.plot(df['time'], df['accel_z'], label='Z', linewidth=1.5, color='blue', alpha=0.7)
ax1.set_xlabel('Tempo', fontsize=12)
ax1.set_ylabel('Aceleração (m/s²)', fontsize=12)
ax1.set_title('Aceleração X, Y e Z', fontsize=14)
ax1.legend(loc='best')
ax1.grid(True, alpha=0.3)
ax1.tick_params(axis='x', rotation=45)

# Formatar eixo X para mostrar apenas hora:minuto
import matplotlib.dates as mdates
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))

# Gráfico 2: Magnitude
ax2.plot(df['time'], df['accel_magnitude'], label='Magnitude', linewidth=2, color='black')
ax2.set_xlabel('Tempo', fontsize=12)
ax2.set_ylabel('Magnitude (m/s²)', fontsize=12)
ax2.set_title('Magnitude da Aceleração', fontsize=14)
ax2.legend(loc='best')
ax2.grid(True, alpha=0.3)
ax2.tick_params(axis='x', rotation=45)
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
ax2.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))

# Ajustar layout
plt.tight_layout()

# Mostrar estatísticas
print("\n" + "="*50)
print("Estatísticas do Acelerômetro:")
print("="*50)
print(f"  X - Média: {df['accel_x'].mean():.4f} m/s²")
print(f"     Desvio padrão: {df['accel_x'].std():.4f} m/s²")
print(f"     Min: {df['accel_x'].min():.4f} m/s², Max: {df['accel_x'].max():.4f} m/s²")
print()
print(f"  Y - Média: {df['accel_y'].mean():.4f} m/s²")
print(f"     Desvio padrão: {df['accel_y'].std():.4f} m/s²")
print(f"     Min: {df['accel_y'].min():.4f} m/s², Max: {df['accel_y'].max():.4f} m/s²")
print()
print(f"  Z - Média: {df['accel_z'].mean():.4f} m/s²")
print(f"     Desvio padrão: {df['accel_z'].std():.4f} m/s²")
print(f"     Min: {df['accel_z'].min():.4f} m/s², Max: {df['accel_z'].max():.4f} m/s²")
print()
print(f"  Magnitude - Média: {df['accel_magnitude'].mean():.4f} m/s²")
print(f"              Máximo: {df['accel_magnitude'].max():.4f} m/s²")
print(f"              Mínimo: {df['accel_magnitude'].min():.4f} m/s²")
print("="*50)

# Mostrar gráfico
print("\nGráfico pronto! Fechando a janela para finalizar.")
plt.show()
