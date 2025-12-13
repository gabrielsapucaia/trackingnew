# Gráfico Interativo Completo: Aceleração Linear (sem gravidade) + Mapa GPS
# Com sincronização ao passar o mouse - mostra linha vertical em todos os gráficos
# Para executar: python grafico_acelerometro_interativo_completo.py

import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.widgets import Button
from matplotlib.patches import Rectangle
from datetime import datetime, timedelta
import numpy as np

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
    SELECT time, device_id, 
           linear_accel_x, linear_accel_y, linear_accel_z, linear_accel_magnitude,
           latitude, longitude, altitude, speed_kmh
    FROM telemetry
    WHERE time >= %s
    ORDER BY time ASC;
"""

cur.execute(query, (hora_atras,))
rows = cur.fetchall()

# Criar DataFrame
df = pd.DataFrame(rows, columns=[
    'time', 'device_id',
    'linear_accel_x', 'linear_accel_y', 'linear_accel_z', 'linear_accel_magnitude',
    'latitude', 'longitude', 'altitude', 'speed_kmh'
])
df['time'] = pd.to_datetime(df['time'])

cur.close()
conn.close()

print(f"Dados carregados: {len(df)} registros")
print(f"Período total: {df['time'].min()} até {df['time'].max()}")

# Variáveis globais
window_minutes = 10
step_minutes = 5
current_start = df['time'].min()
current_end = current_start + timedelta(minutes=window_minutes)
hover_time = None  # Tempo atual do hover
hover_line = None  # Linha vertical do hover

# Criar figura com layout: 3 gráficos de aceleração + 1 mapa
fig = plt.figure(figsize=(18, 12))
fig.suptitle('Aceleracao Linear (SEM gravidade) + Mapa GPS - Janela de 10 minutos', 
             fontsize=16, fontweight='bold')

# Criar subplots
ax1 = plt.subplot(2, 2, 1)  # Aceleração X, Y, Z
ax2 = plt.subplot(2, 2, 2)  # Magnitude
ax3 = plt.subplot(2, 2, 3)  # Mapa GPS
ax4 = plt.subplot(2, 2, 4)  # Velocidade vs Tempo

# Variáveis para armazenar as linhas de hover
hover_lines = {'ax1': None, 'ax2': None, 'ax3': None, 'ax4': None}
hover_marker = None

# Função para encontrar o índice mais próximo de um tempo
def find_nearest_time_index(times, target_time):
    if len(times) == 0:
        return None
    times_array = np.array([t.timestamp() for t in times])
    target_timestamp = target_time.timestamp()
    idx = np.abs(times_array - target_timestamp).argmin()
    return idx

# Função para atualizar linhas de hover em todos os gráficos
def update_hover_lines(hover_time_value):
    global hover_lines, hover_marker
    
    if hover_time_value is None:
        # Remover todas as linhas
        for key in hover_lines:
            if hover_lines[key] is not None:
                hover_lines[key].remove()
                hover_lines[key] = None
        if hover_marker is not None:
            hover_marker.remove()
            hover_marker = None
        plt.draw()
        return
    
    # Filtrar dados da janela atual
    mask = (df['time'] >= current_start) & (df['time'] <= current_end)
    df_window = df[mask].copy()
    
    if len(df_window) == 0:
        return
    
    # Encontrar o ponto mais próximo
    idx = find_nearest_time_index(df_window['time'], hover_time_value)
    if idx is None:
        return
    
    selected_time = df_window['time'].iloc[idx]
    
    # Remover linhas antigas
    for key in hover_lines:
        if hover_lines[key] is not None:
            hover_lines[key].remove()
            hover_lines[key] = None
    if hover_marker is not None:
        hover_marker.remove()
        hover_marker = None
    
    # Adicionar linha vertical no gráfico 1 (Aceleração XYZ)
    if selected_time >= df_window['time'].min() and selected_time <= df_window['time'].max():
        y_min = min(df_window[['linear_accel_x', 'linear_accel_y', 'linear_accel_z']].min())
        y_max = max(df_window[['linear_accel_x', 'linear_accel_y', 'linear_accel_z']].max())
        hover_lines['ax1'] = ax1.axvline(x=selected_time, color='red', linestyle='--', 
                                         linewidth=2, alpha=0.7, zorder=10)
        
        # Adicionar linha vertical no gráfico 2 (Magnitude)
        y_min2 = df_window['linear_accel_magnitude'].min()
        y_max2 = df_window['linear_accel_magnitude'].max()
        hover_lines['ax2'] = ax2.axvline(x=selected_time, color='red', linestyle='--', 
                                         linewidth=2, alpha=0.7, zorder=10)
        
        # Adicionar linha vertical no gráfico 4 (Velocidade)
        if 'speed_kmh' in df_window.columns:
            y_min4 = df_window['speed_kmh'].min()
            y_max4 = df_window['speed_kmh'].max()
            hover_lines['ax4'] = ax4.axvline(x=selected_time, color='red', linestyle='--', 
                                            linewidth=2, alpha=0.7, zorder=10)
        
        # Adicionar marcador no mapa (gráfico 3)
        gps_data = df_window.dropna(subset=['latitude', 'longitude'])
        if len(gps_data) > 0 and idx < len(gps_data):
            gps_idx = gps_data.index.get_loc(df_window.index[idx])
            if gps_idx < len(gps_data):
                hover_marker = ax3.plot(gps_data['longitude'].iloc[gps_idx], 
                                       gps_data['latitude'].iloc[gps_idx],
                                       marker='*', markersize=20, color='red', 
                                       markeredgecolor='black', markeredgewidth=2,
                                       zorder=10, label='Ponto selecionado')
                ax3.legend(loc='best')
    
    plt.draw()

# Função de evento de mouse
def on_mouse_move(event):
    global hover_time
    
    if event.inaxes is None:
        return
    
    # Verificar se o mouse está sobre um dos gráficos de tempo
    if event.inaxes in [ax1, ax2, ax4]:
        # Converter coordenada X do mouse para tempo
        try:
            hover_time_value = mdates.num2date(event.xdata)
            if isinstance(hover_time_value, datetime):
                # Verificar se está dentro da janela atual
                if current_start <= hover_time_value <= current_end:
                    hover_time = hover_time_value
                    update_hover_lines(hover_time_value)
        except:
            pass
    
    # Se o mouse estiver sobre o mapa
    elif event.inaxes == ax3:
        # Encontrar o ponto GPS mais próximo
        mask = (df['time'] >= current_start) & (df['time'] <= current_end)
        df_window = df[mask].copy()
        gps_data = df_window.dropna(subset=['latitude', 'longitude'])
        
        if len(gps_data) > 0:
            # Calcular distância do mouse até cada ponto
            distances = np.sqrt((gps_data['longitude'] - event.xdata)**2 + 
                              (gps_data['latitude'] - event.ydata)**2)
            nearest_idx = distances.idxmin()
            
            if distances.loc[nearest_idx] < 0.001:  # Threshold de proximidade
                selected_time = df_window.loc[nearest_idx, 'time']
                hover_time = selected_time
                update_hover_lines(selected_time)

# Conectar evento de mouse
fig.canvas.mpl_connect('motion_notify_event', on_mouse_move)

# Função para atualizar o gráfico
def update_plot():
    global hover_lines, hover_marker
    
    # Filtrar dados para a janela atual
    mask = (df['time'] >= current_start) & (df['time'] <= current_end)
    df_window = df[mask].copy()
    
    # Limpar eixos
    ax1.clear()
    ax2.clear()
    ax3.clear()
    ax4.clear()
    
    # Resetar linhas de hover
    for key in hover_lines:
        hover_lines[key] = None
    hover_marker = None
    
    if len(df_window) > 0:
        # Gráfico 1: Aceleração Linear X, Y, Z (SEM gravidade)
        ax1.plot(df_window['time'], df_window['linear_accel_x'], 
                label='X', linewidth=1.5, color='red', alpha=0.7)
        ax1.plot(df_window['time'], df_window['linear_accel_y'], 
                label='Y', linewidth=1.5, color='green', alpha=0.7)
        ax1.plot(df_window['time'], df_window['linear_accel_z'], 
                label='Z', linewidth=1.5, color='blue', alpha=0.7)
        ax1.axhline(y=0, color='gray', linestyle='--', linewidth=0.5, alpha=0.3)
        ax1.set_xlabel('Tempo', fontsize=11)
        ax1.set_ylabel('Aceleracao Linear (m/s²)', fontsize=11)
        ax1.set_title(f'Aceleracao Linear XYZ (SEM gravidade) - {current_start.strftime("%H:%M")} ate {current_end.strftime("%H:%M")}', 
                     fontsize=12, fontweight='bold')
        ax1.legend(loc='best', fontsize=9)
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='x', rotation=45)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=2))
        
        # Gráfico 2: Magnitude da Aceleração Linear
        ax2.plot(df_window['time'], df_window['linear_accel_magnitude'], 
                label='Magnitude', linewidth=2, color='black')
        ax2.set_xlabel('Tempo', fontsize=11)
        ax2.set_ylabel('Magnitude (m/s²)', fontsize=11)
        ax2.set_title('Magnitude da Aceleracao Linear', fontsize=12, fontweight='bold')
        ax2.legend(loc='best', fontsize=9)
        ax2.grid(True, alpha=0.3)
        ax2.tick_params(axis='x', rotation=45)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax2.xaxis.set_major_locator(mdates.MinuteLocator(interval=2))
        
        # Gráfico 3: Mapa GPS
        gps_data = df_window.dropna(subset=['latitude', 'longitude'])
        if len(gps_data) > 0:
            scatter = ax3.scatter(gps_data['longitude'], gps_data['latitude'], 
                                c=gps_data['speed_kmh'], s=20, alpha=0.6,
                                cmap='viridis', edgecolors='black', linewidth=0.5)
            ax3.plot(gps_data['longitude'], gps_data['latitude'], 
                    'b-', linewidth=1, alpha=0.3, label='Trajetoria')
            ax3.set_xlabel('Longitude', fontsize=11)
            ax3.set_ylabel('Latitude', fontsize=11)
            ax3.set_title('Mapa GPS - Trajetoria', fontsize=12, fontweight='bold')
            ax3.grid(True, alpha=0.3)
            ax3.legend(loc='best', fontsize=9)
            plt.colorbar(scatter, ax=ax3, label='Velocidade (km/h)')
            ax3.set_aspect('equal', adjustable='box')
        else:
            ax3.text(0.5, 0.5, 'Sem dados GPS nesta janela', 
                    transform=ax3.transAxes, ha='center', va='center', fontsize=12)
        
        # Gráfico 4: Velocidade vs Tempo
        speed_data = df_window.dropna(subset=['speed_kmh'])
        if len(speed_data) > 0:
            ax4.plot(speed_data['time'], speed_data['speed_kmh'], 
                    label='Velocidade', linewidth=2, color='purple')
            ax4.set_xlabel('Tempo', fontsize=11)
            ax4.set_ylabel('Velocidade (km/h)', fontsize=11)
            ax4.set_title('Velocidade vs Tempo', fontsize=12, fontweight='bold')
            ax4.legend(loc='best', fontsize=9)
            ax4.grid(True, alpha=0.3)
            ax4.tick_params(axis='x', rotation=45)
            ax4.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            ax4.xaxis.set_major_locator(mdates.MinuteLocator(interval=2))
        
        # Estatísticas
        stats_text = f"Janela: {len(df_window)} pontos | "
        stats_text += f"X: μ={df_window['linear_accel_x'].mean():.2f} | "
        stats_text += f"Y: μ={df_window['linear_accel_y'].mean():.2f} | "
        stats_text += f"Z: μ={df_window['linear_accel_z'].mean():.2f} | "
        stats_text += f"Mag: μ={df_window['linear_accel_magnitude'].mean():.2f}"
        if len(gps_data) > 0:
            stats_text += f" | Velocidade: μ={gps_data['speed_kmh'].mean():.1f} km/h"
        fig.text(0.5, 0.02, stats_text, ha='center', fontsize=9, 
                bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
    
    plt.tight_layout(rect=[0, 0.08, 1, 0.98])
    plt.draw()

# Funções de navegação
def anterior(event):
    global current_start, current_end, hover_time
    new_start = current_start - timedelta(minutes=step_minutes)
    if new_start >= df['time'].min():
        current_start = new_start
        current_end = current_start + timedelta(minutes=window_minutes)
        hover_time = None
        update_plot()

def proximo(event):
    global current_start, current_end, hover_time
    new_start = current_start + timedelta(minutes=step_minutes)
    new_end = new_start + timedelta(minutes=window_minutes)
    if new_end <= df['time'].max():
        current_start = new_start
        current_end = new_end
        hover_time = None
        update_plot()

def inicio(event):
    global current_start, current_end, hover_time
    current_start = df['time'].min()
    current_end = current_start + timedelta(minutes=window_minutes)
    hover_time = None
    update_plot()

def fim(event):
    global current_start, current_end, hover_time
    current_end = df['time'].max()
    current_start = current_end - timedelta(minutes=window_minutes)
    hover_time = None
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

print("\n" + "="*70)
print("INSTRUCOES:")
print("  - Passe o mouse sobre QUALQUER grafico ou mapa")
print("  - Uma linha vermelha vertical aparecera em todos os graficos de tempo")
print("  - Um marcador vermelho aparecera no mapa GPS")
print("  - Isso sincroniza todos os graficos mostrando o mesmo momento")
print("="*70)
print("\nUse os botoes para navegar pela janela de 10 minutos.")

plt.show()


