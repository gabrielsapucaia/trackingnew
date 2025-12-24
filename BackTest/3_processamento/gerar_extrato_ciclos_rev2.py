#!/usr/bin/env python3
"""
Gerador de Extrato de Ciclos Operacionais - REV2.

Melhorias da rev2:
1. Detecção mais sensível de paradas (threshold 60s ao invés de apenas dentro de ciclos)
2. Tempo de ATIVIDADE real (mede apenas períodos com vibração)
3. Detecção híbrida de paradas ociosas: 60s threshold + MAD adaptativo
4. Detecção de paradas PRÉ-CICLO (antes do primeiro carregamento)

Gera um extrato onde cada linha representa um ciclo completo:
CARREGAMENTO → DESLOCAMENTO CARREGADO → BASCULAMENTO → DESLOCAMENTO VAZIO → próximo ciclo
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula a distância em km entre dois pontos usando a fórmula de Haversine.
    """
    R = 6371  # Raio da Terra em km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def calcular_distancia_percorrida(df: pd.DataFrame, inicio: datetime, fim: datetime) -> float:
    """
    Calcula a distância total percorrida (soma dos segmentos GPS) entre dois timestamps.

    Args:
        df: DataFrame com telemetria (deve ter colunas 'time', 'latitude', 'longitude')
        inicio: timestamp de início
        fim: timestamp de fim

    Returns:
        Distância total em km
    """
    mask = (df['time'] >= inicio) & (df['time'] <= fim)
    periodo = df[mask].copy()

    if len(periodo) < 2:
        return 0.0

    distancia_total = 0.0
    for i in range(1, len(periodo)):
        lat1 = periodo.iloc[i - 1]['latitude']
        lon1 = periodo.iloc[i - 1]['longitude']
        lat2 = periodo.iloc[i]['latitude']
        lon2 = periodo.iloc[i]['longitude']
        distancia_total += haversine(lat1, lon1, lat2, lon2)

    return distancia_total


@dataclass
class Parada:
    """Representa uma parada detectada."""
    start: datetime
    end: datetime
    duration_sec: float
    latitude: float
    longitude: float
    area_nome: str  # Nome da área ou "Desconhecido"
    area_tipo: str  # "carregamento", "basculamento", ou "desconhecido"
    # Métricas para scoring de basculamento
    pitch_range: float = 0.0  # max - min do pitch durante a parada
    accel_variability: float = 0.0  # desvio padrão da aceleração
    accel_mean: float = 0.0  # aceleração média
    is_ociosa: bool = False  # True se for parada ociosa (sem vibração)


@dataclass
class ParadaOciosa:
    """Representa uma parada ociosa (fila, almoço, café, etc.)."""
    inicio: datetime
    fim: datetime
    duracao_sec: float
    latitude: float
    longitude: float
    ciclo_num: int  # Número do ciclo onde ocorreu (0 = antes do primeiro ciclo)
    fase: str  # "antes_carga", "entre_carga_basc", "apos_basc", "fora_ciclo", "pre_ciclo"


def merge_paradas_intervals(paradas: list, fase_prefix: str) -> float:
    """
    Mescla intervalos de paradas sobrepostos e retorna duração total.

    Isso é necessário porque podem existir sobreposições entre:
    - durante_carga e durante_carga_embutida
    - durante_basc e durante_basc_embutida

    Usar soma simples causaria contagem dupla. Esta função:
    1. Coleta todos os intervalos que começam com o prefixo
    2. Ordena por horário de início
    3. Mescla intervalos sobrepostos
    4. Retorna a duração total sem duplicação

    Args:
        paradas: Lista de ParadaOciosa
        fase_prefix: Prefixo da fase (ex: 'durante_carga', 'durante_basc')

    Returns:
        Duração total em segundos (sem duplicações por sobreposição)
    """
    # Filtrar paradas da fase
    intervals = []
    for p in paradas:
        if p.fase.startswith(fase_prefix):
            intervals.append((p.inicio, p.fim))

    if not intervals:
        return 0.0

    # Ordenar por início
    intervals.sort(key=lambda x: x[0])

    # Mesclar sobreposições
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:  # Há sobreposição
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # Calcular duração total
    total = sum((end - start).total_seconds() for start, end in merged)
    return total


def detectar_todas_paradas_globais(
    df: pd.DataFrame,
    min_duracao_sec: float = 60.0,
    speed_threshold: float = 2.0,
    accel_threshold_ociosa: float = 0.008,
) -> list[dict]:
    """
    Detecta TODAS as paradas >= min_duracao_sec em todo o dataset.

    Esta é a detecção mais sensível - encontra paradas independente de ciclo.
    Inclui paradas antes do primeiro ciclo (como a de 32 min que o baseline perdeu).

    Args:
        df: DataFrame com telemetria
        min_duracao_sec: Duração mínima para considerar parada (60s = mais sensível)
        speed_threshold: Velocidade máxima para considerar parado
        accel_threshold_ociosa: Vibração abaixo deste valor = parada ociosa

    Returns:
        Lista de paradas com métricas
    """
    paradas = []

    # Marcar pontos parados
    df = df.copy()
    df['is_parado'] = df['speed_kmh'] < speed_threshold
    df['parada_group'] = (df['is_parado'] != df['is_parado'].shift()).cumsum()

    for group_id, group in df[df['is_parado']].groupby('parada_group'):
        duracao = len(group)

        if duracao < min_duracao_sec:
            continue

        # Calcular métricas
        lat_mean = group['latitude'].mean()
        lon_mean = group['longitude'].mean()

        # Calcular vibração (accel_std)
        accel_std = 0.0
        if 'linear_accel_magnitude' in group.columns:
            accel_vals = pd.to_numeric(group['linear_accel_magnitude'], errors='coerce').dropna()
            if len(accel_vals) > 1:
                accel_std = float(accel_vals.std())

        # Calcular pitch range
        pitch_range = 0.0
        if 'pitch' in group.columns:
            pitch_vals = pd.to_numeric(group['pitch'], errors='coerce').dropna()
            if len(pitch_vals) > 0:
                pitch_range = float(pitch_vals.max() - pitch_vals.min())

        # Determinar se é ociosa (baixa vibração)
        is_ociosa = accel_std < accel_threshold_ociosa

        paradas.append({
            'inicio': group['time'].iloc[0],
            'fim': group['time'].iloc[-1],
            'duracao_sec': duracao,
            'latitude': lat_mean,
            'longitude': lon_mean,
            'accel_std': accel_std,
            'pitch_range': pitch_range,
            'is_ociosa': is_ociosa,
        })

    return paradas


def detectar_paradas_hibrido(
    paradas_globais: list[dict],
    threshold_fixo_sec: float = 60.0,
    num_mads: float = 3.0,
) -> list[dict]:
    """
    Detecção híbrida de paradas ociosas: threshold fixo 60s + MAD adaptativo.

    Combina dois métodos:
    1. Threshold fixo: paradas >= 60s com baixa vibração
    2. MAD: paradas anormalmente longas (outliers estatísticos)

    Args:
        paradas_globais: Lista de todas as paradas detectadas
        threshold_fixo_sec: Threshold fixo para paradas ociosas
        num_mads: Número de MADs para considerar outlier

    Returns:
        Lista de paradas classificadas como ociosas
    """
    if not paradas_globais:
        return []

    # Método 1: Threshold fixo 60s com baixa vibração
    ociosas_60s = [
        p for p in paradas_globais
        if p['duracao_sec'] >= threshold_fixo_sec and p['is_ociosa']
    ]

    # Método 2: MAD para paradas anormalmente longas
    duracoes = [p['duracao_sec'] for p in paradas_globais]
    mediana = float(np.median(duracoes))
    mad = float(np.median([abs(d - mediana) for d in duracoes]))

    # Threshold MAD (1.4826 converte MAD para escala de desvio padrão)
    MAD_SCALE = 1.4826
    threshold_mad = mediana + num_mads * MAD_SCALE * mad

    ociosas_mad = [
        p for p in paradas_globais
        if p['duracao_sec'] > threshold_mad
    ]

    # União dos dois métodos (sem duplicatas)
    # Usar timestamp de início como chave única
    vistas = set()
    todas_ociosas = []

    for p in ociosas_60s + ociosas_mad:
        key = str(p['inicio'])
        if key not in vistas:
            vistas.add(key)
            todas_ociosas.append(p)

    return todas_ociosas


@dataclass
class Ciclo:
    """Representa um ciclo operacional completo."""
    numero: int
    # Carregamento
    carga_area: str
    carga_inicio: datetime
    carga_fim: datetime
    carga_duracao_sec: float
    # Deslocamento carregado
    desloc_carregado_sec: float
    # Basculamento
    basculamento_area: str
    # Campos com valores default
    desloc_carregado_km: float = 0.0  # Distância percorrida em km
    basculamento_inicio: Optional[datetime] = None
    basculamento_fim: Optional[datetime] = None
    basculamento_duracao_sec: float = 0.0
    # Deslocamento vazio
    desloc_vazio_sec: float = 0.0
    desloc_vazio_km: float = 0.0  # Distância percorrida em km
    # Total
    ciclo_total_sec: float = 0.0
    # Paradas ociosas durante este ciclo
    paradas_ociosas: list = field(default_factory=list)
    # Durações limpas (original - paradas embutidas)
    carga_duracao_limpa_sec: float = 0.0
    basculamento_duracao_limpa_sec: float = 0.0

    @property
    def desloc_carregado_min_km(self) -> float:
        """Retorna minutos por km para deslocamento carregado."""
        if self.desloc_carregado_km > 0:
            return (self.desloc_carregado_sec / 60) / self.desloc_carregado_km
        return 0.0

    @property
    def desloc_vazio_min_km(self) -> float:
        """Retorna minutos por km para deslocamento vazio."""
        if self.desloc_vazio_km > 0:
            return (self.desloc_vazio_sec / 60) / self.desloc_vazio_km
        return 0.0


