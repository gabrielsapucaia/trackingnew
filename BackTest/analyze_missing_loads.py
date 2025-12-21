#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class StopSegment:
    start: datetime
    end: datetime
    samples: int
    sum_lat: float
    sum_lon: float
    sum_acc: float
    max_acc: float
    acc_spike_count: int
    spike_first: Optional[datetime]
    spike_last: Optional[datetime]
    min_pitch: float
    max_pitch: float

    @property
    def mean_lat(self) -> float:
        return self.sum_lat / self.samples

    @property
    def mean_lon(self) -> float:
        return self.sum_lon / self.samples

    @property
    def mean_acc(self) -> float:
        return self.sum_acc / self.samples

    @property
    def acc_spike_frac(self) -> float:
        return self.acc_spike_count / self.samples if self.samples > 0 else 0.0

    @property
    def spike_span_sec(self) -> int:
        if self.spike_first is None or self.spike_last is None:
            return 0
        return int((self.spike_last - self.spike_first).total_seconds()) + 1

    @property
    def duration_sec(self) -> int:
        return int((self.end - self.start).total_seconds()) + 1


@dataclass
class DetectedLoad:
    start: datetime
    end: datetime
    lat: float
    lon: float


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S%z")


def try_float(value: str) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_m * math.asin(min(1.0, math.sqrt(a)))


def iter_stop_segments(
    rows: list[dict[str, str]],
    *,
    speed_stop_kmh: float,
    gap_sec: int,
    min_stop_samples: int,
    acc_spike_threshold: float,
) -> list[StopSegment]:
    segments: list[StopSegment] = []
    current: Optional[StopSegment] = None
    previous_time: Optional[datetime] = None

    for row in rows:
        time_value = row.get("time", "")
        try:
            timestamp = parse_time(time_value)
        except Exception:
            previous_time = None
            continue

        speed = try_float(row.get("speed_kmh", ""))
        latitude = try_float(row.get("latitude", ""))
        longitude = try_float(row.get("longitude", ""))
        accel_mag = try_float(row.get("linear_accel_magnitude", ""))
        pitch = try_float(row.get("pitch", ""))

        previous_time_gap = None
        if previous_time is not None:
            previous_time_gap = (timestamp - previous_time).total_seconds()

        previous_time = timestamp

        if speed is None or latitude is None or longitude is None or accel_mag is None or pitch is None:
            continue

        is_stopped = speed < speed_stop_kmh
        if is_stopped:
            if current is None:
                current = StopSegment(
                    start=timestamp,
                    end=timestamp,
                    samples=0,
                    sum_lat=0.0,
                    sum_lon=0.0,
                    sum_acc=0.0,
                    max_acc=float("-inf"),
                    acc_spike_count=0,
                    spike_first=None,
                    spike_last=None,
                    min_pitch=float("inf"),
                    max_pitch=float("-inf"),
                )
            elif previous_time_gap is not None and previous_time_gap > gap_sec:
                if current.samples >= min_stop_samples:
                    segments.append(current)
                current = StopSegment(
                    start=timestamp,
                    end=timestamp,
                    samples=0,
                    sum_lat=0.0,
                    sum_lon=0.0,
                    sum_acc=0.0,
                    max_acc=float("-inf"),
                    acc_spike_count=0,
                    spike_first=None,
                    spike_last=None,
                    min_pitch=float("inf"),
                    max_pitch=float("-inf"),
                )

            current.end = timestamp
            current.samples += 1
            current.sum_lat += latitude
            current.sum_lon += longitude
            current.sum_acc += accel_mag
            current.max_acc = max(current.max_acc, accel_mag)
            if accel_mag >= acc_spike_threshold:
                current.acc_spike_count += 1
                if current.spike_first is None:
                    current.spike_first = timestamp
                current.spike_last = timestamp
            current.min_pitch = min(current.min_pitch, pitch)
            current.max_pitch = max(current.max_pitch, pitch)
        else:
            if current is not None:
                if current.samples >= min_stop_samples:
                    segments.append(current)
                current = None

    if current is not None and current.samples >= min_stop_samples:
        segments.append(current)

    return segments


