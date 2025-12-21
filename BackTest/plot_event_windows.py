#!/usr/bin/env python3
from __future__ import annotations

import argparse
import bisect
import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Event:
    idx: int
    cycle_id: Optional[int]
    kind: str
    start: datetime
    end: datetime
    duration_sec: int
    lat: float
    lon: float
    cluster_key: str

    @property
    def start_epoch(self) -> int:
        return int(self.start.timestamp())

    @property
    def end_epoch(self) -> int:
        return int(self.end.timestamp())

    @property
    def duration_min(self) -> float:
        return self.duration_sec / 60.0

    @property
    def span_sec(self) -> int:
        return max(0, int((self.end - self.start).total_seconds()))

    @property
    def span_min(self) -> float:
        return self.span_sec / 60.0


@dataclass(frozen=True)
class Series:
    name: str
    values: list[float]
    color: str


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S%z")


def try_float(value: str) -> float:
    if value is None:
        return math.nan
    value = value.strip()
    if value == "":
        return math.nan
    try:
        return float(value)
    except ValueError:
        return math.nan


def nice_step(raw: float) -> float:
    if raw <= 0 or math.isnan(raw) or math.isinf(raw):
        return 1.0
    exp = 10 ** math.floor(math.log10(raw))
    frac = raw / exp
    if frac <= 1:
        nice = 1
    elif frac <= 2:
        nice = 2
    elif frac <= 5:
        nice = 5
    else:
        nice = 10
    return nice * exp


def axis_ticks(min_val: float, max_val: float, *, ticks: int = 6, clamp_zero: bool = False) -> tuple[float, float, float]:
    if not (math.isfinite(min_val) and math.isfinite(max_val)):
        min_val, max_val = 0.0, 1.0
    if clamp_zero:
        min_val = 0.0
        max_val = max(0.0, max_val)
    if min_val == max_val:
        min_val -= 1.0
        max_val += 1.0
    raw_step = (max_val - min_val) / max(1, ticks - 1)
    step = nice_step(raw_step)
    lo = math.floor(min_val / step) * step
    hi = math.ceil(max_val / step) * step
    # Expand to ensure we have at least `ticks` tick marks.
    while (hi - lo) / step + 1 < ticks:
        hi += step
    return lo, hi, step


def fmt_value(v: float) -> str:
    if not math.isfinite(v):
        return ""
    av = abs(v)
    if av >= 100:
        return f"{v:.0f}"
    if av >= 10:
        return f"{v:.1f}"
    return f"{v:.2f}"


def svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def safe_filename(text: str) -> str:
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
    return "".join((c if c in allowed else "_") for c in text)


