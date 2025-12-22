import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
from datetime import datetime, timedelta

# Carregar os dados
print("Carregando dados...")
df = pd.read_csv('amostra/telemetria_20251212_20251213.csv')
periods_df = pd.read_csv('amostra/periodos_vibracao_detalhado.csv')

# Converter colunas de tempo
df['time'] = pd.to_datetime(df['time'])
df['speed_kmh'] = df['speed_kmh'].astype(float)
df['linear_accel_magnitude'] = df['linear_accel_magnitude'].astype(float)

print(f"Total de registros: {len(df)}")
print(f"Total de períodos: {len(periods_df)}")

# Definir as 8 classificações que possuem dados
classifications = [
    ('Muito_Curto_Muito_Alta', 'Muito Curto (< 1 min)', 'Muito Alta (> 0.1)', 5),  # Selecionar 5 exemplos
    ('Muito_Curto_Alta', 'Muito Curto (< 1 min)', 'Alta (0.01 - 0.1)', 5),
    ('Curto_Alta', 'Curto (1-5 min)', 'Alta (0.01 - 0.1)', 5),
    ('Curto_Media', 'Curto (1-5 min)', 'Média (0.001 - 0.01)', 8),  # Todos os 8
    ('Medio_Media', 'Médio (5-15 min)', 'Média (0.001 - 0.01)', 7),  # Todos os 7
    ('Longo_Media', 'Longo (15-60 min)', 'Média (0.001 - 0.01)', 6),  # Todos os 6
    ('Medio_Alta', 'Médio (5-15 min)', 'Alta (0.01 - 0.1)', 2),  # Todos os 2
    ('Muito_Longo_Media', 'Muito Longo (> 1h)', 'Média (0.001 - 0.01)', 1),  # O único
]

# Adicionar coluna de categoria de duração se não existir
if 'duration_category' not in periods_df.columns:
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

    periods_df['duration_category'] = periods_df['duration_minutes'].apply(categorize_duration)

# Criar diretório base para as classificações
base_dir = 'amostra/classificacoes_parada'
if not os.path.exists(base_dir):
    os.makedirs(base_dir)

# Processar cada classificação
for class_name, duration_cat, vibration_cat, max_samples in classifications:
    print(f"\n=== Processando {class_name} ===")

    # Criar pasta para a classificação
    class_dir = os.path.join(base_dir, class_name)
    if not os.path.exists(class_dir):
        os.makedirs(class_dir)

    # Filtrar períodos desta classificação
    class_periods = periods_df[(periods_df['duration_category'] == duration_cat) &
                              (periods_df['vibration_level'] == vibration_cat)]

    print(f"Encontrados {len(class_periods)} períodos para {class_name}")

    # Selecionar amostra (todos se <= max_samples, senão amostrar)
    if len(class_periods) <= max_samples:
        selected_periods = class_periods
    else:
        selected_periods = class_periods.sample(n=max_samples, random_state=42)

    print(f"Selecionados {len(selected_periods)} exemplos para análise")

    # Processar cada período selecionado
    for idx, period in selected_periods.iterrows():
        start_time = pd.to_datetime(period['start_time'])
        end_time = pd.to_datetime(period['end_time'])

        # Definir janela: 1 minuto antes e 1 minuto depois
        window_start = start_time - timedelta(minutes=1)
        window_end = end_time + timedelta(minutes=1)

        # Extrair dados da janela
        mask = (df['time'] >= window_start) & (df['time'] <= window_end)
        window_data = df[mask].copy()

        if len(window_data) == 0:
            print(f"  Período {idx}: Nenhum dado encontrado na janela")
            continue

        # Criar o gráfico
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

        # Gráfico 1: Velocidade
        ax1.plot(window_data['time'], window_data['speed_kmh'],
                color='blue', linewidth=2, label='Velocidade (km/h)')

        # Destacar o período de parada
        stop_mask = (window_data['time'] >= start_time) & (window_data['time'] <= end_time)
        if stop_mask.any():
            ax1.fill_between(window_data['time'], 0, window_data['speed_kmh'].max(),
                           where=stop_mask, alpha=0.3, color='red',
                           label='Período de Parada')

        ax1.set_ylabel('Velocidade (km/h)', fontsize=12)
        ax1.set_title(f'Velocidade - {class_name} (Período {idx})', fontsize=14, fontweight='bold')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Gráfico 2: Vibração
        ax2.plot(window_data['time'], window_data['linear_accel_magnitude'],
                color='green', linewidth=2, label='Vibração')

        # Destacar o período de parada
        if stop_mask.any():
            ax2.fill_between(window_data['time'], 0, window_data['linear_accel_magnitude'].max(),
                           where=stop_mask, alpha=0.3, color='red',
                           label='Período de Parada')

        ax2.set_ylabel('Vibração (linear_accel_magnitude)', fontsize=12)
        ax2.set_title(f'Vibração - {class_name} (Período {idx})', fontsize=14, fontweight='bold')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # Formatação do eixo X
        ax2.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%H:%M:%S'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        # Adicionar informações do período
        period_duration = (end_time - start_time).total_seconds() / 60
        avg_vibration = period['avg_vibration']

        info_text = f"""
        Período: {start_time.strftime('%H:%M:%S')} - {end_time.strftime('%H:%M:%S')}
        Duração: {period_duration:.2f} minutos
        Vibração média: {avg_vibration:.6f}
        Pontos na janela: {len(window_data)}
        """

        fig.text(0.02, 0.02, info_text, fontsize=10,
                bbox=dict(boxstyle='round,pad=0.5', facecolor='wheat', alpha=0.8),
                verticalalignment='bottom')

        plt.tight_layout()

        # Salvar gráfico
        filename = f'periodo_{idx}_{start_time.strftime("%H%M%S")}_{end_time.strftime("%H%M%S")}.png'
        filepath = os.path.join(class_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight')

        print(f"  Salvo: {filename}")
        plt.close()

        # Limitar para não processar muitos exemplos
        if len(selected_periods) > 10:
            break

print(f"\n=== PROCESSAMENTO CONCLUÍDO ===")
print(f"Classificações processadas: {len(classifications)}")
print(f"Diretório base: {base_dir}")

# Criar resumo
summary_file = os.path.join(base_dir, 'resumo_classificacoes.txt')
with open(summary_file, 'w', encoding='utf-8') as f:
    f.write("RESUMO DAS CLASSIFICAÇÕES DE PARADA\n")
    f.write("=" * 50 + "\n\n")

    for class_name, duration_cat, vibration_cat, max_samples in classifications:
        class_dir = os.path.join(base_dir, class_name)
        if os.path.exists(class_dir):
            num_files = len([f for f in os.listdir(class_dir) if f.endswith('.png')])
            f.write(f"{class_name}:\n")
            f.write(f"  Tipo: {duration_cat} + {vibration_cat}\n")
            f.write(f"  Exemplos gerados: {num_files}\n")
            f.write(f"  Pasta: {class_dir}\n\n")

print(f"Resumo salvo em: {summary_file}")
print("\nAnálise concluída! Cada classificação tem sua própria pasta com gráficos de exemplo.")
