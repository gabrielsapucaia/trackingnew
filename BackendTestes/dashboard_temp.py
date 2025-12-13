# Instalar dependências (se necessário)
# !pip install dash plotly pandas psycopg2-binary

import dash
from dash import html, dcc, Input, Output
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import psycopg2
from datetime import datetime, timedelta

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
    query = f"SELECT {colunas_select} FROM telemetry WHERE time >= %s ORDER BY time DESC;"

    cur.execute(query, (hora_atras,))
    rows = cur.fetchall()
    cols = [c.name for c in cur.description]

    df = pd.DataFrame(rows, columns=cols)
    df['time'] = pd.to_datetime(df['time'])

    cur.close()
    conn.close()
    return df

# Obter dados
print("Carregando dados das últimas 3 horas...")
df = get_data()
print(f"Dados carregados: {len(df)} registros")
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
    ], style={'marginBottom': 20}),

    # Abas para diferentes categorias
    dcc.Tabs([
        # GPS/Localização
        dcc.Tab(label='📍 GPS/Localização', children=[
            html.Div([
                html.H3("Dados de GPS e Localização"),
                dcc.Graph(id='gps-map'),
                dcc.Graph(id='gps-metrics'),
                dcc.Graph(id='speed-altitude')
            ])
        ]),

        # Acelerômetro
        dcc.Tab(label='📊 Acelerômetro', children=[
            html.Div([
                html.H3("Dados do Acelerômetro"),
                dcc.Graph(id='accelerometer-3d'),
                dcc.Graph(id='accelerometer-time')
            ])
        ]),

        # Giroscópio
        dcc.Tab(label='🔄 Giroscópio', children=[
            html.Div([
                html.H3("Dados do Giroscópio"),
                dcc.Graph(id='gyroscope-time'),
                dcc.Graph(id='gyroscope-magnitude')
            ])
        ]),

        # Bateria
        dcc.Tab(label='🔋 Bateria', children=[
            html.Div([
                html.H3("Status da Bateria"),
                dcc.Graph(id='battery-level'),
                dcc.Graph(id='battery-metrics')
            ])
        ]),

        # Redes
        dcc.Tab(label='📡 Redes', children=[
            html.Div([
                html.H3("Dados de Rede"),
                dcc.Graph(id='wifi-signal'),
                dcc.Graph(id='cellular-signal')
            ])
        ]),

        # Orientação
        dcc.Tab(label='📐 Orientação', children=[
            html.Div([
                html.H3("Orientação do Dispositivo"),
                dcc.Graph(id='orientation-time'),
                dcc.Graph(id='rotation-vector')
            ])
        ]),

        # Movimento
        dcc.Tab(label='🏃 Detecção de Movimento', children=[
            html.Div([
                html.H3("Detecção de Movimento"),
                dcc.Graph(id='motion-detection')
            ])
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
    df_filtered = df[df['device_id'] == selected_device] if selected_device else df

    # GPS Map
    gps_map = px.scatter_mapbox(
        df_filtered.dropna(subset=['latitude', 'longitude']),
        lat='latitude', lon='longitude',
        color='speed_kmh',
        size='gps_accuracy',
        hover_data=['time', 'altitude', 'bearing'],
        title="Trajetória GPS",
        mapbox_style="open-street-map"
    )

    # GPS Metrics
    fig_gps = make_subplots(rows=2, cols=2,
                           subplot_titles=('Velocidade', 'Altitude', 'Precisão GPS', 'Satélites'))
    fig_gps.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['speed_kmh'], name='Velocidade'), row=1, col=1)
    fig_gps.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['altitude'], name='Altitude'), row=1, col=2)
    fig_gps.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['gps_accuracy'], name='Precisão'), row=2, col=1)
    fig_gps.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['satellites'], name='Satélites'), row=2, col=2)

    # Speed vs Altitude
    speed_alt = px.scatter(df_filtered, x='speed_kmh', y='altitude',
                          color='time', title="Velocidade vs Altitude")

    # Acelerômetro 3D
    accel_3d = go.Figure(data=[go.Scatter3d(
        x=df_filtered['accel_x'], y=df_filtered['accel_y'], z=df_filtered['accel_z'],
        mode='markers', marker=dict(size=2, color=df_filtered['time'], colorscale='Viridis')
    )])
    accel_3d.update_layout(title="Aceleração 3D", scene=dict(xaxis_title='X', yaxis_title='Y', zaxis_title='Z'))

    # Acelerômetro vs Tempo
    fig_accel = make_subplots(rows=2, cols=1, subplot_titles=('Aceleração XYZ', 'Magnitude'))
    fig_accel.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['accel_x'], name='X'), row=1, col=1)
    fig_accel.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['accel_y'], name='Y'), row=1, col=1)
    fig_accel.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['accel_z'], name='Z'), row=1, col=1)
    fig_accel.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['accel_magnitude'], name='Magnitude'), row=2, col=1)

    # Giroscópio
    fig_gyro = make_subplots(rows=2, cols=1, subplot_titles=('Giroscópio XYZ', 'Magnitude'))
    fig_gyro.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['gyro_x'], name='X'), row=1, col=1)
    fig_gyro.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['gyro_y'], name='Y'), row=1, col=1)
    fig_gyro.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['gyro_z'], name='Z'), row=1, col=1)
    fig_gyro.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['gyro_magnitude'], name='Magnitude'), row=2, col=1)

    # Magnitude do giroscópio separada
    gyro_mag = px.line(df_filtered, x='time', y='gyro_magnitude', title="Magnitude do Giroscópio")

    # Bateria
    battery_level = px.line(df_filtered, x='time', y='battery_level',
                           title="Nível da Bateria", markers=True)

    fig_battery = make_subplots(rows=2, cols=2,
                               subplot_titles=('Temperatura', 'Voltagem', 'Status', 'Saúde'))
    fig_battery.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['battery_temperature'],
                                    name='Temperatura'), row=1, col=1)
    fig_battery.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['battery_voltage'],
                                    name='Voltagem'), row=1, col=2)
    fig_battery.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['battery_status'],
                                    name='Status'), row=2, col=1)
    fig_battery.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['battery_health'],
                                    name='Saúde'), row=2, col=2)

    # WiFi
    wifi_signal = px.line(df_filtered, x='time', y='wifi_rssi',
                         title="Sinal WiFi (RSSI)", markers=True)

    # Celular
    fig_cellular = make_subplots(rows=2, cols=2,
                                subplot_titles=('RSRP', 'RSRQ', 'RSSNR', 'Tipo de Rede'))
    fig_cellular.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['cellular_rsrp'],
                                     name='RSRP'), row=1, col=1)
    fig_cellular.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['cellular_rsrq'],
                                     name='RSRQ'), row=1, col=2)
    fig_cellular.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['cellular_rssnr'],
                                     name='RSSNR'), row=2, col=1)
    fig_cellular.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['cellular_network_type'],
                                     name='Tipo'), row=2, col=2)

    # Orientação
    fig_orientation = make_subplots(rows=3, cols=1,
                                   subplot_titles=('Azimuth', 'Pitch', 'Roll'))
    fig_orientation.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['azimuth'],
                                        name='Azimuth'), row=1, col=1)
    fig_orientation.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['pitch'],
                                        name='Pitch'), row=2, col=1)
    fig_orientation.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['roll'],
                                        name='Roll'), row=3, col=1)

    # Rotation Vector
    fig_rotation = make_subplots(rows=2, cols=2,
                                subplot_titles=('X', 'Y', 'Z', 'W'))
    fig_rotation.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['rotation_vector_x'],
                                     name='X'), row=1, col=1)
    fig_rotation.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['rotation_vector_y'],
                                     name='Y'), row=1, col=2)
    fig_rotation.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['rotation_vector_z'],
                                     name='Z'), row=2, col=1)
    fig_rotation.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered['rotation_vector_w'],
                                     name='W'), row=2, col=2)

    # Detecção de Movimento
    motion_cols = ['motion_significant_motion', 'motion_stationary_detect',
                  'motion_motion_detect', 'motion_flat_up', 'motion_flat_down',
                  'motion_stowed', 'motion_display_rotate']

    fig_motion = make_subplots(rows=len(motion_cols), cols=1,
                              subplot_titles=motion_cols)

    for i, col in enumerate(motion_cols):
        fig_motion.add_trace(go.Scatter(x=df_filtered['time'], y=df_filtered[col],
                                       name=col), row=i+1, col=1)

    return (gps_map, fig_gps, speed_alt, accel_3d, fig_accel, fig_gyro, gyro_mag,
            battery_level, fig_battery, wifi_signal, fig_cellular, fig_orientation,
            fig_rotation, fig_motion)

# Função para executar o dashboard
def run_dashboard():
    print("Iniciando dashboard... Acesse http://127.0.0.1:8050/")
    print("Pressione Ctrl+C para parar o servidor")
    app.run_server(debug=True, host='0.0.0.0', port=8050)

if __name__ == '__main__':
    run_dashboard()