def render_event_svg(
    *,
    event: Event,
    x_min: float,
    x_max: float,
    x_values: list[float],
    speed: list[float],
    pitch: list[float],
    roll: list[float],
    accel: list[float],
    gyro: list[float],
    out_path: Path,
) -> None:
    # Panels: each has one or more series
    panels: list[tuple[str, str, bool, list[Series]]] = [
        ("Velocidade", "km/h", True, [Series("speed_kmh", speed, "#1976D2")]),
        ("Inclinação", "graus", False, [Series("pitch", pitch, "#2E7D32"), Series("roll", roll, "#6A1B9A")]),
        ("Aceleração (magnitude)", "u.a.", True, [Series("linear_accel_magnitude", accel, "#FB8C00")]),
        ("Giroscópio (magnitude)", "u.a.", True, [Series("gyro_mag", gyro, "#E53935")]),
    ]

    width = 1180
    height = 980
    margin_left = 90
    margin_right = 30
    margin_top = 85
    margin_bottom = 70
    panel_gap = 18
    plot_w = width - margin_left - margin_right
    n_panels = len(panels)
    plot_h_total = height - margin_top - margin_bottom - panel_gap * (n_panels - 1)
    panel_h = plot_h_total / n_panels

    # X ticks
    x_lo, x_hi, x_step = axis_ticks(x_min, x_max, ticks=7, clamp_zero=False)

    def x_px(x: float) -> float:
        return margin_left + (x - x_lo) / (x_hi - x_lo) * plot_w

    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    lines.append("<style>")
    lines.append(
        "text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; fill: #111; }"
    )
    lines.append(".small { font-size: 12px; fill: #222; }")
    lines.append(".title { font-size: 18px; font-weight: 700; }")
    lines.append(".axis { stroke: #111; stroke-width: 1.4; }")
    lines.append(".grid { stroke: #E6E6E6; stroke-width: 1; }")
    lines.append(".event { fill: #FFEB3B; fill-opacity: 0.18; }")
    lines.append(".eventline { stroke: #F9A825; stroke-width: 1.2; stroke-dasharray: 4 3; }")
    lines.append(".series { fill: none; stroke-width: 1.8; }")
    lines.append("</style>")

    # Header
    cycle = "" if event.cycle_id is None else f"ciclo {event.cycle_id} — "
    header = (
        f"{cycle}{event.kind} — {event.start.isoformat()} → {event.end.isoformat()} "
        f"(span {event.span_sec}s, dur {event.duration_sec}s)"
    )
    lines.append(f'<text class="title" x="{margin_left}" y="34">{svg_escape(header)}</text>')
    lines.append(
        f'<text class="small" x="{margin_left}" y="54">GPS: {event.lat:.6f},{event.lon:.6f}  hotspot: {svg_escape(event.cluster_key)}</text>'
    )
    lines.append(
        f'<text class="small" x="{margin_left}" y="70">Janela: {fmt_value(x_min)} → {fmt_value(x_max)} min (relativo ao início do evento)</text>'
    )

    # Shared X grid/ticks will be drawn on each panel (grid vertical)
    x_tick_values = []
    v = x_lo
    # Avoid too many ticks if axis expanded.
    max_ticks = 14
    while v <= x_hi + 1e-9 and len(x_tick_values) < max_ticks:
        x_tick_values.append(v)
        v += x_step

    event_x0 = 0.0
    event_x1 = event.span_min

    # Panels
    for pi, (title, unit, clamp_zero, series_list) in enumerate(panels):
        panel_top = margin_top + pi * (panel_h + panel_gap)
        panel_bottom = panel_top + panel_h

        # Collect y range across series.
        y_vals = []
        for s in series_list:
            for y in s.values:
                if math.isfinite(y):
                    y_vals.append(y)
        if y_vals:
            y_min = min(y_vals)
            y_max = max(y_vals)
        else:
            y_min, y_max = 0.0, 1.0
        if y_min == y_max:
            y_min -= 1.0
            y_max += 1.0
        pad = (y_max - y_min) * 0.08
        if clamp_zero:
            y_min = 0.0
            y_max += pad
        else:
            y_min -= pad
            y_max += pad

        y_lo, y_hi, y_step = axis_ticks(y_min, y_max, ticks=6, clamp_zero=clamp_zero)

        def y_px(y: float) -> float:
            return panel_top + (1 - (y - y_lo) / (y_hi - y_lo)) * panel_h

        # Panel title
        lines.append(f'<text x="{margin_left}" y="{panel_top - 6:.2f}" font-size="14" font-weight="700">{svg_escape(title)} ({svg_escape(unit)})</text>')

        # Event shading
        ex0 = x_px(event_x0)
        ex1 = x_px(event_x1)
        if ex1 < ex0:
            ex0, ex1 = ex1, ex0
        lines.append(f'<rect class="event" x="{ex0:.2f}" y="{panel_top:.2f}" width="{max(0.0, ex1 - ex0):.2f}" height="{panel_h:.2f}" />')
        lines.append(f'<line class="eventline" x1="{ex0:.2f}" y1="{panel_top:.2f}" x2="{ex0:.2f}" y2="{panel_bottom:.2f}" />')
        lines.append(f'<line class="eventline" x1="{ex1:.2f}" y1="{panel_top:.2f}" x2="{ex1:.2f}" y2="{panel_bottom:.2f}" />')

        # Grid Y
        y_tick_values = []
        yv = y_lo
        while yv <= y_hi + 1e-9 and len(y_tick_values) < 14:
            y_tick_values.append(yv)
            yv += y_step
        for yv in y_tick_values:
            y = y_px(yv)
            lines.append(f'<line class="grid" x1="{margin_left}" y1="{y:.2f}" x2="{margin_left + plot_w}" y2="{y:.2f}" />')
            lines.append(f'<text class="small" x="{margin_left - 10}" y="{y + 4:.2f}" text-anchor="end">{fmt_value(yv)}</text>')

        # Grid X (vertical)
        for xv in x_tick_values:
            x = x_px(xv)
            lines.append(f'<line class="grid" x1="{x:.2f}" y1="{panel_top:.2f}" x2="{x:.2f}" y2="{panel_bottom:.2f}" />')

        # Axes
        lines.append(f'<line class="axis" x1="{margin_left}" y1="{panel_top:.2f}" x2="{margin_left}" y2="{panel_bottom:.2f}" />')
        lines.append(
            f'<line class="axis" x1="{margin_left}" y1="{panel_bottom:.2f}" x2="{margin_left + plot_w}" y2="{panel_bottom:.2f}" />'
        )

        # Draw series
        for s in series_list:
            d_parts = []
            pen_down = False
            for x, y in zip(x_values, s.values):
                if not (math.isfinite(x) and math.isfinite(y)):
                    pen_down = False
                    continue
                xp = x_px(x)
                yp = y_px(y)
                if not pen_down:
                    d_parts.append(f"M {xp:.2f} {yp:.2f}")
                    pen_down = True
                else:
                    d_parts.append(f"L {xp:.2f} {yp:.2f}")
            if d_parts:
                path = " ".join(d_parts)
                lines.append(f'<path class="series" d="{path}" stroke="{s.color}" />')

        # Legend for multi-series panel
        if len(series_list) > 1:
            lx = margin_left + plot_w - 250
            ly = panel_top + 16
            for li, s in enumerate(series_list):
                yy = ly + li * 16
                lines.append(f'<line x1="{lx:.2f}" y1="{yy - 4:.2f}" x2="{lx + 18:.2f}" y2="{yy - 4:.2f}" stroke="{s.color}" stroke-width="3" />')
                lines.append(f'<text class="small" x="{lx + 24:.2f}" y="{yy:.2f}">{svg_escape(s.name)}</text>')

    # X axis labels at bottom
    x_label_y = height - 28
    lines.append(
        f'<text x="{margin_left + plot_w / 2:.2f}" y="{x_label_y}" font-size="15" text-anchor="middle">minutos (relativo ao início do evento)</text>'
    )
    for xv in x_tick_values:
        x = x_px(xv)
        lines.append(f'<text class="small" x="{x:.2f}" y="{height - 44}" text-anchor="middle">{fmt_value(xv)}</text>')

    lines.append("</svg>")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def read_events(events_path: Path) -> list[Event]:
    events: list[Event] = []
    with events_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            kind = (row.get("event") or "").strip()
            if not kind:
                continue
            start_raw = (row.get("start") or "").strip()
            end_raw = (row.get("end") or "").strip()
            if not start_raw or not end_raw:
                continue
            try:
                start = datetime.fromisoformat(start_raw)
                end = datetime.fromisoformat(end_raw)
            except Exception:
                continue
            duration_raw = (row.get("duration_sec") or "").strip()
            try:
                duration_sec = int(float(duration_raw))
            except Exception:
                duration_sec = int((end - start).total_seconds())
            cycle_raw = (row.get("cycle_id") or "").strip()
            cycle_id = int(cycle_raw) if cycle_raw else None
            lat = try_float(row.get("latitude") or "")
            lon = try_float(row.get("longitude") or "")
            cluster_key = (row.get("cluster_key") or "").strip()
            events.append(
                Event(
                    idx=i,
                    cycle_id=cycle_id,
                    kind=kind,
                    start=start,
                    end=end,
                    duration_sec=duration_sec,
                    lat=lat,
                    lon=lon,
                    cluster_key=cluster_key,
                )
            )
    return events


