#!/usr/bin/env python3
"""
Servidor HTTP para o Detector Visual de Carregamento
Específico para o arquivo input.csv
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import math
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import os

# Arquivo CSV (por padrão, input.csv ao lado deste script)
DEFAULT_CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'input.csv')
CSV_FILE = os.getenv('CSV_FILE', DEFAULT_CSV_FILE)

# Cache de dados
DATA_CACHE = None


def load_csv_data():
    """Carrega dados do CSV uma vez e mantém em cache."""
    global DATA_CACHE

    if DATA_CACHE is not None:
        return DATA_CACHE

    if not os.path.exists(CSV_FILE):
        raise FileNotFoundError(f"Arquivo não encontrado: {CSV_FILE}")

    print(f"📂 Carregando dados de: {CSV_FILE}")
    df = pd.read_csv(CSV_FILE)

    # Converter timestamp
    df['time'] = pd.to_datetime(df['time'])

    # Criar device_id se não existir (usar um padrão)
    if 'device_id' not in df.columns:
        df['device_id'] = 'VEHICLE-001'

    # Garantir que speed_kmh existe
    if 'speed_kmh' not in df.columns:
        print("❌ ERRO: Coluna 'speed_kmh' não encontrada no CSV!")
        raise ValueError("CSV deve ter coluna 'speed_kmh'")

    # Garantir que linear_accel_magnitude existe
    if 'linear_accel_magnitude' not in df.columns:
        print("❌ ERRO: Coluna 'linear_accel_magnitude' não encontrada no CSV!")
        raise ValueError("CSV deve ter coluna 'linear_accel_magnitude'")

    # Preencher valores nulos com 0
    df['speed_kmh'] = df['speed_kmh'].fillna(0)
    df['linear_accel_magnitude'] = df['linear_accel_magnitude'].fillna(0)
    df['latitude'] = df['latitude'].fillna(0)
    df['longitude'] = df['longitude'].fillna(0)

    DATA_CACHE = df
    print(f"✅ {len(df)} registros carregados")
    print(f"   Período: {df['time'].min()} até {df['time'].max()}")
    print(f"   Colunas: {', '.join(df.columns.tolist())}")

    # Estatísticas básicas
    print("\n📊 Estatísticas dos dados:")
    print(
        f"   Velocidade: min={df['speed_kmh'].min():.2f}, max={df['speed_kmh'].max():.2f}, média={df['speed_kmh'].mean():.2f} km/h"
    )
    print(
        f"   Aceleração: min={df['linear_accel_magnitude'].min():.4f}, max={df['linear_accel_magnitude'].max():.4f}, média={df['linear_accel_magnitude'].mean():.4f} m/s²"
    )

    # Detectar períodos parados
    stopped = (df['speed_kmh'] <= 0.5).sum()
    print(f"   Registros parados (speed <= 0.5 km/h): {stopped} ({100*stopped/len(df):.1f}%)")

    return df


class DetectorInputAPIHandler(BaseHTTPRequestHandler):
    """Handler para requisições HTTP da API do detector (input.csv)."""

    def _set_cors_headers(self):
        """Define headers CORS para permitir requisições do HTML."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _send_json_response(self, data, status=200):
        """Envia resposta JSON."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode('utf-8'))

    def do_OPTIONS(self):
        """Trata requisições OPTIONS (CORS preflight)."""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        """Trata requisições GET."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] GET {path}")

        try:
            if path == '/api/devices':
                self._handle_get_devices()
            elif path == '/api/history':
                self._handle_get_history(query_params)
            elif path == '/health':
                self._send_json_response({
                    'status': 'ok',
                    'source': 'CSV',
                    'file': CSV_FILE,
                    'records': len(DATA_CACHE) if DATA_CACHE is not None else 0
                })
            else:
                self._send_json_response({'error': 'Not found'}, 404)
        except Exception as e:
            print(f"[ERROR] {str(e)}")
            import traceback

            traceback.print_exc()
            self._send_json_response({'error': str(e)}, 500)

    def _handle_get_devices(self):
        """Lista dispositivos disponíveis no CSV."""
        df = load_csv_data()

        devices_info = (
            df.groupby('device_id', dropna=False)
            .agg(
                total_points=('time', 'count'),
                last_seen=('time', 'max'),
            )
            .reset_index()
        )

        devices = []
        for _, row in devices_info.iterrows():
            device_id = row['device_id']
            total_points = row['total_points']
            last_seen = row['last_seen']

            devices.append({
                'device_id': device_id,
                'total_points': int(total_points),
                'last_seen': last_seen.isoformat() if last_seen else None,
                'status': 'offline'  # CSV é sempre histórico
            })

        print(f"  - Retornados: {len(devices)} dispositivos")
        self._send_json_response({
            'devices': devices,
            'count': len(devices)
        })

    def _handle_get_history(self, query_params):
        """Busca histórico de telemetria do CSV."""
        df = load_csv_data()

        # Extrair parâmetros
        device_id = query_params.get('device_id', [None])[0]
        if device_id is not None:
            device_id = device_id.strip() or None

        start_str = query_params.get('start', [None])[0]
        end_str = query_params.get('end', [None])[0]

        try:
            limit = int(query_params.get('limit', ['50000'])[0])
        except (TypeError, ValueError):
            limit = 50000

        if limit <= 0:
            limit = 50000

        # Limitar para evitar respostas gigantes
        limit = min(limit, 200000)

        # Parse de datas
        if start_str:
            start_dt = pd.to_datetime(start_str.replace('Z', '+00:00'))
        else:
            start_dt = df['time'].min()

        if end_str:
            end_dt = pd.to_datetime(end_str.replace('Z', '+00:00'))
        else:
            end_dt = df['time'].max()

        print(f"  - Device: {device_id or 'ALL'}")
        print(f"  - Period: {start_dt} to {end_dt}")
        print(f"  - Limit: {limit}")

        # Filtrar dados
        mask = (df['time'] >= start_dt) & (df['time'] <= end_dt)
        if device_id:
            mask = mask & (df['device_id'] == device_id)

        df_filtered = df[mask].copy()

        # Aplicar limit (fazer sampling se necessário)
        if len(df_filtered) > limit:
            step = math.ceil(len(df_filtered) / limit)
            df_filtered = df_filtered.iloc[::step].copy()
            print(f"  - Aplicado sampling: step={step} (retornando {len(df_filtered)})")

        # Preparar resposta - otimizado com list comprehension e to_dict
        print(f"  - Preparando resposta...")

        # Converter para lista de dicts de forma otimizada
        points = df_filtered[['time', 'device_id', 'speed_kmh', 'linear_accel_magnitude', 'latitude', 'longitude']].to_dict('records')

        # Formatar timestamps e limpar dados
        for point in points:
            point['ts'] = point.pop('time').isoformat()
            point['accel_magnitude'] = point.pop('linear_accel_magnitude')
            # Limpar lat/lon zerados
            if point['latitude'] == 0:
                point['lat'] = None
                point['lon'] = None
            else:
                point['lat'] = point['latitude']
                point['lon'] = point['longitude']
            del point['latitude']
            del point['longitude']

        print(f"  - Returned: {len(points)} points")

        self._send_json_response({
            'count': len(points),
            'device_id': device_id,
            'start': start_dt.isoformat(),
            'end': end_dt.isoformat(),
            'points': points
        })

    def log_message(self, format, *args):
        """Sobrescreve para log customizado."""
        pass


