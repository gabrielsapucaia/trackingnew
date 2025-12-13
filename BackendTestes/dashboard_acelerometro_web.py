# Dashboard Web Leve - Aceleração Linear (sem gravidade) + Mapa GPS
# Para executar: python dashboard_acelerometro_web.py
# Acesse: http://127.0.0.1:8050/

import dash
from dash import html, dcc, Input, Output, callback
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import psycopg2
from datetime import datetime, timedelta

# Conectar ao banco e obter dados
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

    hora_atras = datetime.now() - timedelta(hours=3)
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
    cols = [c.name for c in cur.description]
    
    df = pd.DataFrame(rows, columns=cols)
    df['time'] = pd.to_datetime(df['time'])
    
    cur.close()
    conn.close()
    return df

# Carregar dados
print("Carregando dados...")
df = get_data()
print(f"Dados carregados: {len(df)} registros")
print(f"Período: {df['time'].min()} até {df['time'].max()}")

# Inicializar app Dash
app = dash.Dash(__name__)

# Layout do dashboard
app.layout = html.Div([
    html.H1("Dashboard Acelerometro Linear + GPS", 
            style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': 20}),
    
    # Controles
    html.Div([
        html.Label("Janela de tempo:", style={'fontWeight': 'bold', 'marginRight': 10}),
        dcc.Dropdown(
            id='time-window',
            options=[
                {'label': '10 minutos', 'value': 10},
                {'label': '15 minutos', 'value': 15},
                {'label': '30 minutos', 'value': 30},
                {'label': '1 hora', 'value': 60}
            ],
            value=10,
            style={'width': '150px', 'display': 'inline-block', 'marginRight': 20}
        ),
        html.Label("Início:", style={'fontWeight': 'bold', 'marginRight': 10}),
        dcc.Input(
            id='start-time',
            type='text',
            placeholder='HH:MM',
            value=df['time'].min().strftime('%H:%M'),
            style={'width': '80px', 'display': 'inline-block', 'marginRight': 20}
        ),
        html.Button('Anterior (-5min)', id='btn-prev', n_clicks=0,
                   style={'marginRight': 10, 'padding': '5px 10px'}),
        html.Button('Próximo (+5min)', id='btn-next', n_clicks=0,
                   style={'marginRight': 10, 'padding': '5px 10px'}),
        html.Button('Início', id='btn-start', n_clicks=0,
                   style={'marginRight': 10, 'padding': '5px 10px'}),
        html.Button('Fim', id='btn-end', n_clicks=0,
                   style={'padding': '5px 10px'}),
    ], style={'marginBottom': 20, 'padding': '10px', 'backgroundColor': '#f0f0f0', 'borderRadius': '5px'}),
    
    # Gráficos
    html.Div([
        # Linha 1: Aceleração XYZ e Magnitude
        html.Div([
            dcc.Graph(id='accel-xyz', style={'height': '400px'}),
        ], style={'width': '48%', 'display': 'inline-block', 'marginRight': '2%'}),
        
        html.Div([
            dcc.Graph(id='accel-magnitude', style={'height': '400px'}),
        ], style={'width': '48%', 'display': 'inline-block'}),
    ], style={'marginBottom': 20}),
    
    # Linha 2: Mapa GPS e Velocidade
    html.Div([
        html.Div([
            dcc.Graph(id='gps-map', style={'height': '500px'}),
        ], style={'width': '48%', 'display': 'inline-block', 'marginRight': '2%'}),
        
        html.Div([
            dcc.Graph(id='speed-chart', style={'height': '500px'}),
        ], style={'width': '48%', 'display': 'inline-block'}),
    ]),
    
    # Store para manter o estado da janela de tempo
    dcc.Store(id='time-window-store', data={'start': df['time'].min().isoformat(), 'window': 10}),
])

# Callback para atualizar a janela de tempo
@app.callback(
    Output('time-window-store', 'data'),
    [Input('btn-prev', 'n_clicks'),
     Input('btn-next', 'n_clicks'),
     Input('btn-start', 'n_clicks'),
     Input('btn-end', 'n_clicks'),
     Input('time-window', 'value'),
     Input('start-time', 'value')],
    [dash.dependencies.State('time-window-store', 'data')]
)
def update_time_window(prev_clicks, next_clicks, start_clicks, end_clicks, window_minutes, start_time_str, current_data):
    ctx = dash.callback_context
    if not ctx.triggered:
        return current_data
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    current_start = pd.to_datetime(current_data['start'])
    window = window_minutes if window_minutes else current_data['window']
    
    if button_id == 'btn-prev':
        new_start = current_start - timedelta(minutes=5)
        if new_start >= df['time'].min():
            current_start = new_start
    elif button_id == 'btn-next':
        new_start = current_start + timedelta(minutes=5)
        new_end = new_start + timedelta(minutes=window)
        if new_end <= df['time'].max():
            current_start = new_start
    elif button_id == 'btn-start':
        current_start = df['time'].min()
    elif button_id == 'btn-end':
        current_end = df['time'].max()
        current_start = current_end - timedelta(minutes=window)
    elif button_id == 'start-time' and start_time_str:
        try:
            # Tentar parsear o tempo
            hour, minute = map(int, start_time_str.split(':'))
            new_start = current_start.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if new_start >= df['time'].min():
                current_start = new_start
        except:
            pass
    
    return {'start': current_start.isoformat(), 'window': window}

# Callback para filtrar dados
@app.callback(
    Output('accel-xyz', 'figure'),
    Output('accel-magnitude', 'figure'),
    Output('gps-map', 'figure'),
    Output('speed-chart', 'figure'),
    Input('time-window-store', 'data')
)
def update_graphs(time_data):
    start_time = pd.to_datetime(time_data['start'])
    window_minutes = time_data['window']
    end_time = start_time + timedelta(minutes=window_minutes)
    
    # Filtrar dados
    mask = (df['time'] >= start_time) & (df['time'] <= end_time)
    df_window = df[mask].copy()
    
    if len(df_window) == 0:
        empty_fig = go.Figure()
        empty_fig.add_annotation(text="Nenhum dado disponível", xref="paper", yref="paper", 
                               x=0.5, y=0.5, showarrow=False)
        return empty_fig, empty_fig, empty_fig, empty_fig
    
    # Gráfico 1: Aceleração XYZ
    fig_xyz = go.Figure()
    fig_xyz.add_trace(go.Scatter(x=df_window['time'], y=df_window['linear_accel_x'], 
                                 name='X', line=dict(color='red', width=1.5)))
    fig_xyz.add_trace(go.Scatter(x=df_window['time'], y=df_window['linear_accel_y'], 
                                 name='Y', line=dict(color='green', width=1.5)))
    fig_xyz.add_trace(go.Scatter(x=df_window['time'], y=df_window['linear_accel_z'], 
                                 name='Z', line=dict(color='blue', width=1.5)))
    fig_xyz.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig_xyz.update_layout(
        title=f'Aceleração Linear XYZ (SEM gravidade) - {start_time.strftime("%H:%M")} até {end_time.strftime("%H:%M")}',
        xaxis_title='Tempo',
        yaxis_title='Aceleração (m/s²)',
        hovermode='x unified',
        height=400
    )
    
    # Gráfico 2: Magnitude
    fig_mag = go.Figure()
    fig_mag.add_trace(go.Scatter(x=df_window['time'], y=df_window['linear_accel_magnitude'], 
                                 name='Magnitude', line=dict(color='black', width=2)))
    fig_mag.update_layout(
        title='Magnitude da Aceleração Linear',
        xaxis_title='Tempo',
        yaxis_title='Magnitude (m/s²)',
        hovermode='x unified',
        height=400
    )
    
    # Gráfico 3: Mapa GPS
    gps_data = df_window.dropna(subset=['latitude', 'longitude'])
    if len(gps_data) > 0:
        fig_map = px.scatter_mapbox(
            gps_data,
            lat='latitude',
            lon='longitude',
            color='speed_kmh',
            size='linear_accel_magnitude',
            hover_data=['time', 'altitude', 'speed_kmh'],
            color_continuous_scale='Viridis',
            mapbox_style='open-street-map',
            title='Mapa GPS - Trajetória'
        )
        fig_map.update_layout(height=500, margin=dict(l=0, r=0, t=30, b=0))
    else:
        fig_map = go.Figure()
        fig_map.add_annotation(text="Sem dados GPS", xref="paper", yref="paper", 
                             x=0.5, y=0.5, showarrow=False)
        fig_map.update_layout(height=500)
    
    # Gráfico 4: Velocidade
    speed_data = df_window.dropna(subset=['speed_kmh'])
    if len(speed_data) > 0:
        fig_speed = go.Figure()
        fig_speed.add_trace(go.Scatter(x=speed_data['time'], y=speed_data['speed_kmh'], 
                                      name='Velocidade', line=dict(color='purple', width=2)))
        fig_speed.update_layout(
            title='Velocidade vs Tempo',
            xaxis_title='Tempo',
            yaxis_title='Velocidade (km/h)',
            hovermode='x unified',
            height=500
        )
    else:
        fig_speed = go.Figure()
        fig_speed.add_annotation(text="Sem dados de velocidade", xref="paper", yref="paper", 
                                x=0.5, y=0.5, showarrow=False)
        fig_speed.update_layout(height=500)
    
    return fig_xyz, fig_mag, fig_map, fig_speed

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Dashboard Web iniciado!")
    print("Acesse: http://127.0.0.1:8050/")
    print("="*60)
    print("\nFuncionalidades:")
    print("  - Passe o mouse sobre qualquer gráfico para ver detalhes")
    print("  - Use os botões para navegar pela janela de tempo")
    print("  - Selecione o tamanho da janela (10, 15, 30 ou 60 minutos)")
    print("  - Todos os gráficos são sincronizados automaticamente")
    print("\nPressione Ctrl+C para parar o servidor")
    print("="*60)
    
    app.run(debug=True, host='0.0.0.0', port=8050)


