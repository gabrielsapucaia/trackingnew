# Dashboard Web com Plotly - Agrupamento por Categoria
# Para executar: python dashboard.py

import dash
from dash import html, dcc, Input, Output
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import numpy as np

# Conectar ao banco e obter dados das últimas 3 horas
def get_data():
    conn = psycopg2.connect(
        host="10.135.22.3",
        port=5432,
        dbname="auratracking",
        user="aura",
        password="aura2025",
        connect_timeout=5,
    )
    cur = conn.cursor()

    # Todas as colunas
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'telemetry'
        ORDER BY ordinal_position;
    """)
    colunas = cur.fetchall()
    colunas_nomes = [col[0] for col in colunas]
    colunas_select = ', '.join(colunas_nomes)

    # Últimas 3 horas
    hora_atras = datetime.now() - timedelta(hours=3)
    query = f"SELECT {colunas_select} FROM telemetry WHERE time >= %s ORDER BY time ASC;"

    cur.execute(query, (hora_atras,))
    rows = cur.fetchall()
    cols = [c.name for c in cur.description]

    df = pd.DataFrame(rows, columns=cols)
    df['time'] = pd.to_datetime(df['time'])
    
    # Ordenar por tempo
    df = df.sort_values('time').reset_index(drop=True)

    cur.close()
    conn.close()
    return df

# Obter dados
print("Carregando dados das últimas 3 horas...")
df = get_data()
print(f"Dados carregados: {len(df)} registros")
if not df.empty:
    print(f"Período: {df['time'].min()} até {df['time'].max()}")
    print(f"Dispositivos: {df['device_id'].unique()}")

# Inicializar app Dash
app = dash.Dash(__name__)

# Layout do dashboard
app.layout = html.Div([
    html.H1("Dashboard de Telemetria - AuraTracking",
            style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': 30}),

    # Dropdown para selecionar dispositivo
    html.Div([
        html.Label("Dispositivo:", style={'fontWeight': 'bold', 'marginRight': 10}),
        dcc.Dropdown(
            id='device-dropdown',
            options=[{'label': device, 'value': device} for device in df['device_id'].unique()],
            value=df['device_id'].unique()[0] if len(df['device_id'].unique()) > 0 else None,
            style={'width': '200px'}
        )
    ], style={'marginBottom': 20, 'padding': '10px'}),

    # Abas para diferentes categorias
    dcc.Tabs([
        # GPS/Localização
        dcc.Tab(label='📍 GPS/Localização', children=[
            html.Div([
                html.H3("Dados de GPS e Localização", style={'marginTop': '20px'}),
                dcc.Graph(id='gps-map', style={'height': '500px'}),
                dcc.Graph(id='gps-metrics', style={'height': '700px'}),
                dcc.Graph(id='speed-altitude', style={'height': '500px'})
            ], style={'padding': '20px'})
        ]),

        # Acelerômetro
        dcc.Tab(label='📊 Acelerômetro', children=[
            html.Div([
                html.H3("Dados do Acelerômetro", style={'marginTop': '20px'}),
                dcc.Graph(id='accelerometer-3d', style={'height': '500px'}),
                dcc.Graph(id='accelerometer-time', style={'height': '700px'})
            ], style={'padding': '20px'})
        ]),

        # Giroscópio
        dcc.Tab(label='🔄 Giroscópio', children=[
            html.Div([
                html.H3("Dados do Giroscópio", style={'marginTop': '20px'}),
                dcc.Graph(id='gyroscope-time', style={'height': '700px'}),
                dcc.Graph(id='gyroscope-magnitude', style={'height': '500px'})
            ], style={'padding': '20px'})
        ]),

        # Bateria
        dcc.Tab(label='🔋 Bateria', children=[
            html.Div([
                html.H3("Status da Bateria", style={'marginTop': '20px'}),
                dcc.Graph(id='battery-level', style={'height': '500px'}),
                dcc.Graph(id='battery-metrics', style={'height': '700px'})
            ], style={'padding': '20px'})
        ]),

        # Redes
        dcc.Tab(label='📡 Redes', children=[
            html.Div([
                html.H3("Dados de Rede", style={'marginTop': '20px'}),
                dcc.Graph(id='wifi-signal', style={'height': '500px'}),
                dcc.Graph(id='cellular-signal', style={'height': '700px'})
            ], style={'padding': '20px'})
        ]),

        # Orientação
        dcc.Tab(label='📐 Orientação', children=[
            html.Div([
                html.H3("Orientação do Dispositivo", style={'marginTop': '20px'}),
                dcc.Graph(id='orientation-time', style={'height': '700px'}),
                dcc.Graph(id='rotation-vector', style={'height': '700px'})
            ], style={'padding': '20px'})
        ]),

        # Movimento
        dcc.Tab(label='🏃 Detecção de Movimento', children=[
            html.Div([
                html.H3("Detecção de Movimento", style={'marginTop': '20px'}),
                dcc.Graph(id='motion-detection', style={'height': '1000px'})
            ], style={'padding': '20px'})
        ])
    ])
])

# Callbacks para atualizar gráficos
@app.callback(
    [Output('gps-map', 'figure'),
     Output('gps-metrics', 'figure'),
     Output('speed-altitude', 'figure'),
     Output('accelerometer-3d', 'figure'),
     Output('accelerometer-time', 'figure'),
     Output('gyroscope-time', 'figure'),
     Output('gyroscope-magnitude', 'figure'),
     Output('battery-level', 'figure'),
     Output('battery-metrics', 'figure'),
     Output('wifi-signal', 'figure'),
     Output('cellular-signal', 'figure'),
     Output('orientation-time', 'figure'),
     Output('rotation-vector', 'figure'),
     Output('motion-detection', 'figure')],
    [Input('device-dropdown', 'value')]
)
def update_graphs(selected_device):
    # Filtrar por dispositivo
    df_filtered = df[df['device_id'] == selected_device].copy() if selected_device else df.copy()

    # Verificar se há dados
    if df_filtered.empty:
        empty_fig = go.Figure()
        empty_fig.add_annotation(text="Nenhum dado disponível", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        empty_fig.update_layout(title="Sem dados")
        return [empty_fig] * 14

    # Garantir que time está em formato datetime e ordenado
    df_filtered['time'] = pd.to_datetime(df_filtered['time'])
    df_filtered = df_filtered.sort_values('time').reset_index(drop=True)

    # Função auxiliar para criar gráfico vazio
    def empty_figure(title="Sem dados"):
        fig = go.Figure()
        fig.add_annotation(text="Nenhum dado disponível", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title=title, height=400)
        return fig

    # ========== GPS MAP ==========
    gps_data = df_filtered.dropna(subset=['latitude', 'longitude'])
    if gps_data.empty:
        gps_map = empty_figure("Trajetória GPS")
    else:
        gps_map = px.scatter_mapbox(
            gps_data,
            lat='latitude', lon='longitude',
            color='speed_kmh',
            size='gps_accuracy',
            hover_data=['time', 'altitude', 'bearing'],
            title="Trajetória GPS",
            mapbox_style="open-street-map",
            color_continuous_scale='Viridis'
        )
        gps_map.update_layout(height=500, margin=dict(l=0, r=0, t=30, b=0))

    # ========== GPS METRICS ==========
    fig_gps = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Velocidade (km/h)', 'Altitude (m)', 'Precisão GPS (m)', 'Satélites'),
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )
    
    # Velocidade
    fig_gps.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['speed_kmh'], name='Velocidade',
                  mode='lines', line=dict(color='blue', width=2)),
        row=1, col=1
    )
    
    # Altitude
    fig_gps.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['altitude'], name='Altitude',
                  mode='lines', line=dict(color='green', width=2)),
        row=1, col=2
    )
    
    # Precisão GPS
    fig_gps.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['gps_accuracy'], name='Precisão',
                  mode='lines', line=dict(color='orange', width=2)),
        row=2, col=1
    )
    
    # Satélites
    fig_gps.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['satellites'], name='Satélites',
                  mode='lines+markers', line=dict(color='red', width=2), marker=dict(size=4)),
        row=2, col=2
    )
    
    # Configurar eixos X em todos os subplots
    for i in range(1, 3):
        for j in range(1, 3):
            fig_gps.update_xaxes(
                tickformat='%H:%M:%S',
                tickangle=45,
                title_text="Tempo",
                row=i, col=j
            )
    
    fig_gps.update_layout(height=700, showlegend=True, title_text="Métricas GPS")

    # ========== SPEED vs ALTITUDE ==========
    speed_alt = px.scatter(
        df_filtered, 
        x='speed_kmh', 
        y='altitude',
        color='time',
        title="Velocidade vs Altitude",
        labels={'speed_kmh': 'Velocidade (km/h)', 'altitude': 'Altitude (m)'}
    )
    speed_alt.update_layout(height=500)

    # ========== ACELERÔMETRO 3D ==========
    accel_data = df_filtered.dropna(subset=['accel_x', 'accel_y', 'accel_z'])
    if accel_data.empty:
        accel_3d = empty_figure("Aceleração 3D")
    else:
        accel_3d = go.Figure(data=[go.Scatter3d(
            x=accel_data['accel_x'],
            y=accel_data['accel_y'],
            z=accel_data['accel_z'],
            mode='markers',
            marker=dict(
                size=3,
                color=accel_data['time'],
                colorscale='Viridis',
                showscale=True
            ),
            text=accel_data['time'].dt.strftime('%H:%M:%S')
        )])
        accel_3d.update_layout(
            title="Aceleração 3D",
            scene=dict(
                xaxis_title='X (m/s²)',
                yaxis_title='Y (m/s²)',
                zaxis_title='Z (m/s²)'
            ),
            height=500
        )

    # ========== ACELERÔMETRO vs TEMPO ==========
    fig_accel = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Aceleração XYZ (m/s²)', 'Magnitude (m/s²)'),
        vertical_spacing=0.15
    )
    
    fig_accel.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['accel_x'], name='X',
                  mode='lines', line=dict(color='red', width=1.5)),
        row=1, col=1
    )
    fig_accel.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['accel_y'], name='Y',
                  mode='lines', line=dict(color='green', width=1.5)),
        row=1, col=1
    )
    fig_accel.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['accel_z'], name='Z',
                  mode='lines', line=dict(color='blue', width=1.5)),
        row=1, col=1
    )
    fig_accel.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['accel_magnitude'], name='Magnitude',
                  mode='lines', line=dict(color='black', width=2)),
        row=2, col=1
    )
    
    fig_accel.update_xaxes(tickformat='%H:%M:%S', tickangle=45, title_text="Tempo", row=1, col=1)
    fig_accel.update_xaxes(tickformat='%H:%M:%S', tickangle=45, title_text="Tempo", row=2, col=1)
    fig_accel.update_layout(height=700, showlegend=True)

    # ========== GIROSCÓPIO ==========
    fig_gyro = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Giroscópio XYZ (rad/s)', 'Magnitude (rad/s)'),
        vertical_spacing=0.15
    )
    
    fig_gyro.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['gyro_x'], name='X',
                  mode='lines', line=dict(color='red', width=1.5)),
        row=1, col=1
    )
    fig_gyro.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['gyro_y'], name='Y',
                  mode='lines', line=dict(color='green', width=1.5)),
        row=1, col=1
    )
    fig_gyro.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['gyro_z'], name='Z',
                  mode='lines', line=dict(color='blue', width=1.5)),
        row=1, col=1
    )
    fig_gyro.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['gyro_magnitude'], name='Magnitude',
                  mode='lines', line=dict(color='black', width=2)),
        row=2, col=1
    )
    
    fig_gyro.update_xaxes(tickformat='%H:%M:%S', tickangle=45, title_text="Tempo", row=1, col=1)
    fig_gyro.update_xaxes(tickformat='%H:%M:%S', tickangle=45, title_text="Tempo", row=2, col=1)
    fig_gyro.update_layout(height=700, showlegend=True)

    # ========== MAGNITUDE GIROSCÓPIO ==========
    gyro_mag = px.line(
        df_filtered,
        x='time',
        y='gyro_magnitude',
        title="Magnitude do Giroscópio (rad/s)",
        labels={'time': 'Tempo', 'gyro_magnitude': 'Magnitude (rad/s)'}
    )
    gyro_mag.update_xaxes(tickformat='%H:%M:%S', tickangle=45)
    gyro_mag.update_layout(height=500)

    # ========== BATERIA ==========
    battery_level = px.line(
        df_filtered,
        x='time',
        y='battery_level',
        title="Nível da Bateria (%)",
        labels={'time': 'Tempo', 'battery_level': 'Nível (%)'}
    )
    battery_level.update_xaxes(tickformat='%H:%M:%S', tickangle=45)
    battery_level.update_layout(height=500)

    fig_battery = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Temperatura (°C)', 'Voltagem (V)', 'Status', 'Saúde (%)'),
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )
    
    fig_battery.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['battery_temperature'],
                  name='Temperatura', mode='lines', line=dict(color='red', width=2)),
        row=1, col=1
    )
    fig_battery.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['battery_voltage'],
                  name='Voltagem', mode='lines', line=dict(color='blue', width=2)),
        row=1, col=2
    )
    fig_battery.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['battery_status'],
                  name='Status', mode='lines+markers', line=dict(color='green', width=2), marker=dict(size=4)),
        row=2, col=1
    )
    fig_battery.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['battery_health'],
                  name='Saúde', mode='lines', line=dict(color='orange', width=2)),
        row=2, col=2
    )
    
    for i in range(1, 3):
        for j in range(1, 3):
            fig_battery.update_xaxes(tickformat='%H:%M:%S', tickangle=45, title_text="Tempo", row=i, col=j)
    
    fig_battery.update_layout(height=700, showlegend=True)

    # ========== WIFI ==========
    wifi_signal = px.line(
        df_filtered,
        x='time',
        y='wifi_rssi',
        title="Sinal WiFi (RSSI)",
        labels={'time': 'Tempo', 'wifi_rssi': 'RSSI (dBm)'}
    )
    wifi_signal.update_xaxes(tickformat='%H:%M:%S', tickangle=45)
    wifi_signal.update_layout(height=500)

    # ========== CELULAR ==========
    fig_cellular = make_subplots(
        rows=2, cols=2,
        subplot_titles=('RSRP (dBm)', 'RSRQ (dB)', 'RSSNR (dB)', 'Tipo de Rede'),
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )
    
    fig_cellular.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['cellular_rsrp'],
                  name='RSRP', mode='lines', line=dict(color='blue', width=2)),
        row=1, col=1
    )
    fig_cellular.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['cellular_rsrq'],
                  name='RSRQ', mode='lines', line=dict(color='green', width=2)),
        row=1, col=2
    )
    fig_cellular.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['cellular_rssnr'],
                  name='RSSNR', mode='lines', line=dict(color='orange', width=2)),
        row=2, col=1
    )
    fig_cellular.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['cellular_network_type'],
                  name='Tipo', mode='lines+markers', line=dict(color='red', width=2), marker=dict(size=4)),
        row=2, col=2
    )
    
    for i in range(1, 3):
        for j in range(1, 3):
            fig_cellular.update_xaxes(tickformat='%H:%M:%S', tickangle=45, title_text="Tempo", row=i, col=j)
    
    fig_cellular.update_layout(height=700, showlegend=True)

    # ========== ORIENTAÇÃO ==========
    fig_orientation = make_subplots(
        rows=3, cols=1,
        subplot_titles=('Azimuth (graus)', 'Pitch (graus)', 'Roll (graus)'),
        vertical_spacing=0.1
    )
    
    fig_orientation.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['azimuth'],
                  name='Azimuth', mode='lines', line=dict(color='blue', width=2)),
        row=1, col=1
    )
    fig_orientation.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['pitch'],
                  name='Pitch', mode='lines', line=dict(color='green', width=2)),
        row=2, col=1
    )
    fig_orientation.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['roll'],
                  name='Roll', mode='lines', line=dict(color='red', width=2)),
        row=3, col=1
    )
    
    for i in range(1, 4):
        fig_orientation.update_xaxes(tickformat='%H:%M:%S', tickangle=45, title_text="Tempo", row=i, col=1)
    
    fig_orientation.update_layout(height=700, showlegend=True)

    # ========== ROTATION VECTOR ==========
    fig_rotation = make_subplots(
        rows=2, cols=2,
        subplot_titles=('X', 'Y', 'Z', 'W'),
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )
    
    fig_rotation.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['rotation_vector_x'],
                  name='X', mode='lines', line=dict(color='red', width=2)),
        row=1, col=1
    )
    fig_rotation.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['rotation_vector_y'],
                  name='Y', mode='lines', line=dict(color='green', width=2)),
        row=1, col=2
    )
    fig_rotation.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['rotation_vector_z'],
                  name='Z', mode='lines', line=dict(color='blue', width=2)),
        row=2, col=1
    )
    fig_rotation.add_trace(
        go.Scatter(x=df_filtered['time'], y=df_filtered['rotation_vector_w'],
                  name='W', mode='lines', line=dict(color='orange', width=2)),
        row=2, col=2
    )
    
    for i in range(1, 3):
        for j in range(1, 3):
            fig_rotation.update_xaxes(tickformat='%H:%M:%S', tickangle=45, title_text="Tempo", row=i, col=j)
    
    fig_rotation.update_layout(height=700, showlegend=True)

    # ========== DETECÇÃO DE MOVIMENTO ==========
    motion_cols = ['motion_significant_motion', 'motion_stationary_detect',
                  'motion_motion_detect', 'motion_flat_up', 'motion_flat_down',
                  'motion_stowed', 'motion_display_rotate']

    fig_motion = make_subplots(
        rows=len(motion_cols), cols=1,
        subplot_titles=motion_cols,
        vertical_spacing=0.05
    )

    for i, col in enumerate(motion_cols):
        fig_motion.add_trace(
            go.Scatter(x=df_filtered['time'], y=df_filtered[col],
                      name=col, mode='lines', line=dict(width=2)),
            row=i+1, col=1
        )
        fig_motion.update_xaxes(tickformat='%H:%M:%S', tickangle=45, title_text="Tempo", row=i+1, col=1)

    fig_motion.update_layout(height=1000, showlegend=False)

    return (gps_map, fig_gps, speed_alt, accel_3d, fig_accel, fig_gyro, gyro_mag,
            battery_level, fig_battery, wifi_signal, fig_cellular, fig_orientation,
            fig_rotation, fig_motion)

if __name__ == '__main__':
    print("Iniciando dashboard... Acesse http://127.0.0.1:8050/")
    print("Pressione Ctrl+C para parar o servidor")
    app.run(debug=True, host='0.0.0.0', port=8050)
