"""
Aplicação web Flask para rotulagem interativa de períodos de carregamento.
Interface web simples e estável.
"""
from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
from pathlib import Path

app = Flask(__name__)

# Caminhos dos arquivos
DATA_FILE = 'amostra/telemetria_20251212_20251213.csv'
PERIODS_FILE = 'amostra/periodos_vibracao_detalhado.csv'
LABELS_FILE = 'amostra/rotulos_carregamento.csv'

def load_telemetry_data():
    """Carrega dados de telemetria."""
    df = pd.read_csv(DATA_FILE)
    df['time'] = pd.to_datetime(df['time'])
    df['speed_kmh'] = df['speed_kmh'].astype(float)
    df['linear_accel_magnitude'] = df['linear_accel_magnitude'].astype(float)
    return df

def load_existing_labels():
    """Carrega rótulos existentes."""
    if os.path.exists(LABELS_FILE):
        return pd.read_csv(LABELS_FILE)
    return pd.DataFrame(columns=['period_id', 'start_time', 'end_time', 'duration_minutes', 'label', 'labeled_at'])

def detect_stop_periods(df, min_duration_minutes=1.0, max_speed=1.0):
    """Detecta períodos de parada."""
    periods = []
    start_idx = None
    
    for i in range(len(df)):
        speed = df.iloc[i]['speed_kmh']
        
        if speed < max_speed:
            if start_idx is None:
                start_idx = i
        else:
            if start_idx is not None:
                start_time = df.iloc[start_idx]['time']
                end_time = df.iloc[i-1]['time']
                duration_seconds = (end_time - start_time).total_seconds()
                duration_minutes = duration_seconds / 60
                
                if duration_minutes >= min_duration_minutes:
                    period_id = f"{start_time.strftime('%Y%m%d_%H%M%S')}_{end_time.strftime('%H%M%S')}"
                    periods.append({
                        'period_id': period_id,
                        'start_idx': int(start_idx),
                        'end_idx': int(i-1),
                        'start_time': start_time.isoformat(),
                        'end_time': end_time.isoformat(),
                        'duration_minutes': float(duration_minutes)
                    })
                start_idx = None
    
    # Último período
    if start_idx is not None:
        start_time = df.iloc[start_idx]['time']
        end_time = df.iloc[len(df)-1]['time']
        duration_seconds = (end_time - start_time).total_seconds()
        duration_minutes = duration_seconds / 60
        
        if duration_minutes >= min_duration_minutes:
            period_id = f"{start_time.strftime('%Y%m%d_%H%M%S')}_{end_time.strftime('%H%M%S')}"
            periods.append({
                'period_id': period_id,
                'start_idx': int(start_idx),
                'end_idx': int(len(df)-1),
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_minutes': float(duration_minutes)
            })
    
    return periods

def filter_uncataloged_periods(all_periods, cataloged_periods, labeled_periods):
    """Filtra períodos não catalogados."""
    uncataloged = []
    
    for period in all_periods:
        start_time = pd.to_datetime(period['start_time'])
        end_time = pd.to_datetime(period['end_time'])
        period_id = period['period_id']
        
        # Verificar se está catalogado
        is_cataloged = False
        if cataloged_periods is not None and len(cataloged_periods) > 0:
            cataloged_periods['start_time'] = pd.to_datetime(cataloged_periods['start_time'])
            cataloged_periods['end_time'] = pd.to_datetime(cataloged_periods['end_time'])
            
            overlap = cataloged_periods[
                ((cataloged_periods['start_time'] <= start_time) & (cataloged_periods['end_time'] >= start_time)) |
                ((cataloged_periods['start_time'] <= end_time) & (cataloged_periods['end_time'] >= end_time)) |
                ((cataloged_periods['start_time'] >= start_time) & (cataloged_periods['end_time'] <= end_time))
            ]
            is_cataloged = len(overlap) > 0
        
        # Verificar se já está rotulado
        is_labeled = period_id in labeled_periods['period_id'].values if len(labeled_periods) > 0 else False
        
        if not is_cataloged and not is_labeled:
            uncataloged.append(period)
    
    return uncataloged

@app.route('/')
def index():
    """Página principal."""
    return render_template('labeling.html')

@app.route('/api/load_periods', methods=['POST'])
def load_periods():
    """Carrega períodos não catalogados."""
    try:
        data = request.json
        min_duration = data.get('min_duration', 1.0)
        max_speed = data.get('max_speed', 1.0)
        
        # Carregar dados
        df = load_telemetry_data()
        
        # Detectar períodos
        all_periods = detect_stop_periods(df, min_duration, max_speed)
        
        # Carregar períodos catalogados
        cataloged_periods = None
        if os.path.exists(PERIODS_FILE):
            cataloged_periods = pd.read_csv(PERIODS_FILE)
        
        # Carregar rótulos
        labeled_periods = load_existing_labels()
        
        # Filtrar
        uncataloged = filter_uncataloged_periods(all_periods, cataloged_periods, labeled_periods)
        
        return jsonify({
            'success': True,
            'periods': uncataloged,
            'total': len(uncataloged)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/period_data/<int:start_idx>/<int:end_idx>')
def get_period_data(start_idx, end_idx):
    """Retorna dados de um período específico."""
    try:
        df = load_telemetry_data()
        
        # Adicionar contexto (1 minuto antes e depois)
        window_start_idx = max(0, start_idx - 60)
        window_end_idx = min(len(df), end_idx + 60)
        
        period_data = df.iloc[window_start_idx:window_end_idx+1]
        
        # Converter para formato JSON
        result = {
            'time': period_data['time'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            'speed_kmh': period_data['speed_kmh'].tolist(),
            'linear_accel_magnitude': period_data['linear_accel_magnitude'].tolist(),
            'period_start_idx': start_idx - window_start_idx,
            'period_end_idx': end_idx - window_start_idx
        }
        
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/save_label', methods=['POST'])
def save_label():
    """Salva um rótulo."""
    try:
        data = request.json
        period_id = data['period_id']
        label = data['label']
        start_time = data['start_time']
        end_time = data['end_time']
        duration_minutes = data['duration_minutes']
        
        # Carregar rótulos existentes
        labels_df = load_existing_labels()
        
        # Remover rótulo existente se houver
        labels_df = labels_df[labels_df['period_id'] != period_id]
        
        # Adicionar novo rótulo
        new_label = pd.DataFrame({
            'period_id': [period_id],
            'start_time': [start_time],
            'end_time': [end_time],
            'duration_minutes': [duration_minutes],
            'label': [label],
            'labeled_at': [datetime.now().isoformat()]
        })
        
        labels_df = pd.concat([labels_df, new_label], ignore_index=True)
        labels_df.to_csv(LABELS_FILE, index=False)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/labels')
def get_labels():
    """Retorna todos os rótulos."""
    try:
        labels_df = load_existing_labels()
        return jsonify({
            'success': True,
            'labels': labels_df.to_dict('records')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export_labels')
def export_labels():
    """Exporta rótulos como CSV."""
    try:
        labels_df = load_existing_labels()
        if len(labels_df) == 0:
            return jsonify({'success': False, 'error': 'Nenhum rótulo para exportar'}), 400
        
        export_file = 'amostra/rotulos_export.csv'
        labels_df.to_csv(export_file, index=False)
        return send_file(export_file, as_attachment=True, download_name='rotulos_carregamento.csv')
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Criar diretório de templates se não existir
    os.makedirs('templates', exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)