def cluster_key(segment: StopSegment, *, round_decimals: int) -> tuple[float, float]:
    return (round(segment.mean_lat, round_decimals), round(segment.mean_lon, round_decimals))


def pick_anchor_key(
    segments: list[StopSegment],
    *,
    round_decimals: int,
    predicate,
) -> Optional[tuple[float, float]]:
    counts: dict[tuple[float, float], int] = {}
    for seg in segments:
        if not predicate(seg):
            continue
        key = cluster_key(seg, round_decimals=round_decimals)
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def read_detected_loads(events_path: Path) -> list[DetectedLoad]:
    loads: list[DetectedLoad] = []
    with events_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("event", "").strip() != "carregamento":
                continue
            try:
                start = datetime.fromisoformat(row.get("start", "").strip())
                end = datetime.fromisoformat(row.get("end", "").strip())
                lat = try_float(row.get("latitude", ""))
                lon = try_float(row.get("longitude", ""))
                if lat is not None and lon is not None:
                    loads.append(DetectedLoad(start=start, end=end, lat=lat, lon=lon))
            except Exception:
                continue
    return loads


def overlaps(seg: StopSegment, load: DetectedLoad, tolerance_sec: int = 30) -> bool:
    seg_start = seg.start.timestamp()
    seg_end = seg.end.timestamp()
    load_start = load.start.timestamp() - tolerance_sec
    load_end = load.end.timestamp() + tolerance_sec
    return not (seg_end < load_start or seg_start > load_end)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analisa paradas na área de carregamento que não foram detectadas como carregamentos"
    )
    parser.add_argument("--input", default="input.csv", help="CSV de entrada (padrão: input.csv)")
    parser.add_argument("--events", default="events_detected.csv", help="CSV de eventos detectados (padrão: events_detected.csv)")
    parser.add_argument("--output", default="missing_loads_analysis.csv", help="CSV de saída (padrão: missing_loads_analysis.csv)")
    parser.add_argument("--speed-stop-kmh", type=float, default=0.5, help="limite de velocidade para considerar parado")
    parser.add_argument("--gap-sec", type=int, default=2, help="tolerância de gap (seg) dentro da mesma parada")
    parser.add_argument("--min-stop-sec", type=int, default=10, help="duração mínima (seg) para uma parada")
    parser.add_argument("--round-decimals", type=int, default=3, help="casas decimais para agrupar hotspots GPS")
    parser.add_argument("--load-min-sec", type=int, default=120, help="duração mínima (seg) para carregamento")
    parser.add_argument("--load-active-frac", type=float, default=0.08, help="fração mínima de spikes para carregamento")
    parser.add_argument("--load-radius-m", type=float, default=250.0, help="raio (m) para área de carregamento")
    parser.add_argument("--acc-spike-th", type=float, default=0.05, help="limite de aceleração para spike")
    args = parser.parse_args()

    input_path = Path(args.input)
    events_path = Path(args.events)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Erro: arquivo não encontrado: {input_path}")
        return 1

    if not events_path.exists():
        print(f"Erro: arquivo não encontrado: {events_path}")
        return 1

    print(f"Lendo dados de {input_path}...")
    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"  {len(rows)} linhas lidas")

    print("Identificando paradas...")
    stops = iter_stop_segments(
        rows,
        speed_stop_kmh=args.speed_stop_kmh,
        gap_sec=args.gap_sec,
        min_stop_samples=args.min_stop_sec,
        acc_spike_threshold=args.acc_spike_th,
    )
    print(f"  {len(stops)} paradas identificadas")

    print("Identificando hotspot de carregamento...")
    load_anchor = pick_anchor_key(
        stops,
        round_decimals=args.round_decimals,
        predicate=lambda seg: seg.samples >= args.load_min_sec and seg.acc_spike_frac >= args.load_active_frac,
    )
    if load_anchor is None:
        load_anchor = pick_anchor_key(
            stops,
            round_decimals=args.round_decimals,
            predicate=lambda seg: seg.samples >= args.load_min_sec,
        )
    if load_anchor is None:
        print("Erro: não foi possível identificar hotspot de carregamento")
        return 1

    print(f"  Hotspot: {load_anchor[0]:.3f}, {load_anchor[1]:.3f}")

    def in_load_area(seg: StopSegment) -> bool:
        return haversine_m(load_anchor[0], load_anchor[1], seg.mean_lat, seg.mean_lon) <= args.load_radius_m

    print("Lendo carregamentos detectados...")
    detected_loads = read_detected_loads(events_path)
    print(f"  {len(detected_loads)} carregamentos detectados")

    print("Analisando paradas na área de carregamento...")
    load_area_stops = [seg for seg in stops if in_load_area(seg)]
    print(f"  {len(load_area_stops)} paradas na área de carregamento")

    missing_loads: list[dict] = []
    for seg in load_area_stops:
        # Verifica se já foi detectado
        is_detected = any(overlaps(seg, load) for load in detected_loads)
        if is_detected:
            continue

        # Classifica razão de não detecção
        reasons = []
        if seg.samples < args.load_min_sec:
            reasons.append(f"duracao_curta({seg.samples}s<{args.load_min_sec}s)")
        if seg.acc_spike_frac < args.load_active_frac:
            reasons.append(f"atividade_baixa({seg.acc_spike_frac:.3f}<{args.load_active_frac})")
        if seg.spike_first is None or seg.spike_last is None:
            reasons.append("sem_spikes")
        if not reasons:
            reasons.append("outro")

        missing_loads.append({
            "start": seg.start.isoformat(),
            "end": seg.end.isoformat(),
            "duration_sec": seg.duration_sec,
            "samples": seg.samples,
            "latitude": f"{seg.mean_lat:.6f}",
            "longitude": f"{seg.mean_lon:.6f}",
            "acc_spike_frac": f"{seg.acc_spike_frac:.4f}",
            "acc_spike_count": seg.acc_spike_count,
            "mean_acc": f"{seg.mean_acc:.6f}",
            "max_acc": f"{seg.max_acc:.6f}",
            "has_spikes": "sim" if (seg.spike_first is not None and seg.spike_last is not None) else "nao",
            "spike_span_sec": seg.spike_span_sec,
            "reasons": " | ".join(reasons),
        })

    print(f"\nEncontradas {len(missing_loads)} paradas não detectadas na área de carregamento")

    if missing_loads:
        # Estatísticas
        durations = [m["duration_sec"] for m in missing_loads]
        activities = [float(m["acc_spike_frac"]) for m in missing_loads]
        has_spikes_count = sum(1 for m in missing_loads if m["has_spikes"] == "sim")

        print("\nEstatísticas das paradas não detectadas:")
        print(f"  Duração: min={min(durations)}s, max={max(durations)}s, média={sum(durations)/len(durations):.1f}s")
        print(f"  Atividade: min={min(activities):.4f}, max={max(activities):.4f}, média={sum(activities)/len(activities):.4f}")
        print(f"  Com spikes: {has_spikes_count}/{len(missing_loads)} ({100*has_spikes_count/len(missing_loads):.1f}%)")

        # Razões
        reason_counts: dict[str, int] = {}
        for m in missing_loads:
            for reason in m["reasons"].split(" | "):
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

        print("\nRazões de não detecção:")
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")

        # Salva CSV
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as f:
            if not missing_loads:
                return 0
            writer = csv.DictWriter(f, fieldnames=missing_loads[0].keys())
            writer.writeheader()
            writer.writerows(missing_loads)
        print(f"\nRelatório salvo em: {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())

