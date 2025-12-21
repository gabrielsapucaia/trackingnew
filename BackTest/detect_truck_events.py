#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional


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
        return self.acc_spike_count / self.samples

    @property
    def spike_span_sec(self) -> int:
        if self.spike_first is None or self.spike_last is None:
            return 0
        return int((self.spike_last - self.spike_first).total_seconds()) + 1

    @property
    def spike_density_in_span(self) -> float:
        span = self.spike_span_sec
        if span <= 0:
            return 0.0
        return self.acc_spike_count / span

    @property
    def pitch_range(self) -> float:
        return self.max_pitch - self.min_pitch


@dataclass
class Event:
    kind: str  # "carregamento" | "basculamento" | "espera_carregamento" | "espera_basculamento"
    start: datetime
    end: datetime
    duration_sec: int
    lat: float
    lon: float
    cluster_key: str
    cycle_id: Optional[int] = None
    is_complete: bool = True  # True se tem basculamento subsequente válido


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
    # Mean Earth radius in meters
    radius_m = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_m * math.asin(min(1.0, math.sqrt(a)))


def iter_stop_segments(
    rows: Iterable[dict[str, str]],
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

        # Skip incomplete rows for segmentation.
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


def key_to_str(key: tuple[float, float], *, round_decimals: int) -> str:
    return f"{key[0]:.{round_decimals}f},{key[1]:.{round_decimals}f}"


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


def expand_keys_within_radius(
    segments: list[StopSegment],
    *,
    anchor: tuple[float, float],
    round_decimals: int,
    radius_m: float,
    predicate,
) -> set[tuple[float, float]]:
    selected: set[tuple[float, float]] = set()
    for seg in segments:
        if not predicate(seg):
            continue
        key = cluster_key(seg, round_decimals=round_decimals)
        distance = haversine_m(anchor[0], anchor[1], key[0], key[1])
        if distance <= radius_m:
            selected.add(key)
    selected.add(anchor)
    return selected


def detect_all_loads(
    stops_sorted: list[StopSegment],
    *,
    in_load_area,
    is_load_operation,
    is_load_operation_without_spikes,
    cluster_key,
    key_to_str,
    args,
) -> list[Event]:
    """
    Passada 1: Detecta TODOS os carregamentos possíveis sem restrições de estado.
    Não bloqueia detecção por falta de basculamento anterior.
    """
    loads: list[Event] = []
    load_merge_gap_sec = int(round(args.load_merge_gap_min * 60))
    last_load_end: Optional[datetime] = None
    last_load_latlon: Optional[tuple[float, float]] = None
    current_load_event: Optional[Event] = None

    for seg in stops_sorted:
        if not in_load_area(seg):
            continue

        key = cluster_key(seg)
        key_str = key_to_str(key)

        load_op = is_load_operation(seg)
        load_op_no_spikes = is_load_operation_without_spikes(seg)

        # Tenta detectar carregamento com spikes primeiro
        if load_op and seg.spike_first is not None and seg.spike_last is not None:
            wait_before_sec = int((seg.spike_first - seg.start).total_seconds())
            op_start = seg.spike_first
            op_end = seg.spike_last
            op_dur = seg.spike_span_sec

            # Verifica se deve fazer merge com carregamento anterior
            should_merge = False
            if current_load_event is not None and last_load_end is not None and last_load_latlon is not None:
                time_gap = (op_start - last_load_end).total_seconds()
                dist = haversine_m(last_load_latlon[0], last_load_latlon[1], seg.mean_lat, seg.mean_lon)
                merged_duration = current_load_event.duration_sec + op_dur
                if (
                    time_gap <= load_merge_gap_sec
                    and dist <= args.load_radius_m
                    and merged_duration <= args.load_merge_max_duration_sec
                ):
                    should_merge = True

            if should_merge:
                # Merge com carregamento anterior
                total = current_load_event.duration_sec + op_dur
                current_load_event.end = max(current_load_event.end, op_end)
                current_load_event.lat = (
                    current_load_event.lat * current_load_event.duration_sec + seg.mean_lat * op_dur
                ) / total
                current_load_event.lon = (
                    current_load_event.lon * current_load_event.duration_sec + seg.mean_lon * op_dur
                ) / total
                current_load_event.duration_sec = total
                last_load_end = current_load_event.end
                last_load_latlon = (current_load_event.lat, current_load_event.lon)
                current_load_event.cluster_key = key_to_str(
                    (
                        round(current_load_event.lat, args.round_decimals),
                        round(current_load_event.lon, args.round_decimals),
                    )
                )
            else:
                # Novo carregamento
                new_load = Event(
                    kind="carregamento",
                    start=op_start,
                    end=op_end,
                    duration_sec=op_dur,
                    lat=seg.mean_lat,
                    lon=seg.mean_lon,
                    cluster_key=key_str,
                    cycle_id=None,  # Será atribuído na validação
                    is_complete=True,  # Será validado depois
                )
                loads.append(new_load)
                current_load_event = new_load
                last_load_end = new_load.end
                last_load_latlon = (new_load.lat, new_load.lon)
            continue

        # Tenta detectar carregamento sem spikes
        if load_op_no_spikes:
            # Novo carregamento (sem merge para carregamentos sem spikes)
            new_load = Event(
                kind="carregamento",
                start=seg.start,
                end=seg.end,
                duration_sec=seg.samples,
                lat=seg.mean_lat,
                lon=seg.mean_lon,
                cluster_key=key_str,
                cycle_id=None,
                is_complete=True,
            )
            loads.append(new_load)
            current_load_event = new_load
            last_load_end = new_load.end
            last_load_latlon = (new_load.lat, new_load.lon)
            continue

    return loads


def validate_loads_with_dumps(
    loads: list[Event],
    dumps: list[Event],
    *,
    max_time_between_load_and_dump_hours: float = 4.0,
) -> list[Event]:
    """
    Passada 2: Valida basculamentos entre carregamentos consecutivos.
    Marca carregamentos como incompletos se não houver basculamento subsequente válido.
    Atribui cycle_id baseado na sequência de carregamentos válidos.
    """
    if not loads:
        return loads

    max_time_sec = int(round(max_time_between_load_and_dump_hours * 3600))
    loads_sorted = sorted(loads, key=lambda e: e.start)
    dumps_sorted = sorted(dumps, key=lambda e: e.start)

    cycle_id = 0
    for i, load in enumerate(loads_sorted):
        # Procura basculamento após este carregamento e antes do próximo (ou dentro do timeout)
        load_end_time = load.end.timestamp()
        next_load_start_time = (
            loads_sorted[i + 1].start.timestamp() if i + 1 < len(loads_sorted) else float("inf")
        )
        timeout_time = load_end_time + max_time_sec

        # Encontra basculamento válido entre este carregamento e o próximo
        has_valid_dump = False
        for dump in dumps_sorted:
            dump_start_time = dump.start.timestamp()
            # Basculamento deve estar após o carregamento e antes do próximo carregamento ou timeout
            if dump_start_time >= load_end_time and dump_start_time <= min(next_load_start_time, timeout_time):
                has_valid_dump = True
                break

        if has_valid_dump:
            # Carregamento completo: tem basculamento subsequente válido
            cycle_id += 1
            load.cycle_id = cycle_id
            load.is_complete = True
        else:
            # Carregamento incompleto: sem basculamento subsequente válido
            load.is_complete = False
            # Ainda atribui cycle_id se for o primeiro ou se o anterior estava completo
            if i == 0 or loads_sorted[i - 1].is_complete:
                cycle_id += 1
                load.cycle_id = cycle_id

    return loads_sorted


def write_events_csv(path: Path, events: list[Event]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "cycle_id",
                "event",
                "start",
                "end",
                "duration_sec",
                "latitude",
                "longitude",
                "cluster_key",
                "is_complete",
            ],
        )
        writer.writeheader()
        for e in events:
            writer.writerow(
                {
                    "cycle_id": "" if e.cycle_id is None else e.cycle_id,
                    "event": e.kind,
                    "start": e.start.isoformat(),
                    "end": e.end.isoformat(),
                    "duration_sec": e.duration_sec,
                    "latitude": f"{e.lat:.6f}",
                    "longitude": f"{e.lon:.6f}",
                    "cluster_key": e.cluster_key,
                    "is_complete": 1 if e.is_complete else 0,
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Detecta carregamento/basculamento e separa 'espera' (fila) por paradas (speed_kmh) + GPS + vibração.\n"
            "Regras principais:\n"
            "- Carregamento: parada no hotspot de carregamento + (duração>=load-min-sec) + atividade (acc>=acc-spike-th).\n"
            "- Basculamento: parada no hotspot de basculamento + (dump-min-sec<=duração<=dump-max-sec) + atividade.\n"
            "- Espera: paradas no hotspot, não-operacionais, com duração>=wait-min-sec.\n"
            "- Entre 2 carregamentos, deve haver basculamento (estado carregado/vazio)."
        )
    )
    parser.add_argument("--input", default="input.csv", help="CSV de entrada (padrão: input.csv)")
    parser.add_argument("--output", default="events_detected.csv", help="CSV de saída (padrão: events_detected.csv)")
    parser.add_argument("--speed-stop-kmh", type=float, default=0.5, help="limite de velocidade para considerar parado")
    parser.add_argument("--gap-sec", type=int, default=2, help="tolerância de gap (seg) dentro da mesma parada")
    parser.add_argument("--min-stop-sec", type=int, default=10, help="duração mínima (seg) para uma parada")
    parser.add_argument("--round-decimals", type=int, default=3, help="casas decimais para agrupar hotspots GPS")
    parser.add_argument("--load-min-sec", type=int, default=120, help="duração mínima (seg) para carregamento")
    parser.add_argument("--dump-min-sec", type=int, default=10, help="duração mínima (seg) para basculamento")
    parser.add_argument("--dump-max-sec", type=int, default=120, help="duração máxima (seg) para basculamento")
    parser.add_argument("--wait-min-sec", type=int, default=15, help="duração mínima (seg) para registrar espera")
    parser.add_argument(
        "--acc-spike-th",
        type=float,
        default=0.05,
        help="limite de linear_accel_magnitude para contar como 'atividade' (spike)",
    )
    parser.add_argument(
        "--load-active-frac",
        type=float,
        default=0.08,
        help="fração mínima de spikes (acc>=acc-spike-th) para considerar carregamento",
    )
    parser.add_argument(
        "--dump-active-frac",
        type=float,
        default=0.30,
        help="fração mínima de spikes (acc>=acc-spike-th) para considerar basculamento",
    )
    parser.add_argument("--load-radius-m", type=float, default=250.0, help="raio (m) para agrupar hotspots de carregamento")
    parser.add_argument("--dump-radius-m", type=float, default=250.0, help="raio (m) para agrupar hotspots de basculamento")
    parser.add_argument("--load-merge-gap-min", type=float, default=15.0, help="janela (min) para mesclar blocos de carregamento")
    parser.add_argument(
        "--load-min-sec-relaxed",
        type=int,
        default=90,
        help="duração mínima alternativa (seg) para carregamento quando outras condições são atendidas",
    )
    parser.add_argument(
        "--load-active-frac-relaxed",
        type=float,
        default=0.05,
        help="fração de atividade alternativa para carregamento (padrão: 0.05)",
    )
    parser.add_argument(
        "--load-timeout-hours",
        type=float,
        default=2.0,
        help="timeout (horas) para resetar estado 'loaded' e permitir novo carregamento",
    )
    parser.add_argument(
        "--load-merge-max-duration-sec",
        type=int,
        default=600,
        help="duração máxima (seg) para mesclar carregamentos (padrão: 600s = 10min)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Arquivo não encontrado: {input_path}")

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    stops = iter_stop_segments(
        rows,
        speed_stop_kmh=args.speed_stop_kmh,
        gap_sec=args.gap_sec,
        min_stop_samples=args.min_stop_sec,
        acc_spike_threshold=args.acc_spike_th,
    )
    if not stops:
        raise SystemExit("Nenhuma parada encontrada com os parâmetros atuais.")

    load_anchor = pick_anchor_key(
        stops,
        round_decimals=args.round_decimals,
        predicate=lambda seg: seg.samples >= args.load_min_sec and seg.acc_spike_frac >= args.load_active_frac,
    )
    if load_anchor is None:
        # Fallback: if activity filter is too strict, use any long stop.
        load_anchor = pick_anchor_key(
            stops,
            round_decimals=args.round_decimals,
            predicate=lambda seg: seg.samples >= args.load_min_sec,
        )
    if load_anchor is None:
        raise SystemExit("Não consegui inferir hotspot de carregamento (nenhuma parada longa encontrada).")

    dump_anchor = pick_anchor_key(
        stops,
        round_decimals=args.round_decimals,
        predicate=lambda seg: args.dump_min_sec <= seg.samples <= args.dump_max_sec
        and seg.acc_spike_frac >= args.dump_active_frac
        and haversine_m(load_anchor[0], load_anchor[1], seg.mean_lat, seg.mean_lon) > args.load_radius_m,
    )
    if dump_anchor is None:
        # Fallback: ignore activity filter, keep only duration + outside load.
        dump_anchor = pick_anchor_key(
            stops,
            round_decimals=args.round_decimals,
            predicate=lambda seg: args.dump_min_sec <= seg.samples <= args.dump_max_sec
            and haversine_m(load_anchor[0], load_anchor[1], seg.mean_lat, seg.mean_lon) > args.load_radius_m,
        )
    if dump_anchor is None:
        raise SystemExit("Não consegui inferir hotspot de basculamento (nenhuma parada curta fora do carregamento).")

    stops_sorted = sorted(stops, key=lambda s: s.start)

    def in_load_area(seg: StopSegment) -> bool:
        return haversine_m(load_anchor[0], load_anchor[1], seg.mean_lat, seg.mean_lon) <= args.load_radius_m

    def in_dump_area(seg: StopSegment) -> bool:
        return haversine_m(dump_anchor[0], dump_anchor[1], seg.mean_lat, seg.mean_lon) <= args.dump_radius_m

    def is_load_operation(seg: StopSegment) -> bool:
        if not in_load_area(seg):
            return False
        # Condição padrão: duração >= load_min_sec E atividade >= load_active_frac
        if seg.samples >= args.load_min_sec and seg.acc_spike_frac >= args.load_active_frac:
            return True
        # Condição relaxada: duração >= load_min_sec_relaxed E atividade >= load_active_frac_relaxed
        if seg.samples >= args.load_min_sec_relaxed and seg.acc_spike_frac >= args.load_active_frac_relaxed:
            return True
        return False

    def is_load_operation_without_spikes(seg: StopSegment) -> bool:
        """Verifica se é carregamento mesmo sem spikes detectados, usando duração e localização."""
        if not in_load_area(seg):
            return False
        # Se não tem spikes mas tem duração suficiente e está na área correta
        if seg.spike_first is None or seg.spike_last is None:
            # Usa duração total se >= load_min_sec_relaxed
            return seg.samples >= args.load_min_sec_relaxed
        return False

    def is_dump_operation(seg: StopSegment) -> bool:
        # Operação pode estar dentro de uma parada longa (fila/aguardo). Use o span de atividade (1º→último spike).
        if not in_dump_area(seg):
            return False
        span = seg.spike_span_sec
        if span <= 0:
            return False
        return args.dump_min_sec <= span <= args.dump_max_sec and seg.spike_density_in_span >= args.dump_active_frac

    # ===== PASSADA 1: Detectar TODOS os carregamentos sem restrições de estado =====
    print("Passada 1: Detectando todos os carregamentos...")
    def cluster_key_wrapper(seg: StopSegment) -> tuple[float, float]:
        return cluster_key(seg, round_decimals=args.round_decimals)

    def key_to_str_wrapper(key: tuple[float, float]) -> str:
        return key_to_str(key, round_decimals=args.round_decimals)

    all_loads = detect_all_loads(
        stops_sorted,
        in_load_area=in_load_area,
        is_load_operation=is_load_operation,
        is_load_operation_without_spikes=is_load_operation_without_spikes,
        cluster_key=cluster_key_wrapper,
        key_to_str=key_to_str_wrapper,
        args=args,
    )
    print(f"  {len(all_loads)} carregamentos detectados na primeira passada")

    # ===== PASSADA 2: Detectar basculamentos e esperas =====
    print("Passada 2: Detectando basculamentos e esperas...")
    dumps: list[Event] = []
    waits: list[Event] = []

    for seg in stops_sorted:
        key = cluster_key(seg, round_decimals=args.round_decimals)
        key_str = key_to_str(key, round_decimals=args.round_decimals)

        load_area = in_load_area(seg)
        dump_area = in_dump_area(seg)
        dump_op = is_dump_operation(seg)

        # Detectar basculamentos (sem restrições de estado)
        if dump_area and dump_op and seg.spike_first is not None and seg.spike_last is not None:
            wait_before_sec = int((seg.spike_first - seg.start).total_seconds())
            if wait_before_sec >= args.wait_min_sec:
                wait_end = seg.spike_first - timedelta(seconds=1)
                waits.append(
                    Event(
                        kind="espera_basculamento",
                        start=seg.start,
                        end=wait_end,
                        duration_sec=wait_before_sec,
                        lat=seg.mean_lat,
                        lon=seg.mean_lon,
                        cluster_key=key_str,
                        cycle_id=None,  # Será atribuído depois
                    )
                )

            op_start = seg.spike_first
            op_end = seg.spike_last
            op_dur = seg.spike_span_sec
            dumps.append(
                Event(
                    kind="basculamento",
                    start=op_start,
                    end=op_end,
                    duration_sec=op_dur,
                    lat=seg.mean_lat,
                    lon=seg.mean_lon,
                    cluster_key=key_str,
                    cycle_id=None,  # Será atribuído depois
                )
            )

            wait_after_sec = int((seg.end - seg.spike_last).total_seconds())
            if wait_after_sec >= args.wait_min_sec:
                wait_start = seg.spike_last + timedelta(seconds=1)
                waits.append(
                    Event(
                        kind="espera_basculamento",
                        start=wait_start,
                        end=seg.end,
                        duration_sec=wait_after_sec,
                        lat=seg.mean_lat,
                        lon=seg.mean_lon,
                        cluster_key=key_str,
                        cycle_id=None,  # Será atribuído depois
                    )
                )
            continue

        # Detectar esperas de basculamento (sem operação)
        if dump_area and seg.samples >= args.wait_min_sec and not dump_op:
            waits.append(
                Event(
                    kind="espera_basculamento",
                    start=seg.start,
                    end=seg.end,
                    duration_sec=seg.samples,
                    lat=seg.mean_lat,
                    lon=seg.mean_lon,
                    cluster_key=key_str,
                    cycle_id=None,  # Será atribuído depois
                )
            )
            continue

        # Detectar esperas de carregamento (sem operação)
        if load_area and seg.samples >= args.wait_min_sec:
            # Verifica se não é um carregamento já detectado
            is_detected_load = False
            for load in all_loads:
                if abs((load.start - seg.start).total_seconds()) < 5:
                    is_detected_load = True
                    break

            if not is_detected_load:
                waits.append(
                    Event(
                        kind="espera_carregamento",
                        start=seg.start,
                        end=seg.end,
                        duration_sec=seg.samples,
                        lat=seg.mean_lat,
                        lon=seg.mean_lon,
                        cluster_key=key_str,
                        cycle_id=None,  # Será atribuído depois
                    )
                )
            continue

    print(f"  {len(dumps)} basculamentos detectados")
    print(f"  {len(waits)} eventos de espera detectados")

    # ===== VALIDAÇÃO: Validar carregamentos com basculamentos =====
    print("Validando carregamentos com basculamentos...")
    validated_loads = validate_loads_with_dumps(all_loads, dumps, max_time_between_load_and_dump_hours=4.0)
    complete_loads = [l for l in validated_loads if l.is_complete]
    incomplete_loads = [l for l in validated_loads if not l.is_complete]
    print(f"  {len(complete_loads)} carregamentos completos (com basculamento subsequente)")
    print(f"  {len(incomplete_loads)} carregamentos incompletos (sem basculamento subsequente)")

    # Atribuir cycle_id aos basculamentos baseado nos carregamentos completos
    loads_sorted = sorted(validated_loads, key=lambda e: e.start)
    dumps_sorted = sorted(dumps, key=lambda e: e.start)
    for dump in dumps_sorted:
        # Encontra o carregamento completo anterior mais próximo
        for load in reversed(loads_sorted):
            if load.is_complete and load.end <= dump.start and dump.start <= load.end + timedelta(hours=4):
                dump.cycle_id = load.cycle_id
                break

    # Atribuir cycle_id às esperas baseado nos eventos próximos
    for wait in waits:
        # Procura carregamento ou basculamento próximo
        wait_time = wait.start.timestamp()
        for load in loads_sorted:
            if abs(load.start.timestamp() - wait_time) < 300:  # 5 minutos
                wait.cycle_id = load.cycle_id
                break
        if wait.cycle_id is None:
            for dump in dumps_sorted:
                if abs(dump.start.timestamp() - wait_time) < 300:  # 5 minutos
                    wait.cycle_id = dump.cycle_id
                    break

    # Merge de esperas de carregamento com carregamentos subsequentes
    # Se uma espera_carregamento é seguida imediatamente por um carregamento na mesma área,
    # mescla em um único carregamento começando no início da espera
    merged_loads = []
    waits_to_remove = set()
    
    for wait in waits:
        if wait.kind != "espera_carregamento":
            continue
        
        # Procura carregamento que começa logo após esta espera (até 5 segundos)
        for load in validated_loads:
            time_gap = (load.start - wait.end).total_seconds()
            if 0 <= time_gap <= 5:
                # Verifica se estão na mesma área (mesmo cluster_key ou próximos)
                dist = haversine_m(wait.lat, wait.lon, load.lat, load.lon)
                if dist <= args.load_radius_m:
                    # Mescla: carregamento começa no início da espera
                    load.start = wait.start
                    load.duration_sec = int((load.end - load.start).total_seconds())
                    # Atualiza coordenadas para média ponderada
                    total_dur = wait.duration_sec + load.duration_sec
                    load.lat = (wait.lat * wait.duration_sec + load.lat * load.duration_sec) / total_dur
                    load.lon = (wait.lon * wait.duration_sec + load.lon * load.duration_sec) / total_dur
                    waits_to_remove.add(id(wait))
                    print(f"  Mesclado: espera {wait.start.strftime('%H:%M:%S')} + carregamento {load.start.strftime('%H:%M:%S')} -> carregamento {wait.start.strftime('%H:%M:%S')}")
                    break
    
    # Remove esperas que foram mescladas
    waits_filtered = [w for w in waits if id(w) not in waits_to_remove]

    # Combinar todos os eventos
    validated = validated_loads + dumps + waits_filtered
    validated.sort(key=lambda e: e.start)

    # Write output
    output_path = Path(args.output)
    write_events_csv(output_path, validated)

    loads = [e for e in validated if e.kind == "carregamento"]
    dumps = [e for e in validated if e.kind == "basculamento"]
    wait_loads = [e for e in validated if e.kind == "espera_carregamento"]
    wait_dumps = [e for e in validated if e.kind == "espera_basculamento"]
    loads_path = output_path.with_name("carregamentos_detectados.csv")
    dumps_path = output_path.with_name("basculamentos_detectados.csv")
    wait_loads_path = output_path.with_name("esperas_carregamento_detectadas.csv")
    wait_dumps_path = output_path.with_name("esperas_basculamento_detectadas.csv")
    write_events_csv(loads_path, loads)
    write_events_csv(dumps_path, dumps)
    write_events_csv(wait_loads_path, wait_loads)
    write_events_csv(wait_dumps_path, wait_dumps)

    print(f"Hotspot carregamento (anchor): {key_to_str(load_anchor, round_decimals=args.round_decimals)}")
    print(f"Hotspot basculamento (anchor): {key_to_str(dump_anchor, round_decimals=args.round_decimals)}")
    print(
        f"Eventos detectados: carregamentos={len(loads)} basculamentos={len(dumps)} "
        f"espera_carregamento={len(wait_loads)} espera_basculamento={len(wait_dumps)}"
    )
    print(f"Saídas: {output_path} | {loads_path} | {dumps_path} | {wait_loads_path} | {wait_dumps_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
