# Gráfico Comparativo: Acelerômetro Bruto vs Aceleração Linear (sem gravidade)
# Para executar: python grafico_acelerometro_comparativo.py

import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.widgets import Button
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
    SELECT time, device_id, 
           accel_x, accel_y, accel_z, accel_magnitude,
           linear_accel_x, linear_accel_y, linear_accel_z, linear_accel_magnitude,
           gravity_x, gravity_y, gravity_z
    FROM telemetry
    WHERE time >= %s
    ORDER BY time ASC;
"""

cur.execute(query, (hora_atras,))
rows = cur.fetchall()

# Criar DataFrame
df = pd.DataFrame(rows, columns=[
    'time', 'device_id',
    'accel_x', 'accel_y', 'accel_z', 'accel_magnitude',
    'linear_accel_x', 'linear_accel_y', 'linear_accel_z', 'linear_accel_magnitude',
    'gravity_x', 'gravity_y', 'gravity_z'
])
df['time'] = pd.to_datetime(df['time'])

cur.close()
conn.close()

print(f"Dados carregados: {len(df)} registros")
print(f"Período total: {df['time'].min()} até {df['time'].max()}")

# Variáveis globais para controle da janela
window_minutes = 10
step_minutes = 5
current_start = df['time'].min()
current_end = current_start + timedelta(minutes=window_minutes)

# Criar figura com 3 linhas de gráficos
fig = plt.figure(figsize=(16, 12))
fig.suptitle('Comparacao: Acelerometro Bruto vs Linear (sem gravidade)', fontsize=16, fontweight='bold')

# Criar subplots
ax1 = plt.subplot(3, 1, 1)  # Acelerômetro bruto (com gravidade)
ax2 = plt.subplot(3, 1, 2)  # Aceleração linear (sem gravidade)
ax3 = plt.subplot(3, 1, 3)  # Comparação de magnitudes

# Função para atualizar o gráfico
def update_plot():
    global current_start, current_end
    
    # Filtrar dados para a janela atual
    mask = (df['time'] >= current_start) & (df['time'] <= current_end)
    df_window = df[mask].copy()
    
    # Limpar eixos
    ax1.clear()
    ax2.clear()
    ax3.clear()
    
    if len(df_window) > 0:
        # Gráfico 1: Acelerômetro BRUTO (COM gravidade)
        ax1.plot(df_window['time'], df_window['accel_x'], label='X (bruto)', 
                linewidth=1.5, color='red', alpha=0.7)
        ax1.plot(df_window['time'], df_window['accel_y'], label='Y (bruto)', 
                linewidth=1.5, color='green', alpha=0.7)
        ax1.plot(df_window['time'], df_window['accel_z'], label='Z (bruto)', 
                linewidth=1.5, color='blue', alpha=0.7)
        ax1.axhline(y=9.8, color='gray', linestyle='--', linewidth=1, alpha=0.5, label='Gravidade (~9.8 m/s²)')
        ax1.set_xlabel('Tempo', fontsize=11)
        ax1.set_ylabel('Aceleracao (m/s²)', fontsize=11)
        ax1.set_title(f'Acelerometro BRUTO (COM gravidade) - {current_start.strftime("%H:%M")} ate {current_end.strftime("%H:%M")}', 
                     fontsize=13, fontweight='bold')
        ax1.legend(loc='best', fontsize=9)
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='x', rotation=45)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=2))
        
        # Gráfico 2: Aceleração LINEAR (SEM gravidade)
        ax2.plot(df_window['time'], df_window['linear_accel_x'], label='X (linear)', 
                linewidth=1.5, color='red', alpha=0.7)
        ax2.plot(df_window['time'], df_window['linear_accel_y'], label='Y (linear)', 
                linewidth=1.5, color='green', alpha=0.7)
        ax2.plot(df_window['time'], df_window['linear_accel_z'], label='Z (linear)', 
                linewidth=1.5, color='blue', alpha=0.7)
        ax2.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
        ax2.set_xlabel('Tempo', fontsize=11)
        ax2.set_ylabel('Aceleracao Linear (m/s²)', fontsize=11)
        ax2.set_title('Aceleracao LINEAR (SEM gravidade)', fontsize=13, fontweight='bold')
        ax2.legend(loc='best', fontsize=9)
        ax2.grid(True, alpha=0.3)
        ax2.tick_params(axis='x', rotation=45)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax2.xaxis.set_major_locator(mdates.MinuteLocator(interval=2))
        
        # Gráfico 3: Comparação de Magnitudes
        ax3.plot(df_window['time'], df_window['accel_magnitude'], 
                label='Magnitude Bruta (com gravidade)', linewidth=2, color='orange')
        ax3.plot(df_window['time'], df_window['linear_accel_magnitude'], 
                label='Magnitude Linear (sem gravidade)', linewidth=2, color='purple')
        ax3.set_xlabel('Tempo', fontsize=11)
        ax3.set_ylabel('Magnitude (m/s²)', fontsize=11)
        ax3.set_title('Comparacao de Magnitudes', fontsize=13, fontweight='bold')
        ax3.legend(loc='best', fontsize=9)
        ax3.grid(True, alpha=0.3)
        ax3.tick_params(axis='x', rotation=45)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax3.xaxis.set_major_locator(mdates.MinuteLocator(interval=2))
        
        # Estatísticas
        stats_text = f"Janela: {len(df_window)} pontos | "
        stats_text += f"Bruto Z: μ={df_window['accel_z'].mean():.2f} | "
        stats_text += f"Linear Z: μ={df_window['linear_accel_z'].mean():.2f} | "
        stats_text += f"Mag Bruta: μ={df_window['accel_magnitude'].mean():.2f} | "
        stats_text += f"Mag Linear: μ={df_window['linear_accel_magnitude'].mean():.2f}"
        fig.text(0.5, 0.02, stats_text, ha='center', fontsize=9, 
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))
    
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

print("\n" + "="*70)
print("DADOS DISPONIVEIS:")
print("  - Acelerometro BRUTO (accel_x/y/z): COM efeito da gravidade")
print("  - Aceleracao LINEAR (linear_accel_x/y/z): SEM efeito da gravidade")
print("  - Gravidade (gravity_x/y/z): Componentes da gravidade")
print("="*70)
print("\nUse os botoes para navegar pela janela de 10 minutos.")

plt.show()