def read_telemetry(input_path: Path) -> tuple[list[int], list[float], list[float], list[float], list[float], list[float]]:
    times: list[int] = []
    speed: list[float] = []
    pitch: list[float] = []
    roll: list[float] = []
    accel: list[float] = []
    gyro_mag: list[float] = []

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t = parse_time(row.get("time", ""))
            except Exception:
                continue
            times.append(int(t.timestamp()))
            speed.append(try_float(row.get("speed_kmh", "")))
            pitch.append(try_float(row.get("pitch", "")))
            roll.append(try_float(row.get("roll", "")))
            accel.append(try_float(row.get("linear_accel_magnitude", "")))

            gx = try_float(row.get("gyro_x", ""))
            gy = try_float(row.get("gyro_y", ""))
            gz = try_float(row.get("gyro_z", ""))
            if math.isfinite(gx) and math.isfinite(gy) and math.isfinite(gz):
                gyro_mag.append(math.sqrt(gx * gx + gy * gy + gz * gz))
            else:
                gyro_mag.append(math.nan)

    return times, speed, pitch, roll, accel, gyro_mag


def write_index_html(out_path: Path, items: list[tuple[Event, str]]) -> None:
    rows = []
    for ev, filename in items:
        cycle = "" if ev.cycle_id is None else str(ev.cycle_id)
        rows.append(
            f"<tr><td>{ev.idx}</td><td>{svg_escape(cycle)}</td><td>{svg_escape(ev.kind)}</td><td>{svg_escape(ev.start.isoformat())}</td><td>{ev.duration_sec}</td><td><a href='{svg_escape(filename)}'>{svg_escape(filename)}</a></td></tr>\n"
        )
    html = f"""<!doctype html>
<html lang="pt-br">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Eventos — janelas</title>
    <style>
      body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        margin: 24px;
        color: #111;
      }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: 1px solid #E6E6E6; padding: 8px; font-size: 13px; }}
      th {{ background: #F6F8FA; text-align: left; }}
      .hint {{ color: #444; font-size: 13px; margin: 10px 0 16px; }}
      code {{ background: #F6F8FA; padding: 2px 6px; border-radius: 6px; }}
    </style>
  </head>
  <body>
	    <h1>Gráficos por evento (janela ±3 min)</h1>
	    <p class="hint">Abra qualquer SVG (coluna “arquivo”). Dica: ordene/filtre no seu editor/planilha usando <code>cycle_id</code> e <code>event</code>.</p>
	    <p class="hint"><a href="../timeline_viewer.html">Abrir linha do tempo (scroll horizontal, 1h visível)</a></p>
	    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>cycle_id</th>
          <th>event</th>
          <th>start</th>
          <th>duration_sec</th>
          <th>arquivo</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera um SVG por evento com contexto (antes/depois) usando input.csv.")
    parser.add_argument("--input", default="input.csv", help="telemetria (CSV bruto)")
    parser.add_argument("--events", default="events_detected.csv", help="CSV de eventos detectados")
    parser.add_argument("--outdir", default="plots/event_windows", help="diretório de saída")
    parser.add_argument("--before-min", type=float, default=3.0, help="minutos antes do evento")
    parser.add_argument("--after-min", type=float, default=3.0, help="minutos depois do evento")
    parser.add_argument("--max-points", type=int, default=2200, help="máximo de pontos por gráfico (downsample se necessário)")
    args = parser.parse_args()

    input_path = Path(args.input)
    events_path = Path(args.events)
    outdir = Path(args.outdir)

    if not input_path.exists():
        raise SystemExit(f"Arquivo não encontrado: {input_path}")
    if not events_path.exists():
        raise SystemExit(f"Arquivo não encontrado: {events_path}")

    events = read_events(events_path)
    if not events:
        raise SystemExit(f"Nenhum evento lido de {events_path}")

    times, speed, pitch, roll, accel, gyro = read_telemetry(input_path)
    if not times:
        raise SystemExit(f"Nenhum dado lido de {input_path}")

    # Ensure sorted for bisect.
    if any(times[i] > times[i + 1] for i in range(len(times) - 1)):
        raise SystemExit("Telemetria não está ordenada por tempo; ordenação não implementada nesta ferramenta.")

    before_sec = int(round(args.before_min * 60))
    after_sec = int(round(args.after_min * 60))

    generated: list[tuple[Event, str]] = []
    for ev in events:
        start = ev.start_epoch
        end = ev.end_epoch
        window_start = start - before_sec
        window_end = end + after_sec

        i0 = bisect.bisect_left(times, window_start)
        i1 = bisect.bisect_right(times, window_end)

        # If there are no points, still generate an empty chart.
        x_min = -args.before_min
        x_max = ev.span_min + args.after_min

        t_slice = times[i0:i1]
        if t_slice:
            x_vals_all = [(t - start) / 60.0 for t in t_slice]
        else:
            x_vals_all = []

        speed_slice = speed[i0:i1]
        pitch_slice = pitch[i0:i1]
        roll_slice = roll[i0:i1]
        accel_slice = accel[i0:i1]
        gyro_slice = gyro[i0:i1]

        n = len(x_vals_all)
        if n > 0 and args.max_points > 0 and n > args.max_points:
            step = int(math.ceil(n / args.max_points))

            def ds(vals: list[float]) -> list[float]:
                return vals[::step]

            x_vals = x_vals_all[::step]
            speed_slice = ds(speed_slice)
            pitch_slice = ds(pitch_slice)
            roll_slice = ds(roll_slice)
            accel_slice = ds(accel_slice)
            gyro_slice = ds(gyro_slice)
        else:
            x_vals = x_vals_all

        cycle = "na" if ev.cycle_id is None else f"{ev.cycle_id:03d}"
        name = safe_filename(f"{ev.idx:03d}_cycle_{cycle}_{ev.kind}_{ev.start.strftime('%Y%m%dT%H%M%S')}.svg")
        out_svg = outdir / name
        render_event_svg(
            event=ev,
            x_min=x_min,
            x_max=x_max,
            x_values=x_vals,
            speed=speed_slice,
            pitch=pitch_slice,
            roll=roll_slice,
            accel=accel_slice,
            gyro=gyro_slice,
            out_path=out_svg,
        )
        generated.append((ev, name))

    index = outdir / "index.html"
    outdir.mkdir(parents=True, exist_ok=True)
    write_index_html(index, generated)

    print(f"Gerados {len(generated)} SVGs em {outdir}")
    print(f"Abra: {index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
