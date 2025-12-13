# Dashboard simples para teste
import dash
from dash import html, dcc
import plotly.express as px
import pandas as pd

# Dados de teste simples
df_teste = pd.DataFrame({
    'time': pd.date_range('2023-01-01', periods=100, freq='1min'),
    'valor': [i + (i % 10) for i in range(100)],
    'categoria': ['A'] * 50 + ['B'] * 50
})

# Criar app Dash simples
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1('Dashboard Simples - Teste', style={'textAlign': 'center'}),
    html.P('Se você vê esta página, o Dash está funcionando!', style={'textAlign': 'center'}),

    dcc.Graph(
        figure=px.line(df_teste, x='time', y='valor', color='categoria',
                      title='Gráfico de Teste Simples')
    ),

    html.Hr(),
    html.H3('Status:'),
    html.Ul([
        html.Li('✅ Dash funcionando'),
        html.Li('✅ Plotly funcionando'),
        html.Li('✅ Pandas funcionando'),
        html.Li('📊 Dados de teste carregados')
    ])
])

if __name__ == '__main__':
    print("Iniciando dashboard simples... Acesse http://127.0.0.1:8050/")
    print("Pressione Ctrl+C para parar")
    app.run(debug=True, host='0.0.0.0', port=8050)