def main():
    """Inicia o servidor HTTP."""
    PORT = int(os.getenv('PORT', '8080'))
    HOST = os.getenv('HOST', '0.0.0.0')

    print("=" * 70)
    print("🚛 SERVIDOR DETECTOR VISUAL - INPUT.CSV")
    print("=" * 70)
    print(f"Servidor iniciado em: http://{HOST}:{PORT}")
    print(f"Arquivo CSV: {CSV_FILE}")
    print("\nEndpoints disponíveis:")
    print(f"  - http://localhost:{PORT}/health")
    print(f"  - http://localhost:{PORT}/api/devices")
    print(f"  - http://localhost:{PORT}/api/history")
    print("\nAbra o detector visual em:")
    print("  - file:///Users/sapucaia/.claude-worktrees/BackTest/serene-mccarthy/BackendTestes/detector_visual.html")
    print("\nPressione Ctrl+C para parar o servidor")
    print("=" * 70)
    print()

    # Carregar dados
    try:
        load_csv_data()
    except Exception as e:
        print(f"❌ ERRO ao carregar CSV: {e}")
        return

    # Iniciar servidor
    try:
        server = HTTPServer((HOST, PORT), DetectorInputAPIHandler)
        print("\n✅ Servidor rodando e pronto para receber requisições!\n")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n⏹️  Servidor encerrado pelo usuário")
        server.shutdown()
    except Exception as e:
        print(f"\n❌ ERRO: {e}")


if __name__ == '__main__':
    main()
