# Código para copiar e colar em uma célula do Jupyter Notebook
# Gráfico Interativo do Acelerômetro - Janela de 10 minutos com navegação

import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.widgets import Button
from datetime import datetime, timedelta

# Conectar ao banco
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

cur.close()
conn.close()

# Variáveis globais para controle da janela
window_minutes = 10  # Tamanho da janela em minutos
step_minutes = 5     # Passo de navegação em minutos
current_start = df['time'].min()
current_end = current_start + timedelta(minutes=window_minutes)

# Criar figura e eixos
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
fig.suptitle('Dados do Acelerometro - Janela de 10 minutos', fontsize=16, fontweight='bold')

# Função para atualizar o gráfico
def update_plot():
    global current_start, current_end
    
    # Filtrar dados para a janela atual
    mask = (df['time'] >= current_start) & (df['time'] <= current_end)
    df_window = df[mask].copy()
    
    # Limpar eixos
    ax1.clear()
    ax2.clear()
    
    if len(df_window) > 0:
        # Gráfico 1: Aceleração X, Y, Z
        ax1.plot(df_window['time'], df_window['accel_x'], label='X', linewidth=1.5, color='red', alpha=0.7)
        ax1.plot(df_window['time'], df_window['accel_y'], label='Y', linewidth=1.5, color='green', alpha=0.7)
        ax1.plot(df_window['time'], df_window['accel_z'], label='Z', linewidth=1.5, color='blue', alpha=0.7)
        ax1.set_xlabel('Tempo', fontsize=12)
        ax1.set_ylabel('Aceleracao (m/s²)', fontsize=12)
        ax1.set_title(f'Aceleracao X, Y e Z - {current_start.strftime("%H:%M")} ate {current_end.strftime("%H:%M")}', fontsize=14)
        ax1.legend(loc='best')
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='x', rotation=45)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=2))
        
        # Gráfico 2: Magnitude
        ax2.plot(df_window['time'], df_window['accel_magnitude'], label='Magnitude', linewidth=2, color='black')
        ax2.set_xlabel('Tempo', fontsize=12)
        ax2.set_ylabel('Magnitude (m/s²)', fontsize=12)
        ax2.set_title('Magnitude da Aceleracao', fontsize=14)
        ax2.legend(loc='best')
        ax2.grid(True, alpha=0.3)
        ax2.tick_params(axis='x', rotation=45)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax2.xaxis.set_major_locator(mdates.MinuteLocator(interval=2))
        
        # Estatísticas da janela atual
        stats_text = f"Janela: {len(df_window)} pontos | "
        stats_text += f"X: μ={df_window['accel_x'].mean():.2f} | "
        stats_text += f"Y: μ={df_window['accel_y'].mean():.2f} | "
        stats_text += f"Z: μ={df_window['accel_z'].mean():.2f} | "
        stats_text += f"Mag: μ={df_window['accel_magnitude'].mean():.2f}"
        fig.text(0.5, 0.02, stats_text, ha='center', fontsize=10, 
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout(rect=[0, 0.08, 1, 0.98])
    plt.draw()

# Funções de navegação
def anterior(event):
    global current_start, current_end
    new_start = current_start - timedelta(minutes=step_minutes)
    if new_start >= df['time'].min():
        current_start = new_start
        current_end = current_start + timedelta(minutes=window_minutes)
        update_plot()

def proximo(event):
    global current_start, current_end
    new_start = current_start + timedelta(minutes=step_minutes)
    new_end = new_start + timedelta(minutes=window_minutes)
    if new_end <= df['time'].max():
        current_start = new_start
        current_end = new_end
        update_plot()

def inicio(event):
    global current_start, current_end
    current_start = df['time'].min()
    current_end = current_start + timedelta(minutes=window_minutes)
    update_plot()

def fim(event):
    global current_start, current_end
    current_end = df['time'].max()
    current_start = current_end - timedelta(minutes=window_minutes)
    update_plot()

# Criar botões de navegação
ax_prev = plt.axes([0.1, 0.02, 0.1, 0.04])
ax_next = plt.axes([0.25, 0.02, 0.1, 0.04])
ax_inicio = plt.axes([0.4, 0.02, 0.1, 0.04])
ax_fim = plt.axes([0.55, 0.02, 0.1, 0.04])

btn_prev = Button(ax_prev, '< Anterior\n(-5 min)')
btn_next = Button(ax_next, 'Proximo >\n(+5 min)')
btn_inicio = Button(ax_inicio, '<< Inicio')
btn_fim = Button(ax_fim, 'Fim >>')

btn_prev.on_clicked(anterior)
btn_next.on_clicked(proximo)
btn_inicio.on_clicked(inicio)
btn_fim.on_clicked(fim)

# Plotar gráfico inicial
update_plot()

plt.show()