def ponto_em_poligono(lat: float, lon: float, polygon_coords: list) -> bool:
    """Verifica se um ponto está dentro de um polígono usando ray casting."""
    n = len(polygon_coords)
    inside = False
    x, y = lon, lat
    p1x, p1y = polygon_coords[0]

    for i in range(1, n + 1):
        p2x, p2y = polygon_coords[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def identificar_area(lat: float, lon: float, poligonos: list) -> tuple[str, str]:
    """
    Identifica em qual área um ponto está.

    Returns:
        Tupla (nome_area, tipo_area)
    """
    for poly in poligonos:
        coords = poly['geometry']['coordinates'][0]
        if ponto_em_poligono(lat, lon, coords):
            nome = poly['properties'].get('name', 'Sem nome')
            tipo = poly['properties'].get('type', 'desconhecido')
            return nome, tipo
    return "Desconhecido", "desconhecido"


def detectar_carregamentos_automatico(
    df: pd.DataFrame,
    poligonos: list,
    min_duracao_sec: float = 60.0,
    speed_threshold: float = 1.0,
    accel_threshold: float = 0.012,
) -> pd.DataFrame:
    """
    Detecta automaticamente eventos de carregamento a partir da telemetria.

    Estratégia:
    1. Detectar todas as paradas em áreas conhecidas
    2. Identificar padrão de alternância entre áreas (ciclos)
    3. A área mais frequente como "primeiro destino" é carregamento
    4. Filtrar para manter apenas alternâncias válidas

    Args:
        df: DataFrame com dados de telemetria
        poligonos: Lista de polígonos das áreas
        min_duracao_sec: Duração mínima para considerar carregamento
        speed_threshold: Velocidade máxima para considerar parado
        accel_threshold: Threshold de vibração para confirmar atividade

    Returns:
        DataFrame com eventos de carregamento detectados
    """
    print("  Detectando paradas em áreas conhecidas...")

    # Fase 1: Detectar todas as paradas em áreas
    todas_paradas = _detectar_todas_paradas_em_areas(
        df, poligonos, min_duracao_sec, speed_threshold, accel_threshold
    )

    if not todas_paradas:
        return pd.DataFrame(columns=['start', 'end', 'duration_sec', 'latitude', 'longitude', 'area'])

    print(f"    {len(todas_paradas)} paradas detectadas")

    # Fase 2: Consolidar paradas consecutivas na mesma área
    paradas_consolidadas = _consolidar_paradas_consecutivas(todas_paradas)
    print(f"    {len(paradas_consolidadas)} paradas após consolidação")

    # Fase 3: Identificar área principal de carregamento
    # (a área que aparece mais vezes como ponto inicial de alternância)
    area_carga = _identificar_area_carregamento(paradas_consolidadas)
    print(f"    Área de carregamento identificada: {area_carga}")

    # Fase 4: Filtrar apenas paradas na área de carregamento
    carregamentos = [p for p in paradas_consolidadas if p['area'] == area_carga]
    print(f"    {len(carregamentos)} eventos de carregamento")

    if carregamentos:
        return pd.DataFrame(carregamentos)
    else:
        return pd.DataFrame(columns=['start', 'end', 'duration_sec', 'latitude', 'longitude', 'area'])


def _detectar_todas_paradas_em_areas(
    df: pd.DataFrame,
    poligonos: list,
    min_duracao_sec: float,
    speed_threshold: float,
    accel_threshold: float,
    moving_tolerance: int = 10,  # Tolerância para picos de velocidade
) -> list[dict]:
    """
    Detecta todas as paradas em áreas conhecidas.

    Args:
        moving_tolerance: Número de pontos consecutivos em movimento antes de
                         considerar que a parada realmente terminou. Isso evita
                         que pequenos picos de velocidade (GPS jitter) quebrem
                         a detecção de carregamento.
    """
    paradas = []
    seg_start = None
    seg_indices = []
    seg_lat_sum = 0.0
    seg_lon_sum = 0.0
    seg_count = 0
    prev_time = None
    current_area = None
    consecutive_moving = 0  # Contador de pontos consecutivos em movimento

    for idx, row in df.iterrows():
        is_stopped = row['speed_kmh'] < speed_threshold
        area_nome, _ = identificar_area(row['latitude'], row['longitude'], poligonos)

        if is_stopped and area_nome != "Desconhecido":
            # Resetar contador de movimento
            consecutive_moving = 0

            gap = 0
            if prev_time is not None:
                gap = (row['time'] - prev_time).total_seconds()

            if seg_start is None or gap > 60 or area_nome != current_area:
                if seg_count > 0 and seg_indices:
                    parada = _processar_segmento_carregamento(
                        df, seg_indices, seg_start, prev_time,
                        seg_count, seg_lat_sum, seg_lon_sum,
                        current_area, min_duracao_sec, accel_threshold
                    )
                    if parada:
                        paradas.append(parada)

                seg_start = row['time']
                seg_lat_sum = row['latitude']
                seg_lon_sum = row['longitude']
                seg_count = 1
                seg_indices = [idx]
                current_area = area_nome
            else:
                seg_lat_sum += row['latitude']
                seg_lon_sum += row['longitude']
                seg_count += 1
                seg_indices.append(idx)

            prev_time = row['time']
        else:
            # Ponto em movimento ou fora de área conhecida
            if seg_count > 0:
                consecutive_moving += 1

                # Ainda incluir o ponto no segmento (tolerância)
                if consecutive_moving <= moving_tolerance:
                    seg_lat_sum += row['latitude']
                    seg_lon_sum += row['longitude']
                    seg_count += 1
                    seg_indices.append(idx)
                    prev_time = row['time']
                else:
                    # Tolerância excedida, finalizar segmento
                    # Remover os últimos pontos de tolerância
                    if len(seg_indices) > moving_tolerance:
                        seg_indices = seg_indices[:-moving_tolerance]
                        seg_count = len(seg_indices)
                        if seg_indices:
                            seg_lat_sum = df.loc[seg_indices, 'latitude'].sum()
                            seg_lon_sum = df.loc[seg_indices, 'longitude'].sum()
                            prev_time = df.loc[seg_indices[-1], 'time']

                    if seg_count > 0 and seg_indices:
                        parada = _processar_segmento_carregamento(
                            df, seg_indices, seg_start, prev_time,
                            seg_count, seg_lat_sum, seg_lon_sum,
                            current_area, min_duracao_sec, accel_threshold
                        )
                        if parada:
                            paradas.append(parada)

                    seg_start = None
                    seg_count = 0
                    seg_lat_sum = 0.0
                    seg_lon_sum = 0.0
                    seg_indices = []
                    current_area = None
                    consecutive_moving = 0

    if seg_count > 0 and seg_indices:
        parada = _processar_segmento_carregamento(
            df, seg_indices, seg_start, prev_time,
            seg_count, seg_lat_sum, seg_lon_sum,
            current_area, min_duracao_sec, accel_threshold
        )
        if parada:
            paradas.append(parada)

    return paradas


def _consolidar_paradas_consecutivas(paradas: list[dict]) -> list[dict]:
    """Consolida paradas consecutivas na mesma área."""
    if not paradas:
        return []

    consolidadas = []
    atual = paradas[0].copy()

    for p in paradas[1:]:
        # Se mesma área e gap < 5 minutos, consolidar
        gap = (p['start'] - atual['end']).total_seconds()
        if p['area'] == atual['area'] and gap < 300:
            atual['end'] = p['end']
            atual['duration_sec'] = (atual['end'] - atual['start']).total_seconds()
        else:
            consolidadas.append(atual)
            atual = p.copy()

    consolidadas.append(atual)
    return consolidadas


def _identificar_area_carregamento(paradas: list[dict]) -> str:
    """
    Identifica qual área é a de carregamento baseado no padrão de uso.

    Estratégia: A área que mais aparece como "primeiro destino" após mudança
    de área é provavelmente a área de carregamento.
    """
    if not paradas:
        return ""

    # Contar frequência de cada área
    contagem = {}
    for p in paradas:
        area = p['area']
        contagem[area] = contagem.get(area, 0) + 1

    # A área mais frequente é provavelmente a de carregamento
    # (caminhões passam mais tempo carregando)
    area_mais_frequente = max(contagem.items(), key=lambda x: x[1])[0]
    return area_mais_frequente


def _processar_segmento_carregamento(
    df: pd.DataFrame,
    indices: list,
    start: datetime,
    end: datetime,
    count: int,
    lat_sum: float,
    lon_sum: float,
    area_nome: str,
    min_duracao_sec: float,
    accel_threshold: float,
) -> Optional[dict]:
    """
    Processa um segmento para verificar se é um evento de carregamento válido.

    Estratégia melhorada:
    1. Dividir o segmento em janelas de 30s
    2. Contar quantas janelas têm vibração (atividade)
    3. Só aceitar se >= 50% das janelas têm atividade
    4. Ajustar início/fim para incluir apenas períodos com atividade
    """
    duracao = (end - start).total_seconds()

    if duracao < min_duracao_sec:
        return None

    seg_data = df.loc[indices].copy()

    if 'linear_accel_magnitude' not in seg_data.columns:
        return None

    # Dividir em janelas de 30 segundos e verificar atividade em cada uma
    seg_data['accel'] = pd.to_numeric(seg_data['linear_accel_magnitude'], errors='coerce')
    seg_data = seg_data.dropna(subset=['accel'])

    if len(seg_data) < 10:
        return None

    # Calcular variabilidade por janela de 30s
    seg_data['window'] = ((seg_data['time'] - seg_data['time'].iloc[0]).dt.total_seconds() // 30).astype(int)

    janelas_com_atividade = []
    for window_id, group in seg_data.groupby('window'):
        if len(group) >= 5:
            accel_std = group['accel'].std()
            if accel_std >= accel_threshold:
                janelas_com_atividade.append({
                    'window': window_id,
                    'start': group['time'].min(),
                    'end': group['time'].max(),
                    'accel_std': accel_std
                })

    if not janelas_com_atividade:
        return None

    # Encontrar o MAIOR bloco contíguo de janelas ativas
    # Janelas são contíguas se window_id difere por no máximo 6 (permitir 5 gaps)
    # Isso é importante porque durante carregamento pode haver períodos de espera
    # sem vibração (ex: aguardando posicionamento da pá carregadeira)
    janelas_com_atividade.sort(key=lambda x: x['window'])

    blocos = []
    bloco_atual = [janelas_com_atividade[0]]

    for j in janelas_com_atividade[1:]:
        # Contíguo se diferença <= 6 (permite 5 janelas de gap = ~2.5 min)
        if j['window'] - bloco_atual[-1]['window'] <= 6:
            bloco_atual.append(j)
        else:
            blocos.append(bloco_atual)
            bloco_atual = [j]
    blocos.append(bloco_atual)

    # Encontrar o maior bloco por duração
    melhor_bloco = max(blocos, key=lambda b: len(b))

    # Calcular duração do melhor bloco
    start_real = min(j['start'] for j in melhor_bloco)
    end_real = max(j['end'] for j in melhor_bloco)
    duracao_real = (end_real - start_real).total_seconds()

    if duracao_real < min_duracao_sec:
        return None

    return {
        'start': start_real,
        'end': end_real,
        'duration_sec': duracao_real,
        'latitude': lat_sum / count,
        'longitude': lon_sum / count,
        'area': area_nome,
    }


def encontrar_paradas(
    df: pd.DataFrame,
    inicio: datetime,
    fim: datetime,
    min_duracao_sec: float = 20.0,
    speed_threshold: float = 3.0,
    moving_tolerance: int = 5,
) -> list[dict]:
    """
    Encontra paradas em um intervalo de tempo.

    Args:
        df: DataFrame com dados de telemetria
        inicio: Início do intervalo
        fim: Fim do intervalo
        min_duracao_sec: Duração mínima para considerar uma parada
        speed_threshold: Velocidade máxima para considerar parado (aumentado para 3.0 km/h)
        moving_tolerance: Número de pontos "em movimento" tolerados antes de quebrar a parada

    Returns:
        Lista de paradas encontradas com métricas de sensor
    """
    mask = (df['time'] > inicio) & (df['time'] < fim)
    interval = df[mask].copy()

    if len(interval) == 0:
        return []

    paradas = []
    seg_start = None
    seg_lat_sum = 0.0
    seg_lon_sum = 0.0
    seg_count = 0
    prev_time = None
    seg_indices = []  # Índices das linhas no segmento atual
    moving_count = 0  # Contador de pontos consecutivos em movimento

    for idx, row in interval.iterrows():
        is_stopped = row['speed_kmh'] < speed_threshold

        if is_stopped:
            moving_count = 0  # Reset contador de movimento
            gap = 0
            if prev_time is not None:
                gap = (row['time'] - prev_time).total_seconds()

            if seg_start is None or gap > 10:
                # Salvar segmento anterior se válido
                if seg_count >= min_duracao_sec and seg_indices:
                    parada = _criar_parada_com_metricas(
                        interval, seg_indices, seg_start, prev_time,
                        seg_count, seg_lat_sum, seg_lon_sum
                    )
                    paradas.append(parada)
                seg_start = row['time']
                seg_lat_sum = row['latitude']
                seg_lon_sum = row['longitude']
                seg_count = 1
                seg_indices = [idx]
            else:
                seg_lat_sum += row['latitude']
                seg_lon_sum += row['longitude']
                seg_count += 1
                seg_indices.append(idx)
            prev_time = row['time']
        else:
            moving_count += 1
            # Só quebra a parada se houver múltiplos pontos consecutivos em movimento
            if moving_count >= moving_tolerance:
                if seg_count >= min_duracao_sec and seg_indices:
                    parada = _criar_parada_com_metricas(
                        interval, seg_indices, seg_start, prev_time,
                        seg_count, seg_lat_sum, seg_lon_sum
                    )
                    paradas.append(parada)
                seg_start = None
                seg_count = 0
                seg_lat_sum = 0.0
                seg_lon_sum = 0.0
                seg_indices = []
                moving_count = 0

    # Último segmento
    if seg_count >= min_duracao_sec and seg_indices:
        parada = _criar_parada_com_metricas(
            interval, seg_indices, seg_start, prev_time,
            seg_count, seg_lat_sum, seg_lon_sum
        )
        paradas.append(parada)

    return paradas


def _criar_parada_com_metricas(
    df: pd.DataFrame,
    indices: list,
    start: datetime,
    end: datetime,
    count: int,
    lat_sum: float,
    lon_sum: float,
) -> dict:
    """
    Cria um dicionário de parada com métricas de sensor.
    """
    seg_data = df.loc[indices]

    # Calcular métricas de pitch
    pitch_range = 0.0
    if 'pitch' in seg_data.columns:
        pitch_vals = pd.to_numeric(seg_data['pitch'], errors='coerce').dropna()
        if len(pitch_vals) > 0:
            pitch_range = float(pitch_vals.max() - pitch_vals.min())

    # Calcular métricas de aceleração
    accel_variability = 0.0
    accel_mean = 0.0
    if 'linear_accel_magnitude' in seg_data.columns:
        accel_vals = pd.to_numeric(seg_data['linear_accel_magnitude'], errors='coerce').dropna()
        if len(accel_vals) > 0:
            accel_mean = float(accel_vals.mean())
            accel_variability = float(accel_vals.std()) if len(accel_vals) > 1 else 0.0

    # Determinar se é parada ociosa (baixa vibração)
    # Threshold: variabilidade < 0.012 (abaixo do threshold de carregamento)
    is_ociosa = accel_variability < 0.012

    return {
        'start': start,
        'end': end,
        'duration_sec': count,
        'lat': lat_sum / count,
        'lon': lon_sum / count,
        'pitch_range': pitch_range,
        'accel_variability': accel_variability,
        'accel_mean': accel_mean,
        'is_ociosa': is_ociosa,
    }


# =============================================================================
# THRESHOLDS PARA DETECÇÃO DE PARADAS EMBUTIDAS
# =============================================================================
# Fases com duração acima destes thresholds provavelmente têm paradas ociosas
CARGA_MAX_NORMAL_SEC = 8 * 60      # 8 minutos
BASC_MAX_NORMAL_SEC = 2 * 60       # 2 minutos
DESLOC_MAX_MIN_KM = 7.0            # 7 min/km

# Thresholds de atividade
CARGA_VIBR_MIN = 0.012    # Carregamento: vibração mínima para considerar ativo
BASC_VIBR_MIN = 0.012     # Basculamento: vibração mínima para considerar ativo
DESLOC_SPEED_MIN = 3.0    # Deslocamento: velocidade mínima para considerar em movimento (km/h)

# Duração mínima para considerar parada embutida (segundos)
MIN_PARADA_EMBUTIDA_SEC = 30


def extrair_paradas_embutidas(
    telemetria: pd.DataFrame,
    inicio: datetime,
    fim: datetime,
    fase: str,
    ciclo_num: int,
) -> tuple[float, list[ParadaOciosa]]:
    """
    Extrai paradas ociosas embutidas dentro de uma fase.

    Analisa a telemetria do período e identifica segmentos de baixa atividade:
    - Para carregamento/basculamento: segmentos com baixa vibração (accel_std < threshold)
    - Para deslocamentos: segmentos com baixa velocidade (< 3 km/h)

    Args:
        telemetria: DataFrame com telemetria completa
        inicio: Início do período da fase
        fim: Fim do período da fase
        fase: Tipo da fase ("carregamento", "basculamento", "desloc_carregado", "desloc_vazio")
        ciclo_num: Número do ciclo

    Returns:
        Tupla (duracao_ativa_sec, lista_paradas_embutidas)
    """
    mask = (telemetria['time'] >= inicio) & (telemetria['time'] <= fim)
    seg = telemetria[mask].copy()

    if len(seg) < 2:
        duracao_total = (fim - inicio).total_seconds()
        return duracao_total, []

    duracao_total = (fim - inicio).total_seconds()

    # Determinar critério de atividade baseado na fase
    if fase in ['carregamento', 'basculamento']:
        # Para carregamento/basculamento, usar vibração
        threshold = CARGA_VIBR_MIN if fase == 'carregamento' else BASC_VIBR_MIN

        # Calcular vibração por janela de 10s
        seg['window'] = ((seg['time'] - seg['time'].iloc[0]).dt.total_seconds() // 10).astype(int)

        # Calcular accel_std por janela
        if 'linear_accel_magnitude' not in seg.columns:
            return duracao_total, []

        seg['accel'] = pd.to_numeric(seg['linear_accel_magnitude'], errors='coerce')

        janela_stats = seg.groupby('window').agg({
            'accel': 'std',
            'time': ['min', 'max'],
            'latitude': 'mean',
            'longitude': 'mean'
        }).reset_index()

        janela_stats.columns = ['window', 'accel_std', 'time_min', 'time_max', 'lat', 'lon']
        janela_stats['ativo'] = janela_stats['accel_std'].fillna(0) >= threshold

    else:
        # Para deslocamentos, usar velocidade
        seg['window'] = ((seg['time'] - seg['time'].iloc[0]).dt.total_seconds() // 10).astype(int)

        janela_stats = seg.groupby('window').agg({
            'speed_kmh': 'mean',
            'time': ['min', 'max'],
            'latitude': 'mean',
            'longitude': 'mean'
        }).reset_index()

        janela_stats.columns = ['window', 'speed_mean', 'time_min', 'time_max', 'lat', 'lon']
        janela_stats['ativo'] = janela_stats['speed_mean'] >= DESLOC_SPEED_MIN

    if len(janela_stats) == 0:
        return duracao_total, []

    # Agrupar períodos contíguos inativos
    janela_stats['grupo'] = (janela_stats['ativo'] != janela_stats['ativo'].shift()).cumsum()

    paradas_embutidas = []
    duracao_ativa = 0.0

    for gid, g in janela_stats.groupby('grupo'):
        duracao_grupo = (g['time_max'].max() - g['time_min'].min()).total_seconds()

        if g['ativo'].iloc[0]:
            duracao_ativa += duracao_grupo
        else:
            # Período inativo
            if duracao_grupo >= MIN_PARADA_EMBUTIDA_SEC:
                # Mapear fase para nome correto
                fase_nome = {
                    'carregamento': 'durante_carga',
                    'basculamento': 'durante_basc',
                    'desloc_carregado': 'entre_carga_basc',
                    'desloc_vazio': 'apos_basc'
                }.get(fase, fase)

                paradas_embutidas.append(ParadaOciosa(
                    inicio=g['time_min'].min(),
                    fim=g['time_max'].max(),
                    duracao_sec=duracao_grupo,
                    latitude=g['lat'].mean(),
                    longitude=g['lon'].mean(),
                    ciclo_num=ciclo_num,
                    fase=f"{fase_nome}_embutida"
                ))

    return duracao_ativa, paradas_embutidas


def calcular_score_basculamento(parada: dict) -> float:
    """
    Calcula um score de basculamento baseado nas métricas de sensor.

    Basculamento típico tem:
    - Pitch range alto (caçamba subindo/descendo)
    - Variabilidade de aceleração alta (vibração do material)

    Returns:
        Score de 0 a 100
    """
    score = 0.0

    # Pitch range: 0-2° = 0pts, 2-5° = 25pts, 5-10° = 50pts, >10° = 75pts
    pitch_range = parada.get('pitch_range', 0)
    if pitch_range >= 10:
        score += 40
    elif pitch_range >= 5:
        score += 30
    elif pitch_range >= 2:
        score += 15

    # Variabilidade de aceleração: 0-0.02 = 0pts, 0.02-0.05 = 25pts, >0.05 = 50pts
    accel_var = parada.get('accel_variability', 0)
    if accel_var >= 0.05:
        score += 40
    elif accel_var >= 0.02:
        score += 25
    elif accel_var >= 0.012:
        score += 10

    # Aceleração média alta indica atividade (máx 20pts)
    accel_mean = parada.get('accel_mean', 0)
    if accel_mean >= 0.05:
        score += 20
    elif accel_mean >= 0.02:
        score += 10

    return score


def encontrar_basculamento(
    paradas: list[dict],
    poligonos: list,
) -> Optional[dict]:
    """
    Encontra o basculamento mais provável entre as paradas.

    Estratégia:
    1. Se há paradas em áreas de basculamento conhecidas, escolhe a PRIMEIRA
       (o caminhão descarrega antes de retornar, então a primeira parada na área
       de basculamento é a mais provável de ser o basculamento real)
    2. Senão, entre paradas >= 30s, escolhe a com maior score de basculamento
    3. Score baseado em pitch range + variabilidade de aceleração
    """
    if not paradas:
        return None

    # Filtrar paradas válidas (>= 20s e não ociosas para basculamento)
    paradas_validas = [p for p in paradas if p['duration_sec'] >= 20 and not p.get('is_ociosa', False)]

    if not paradas_validas:
        # Tentar sem filtro de is_ociosa
        paradas_validas = [p for p in paradas if p['duration_sec'] >= 20]

    if not paradas_validas:
        return None

    # Primeiro, buscar paradas em áreas de basculamento
    paradas_em_area = []
    for parada in paradas_validas:
        nome, tipo = identificar_area(parada['lat'], parada['lon'], poligonos)
        if tipo == 'basculamento':
            parada['area_nome'] = nome
            parada['area_tipo'] = tipo
            parada['score'] = calcular_score_basculamento(parada)
            paradas_em_area.append(parada)

    # Se encontrou paradas em áreas de basculamento, escolher usando SCORE COMBINADO
    # Score combinado = score × (duração/30) - dá peso à duração normalizada
    # Isso evita escolher paradas muito curtas com alta vibração momentânea
    if paradas_em_area:
        # FILTRO 1: Excluir paradas muito longas (> 10 min provavelmente inclui ociosa)
        # e paradas ociosas (baixa vibração = não está basculando)
        MAX_DURACAO_PARADA = 600  # 10 min max para uma parada individual
        MIN_VIBRACAO_BASCULAMENTO = 0.008

        paradas_ativas = [p for p in paradas_em_area
                         if p.get('duration_sec', 0) <= MAX_DURACAO_PARADA
                         and p.get('accel_variability', 0) >= MIN_VIBRACAO_BASCULAMENTO]

        # Se não há paradas ativas, tentar só com filtro de duração
        if not paradas_ativas:
            paradas_ativas = [p for p in paradas_em_area
                             if p.get('duration_sec', 0) <= MAX_DURACAO_PARADA]

        # Se ainda não há paradas válidas, usar todas (fallback)
        if not paradas_ativas:
            paradas_ativas = paradas_em_area

        # FILTRO 2: Cap de duração para score (3 × mediana típica de basculamento)
        MAX_DURACAO_BASCULAMENTO = 256  # ~4.3 min (3 × 85.5s mediana)

        # Calcular score combinado: score × (duração/30) com cap
        for p in paradas_ativas:
            duracao = min(p.get('duration_sec', 20), MAX_DURACAO_BASCULAMENTO)
            p['score_combinado'] = p['score'] * (duracao / 30.0)

        # Ordenar por score combinado (maior primeiro), depois por tempo (mais cedo primeiro)
        paradas_ativas.sort(key=lambda p: (-p['score_combinado'], p['start']))
        return paradas_ativas[0]

    # Se não encontrou em área conhecida, calcular scores e escolher o melhor
    for parada in paradas_validas:
        nome, tipo = identificar_area(parada['lat'], parada['lon'], poligonos)
        parada['area_nome'] = nome if tipo != 'desconhecido' else 'Desconhecido'
        parada['area_tipo'] = tipo
        parada['score'] = calcular_score_basculamento(parada)

    # Retornar a parada com maior score (mínimo de 20 pontos para ser considerado)
    melhor = max(paradas_validas, key=lambda p: p.get('score', 0))
    if melhor.get('score', 0) >= 20:
        return melhor

    # Se nenhuma tem score bom, retornar a primeira >= 30s
    for parada in paradas:
        if parada['duration_sec'] >= 30:
            nome, tipo = identificar_area(parada['lat'], parada['lon'], poligonos)
            parada['area_nome'] = nome if tipo != 'desconhecido' else 'Desconhecido'
            parada['area_tipo'] = tipo
            return parada

    return None


def _filtrar_carregamentos_validos(
    carregamentos: pd.DataFrame,
    telemetria: pd.DataFrame,
    poligonos: list,
) -> pd.DataFrame:
    """
    Filtra carregamentos que resultariam em ciclos inválidos.

    Um ciclo é inválido se:
    - O basculamento acontece na mesma área do carregamento (indica falso positivo)

    Carregamentos inválidos são removidos e seus eventos são "absorvidos" pelo
    próximo carregamento válido.
    """
    if len(carregamentos) == 0:
        return carregamentos

    indices_validos = []

    for i in range(len(carregamentos)):
        carga = carregamentos.iloc[i]
        carga_inicio = carga['start']
        carga_fim = carga['end']

        # Identificar área de carregamento
        carga_area, _ = identificar_area(
            float(carga['latitude']),
            float(carga['longitude']),
            poligonos
        )

        # Determinar fim do intervalo (início do próximo carregamento ou fim dos dados)
        if i < len(carregamentos) - 1:
            prox_carga_inicio = carregamentos.iloc[i + 1]['start']
        else:
            prox_carga_inicio = telemetria['time'].max()

        # Encontrar paradas entre este carregamento e o próximo
        paradas = encontrar_paradas(telemetria, carga_fim, prox_carga_inicio)

        # Encontrar basculamento
        basculamento = encontrar_basculamento(paradas, poligonos)

        # Verificar se o ciclo seria válido
        if basculamento:
            basc_area = basculamento.get('area_nome', '')
            # Ciclo inválido se basculamento na mesma área do carregamento
            if basc_area == carga_area:
                print(f"    Removendo carregamento falso em {carga_inicio} "
                      f"(basculamento na mesma área: {carga_area})")
                continue

        indices_validos.append(i)

    return carregamentos.iloc[indices_validos].reset_index(drop=True)


@dataclass
class EstatisticasCiclos:
    """Estatísticas robustas dos ciclos para detecção de anomalias (mediana + MAD)."""
    # Carregamento
    carga_mediana: float = 0.0
    carga_mad: float = 0.0  # Median Absolute Deviation
    # Basculamento
    basc_mediana: float = 0.0
    basc_mad: float = 0.0
    # Deslocamento carregado (min/km)
    desloc_carregado_min_km_mediana: float = 0.0
    desloc_carregado_min_km_mad: float = 0.0
    # Deslocamento vazio (min/km)
    desloc_vazio_min_km_mediana: float = 0.0
    desloc_vazio_min_km_mad: float = 0.0


def calcular_mad(valores: list) -> float:
    """
    Calcula o MAD (Median Absolute Deviation) de uma lista de valores.

    MAD = median(|Xi - median(X)|)

    Para converter em escala comparável ao desvio padrão:
    σ ≈ 1.4826 * MAD (para distribuição normal)
    """
    if len(valores) < 2:
        return 0.0
    mediana = np.median(valores)
    desvios_absolutos = [abs(x - mediana) for x in valores]
    return float(np.median(desvios_absolutos))


def calcular_estatisticas_ciclos(ciclos: list[Ciclo]) -> EstatisticasCiclos:
    """
    Calcula estatísticas ROBUSTAS (mediana + MAD) para cada fase dos ciclos.

    Usa mediana e MAD ao invés de média e desvio padrão para ser resistente
    a outliers. Um outlier extremo não afeta a mediana nem o MAD.

    Args:
        ciclos: Lista de ciclos gerados

    Returns:
        EstatisticasCiclos com medianas e MADs
    """
    if not ciclos:
        return EstatisticasCiclos()

    # Extrair valores de cada fase
    cargas = [c.carga_duracao_sec for c in ciclos]
    bascs = [c.basculamento_duracao_sec for c in ciclos if c.basculamento_duracao_sec > 0]
    desloc_carreg_min_km = [c.desloc_carregado_min_km for c in ciclos if c.desloc_carregado_km > 0.1]
    desloc_vazio_min_km = [c.desloc_vazio_min_km for c in ciclos if c.desloc_vazio_km > 0.1]

    return EstatisticasCiclos(
        carga_mediana=float(np.median(cargas)) if cargas else 0.0,
        carga_mad=calcular_mad(cargas),
        basc_mediana=float(np.median(bascs)) if bascs else 0.0,
        basc_mad=calcular_mad(bascs),
        desloc_carregado_min_km_mediana=float(np.median(desloc_carreg_min_km)) if desloc_carreg_min_km else 0.0,
        desloc_carregado_min_km_mad=calcular_mad(desloc_carreg_min_km),
        desloc_vazio_min_km_mediana=float(np.median(desloc_vazio_min_km)) if desloc_vazio_min_km else 0.0,
        desloc_vazio_min_km_mad=calcular_mad(desloc_vazio_min_km),
    )


def encontrar_parada_real_no_periodo(
    telemetria: pd.DataFrame,
    inicio: datetime,
    fim: datetime,
    speed_threshold: float = 3.0,
    min_duracao_sec: float = 60.0,
) -> Optional[dict]:
    """
    Encontra a maior parada real (velocidade baixa) dentro de um período.

    Retorna as coordenadas exatas onde o veículo parou, não a média do período.

    Returns:
        Dict com 'inicio', 'fim', 'duracao_sec', 'lat', 'lon' ou None se não encontrar
    """
    mask = (telemetria['time'] >= inicio) & (telemetria['time'] <= fim)
    periodo = telemetria[mask].copy()

    if len(periodo) < 2:
        return None

    # Encontrar segmentos de parada
    paradas = []
    em_parada = False
    inicio_parada = None
    lat_parada = None
    lon_parada = None

    for idx, row in periodo.iterrows():
        is_stopped = row['speed_kmh'] < speed_threshold

        if is_stopped and not em_parada:
            em_parada = True
            inicio_parada = row['time']
            lat_parada = row['latitude']
            lon_parada = row['longitude']
        elif not is_stopped and em_parada:
            em_parada = False
            fim_parada = row['time']
            duracao = (fim_parada - inicio_parada).total_seconds()
            if duracao >= min_duracao_sec:
                paradas.append({
                    'inicio': inicio_parada,
                    'fim': fim_parada,
                    'duracao_sec': duracao,
                    'lat': lat_parada,
                    'lon': lon_parada
                })

    # Se ainda em parada no final do período
    if em_parada and inicio_parada is not None:
        fim_parada = periodo.iloc[-1]['time']
        duracao = (fim_parada - inicio_parada).total_seconds()
        if duracao >= min_duracao_sec:
            paradas.append({
                'inicio': inicio_parada,
                'fim': fim_parada,
                'duracao_sec': duracao,
                'lat': lat_parada,
                'lon': lon_parada
            })

    if not paradas:
        return None

    # Retornar a maior parada
    return max(paradas, key=lambda p: p['duracao_sec'])


def detectar_paradas_por_anomalia(
    ciclos: list[Ciclo],
    estatisticas: EstatisticasCiclos,
    telemetria: pd.DataFrame,
    min_excedente_sec: float = 60.0,
    num_mads: float = 3.0,
) -> list[ParadaOciosa]:
    """
    Detecta paradas ociosas baseado em anomalias estatísticas usando estatísticas robustas.

    Lógica:
    - Usa mediana + k*MAD ao invés de média + k*std
    - MAD (Median Absolute Deviation) é resistente a outliers
    - Se tempo > mediana + num_mads * 1.4826 * MAD, há uma anomalia
    - 1.4826 converte MAD para escala equivalente ao desvio padrão

    Args:
        ciclos: Lista de ciclos
        estatisticas: Estatísticas robustas (mediana + MAD)
        telemetria: DataFrame com telemetria para localização das paradas
        min_excedente_sec: Tempo mínimo excedente para criar parada ociosa
        num_mads: Número de MADs para considerar outlier (3.0 ≈ 2σ)

    Returns:
        Lista de ParadaOciosa detectadas por anomalia
    """
    paradas_anomalia = []

    # Fator de conversão MAD → desvio padrão equivalente
    MAD_SCALE = 1.4826

    # Calcular thresholds robustos
    threshold_carga = estatisticas.carga_mediana + num_mads * MAD_SCALE * estatisticas.carga_mad
    threshold_basc = estatisticas.basc_mediana + num_mads * MAD_SCALE * estatisticas.basc_mad
    threshold_desloc_carreg = (
        estatisticas.desloc_carregado_min_km_mediana +
        num_mads * MAD_SCALE * estatisticas.desloc_carregado_min_km_mad
    )
    threshold_desloc_vazio = (
        estatisticas.desloc_vazio_min_km_mediana +
        num_mads * MAD_SCALE * estatisticas.desloc_vazio_min_km_mad
    )

    print(f"\n  Thresholds de anomalia (mediana + {num_mads}×MAD):")
    print(f"    Carregamento: {threshold_carga:.0f}s ({threshold_carga/60:.1f} min)")
    print(f"    Basculamento: {threshold_basc:.0f}s ({threshold_basc/60:.1f} min)")
    print(f"    Desloc. carregado: {threshold_desloc_carreg:.2f} min/km")
    print(f"    Desloc. vazio: {threshold_desloc_vazio:.2f} min/km")

    for ciclo in ciclos:
        # 1. Verificar anomalia no carregamento
        if estatisticas.carga_mad > 0 and ciclo.carga_duracao_sec > threshold_carga:
            excedente = ciclo.carga_duracao_sec - estatisticas.carga_mediana
            if excedente >= min_excedente_sec:
                # Encontrar parada real dentro do período de carregamento
                parada_real = encontrar_parada_real_no_periodo(
                    telemetria, ciclo.carga_inicio, ciclo.carga_fim, min_duracao_sec=30
                )
                if parada_real:
                    paradas_anomalia.append(ParadaOciosa(
                        inicio=parada_real['inicio'],
                        fim=parada_real['fim'],
                        duracao_sec=excedente,
                        latitude=parada_real['lat'],
                        longitude=parada_real['lon'],
                        ciclo_num=ciclo.numero,
                        fase="durante_carga"
                    ))
                    print(f"    Ciclo {ciclo.numero}: Carga anômala ({ciclo.carga_duracao_sec:.0f}s > {threshold_carga:.0f}s) → parada ociosa de {excedente:.0f}s")

        # 2. Verificar anomalia no deslocamento carregado
        if (estatisticas.desloc_carregado_min_km_mad > 0 and
            ciclo.desloc_carregado_km > 0.1 and
            ciclo.desloc_carregado_min_km > threshold_desloc_carreg):

            # Calcular tempo esperado e excedente
            tempo_esperado = estatisticas.desloc_carregado_min_km_mediana * ciclo.desloc_carregado_km * 60
            excedente = ciclo.desloc_carregado_sec - tempo_esperado
            if excedente >= min_excedente_sec:
                if ciclo.basculamento_inicio:
                    # Encontrar parada real no trajeto carregado
                    parada_real = encontrar_parada_real_no_periodo(
                        telemetria, ciclo.carga_fim, ciclo.basculamento_inicio, min_duracao_sec=30
                    )
                    if parada_real:
                        paradas_anomalia.append(ParadaOciosa(
                            inicio=parada_real['inicio'],
                            fim=parada_real['fim'],
                            duracao_sec=excedente,
                            latitude=parada_real['lat'],
                            longitude=parada_real['lon'],
                            ciclo_num=ciclo.numero,
                            fase="entre_carga_basc"
                        ))
                        print(f"    Ciclo {ciclo.numero}: Desloc. carregado anômalo ({ciclo.desloc_carregado_min_km:.2f} > {threshold_desloc_carreg:.2f} min/km) → parada ociosa de {excedente:.0f}s")

        # 3. Verificar anomalia no basculamento
        if (estatisticas.basc_mad > 0 and
            ciclo.basculamento_duracao_sec > 0 and
            ciclo.basculamento_duracao_sec > threshold_basc):

            excedente = ciclo.basculamento_duracao_sec - estatisticas.basc_mediana
            if excedente >= min_excedente_sec:
                if ciclo.basculamento_inicio and ciclo.basculamento_fim:
                    # Encontrar parada real durante basculamento
                    parada_real = encontrar_parada_real_no_periodo(
                        telemetria, ciclo.basculamento_inicio, ciclo.basculamento_fim, min_duracao_sec=30
                    )
                    if parada_real:
                        paradas_anomalia.append(ParadaOciosa(
                            inicio=parada_real['inicio'],
                            fim=parada_real['fim'],
                            duracao_sec=excedente,
                            latitude=parada_real['lat'],
                            longitude=parada_real['lon'],
                            ciclo_num=ciclo.numero,
                            fase="durante_basc"
                        ))
                        print(f"    Ciclo {ciclo.numero}: Basculamento anômalo ({ciclo.basculamento_duracao_sec:.0f}s > {threshold_basc:.0f}s) → parada ociosa de {excedente:.0f}s")

        # 4. Verificar anomalia no deslocamento vazio
        if (estatisticas.desloc_vazio_min_km_mad > 0 and
            ciclo.desloc_vazio_km > 0.1 and
            ciclo.desloc_vazio_min_km > threshold_desloc_vazio):

            tempo_esperado = estatisticas.desloc_vazio_min_km_mediana * ciclo.desloc_vazio_km * 60
            excedente = ciclo.desloc_vazio_sec - tempo_esperado
            if excedente >= min_excedente_sec:
                # Determinar fim do período de deslocamento vazio
                # É o início do próximo carregamento ou fim dos dados
                ciclo_idx = ciclo.numero - 1
                if ciclo_idx < len(ciclos) - 1:
                    fim_periodo = ciclos[ciclo_idx + 1].carga_inicio
                else:
                    fim_periodo = telemetria['time'].max()

                if ciclo.basculamento_fim:
                    # Encontrar parada real no trajeto vazio
                    parada_real = encontrar_parada_real_no_periodo(
                        telemetria, ciclo.basculamento_fim, fim_periodo, min_duracao_sec=30
                    )
                    if parada_real:
                        paradas_anomalia.append(ParadaOciosa(
                            inicio=parada_real['inicio'],
                            fim=parada_real['fim'],
                            duracao_sec=excedente,
                            latitude=parada_real['lat'],
                            longitude=parada_real['lon'],
                            ciclo_num=ciclo.numero,
                            fase="apos_basc"
                        ))
                        print(f"    Ciclo {ciclo.numero}: Desloc. vazio anômalo ({ciclo.desloc_vazio_min_km:.2f} > {threshold_desloc_vazio:.2f} min/km) → parada ociosa de {excedente:.0f}s")

    return paradas_anomalia


def gerar_ciclos(
    carregamentos: pd.DataFrame,
    telemetria: pd.DataFrame,
    poligonos: list,
) -> tuple[list[Ciclo], list[ParadaOciosa]]:
    """
    Gera a lista de ciclos operacionais e paradas ociosas.

    Returns:
        Tupla (ciclos, todas_paradas_ociosas)
    """
    ciclos = []
    todas_paradas_ociosas = []

    # Primeiro passo: filtrar carregamentos que resultariam em ciclos inválidos
    # (basculamento na mesma área do carregamento)
    carregamentos_validos = _filtrar_carregamentos_validos(
        carregamentos, telemetria, poligonos
    )

    for i in range(len(carregamentos_validos)):
        carga = carregamentos_validos.iloc[i]
        carga_inicio = carga['start']
        carga_fim = carga['end']
        carga_duracao = float(carga['duration_sec'])

        # Identificar área de carregamento
        carga_area, _ = identificar_area(
            float(carga['latitude']),
            float(carga['longitude']),
            poligonos
        )

        # Determinar fim do ciclo (início do próximo carregamento ou fim dos dados)
        if i < len(carregamentos_validos) - 1:
            prox_carga_inicio = carregamentos_validos.iloc[i + 1]['start']
        else:
            prox_carga_inicio = telemetria['time'].max()

        # Encontrar paradas entre este carregamento e o próximo
        paradas = encontrar_paradas(telemetria, carga_fim, prox_carga_inicio)

        # Encontrar basculamento
        basculamento = encontrar_basculamento(paradas, poligonos)

        # Coletar paradas ociosas (>= 30s, baixa vibração)
        paradas_ociosas_ciclo = []
        for p in paradas:
            if p.get('is_ociosa', False) and p['duration_sec'] >= 30:
                # Determinar fase da parada
                if basculamento:
                    if p['start'] < basculamento['start']:
                        fase = "entre_carga_basc"
                    else:
                        fase = "apos_basc"
                else:
                    fase = "entre_carga_basc"

                parada_ociosa = ParadaOciosa(
                    inicio=p['start'],
                    fim=p['end'],
                    duracao_sec=p['duration_sec'],
                    latitude=p['lat'],
                    longitude=p['lon'],
                    ciclo_num=i + 1,
                    fase=fase
                )
                paradas_ociosas_ciclo.append(parada_ociosa)
                todas_paradas_ociosas.append(parada_ociosa)

        if basculamento:
            basc_inicio = basculamento['start']
            basc_fim = basculamento['end']
            # Usar duração original - anomalias são detectadas separadamente
            basc_duracao = basculamento['duration_sec']
            basc_area = basculamento['area_nome']

            # Calcular deslocamentos (tempo)
            desloc_carregado = (basc_inicio - carga_fim).total_seconds()
            desloc_vazio = (prox_carga_inicio - basc_fim).total_seconds()

            # Calcular distâncias percorridas (km)
            desloc_carregado_km = calcular_distancia_percorrida(
                telemetria, carga_fim, basc_inicio
            )
            desloc_vazio_km = calcular_distancia_percorrida(
                telemetria, basc_fim, prox_carga_inicio
            )
        else:
            basc_inicio = None
            basc_fim = None
            basc_duracao = 0
            basc_area = "Nenhum"
            desloc_carregado = (prox_carga_inicio - carga_fim).total_seconds()
            desloc_vazio = 0
            desloc_carregado_km = calcular_distancia_percorrida(
                telemetria, carga_fim, prox_carga_inicio
            )
            desloc_vazio_km = 0.0

        # =====================================================================
        # EXTRAÇÃO DE PARADAS EMBUTIDAS (fases que excedem thresholds)
        # =====================================================================
        paradas_embutidas_ciclo = []

        # 1. Carregamento > 8 min → extrair paradas embutidas
        if carga_duracao > CARGA_MAX_NORMAL_SEC:
            _, paradas_emb = extrair_paradas_embutidas(
                telemetria, carga_inicio, carga_fim,
                'carregamento', i + 1
            )
            if paradas_emb:
                paradas_embutidas_ciclo.extend(paradas_emb)
                tempo_embutido = sum(p.duracao_sec for p in paradas_emb)
                print(f"    Ciclo {i+1}: Carga {carga_duracao:.0f}s > {CARGA_MAX_NORMAL_SEC}s → {len(paradas_emb)} paradas embutidas ({tempo_embutido:.0f}s)")

        # 2. Basculamento > 2 min → extrair paradas embutidas
        if basc_duracao > BASC_MAX_NORMAL_SEC and basc_inicio and basc_fim:
            _, paradas_emb = extrair_paradas_embutidas(
                telemetria, basc_inicio, basc_fim,
                'basculamento', i + 1
            )
            if paradas_emb:
                paradas_embutidas_ciclo.extend(paradas_emb)
                tempo_embutido = sum(p.duracao_sec for p in paradas_emb)
                print(f"    Ciclo {i+1}: Basc {basc_duracao:.0f}s > {BASC_MAX_NORMAL_SEC}s → {len(paradas_emb)} paradas embutidas ({tempo_embutido:.0f}s)")

        # 3. Deslocamento carregado > 7 min/km → extrair paradas embutidas
        if desloc_carregado_km > 0.1:
            desloc_carregado_min_km = (desloc_carregado / 60) / desloc_carregado_km
            if desloc_carregado_min_km > DESLOC_MAX_MIN_KM and basc_inicio:
                _, paradas_emb = extrair_paradas_embutidas(
                    telemetria, carga_fim, basc_inicio,
                    'desloc_carregado', i + 1
                )
                if paradas_emb:
                    paradas_embutidas_ciclo.extend(paradas_emb)
                    tempo_embutido = sum(p.duracao_sec for p in paradas_emb)
                    print(f"    Ciclo {i+1}: Desloc.Carreg {desloc_carregado_min_km:.1f}min/km > {DESLOC_MAX_MIN_KM}min/km → {len(paradas_emb)} paradas embutidas ({tempo_embutido:.0f}s)")

        # 4. Deslocamento vazio > 7 min/km → extrair paradas embutidas
        if desloc_vazio_km > 0.1:
            desloc_vazio_min_km = (desloc_vazio / 60) / desloc_vazio_km
            if desloc_vazio_min_km > DESLOC_MAX_MIN_KM and basc_fim:
                _, paradas_emb = extrair_paradas_embutidas(
                    telemetria, basc_fim, prox_carga_inicio,
                    'desloc_vazio', i + 1
                )
                if paradas_emb:
                    paradas_embutidas_ciclo.extend(paradas_emb)
                    tempo_embutido = sum(p.duracao_sec for p in paradas_emb)
                    print(f"    Ciclo {i+1}: Desloc.Vazio {desloc_vazio_min_km:.1f}min/km > {DESLOC_MAX_MIN_KM}min/km → {len(paradas_emb)} paradas embutidas ({tempo_embutido:.0f}s)")

        # Adicionar paradas embutidas à lista de todas paradas ociosas
        todas_paradas_ociosas.extend(paradas_embutidas_ciclo)
        paradas_ociosas_ciclo.extend(paradas_embutidas_ciclo)

        # Calcular durações limpas (original - paradas DURANTE a fase)
        # Usar merge_paradas_intervals para evitar contagem dupla de sobreposições
        # entre durante_X e durante_X_embutida
        paradas_carga_merged = merge_paradas_intervals(
            paradas_ociosas_ciclo, 'durante_carga'
        )
        paradas_basc_merged = merge_paradas_intervals(
            paradas_ociosas_ciclo, 'durante_basc'
        )
        carga_duracao_limpa = max(0, carga_duracao - paradas_carga_merged)
        basc_duracao_limpa = max(0, basc_duracao - paradas_basc_merged)

        # Calcular total do ciclo
        ciclo_total = carga_duracao + desloc_carregado + basc_duracao + desloc_vazio

        ciclos.append(Ciclo(
            numero=i + 1,
            carga_area=carga_area,
            carga_inicio=carga_inicio,
            carga_fim=carga_fim,
            carga_duracao_sec=carga_duracao,
            desloc_carregado_sec=desloc_carregado,
            desloc_carregado_km=desloc_carregado_km,
            basculamento_area=basc_area,
            basculamento_inicio=basc_inicio,
            basculamento_fim=basc_fim,
            basculamento_duracao_sec=basc_duracao,
            desloc_vazio_sec=desloc_vazio,
            desloc_vazio_km=desloc_vazio_km,
            ciclo_total_sec=ciclo_total,
            paradas_ociosas=paradas_ociosas_ciclo,
            carga_duracao_limpa_sec=carga_duracao_limpa,
            basculamento_duracao_limpa_sec=basc_duracao_limpa,
        ))

    return ciclos, todas_paradas_ociosas


def formatar_tempo(dt: Optional[datetime]) -> str:
    """Formata datetime para string ISO."""
    if dt is None:
        return ""
    return dt.isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera extrato de ciclos operacionais"
    )
    parser.add_argument(
        "--carregamentos",
        default=None,
        help="CSV com eventos de carregamento (opcional - se não fornecido, detecta automaticamente)"
    )
    parser.add_argument(
        "--telemetria",
        default="input.csv",
        help="CSV com dados de telemetria"
    )
    parser.add_argument(
        "--poligonos",
        default="areas_carregamento.json",
        help="JSON com polígonos das áreas"
    )
    parser.add_argument(
        "--output",
        default="extrato_ciclos.csv",
        help="CSV de saída"
    )
    parser.add_argument(
        "--min-carga-sec",
        type=float,
        default=60.0,
        help="Duração mínima em segundos para considerar carregamento (default: 60)"
    )
    args = parser.parse_args()

    # Carregar dados
    print("Carregando dados...")

    telemetria = pd.read_csv(args.telemetria)
    telemetria['time'] = pd.to_datetime(telemetria['time'])
    telemetria = telemetria.sort_values('time')
    print(f"  {len(telemetria)} registros de telemetria")

    with open(args.poligonos, 'r', encoding='utf-8') as f:
        geojson = json.load(f)
    poligonos = geojson.get('features', [])
    print(f"  {len(poligonos)} áreas definidas")

    # Carregar ou detectar carregamentos
    if args.carregamentos and Path(args.carregamentos).exists():
        print(f"\nUsando eventos de carregamento de: {args.carregamentos}")
        carregamentos = pd.read_csv(args.carregamentos)
        carregamentos['start'] = pd.to_datetime(carregamentos['start'])
        carregamentos['end'] = pd.to_datetime(carregamentos['end'])
        print(f"  {len(carregamentos)} carregamentos do arquivo")
    else:
        print("\nDetectando carregamentos automaticamente a partir da telemetria...")
        carregamentos = detectar_carregamentos_automatico(
            telemetria, poligonos, min_duracao_sec=args.min_carga_sec
        )
        if len(carregamentos) == 0:
            print("ERRO: Nenhum carregamento detectado!")
            print("Verifique se os polígonos estão definidos corretamente.")
            return 1

    # Gerar ciclos
    print("\nGerando ciclos...")
    ciclos, paradas_ociosas_ciclo = gerar_ciclos(carregamentos, telemetria, poligonos)
    print(f"  {len(ciclos)} ciclos gerados")
    print(f"  {len(paradas_ociosas_ciclo)} paradas ociosas detectadas dentro de ciclos")

    # =========================================================================
    # REV2: Detecção GLOBAL de paradas (mais sensível)
    # =========================================================================
    print("\n" + "=" * 70)
    print("REV2: DETECÇÃO GLOBAL DE PARADAS (threshold 60s)")
    print("=" * 70)

    # Detectar TODAS as paradas >= 60s em todo o dataset
    paradas_globais = detectar_todas_paradas_globais(
        telemetria, min_duracao_sec=60.0, speed_threshold=2.0
    )
    print(f"  {len(paradas_globais)} paradas >= 60s detectadas globalmente")

    # Detecção híbrida: 60s + MAD
    print("\n  Aplicando detecção híbrida (60s threshold + MAD)...")
    paradas_hibridas = detectar_paradas_hibrido(
        paradas_globais, threshold_fixo_sec=60.0, num_mads=3.0
    )
    print(f"  {len(paradas_hibridas)} paradas ociosas (híbrido 60s + MAD)")

    # Detectar paradas PRÉ-CICLO (antes do primeiro carregamento)
    primeiro_carga = carregamentos.iloc[0]['start'] if len(carregamentos) > 0 else None
    paradas_pre_ciclo = []

    if primeiro_carga:
        for p in paradas_hibridas:
            if p['fim'] < primeiro_carga:
                paradas_pre_ciclo.append(ParadaOciosa(
                    inicio=p['inicio'],
                    fim=p['fim'],
                    duracao_sec=p['duracao_sec'],
                    latitude=p['latitude'],
                    longitude=p['longitude'],
                    ciclo_num=0,  # 0 = antes do primeiro ciclo
                    fase="pre_ciclo"
                ))

    if paradas_pre_ciclo:
        print(f"\n  🆕 {len(paradas_pre_ciclo)} paradas PRÉ-CICLO detectadas!")
        for p in paradas_pre_ciclo:
            print(f"     - {p.inicio.strftime('%H:%M:%S')} a {p.fim.strftime('%H:%M:%S')}: {p.duracao_sec:.0f}s ({p.duracao_sec/60:.1f} min)")

    # Análise estatística para detecção de anomalias (método antigo também)
    print("\n" + "=" * 70)
    print("DETECÇÃO POR ANOMALIA ESTATÍSTICA (mediana + MAD)")
    print("=" * 70)
    estatisticas = calcular_estatisticas_ciclos(ciclos)
    print(f"  Estatísticas robustas calculadas:")
    print(f"    Carregamento: mediana={estatisticas.carga_mediana:.0f}s, MAD={estatisticas.carga_mad:.0f}s")
    print(f"    Basculamento: mediana={estatisticas.basc_mediana:.0f}s, MAD={estatisticas.basc_mad:.0f}s")
    print(f"    Desloc. carregado: mediana={estatisticas.desloc_carregado_min_km_mediana:.2f} min/km, MAD={estatisticas.desloc_carregado_min_km_mad:.2f}")
    print(f"    Desloc. vazio: mediana={estatisticas.desloc_vazio_min_km_mediana:.2f} min/km, MAD={estatisticas.desloc_vazio_min_km_mad:.2f}")

    paradas_anomalia = detectar_paradas_por_anomalia(
        ciclos, estatisticas, telemetria, min_excedente_sec=60.0, num_mads=3.0
    )
    print(f"\n  {len(paradas_anomalia)} paradas ociosas detectadas por anomalia estatística")

    # =========================================================================
    # PÓS-PROCESSAMENTO: Adicionar paradas de anomalia aos ciclos e recalcular
    # durações limpas
    # =========================================================================
    if paradas_anomalia:
        print("\n  Recalculando durações limpas com paradas de anomalia...")
        for parada in paradas_anomalia:
            # Encontrar o ciclo correspondente
            for ciclo in ciclos:
                if ciclo.numero == parada.ciclo_num:
                    # Adicionar parada à lista do ciclo
                    ciclo.paradas_ociosas.append(parada)
                    break

        # Recalcular durações limpas para todos os ciclos afetados
        ciclos_afetados = set(p.ciclo_num for p in paradas_anomalia)
        for ciclo in ciclos:
            if ciclo.numero in ciclos_afetados:
                # Recalcular usando merge para evitar duplicações
                paradas_carga_merged = merge_paradas_intervals(
                    ciclo.paradas_ociosas, 'durante_carga'
                )
                paradas_basc_merged = merge_paradas_intervals(
                    ciclo.paradas_ociosas, 'durante_basc'
                )
                carga_limpa_antiga = ciclo.carga_duracao_limpa_sec
                basc_limpa_antiga = ciclo.basculamento_duracao_limpa_sec

                ciclo.carga_duracao_limpa_sec = max(0, ciclo.carga_duracao_sec - paradas_carga_merged)
                ciclo.basculamento_duracao_limpa_sec = max(0, ciclo.basculamento_duracao_sec - paradas_basc_merged)

                if ciclo.carga_duracao_limpa_sec != carga_limpa_antiga:
                    print(f"    Ciclo {ciclo.numero}: Carga limpa {carga_limpa_antiga:.0f}s → {ciclo.carga_duracao_limpa_sec:.0f}s (merged: {paradas_carga_merged:.0f}s)")
                if ciclo.basculamento_duracao_limpa_sec != basc_limpa_antiga:
                    print(f"    Ciclo {ciclo.numero}: Basc limpa {basc_limpa_antiga:.0f}s → {ciclo.basculamento_duracao_limpa_sec:.0f}s (merged: {paradas_basc_merged:.0f}s)")

    # Combinar TODAS as paradas: ciclo + pré-ciclo + anomalia
    todas_paradas = paradas_ociosas_ciclo + paradas_pre_ciclo + paradas_anomalia

    # Remover duplicatas (por timestamp de início)
    vistas = set()
    paradas_unicas = []
    for p in todas_paradas:
        key = str(p.inicio)
        if key not in vistas:
            vistas.add(key)
            paradas_unicas.append(p)

    todas_paradas = paradas_unicas
    print(f"\n  Total de paradas ociosas (sem duplicatas): {len(todas_paradas)}")

    # Salvar JSON com paradas ociosas
    paradas_json = {
        "paradas_ociosas": [
            {
                "inicio": formatar_tempo(p.inicio),
                "fim": formatar_tempo(p.fim),
                "duracao_sec": int(p.duracao_sec),
                "latitude": p.latitude,
                "longitude": p.longitude,
                "ciclo_num": p.ciclo_num,
                "fase": p.fase
            }
            for p in todas_paradas
        ]
    }

    paradas_output = args.output.replace('.csv', '_paradas_ociosas.json')
    with open(paradas_output, 'w', encoding='utf-8') as f:
        json.dump(paradas_json, f, indent=2, ensure_ascii=False)
    print(f"  Paradas ociosas salvas em {paradas_output}")

    # Salvar CSV
    print(f"\nSalvando em {args.output}...")

    rows = []
    for c in ciclos:
        rows.append({
            'ciclo': c.numero,
            'carga_area': c.carga_area,
            'carga_inicio': formatar_tempo(c.carga_inicio),
            'carga_fim': formatar_tempo(c.carga_fim),
            'carga_duracao_sec': int(c.carga_duracao_sec),
            'desloc_carregado_sec': int(c.desloc_carregado_sec),
            'desloc_carregado_km': round(c.desloc_carregado_km, 2),
            'basculamento_area': c.basculamento_area,
            'basculamento_inicio': formatar_tempo(c.basculamento_inicio),
            'basculamento_fim': formatar_tempo(c.basculamento_fim),
            'basculamento_duracao_sec': int(c.basculamento_duracao_sec),
            'desloc_vazio_sec': int(c.desloc_vazio_sec),
            'desloc_vazio_km': round(c.desloc_vazio_km, 2),
            'ciclo_total_sec': int(c.ciclo_total_sec),
            'carga_duracao_limpa_sec': int(c.carga_duracao_limpa_sec),
            'basculamento_duracao_limpa_sec': int(c.basculamento_duracao_limpa_sec),
        })

    with open(args.output, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    # Estatísticas
    print("\n" + "=" * 70)
    print("ESTATÍSTICAS DOS CICLOS")
    print("=" * 70)

    # Por área de carregamento
    areas_carga = {}
    for c in ciclos:
        areas_carga[c.carga_area] = areas_carga.get(c.carga_area, 0) + 1
    print("\nCarregamentos por área:")
    for area, count in sorted(areas_carga.items(), key=lambda x: -x[1]):
        print(f"  {area}: {count}")

    # Por área de basculamento
    areas_basc = {}
    for c in ciclos:
        areas_basc[c.basculamento_area] = areas_basc.get(c.basculamento_area, 0) + 1
    print("\nBasculamentos por área:")
    for area, count in sorted(areas_basc.items(), key=lambda x: -x[1]):
        print(f"  {area}: {count}")

    # Tempos médios
    if ciclos:
        avg_carga = sum(c.carga_duracao_sec for c in ciclos) / len(ciclos)
        avg_desloc_carreg = sum(c.desloc_carregado_sec for c in ciclos) / len(ciclos)
        avg_basc = sum(c.basculamento_duracao_sec for c in ciclos) / len(ciclos)
        avg_desloc_vazio = sum(c.desloc_vazio_sec for c in ciclos) / len(ciclos)
        avg_total = sum(c.ciclo_total_sec for c in ciclos) / len(ciclos)

        print("\nTempos médios:")
        print(f"  Carregamento: {avg_carga:.0f}s ({avg_carga/60:.1f} min)")
        print(f"  Desloc. carregado: {avg_desloc_carreg:.0f}s ({avg_desloc_carreg/60:.1f} min)")
        print(f"  Basculamento: {avg_basc:.0f}s ({avg_basc/60:.1f} min)")
        print(f"  Desloc. vazio: {avg_desloc_vazio:.0f}s ({avg_desloc_vazio/60:.1f} min)")
        print(f"  Ciclo total: {avg_total:.0f}s ({avg_total/60:.1f} min)")

    # Estatísticas de paradas ociosas
    if todas_paradas:
        print("\n" + "=" * 70)
        print("PARADAS OCIOSAS (fila, almoço, café, anomalias, etc.)")
        print("=" * 70)
        print(f"\nTotal: {len(todas_paradas)} paradas")
        print(f"  - Dentro de ciclos: {len(paradas_ociosas_ciclo)}")
        print(f"  - Pré-ciclo: {len(paradas_pre_ciclo)}")
        print(f"  - Por anomalia estatística: {len(paradas_anomalia)}")

        tempo_total_ociosas = sum(p.duracao_sec for p in todas_paradas)
        print(f"Tempo total: {tempo_total_ociosas:.0f}s ({tempo_total_ociosas/60:.1f} min)")

        if len(todas_paradas) > 0:
            duracao_media = tempo_total_ociosas / len(todas_paradas)
            print(f"Duração média: {duracao_media:.0f}s ({duracao_media/60:.1f} min)")

        # Por fase
        fases = {}
        for p in todas_paradas:
            fases[p.fase] = fases.get(p.fase, 0) + 1
        print("\nPor fase:")
        for fase, count in sorted(fases.items(), key=lambda x: -x[1]):
            print(f"  {fase}: {count}")

    # Gerar JSON de distribuição (com valores limpos para histogramas)
    if ciclos:
        import statistics as stat

        def calc_stats(valores, unidade, cor):
            """Calcula estatísticas para uma série de valores."""
            return {
                "valores": valores,
                "media": stat.mean(valores) if valores else 0,
                "mediana": stat.median(valores) if valores else 0,
                "std": stat.stdev(valores) if len(valores) > 1 else 0,
                "min": min(valores) if valores else 0,
                "max": max(valores) if valores else 0,
                "n": len(valores),
                "unidade": unidade,
                "cor": cor
            }

        # Usar valores LIMPOS para carregamento e basculamento
        carga_vals = [c.carga_duracao_limpa_sec / 60 for c in ciclos]  # em minutos
        basc_vals = [c.basculamento_duracao_limpa_sec / 60 for c in ciclos]  # em minutos

        # Deslocamentos: min/km (usar valores brutos pois são normalizados)
        desloc_carreg_vals = [
            c.desloc_carregado_min_km for c in ciclos
            if c.desloc_carregado_km > 0.1
        ]
        desloc_vazio_vals = [
            c.desloc_vazio_min_km for c in ciclos
            if c.desloc_vazio_km > 0.1
        ]

        distribuicao = {
            "Carregamento": calc_stats(carga_vals, "min", "#4CAF50"),
            "Desloc. Carregado": calc_stats(desloc_carreg_vals, "min/km", "#2196F3"),
            "Basculamento": calc_stats(basc_vals, "min", "#FF9800"),
            "Desloc. Vazio": calc_stats(desloc_vazio_vals, "min/km", "#E91E63"),
        }

        dist_output = args.output.replace('.csv', '').replace('extrato_ciclos', 'distribuicao_data') + '.json'
        with open(dist_output, 'w', encoding='utf-8') as f:
            json.dump(distribuicao, f, indent=2, ensure_ascii=False)
        print(f"\n  Distribuição salva em {dist_output}")

    print("\nConcluído!")
    return 0


if __name__ == "__main__":
    exit(main())
