#!/usr/bin/env python3
"""
Detector de eventos de CARREGAMENTO em caminhões de mineração.

Regra de detecção (baseada em velocidade + vibração):
- velocidade < 0.5 km/h (caminhão parado)
- 90s <= duração <= 320s
- 0.012 <= variabilidade_vibração <= 0.04

Onde variabilidade_vibração = média do desvio padrão móvel da aceleração (janela 10s)

Pós-processamento:
- Mesclagem de eventos com gap < 120s
- Filtro espacial por polígonos (opcional)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass
class StopSegment:
    """Representa um segmento de parada (velocidade < threshold)."""
    start_idx: int
    end_idx: int
    start_time: datetime
    end_time: datetime

    @property
    def duration_sec(self) -> float:
        return (self.end_time - self.start_time).total_seconds()


@dataclass
class DetectedEvent:
    """Representa um evento detectado."""
    event_type: str
    start: datetime
    end: datetime
    duration_sec: float
    latitude: float
    longitude: float
    variabilidade_vibracao: float
    accel_mean: float
    spike_fraction: float


def parse_time(value: str) -> datetime:
    """Parse timestamp string to datetime."""
    return datetime.fromisoformat(value.replace(" ", "T"))


def segment_stops(
    df: pd.DataFrame,
    speed_threshold: float = 0.5,
    min_duration_sec: float = 60.0,
) -> list[StopSegment]:
    """
    Segmenta os dados em períodos de parada.

    Args:
        df: DataFrame com coluna 'speed_kmh'
        speed_threshold: velocidade máxima para considerar parado (km/h)
        min_duration_sec: duração mínima para uma parada (segundos)

    Returns:
        Lista de segmentos de parada
    """
    df = df.copy()
    df['is_stopped'] = df['speed_kmh'] < speed_threshold

    segments = []
    current: Optional[dict] = None

    for i, row in df.iterrows():
        if row['is_stopped']:
            if current is None:
                current = {
                    'start_idx': i,
                    'start_time': row['time']
                }
            current['end_idx'] = i
            current['end_time'] = row['time']
        else:
            if current is not None:
                duration = (current['end_time'] - current['start_time']).total_seconds()
                if duration >= min_duration_sec:
                    segments.append(StopSegment(
                        start_idx=current['start_idx'],
                        end_idx=current['end_idx'],
                        start_time=current['start_time'],
                        end_time=current['end_time'],
                    ))
                current = None

    # Verificar último segmento
    if current is not None:
        duration = (current['end_time'] - current['start_time']).total_seconds()
        if duration >= min_duration_sec:
            segments.append(StopSegment(
                start_idx=current['start_idx'],
                end_idx=current['end_idx'],
                start_time=current['start_time'],
                end_time=current['end_time'],
            ))

    return segments


def calcular_variabilidade_vibracao(accel_series: pd.Series, janela: int = 10) -> float:
    """
    Calcula a variabilidade da vibração usando desvio padrão móvel.

    Args:
        accel_series: Series com linear_accel_magnitude
        janela: tamanho da janela em segundos (default: 10)

    Returns:
        float: média do desvio padrão móvel
    """
    rolling_std = accel_series.rolling(window=janela, min_periods=5).std()
    return rolling_std.mean()


def detect_carregamentos(
    df: pd.DataFrame,
    segments: list[StopSegment],
    min_duration: float = 90.0,
    max_duration: float = 320.0,
    min_variab: float = 0.012,
    max_variab: float = 0.04,
    spike_threshold: float = 0.05,
    min_duration_strict: float = 130.0,
    min_spike_fraction: float = 0.10,
) -> list[DetectedEvent]:
    """
    Detecta eventos de carregamento nos segmentos de parada.

    Regra refinada: (duração >= 130s) OU (spike_fraction >= 10%)
    Dentro do range de variabilidade 0.012-0.04

    Args:
        df: DataFrame com dados de telemetria
        segments: Lista de segmentos de parada
        min_duration: duração mínima absoluta (segundos)
        max_duration: duração máxima para carregamento (segundos)
        min_variab: variabilidade mínima de vibração
        max_variab: variabilidade máxima de vibração
        spike_threshold: threshold para contar spikes de aceleração
        min_duration_strict: duração mínima para regra OR (segundos)
        min_spike_fraction: spike fraction mínimo para regra OR

    Returns:
        Lista de eventos de carregamento detectados
    """
    events = []

    for seg in segments:
        duration = seg.duration_sec

        # Critério 1: Duração dentro do range básico
        if not (min_duration <= duration <= max_duration):
            continue

        # Extrair dados do segmento
        segment_data = df.iloc[seg.start_idx:seg.end_idx + 1]
        accel = segment_data['linear_accel_magnitude']

        # Critério 2: Variabilidade da vibração
        variab = calcular_variabilidade_vibracao(accel)
        if not (min_variab <= variab <= max_variab):
            continue

        # Calcular métricas adicionais
        accel_mean = accel.mean()
        spike_fraction = (accel >= spike_threshold).mean()

        # Critério 3 (refinado): (duração >= 130s) OU (spike >= 10%)
        if not (duration >= min_duration_strict or spike_fraction >= min_spike_fraction):
            continue

        lat_mean = segment_data['latitude'].mean()
        lon_mean = segment_data['longitude'].mean()

        events.append(DetectedEvent(
            event_type='carregamento',
            start=seg.start_time,
            end=seg.end_time,
            duration_sec=duration,
            latitude=lat_mean,
            longitude=lon_mean,
            variabilidade_vibracao=variab,
            accel_mean=accel_mean,
            spike_fraction=spike_fraction,
        ))

    return events


def mesclar_eventos_proximos(
    events: list[DetectedEvent],
    gap_threshold_sec: float = 120.0,
) -> list[DetectedEvent]:
    """
    Mescla eventos consecutivos que estão muito próximos no tempo.

    Isso elimina "falsos inícios" onde o caminhão parou brevemente
    antes de iniciar o carregamento real.

    Args:
        events: Lista de eventos ordenados por tempo
        gap_threshold_sec: Gap máximo para mesclar (segundos)

    Returns:
        Lista de eventos mesclados
    """
    if not events:
        return []

    # Ordenar por início
    sorted_events = sorted(events, key=lambda e: e.start)
    merged = []
    current = sorted_events[0]

    for next_event in sorted_events[1:]:
        gap = (next_event.start - current.end).total_seconds()

        if gap < gap_threshold_sec:
            # Mesclar: combinar os dois eventos
            new_duration = (next_event.end - current.start).total_seconds()
            # Usar médias ponderadas para métricas
            w1 = current.duration_sec
            w2 = next_event.duration_sec
            total_w = w1 + w2

            current = DetectedEvent(
                event_type=current.event_type,
                start=current.start,
                end=next_event.end,
                duration_sec=new_duration,
                latitude=(current.latitude * w1 + next_event.latitude * w2) / total_w,
                longitude=(current.longitude * w1 + next_event.longitude * w2) / total_w,
                variabilidade_vibracao=(current.variabilidade_vibracao * w1 + next_event.variabilidade_vibracao * w2) / total_w,
                accel_mean=(current.accel_mean * w1 + next_event.accel_mean * w2) / total_w,
                spike_fraction=(current.spike_fraction * w1 + next_event.spike_fraction * w2) / total_w,
            )
        else:
            merged.append(current)
            current = next_event

    merged.append(current)
    return merged


def ponto_em_poligono(lat: float, lon: float, polygon_coords: list) -> bool:
    """
    Verifica se um ponto está dentro de um polígono usando ray casting.

    Args:
        lat: Latitude do ponto
        lon: Longitude do ponto
        polygon_coords: Lista de coordenadas [[lon, lat], ...] do polígono

    Returns:
        True se o ponto está dentro do polígono
    """
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


def carregar_poligonos(filepath: Path) -> list[dict]:
    """
    Carrega polígonos de um arquivo GeoJSON.

    Args:
        filepath: Caminho para o arquivo areas_carregamento.json

    Returns:
        Lista de features (polígonos) do GeoJSON
    """
    if not filepath.exists():
        return []

    with filepath.open('r', encoding='utf-8') as f:
        geojson = json.load(f)

    return geojson.get('features', [])


def filtrar_por_poligonos(
    events: list[DetectedEvent],
    poligonos: list[dict],
    tipo_filtro: str = 'carregamento',
) -> list[DetectedEvent]:
    """
    Filtra eventos mantendo apenas os que estão dentro dos polígonos.

    Args:
        events: Lista de eventos
        poligonos: Lista de features GeoJSON
        tipo_filtro: Tipo de polígono a considerar ('carregamento' ou 'basculamento')

    Returns:
        Lista de eventos filtrados
    """
    if not poligonos:
        return events

    # Filtrar polígonos pelo tipo
    poligonos_filtrados = [
        p for p in poligonos
        if p.get('properties', {}).get('type') == tipo_filtro
    ]

    if not poligonos_filtrados:
        return events

    filtered = []
    for event in events:
        # Verificar se está dentro de algum polígono
        for poly in poligonos_filtrados:
            coords = poly['geometry']['coordinates'][0]
            if ponto_em_poligono(event.latitude, event.longitude, coords):
                filtered.append(event)
                break

    return filtered


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detecta eventos de carregamento em dados de telemetria de caminhões"
    )
    parser.add_argument(
        "--input",
        default="input.csv.csv",
        help="CSV de entrada (padrão: input.csv.csv)"
    )
    parser.add_argument(
        "--output",
        default="events_carregamento.csv",
        help="CSV de saída (padrão: events_carregamento.csv)"
    )
    parser.add_argument(
        "--speed-stop-kmh",
        type=float,
        default=0.5,
        help="Velocidade máxima para considerar parado (km/h)"
    )
    parser.add_argument(
        "--min-stop-sec",
        type=float,
        default=60.0,
        help="Duração mínima para uma parada (segundos)"
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=90.0,
        help="Duração mínima para carregamento (segundos)"
    )
    parser.add_argument(
        "--max-duration",
        type=float,
        default=320.0,
        help="Duração máxima para carregamento (segundos)"
    )
    parser.add_argument(
        "--min-variab",
        type=float,
        default=0.012,
        help="Variabilidade mínima de vibração"
    )
    parser.add_argument(
        "--max-variab",
        type=float,
        default=0.04,
        help="Variabilidade máxima de vibração"
    )
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=120.0,
        help="Gap máximo para mesclar eventos próximos (segundos, 0 para desabilitar)"
    )
    parser.add_argument(
        "--polygons",
        default="areas_carregamento.json",
        help="Arquivo GeoJSON com polígonos de áreas de carregamento (opcional)"
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Desabilitar mesclagem de eventos próximos"
    )
    parser.add_argument(
        "--no-polygon-filter",
        action="store_true",
        help="Desabilitar filtro por polígonos"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Erro: arquivo não encontrado: {input_path}")
        return 1

    # Carregar dados
    print(f"Carregando dados de {input_path}...")
    df = pd.read_csv(input_path)
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').reset_index(drop=True)
    print(f"  {len(df)} registros carregados")

    # Segmentar paradas
    print("Identificando paradas...")
    stops = segment_stops(
        df,
        speed_threshold=args.speed_stop_kmh,
        min_duration_sec=args.min_stop_sec,
    )
    print(f"  {len(stops)} paradas identificadas (>= {args.min_stop_sec}s)")

    # Detectar carregamentos
    print("Detectando carregamentos...")
    events = detect_carregamentos(
        df,
        stops,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        min_variab=args.min_variab,
        max_variab=args.max_variab,
    )
    print(f"  {len(events)} carregamentos detectados (antes do pós-processamento)")

    # Pós-processamento: Mesclagem de eventos próximos
    if not args.no_merge and args.merge_gap > 0:
        events_before = len(events)
        events = mesclar_eventos_proximos(events, gap_threshold_sec=args.merge_gap)
        merged_count = events_before - len(events)
        if merged_count > 0:
            print(f"  {merged_count} eventos mesclados (gap < {args.merge_gap}s)")
        print(f"  {len(events)} carregamentos após mesclagem")

    # Pós-processamento: Filtro por polígonos
    polygons_path = Path(args.polygons)
    if not args.no_polygon_filter and polygons_path.exists():
        poligonos = carregar_poligonos(polygons_path)
        if poligonos:
            events_before = len(events)
            events = filtrar_por_poligonos(events, poligonos, tipo_filtro='carregamento')
            filtered_count = events_before - len(events)
            if filtered_count > 0:
                print(f"  {filtered_count} eventos filtrados (fora dos polígonos)")
            print(f"  {len(events)} carregamentos após filtro espacial")

    # Salvar resultados
    if events:
        print(f"\nSalvando resultados em {output_path}...")

        # Converter para dicionários
        rows = []
        for i, e in enumerate(events, 1):
            rows.append({
                'id': i,
                'event': e.event_type,
                'start': e.start.isoformat(),
                'end': e.end.isoformat(),
                'duration_sec': f"{e.duration_sec:.0f}",
                'latitude': f"{e.latitude:.6f}",
                'longitude': f"{e.longitude:.6f}",
                'variabilidade_vibracao': f"{e.variabilidade_vibracao:.4f}",
                'accel_mean': f"{e.accel_mean:.4f}",
                'spike_fraction': f"{e.spike_fraction:.3f}",
            })

        with output_path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        print("Concluído!")

        # Estatísticas
        print("\n" + "=" * 60)
        print("ESTATÍSTICAS")
        print("=" * 60)
        durations = [e.duration_sec for e in events]
        variabs = [e.variabilidade_vibracao for e in events]
        spikes = [e.spike_fraction for e in events]

        print(f"Total de carregamentos: {len(events)}")
        print(f"Duração: min={min(durations):.0f}s, max={max(durations):.0f}s, média={sum(durations)/len(durations):.0f}s")
        print(f"Variabilidade: min={min(variabs):.4f}, max={max(variabs):.4f}, média={sum(variabs)/len(variabs):.4f}")
        print(f"Spike fraction: min={min(spikes):.1%}, max={max(spikes):.1%}, média={sum(spikes)/len(spikes):.1%}")

        # Período coberto
        first = min(e.start for e in events)
        last = max(e.end for e in events)
        total_hours = (last - first).total_seconds() / 3600
        print(f"\nPeríodo: {first.strftime('%Y-%m-%d %H:%M')} a {last.strftime('%Y-%m-%d %H:%M')}")
        print(f"Duração total: {total_hours:.1f} horas")
        print(f"Média de carregamentos por hora: {len(events) / total_hours:.1f}")
    else:
        print("\nNenhum carregamento detectado com os parâmetros atuais.")

    return 0


if __name__ == "__main__":
    exit(main())
