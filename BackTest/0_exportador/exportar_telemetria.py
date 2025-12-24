#!/usr/bin/env python3
"""
Exportador de Telemetria do TimescaleDB para CSV.

Exporta dados de telemetria do banco PostgreSQL/TimescaleDB para CSV
com reamostragem para 1 Hz e selecao de variaveis.

Uso:
    python exportar_telemetria.py --device DEVICE_ID --inicio "2024-12-01 00:00" --fim "2024-12-01 12:00"
    python exportar_telemetria.py --listar-devices
    python exportar_telemetria.py --interativo
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import psycopg2
import yaml


def carregar_config(config_path: str = "config_db.yaml") -> dict:
    """Carrega configuracao do arquivo YAML."""
    config_file = Path(__file__).parent / config_path
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def conectar_banco(config: dict) -> psycopg2.extensions.connection:
    """Estabelece conexao com o banco de dados."""
    db_config = config['database']
    conn = psycopg2.connect(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )
    return conn


def listar_devices(conn: psycopg2.extensions.connection) -> pd.DataFrame:
    """Lista todos os devices disponiveis no banco."""
    query = """
        SELECT
            device_id,
            device_model,
            first_seen,
            last_seen,
            total_telemetry_count,
            is_active
        FROM devices
        ORDER BY last_seen DESC
    """
    return pd.read_sql(query, conn)


def obter_periodo_disponivel(conn: psycopg2.extensions.connection, device_id: str) -> tuple:
    """Obtem o periodo de dados disponiveis para um device."""
    query = """
        SELECT
            MIN(time) as inicio,
            MAX(time) as fim,
            COUNT(*) as total_registros
        FROM telemetry
        WHERE device_id = %s
    """
    df = pd.read_sql(query, conn, params=(device_id,))
    return df.iloc[0]['inicio'], df.iloc[0]['fim'], df.iloc[0]['total_registros']


def exportar_telemetria(
    conn: psycopg2.extensions.connection,
    device_id: str,
    inicio: datetime,
    fim: datetime,
    variaveis: list[str],
    frequencia_hz: int = 1
) -> pd.DataFrame:
    """
    Exporta dados de telemetria para um DataFrame.

    Args:
        conn: Conexao com o banco
        device_id: ID do dispositivo
        inicio: Timestamp de inicio
        fim: Timestamp de fim
        variaveis: Lista de colunas para exportar
        frequencia_hz: Frequencia de amostragem (padrao 1 Hz)

    Returns:
        DataFrame com os dados reamostrados
    """
    # Garante que 'time' esta nas variaveis
    if 'time' not in variaveis:
        variaveis = ['time'] + variaveis

    # Monta query
    colunas = ', '.join(variaveis)
    query = f"""
        SELECT {colunas}
        FROM telemetry
        WHERE device_id = %s
          AND time >= %s
          AND time < %s
        ORDER BY time ASC
    """

    print(f"Consultando banco de dados...")
    df = pd.read_sql(query, conn, params=(device_id, inicio, fim))

    if df.empty:
        print("Nenhum dado encontrado para o periodo especificado.")
        return df

    print(f"Registros brutos: {len(df)}")

    # Converte time para datetime
    df['time'] = pd.to_datetime(df['time'])
    df = df.set_index('time')

    # Reamostra para frequencia desejada
    if frequencia_hz == 1:
        resample_rule = '1s'
    else:
        resample_rule = f'{1000//frequencia_hz}ms'

    print(f"Reamostrando para {frequencia_hz} Hz...")

    # Separa colunas numericas das nao-numericas
    numeric_cols = df.select_dtypes(include=['number']).columns
    non_numeric_cols = df.select_dtypes(exclude=['number']).columns

    # Reamostra numericas com media
    df_resampled = df[numeric_cols].resample(resample_rule).mean()

    # Para nao-numericas, pega o primeiro valor
    for col in non_numeric_cols:
        df_resampled[col] = df[col].resample(resample_rule).first()

    # Remove linhas com todos NaN
    df_resampled = df_resampled.dropna(how='all')

    # Reset index para ter 'time' como coluna
    df_resampled = df_resampled.reset_index()

    print(f"Registros apos resample: {len(df_resampled)}")

    return df_resampled


def obter_todas_variaveis(config: dict) -> list[str]:
    """Retorna lista de todas as variaveis disponiveis."""
    variaveis = []
    for categoria in ['gps', 'acelerometro', 'giroscopio', 'orientacao', 'sistema']:
        if categoria in config['variaveis']:
            variaveis.extend(config['variaveis'][categoria])
    return variaveis


def selecionar_variaveis_interativo(config: dict) -> list[str]:
    """Interface interativa para selecionar variaveis."""
    print("\n=== SELECAO DE VARIAVEIS ===\n")

    categorias = {
        'gps': 'GPS (localizacao e velocidade)',
        'acelerometro': 'Acelerometro (vibracoes)',
        'giroscopio': 'Giroscopio (rotacao)',
        'orientacao': 'Orientacao (pitch/roll/azimuth)',
        'sistema': 'Sistema (bateria, wifi, operador)'
    }

    selecionadas = []

    for cat_key, cat_nome in categorias.items():
        if cat_key not in config['variaveis']:
            continue

        vars_cat = config['variaveis'][cat_key]
        print(f"\n{cat_nome}:")
        print(f"  Variaveis: {', '.join(vars_cat)}")
        resp = input(f"  Incluir todas? (s/n/lista): ").strip().lower()

        if resp == 's':
            selecionadas.extend(vars_cat)
        elif resp == 'n':
            pass
        else:
            # Permite lista separada por virgula
            vars_escolhidas = [v.strip() for v in resp.split(',')]
            for v in vars_escolhidas:
                if v in vars_cat:
                    selecionadas.append(v)

    return selecionadas


def modo_interativo(config: dict, conn: psycopg2.extensions.connection):
    """Modo interativo para exportacao."""
    print("\n" + "=" * 60)
    print("EXPORTADOR DE TELEMETRIA - MODO INTERATIVO")
    print("=" * 60)

    # Lista devices
    print("\nDispositivos disponiveis:")
    devices = listar_devices(conn)
    for i, row in devices.iterrows():
        status = "ATIVO" if row['is_active'] else "inativo"
        print(f"  [{i+1}] {row['device_id']} ({row['device_model']}) - {status}")
        print(f"      Ultimo dado: {row['last_seen']}")
        print(f"      Total registros: {row['total_telemetry_count']:,}")

    # Seleciona device
    idx = int(input("\nEscolha o dispositivo (numero): ")) - 1
    device_id = devices.iloc[idx]['device_id']

    # Mostra periodo disponivel
    inicio_disp, fim_disp, total = obter_periodo_disponivel(conn, device_id)
    print(f"\nPeriodo disponivel para {device_id}:")
    print(f"  Inicio: {inicio_disp}")
    print(f"  Fim: {fim_disp}")
    print(f"  Total: {total:,} registros")

    # Seleciona periodo
    print("\nDefina o periodo para exportacao:")
    inicio_str = input(f"  Data/hora inicio (YYYY-MM-DD HH:MM ou Enter para {inicio_disp.strftime('%Y-%m-%d %H:%M')}): ").strip()
    if not inicio_str:
        inicio = inicio_disp
    else:
        inicio = datetime.strptime(inicio_str, "%Y-%m-%d %H:%M")

    fim_str = input(f"  Data/hora fim (YYYY-MM-DD HH:MM ou Enter para {fim_disp.strftime('%Y-%m-%d %H:%M')}): ").strip()
    if not fim_str:
        fim = fim_disp
    else:
        fim = datetime.strptime(fim_str, "%Y-%m-%d %H:%M")

    # Seleciona variaveis
    resp = input("\nExportar todas as variaveis? (s/n): ").strip().lower()
    if resp == 's':
        variaveis = obter_todas_variaveis(config)
    else:
        variaveis = selecionar_variaveis_interativo(config)

    print(f"\nVariaveis selecionadas: {', '.join(variaveis)}")

    # Exporta
    print("\n" + "-" * 40)
    df = exportar_telemetria(conn, device_id, inicio, fim, variaveis)

    if df.empty:
        print("Nenhum dado para exportar.")
        return

    # Define nome do arquivo
    output_dir = Path(__file__).parent / config['exportacao']['diretorio_saida']
    output_dir.mkdir(parents=True, exist_ok=True)

    nome_arquivo = f"telemetria_{device_id}_{inicio.strftime('%Y%m%d_%H%M')}_{fim.strftime('%Y%m%d_%H%M')}.csv"
    output_path = output_dir / nome_arquivo

    # Salva
    df.to_csv(output_path, index=False)
    print(f"\nArquivo salvo: {output_path}")
    print(f"Registros: {len(df)}")
    print(f"Colunas: {', '.join(df.columns)}")


def main():
    parser = argparse.ArgumentParser(description='Exportador de Telemetria TimescaleDB')
    parser.add_argument('--listar-devices', action='store_true', help='Lista dispositivos disponiveis')
    parser.add_argument('--interativo', action='store_true', help='Modo interativo')
    parser.add_argument('--device', type=str, help='ID do dispositivo')
    parser.add_argument('--inicio', type=str, help='Data/hora inicio (YYYY-MM-DD HH:MM)')
    parser.add_argument('--fim', type=str, help='Data/hora fim (YYYY-MM-DD HH:MM)')
    parser.add_argument('--variaveis', type=str, help='Variaveis separadas por virgula (ou "todas")')
    parser.add_argument('--output', type=str, help='Caminho do arquivo de saida')
    parser.add_argument('--config', type=str, default='config_db.yaml', help='Arquivo de configuracao')

    args = parser.parse_args()

    # Carrega config
    config = carregar_config(args.config)

    # Conecta ao banco
    print("Conectando ao banco de dados...")
    try:
        conn = conectar_banco(config)
        print("Conectado com sucesso!")
    except Exception as e:
        print(f"Erro ao conectar: {e}")
        sys.exit(1)

    try:
        if args.listar_devices:
            devices = listar_devices(conn)
            print("\nDispositivos disponiveis:")
            print(devices.to_string(index=False))

        elif args.interativo:
            modo_interativo(config, conn)

        elif args.device and args.inicio and args.fim:
            # Modo linha de comando
            device_id = args.device
            inicio = datetime.strptime(args.inicio, "%Y-%m-%d %H:%M")
            fim = datetime.strptime(args.fim, "%Y-%m-%d %H:%M")

            if args.variaveis == 'todas':
                variaveis = obter_todas_variaveis(config)
            elif args.variaveis:
                variaveis = [v.strip() for v in args.variaveis.split(',')]
            else:
                variaveis = obter_todas_variaveis(config)

            df = exportar_telemetria(conn, device_id, inicio, fim, variaveis)

            if not df.empty:
                if args.output:
                    output_path = Path(args.output)
                else:
                    output_dir = Path(__file__).parent / config['exportacao']['diretorio_saida']
                    output_dir.mkdir(parents=True, exist_ok=True)
                    nome = f"telemetria_{device_id}_{inicio.strftime('%Y%m%d_%H%M')}_{fim.strftime('%Y%m%d_%H%M')}.csv"
                    output_path = output_dir / nome

                df.to_csv(output_path, index=False)
                print(f"\nArquivo salvo: {output_path}")
                print(f"Registros: {len(df)}")

        else:
            parser.print_help()
            print("\nExemplos de uso:")
            print("  python exportar_telemetria.py --listar-devices")
            print("  python exportar_telemetria.py --interativo")
            print('  python exportar_telemetria.py --device moto_g34 --inicio "2024-12-20 00:00" --fim "2024-12-20 12:00"')

    finally:
        conn.close()


if __name__ == '__main__':
    main()
