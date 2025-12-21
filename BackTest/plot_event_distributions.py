#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class DistributionStats:
    n: int
    mean: float
    std: float
    min: float
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    max: float


def quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("empty list")
    if q <= 0:
        return sorted_values[0]
    if q >= 1:
        return sorted_values[-1]
    pos = (len(sorted_values) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_values[lo]
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def compute_stats(values: list[float]) -> DistributionStats:
    values_sorted = sorted(values)
    n = len(values_sorted)
    mean = statistics.mean(values_sorted)
    std = statistics.pstdev(values_sorted) if n >= 2 else 0.0
    return DistributionStats(
        n=n,
        mean=mean,
        std=std,
        min=values_sorted[0],
        p10=quantile(values_sorted, 0.10),
        p25=quantile(values_sorted, 0.25),
        p50=quantile(values_sorted, 0.50),
        p75=quantile(values_sorted, 0.75),
        p90=quantile(values_sorted, 0.90),
        max=values_sorted[-1],
    )


def choose_bins(values: list[float]) -> tuple[list[float], float]:
    values_sorted = sorted(values)
    n = len(values_sorted)
    vmin = values_sorted[0]
    vmax = values_sorted[-1]
    if vmin == vmax:
        return [vmin - 0.5, vmax + 0.5], 1.0

    q25 = quantile(values_sorted, 0.25)
    q75 = quantile(values_sorted, 0.75)
    iqr = max(0.0, q75 - q25)
    if iqr > 0 and n >= 2:
        bin_w = 2 * iqr * (n ** (-1 / 3))
    else:
        bin_w = 0.0

    if not (bin_w > 0):
        bins = max(5, min(30, int(math.sqrt(n)) if n > 0 else 10))
        bin_w = (vmax - vmin) / bins

    bins = int(math.ceil((vmax - vmin) / bin_w))
    bins = max(5, min(60, bins))
    bin_w = (vmax - vmin) / bins

    edges = [vmin + i * bin_w for i in range(bins + 1)]
    edges[-1] = vmax
    return edges, bin_w


def histogram(values: list[float], edges: list[float]) -> list[int]:
    counts = [0] * (len(edges) - 1)
    if not counts:
        return counts
    vmin = edges[0]
    vmax = edges[-1]
    bins = len(counts)
    span = vmax - vmin
    if span <= 0:
        counts[0] = len(values)
        return counts
    for v in values:
        if v <= vmin:
            idx = 0
        elif v >= vmax:
            idx = bins - 1
        else:
            idx = int((v - vmin) / span * bins)
            idx = max(0, min(bins - 1, idx))
        counts[idx] += 1
    return counts


def normal_pdf(x: float, mu: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    z = (x - mu) / sigma
    return math.exp(-0.5 * z * z) / (sigma * math.sqrt(2 * math.pi))


def svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


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


def render_histogram_svg(
    *,
    values: list[float],
    title: str,
    x_label: str,
    out_path: Path,
    color: str,
) -> None:
    stats = compute_stats(values)
    edges, bin_w = choose_bins(values)
    counts = histogram(values, edges)
    bins = len(counts)

    mu = stats.mean
    sigma = stats.std

    # Scale normal curve to histogram counts.
    normal_counts = []
    for i in range(bins):
        x0 = edges[i]
        x1 = edges[i + 1]
        xmid = (x0 + x1) / 2
        y = normal_pdf(xmid, mu, sigma) * stats.n * (x1 - x0)
        normal_counts.append(y)

    y_max = max([0.0] + [float(c) for c in counts] + normal_counts)
    y_max = max(1.0, y_max * 1.15)

    x_min = edges[0]
    x_max = edges[-1]
    if x_max == x_min:
        x_max = x_min + 1.0

    width = 980
    height = 520
    margin_left = 80
    margin_right = 30
    margin_top = 60
    margin_bottom = 90
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    def x_px(x: float) -> float:
        return margin_left + (x - x_min) / (x_max - x_min) * plot_w

    def y_px(y: float) -> float:
        return margin_top + (1 - (y / y_max)) * plot_h

    # Ticks
    x_ticks = 6
    y_ticks = 6

    def fmt_num(v: float) -> str:
        if abs(v) >= 100:
            return f"{v:.0f}"
        if abs(v) >= 10:
            return f"{v:.1f}"
        return f"{v:.2f}"

    y_step = max(1.0, nice_step(y_max / (y_ticks - 1)))
    y_max = y_step * (y_ticks - 1)

    def fmt_y(v: float) -> str:
        return f"{int(round(v))}"

    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    lines.append("<style>")
    lines.append(
        "text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; fill: #111; }"
    )
    lines.append(".small { font-size: 12px; fill: #222; }")
    lines.append(".axis { stroke: #111; stroke-width: 1.5; }")
    lines.append(".grid { stroke: #E6E6E6; stroke-width: 1; }")
    lines.append(".bar { fill-opacity: 0.55; }")
    lines.append(".curve { fill: none; stroke: #E53935; stroke-width: 2.5; }")
    lines.append("</style>")

    # Title
    lines.append(f'<text x="{margin_left}" y="{margin_top - 25}" font-size="20" font-weight="700">{svg_escape(title)}</text>')

    # Grid + Y axis ticks
    for i in range(y_ticks):
        y_val = y_step * i
        y = y_px(y_val)
        lines.append(f'<line class="grid" x1="{margin_left}" y1="{y:.2f}" x2="{margin_left + plot_w}" y2="{y:.2f}" />')
        lines.append(f'<text class="small" x="{margin_left - 10}" y="{y + 4:.2f}" text-anchor="end">{fmt_y(y_val)}</text>')

    # X axis ticks
    for i in range(x_ticks):
        x_val = x_min + (x_max - x_min) * i / (x_ticks - 1)
        x = x_px(x_val)
        lines.append(f'<line class="grid" x1="{x:.2f}" y1="{margin_top}" x2="{x:.2f}" y2="{margin_top + plot_h}" />')
        lines.append(
            f'<text class="small" x="{x:.2f}" y="{margin_top + plot_h + 22}" text-anchor="middle">{fmt_num(x_val)}</text>'
        )

    # Axes
    lines.append(
        f'<line class="axis" x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}" />'
    )
    lines.append(
        f'<line class="axis" x1="{margin_left}" y1="{margin_top + plot_h}" x2="{margin_left + plot_w}" y2="{margin_top + plot_h}" />'
    )
    lines.append(
        f'<text x="{margin_left + plot_w / 2:.2f}" y="{margin_top + plot_h + 55}" font-size="16" text-anchor="middle">{svg_escape(x_label)}</text>'
    )
    lines.append(
        f'<text x="{margin_left - 55}" y="{margin_top + plot_h / 2:.2f}" font-size="16" text-anchor="middle" transform="rotate(-90 {margin_left - 55} {margin_top + plot_h / 2:.2f})">contagem</text>'
    )

    # Bars
    for i in range(bins):
        x0 = x_px(edges[i])
        x1 = x_px(edges[i + 1])
        bar_w = max(1.0, x1 - x0 - 1.0)
        y0 = y_px(float(counts[i]))
        y_base = y_px(0.0)
        h = max(0.0, y_base - y0)
        lines.append(
            f'<rect class="bar" x="{x0:.2f}" y="{y0:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{color}" />'
        )

    # Normal curve (scaled to counts)
    pts = []
    points = 240
    for j in range(points):
        x = x_min + (x_max - x_min) * j / (points - 1)
        y = normal_pdf(x, mu, sigma) * stats.n * bin_w
        pts.append((x_px(x), y_px(y)))
    path = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pts)
    lines.append(f'<path class="curve" d="{path}" />')
    lines.append(
        f'<text class="small" x="{margin_left + plot_w - 5}" y="{margin_top + 18}" text-anchor="end">curva normal (μ, σ)</text>'
    )

    # Stats box
    box_x = margin_left
    box_y = margin_top + plot_h + 70
    stats_text = (
        f"n={stats.n}  "
        f"min={fmt_num(stats.min)}  p50={fmt_num(stats.p50)}  p90={fmt_num(stats.p90)}  max={fmt_num(stats.max)}  "
        f"μ={fmt_num(stats.mean)}  σ={fmt_num(stats.std)}"
    )
    lines.append(f'<text class="small" x="{box_x}" y="{box_y}">{svg_escape(stats_text)}</text>')

    lines.append("</svg>")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def read_durations(csv_path: Path) -> list[int]:
    if not csv_path.exists():
        raise FileNotFoundError(str(csv_path))
    durations: list[int] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = (row.get("duration_sec") or "").strip()
            if not raw:
                continue
            try:
                durations.append(int(float(raw)))
            except ValueError:
                continue
    return durations


def write_html(out_path: Path, *, load_svg: Path, dump_svg: Path) -> None:
    html = f"""<!doctype html>
<html lang="pt-br">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Distribuições de Duração</title>
    <style>
      body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        margin: 24px;
        color: #111;
      }}
      .grid {{
        display: grid;
        grid-template-columns: 1fr;
        gap: 24px;
        max-width: 1100px;
      }}
      .card {{
        border: 1px solid #E6E6E6;
        border-radius: 10px;
        padding: 16px;
      }}
      h1 {{ margin: 0 0 14px 0; font-size: 22px; }}
      h2 {{ margin: 0 0 10px 0; font-size: 18px; }}
      .hint {{ color: #444; font-size: 13px; }}
      img {{ width: 100%; height: auto; }}
      code {{ background: #F6F8FA; padding: 2px 6px; border-radius: 6px; }}
    </style>
  </head>
  <body>
    <h1>Distribuições de Duração (histograma + curva normal ajustada)</h1>
    <p class="hint">Arquivos de entrada: <code>{svg_escape(load_svg.name)}</code> e <code>{svg_escape(dump_svg.name)}</code></p>
    <div class="grid">
      <div class="card">
        <h2>Carregamento</h2>
        <img src="{svg_escape(load_svg.name)}" alt="Distribuição de duração de carregamentos" />
      </div>
      <div class="card">
        <h2>Basculamento</h2>
        <img src="{svg_escape(dump_svg.name)}" alt="Distribuição de duração de basculamentos" />
      </div>
    </div>
  </body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera gráficos (SVG/HTML) de distribuição de duração dos eventos.")
    parser.add_argument("--carregamentos", default="carregamentos_detectados.csv", help="CSV de carregamentos")
    parser.add_argument("--basculamentos", default="basculamentos_detectados.csv", help="CSV de basculamentos")
    parser.add_argument("--outdir", default="plots", help="Diretório de saída")
    parser.add_argument("--unit", choices=["sec", "min"], default="min", help="Unidade do eixo X (padrão: min)")
    args = parser.parse_args()

    load_path = Path(args.carregamentos)
    dump_path = Path(args.basculamentos)
    outdir = Path(args.outdir)

    load_dur_sec = read_durations(load_path)
    dump_dur_sec = read_durations(dump_path)
    if not load_dur_sec:
        raise SystemExit(f"Nenhum duration_sec lido de {load_path}")
    if not dump_dur_sec:
        raise SystemExit(f"Nenhum duration_sec lido de {dump_path}")

    if args.unit == "sec":
        load_values = [float(v) for v in load_dur_sec]
        dump_values = [float(v) for v in dump_dur_sec]
        x_label = "duração (seg)"
    else:
        load_values = [v / 60.0 for v in load_dur_sec]
        dump_values = [v / 60.0 for v in dump_dur_sec]
        x_label = "duração (min)"

    load_svg = outdir / "duracao_carregamento.svg"
    dump_svg = outdir / "duracao_basculamento.svg"
    html = outdir / "duracao_distribuicoes.html"

    render_histogram_svg(
        values=load_values,
        title="Carregamento — distribuição de duração",
        x_label=x_label,
        out_path=load_svg,
        color="#1976D2",
    )
    render_histogram_svg(
        values=dump_values,
        title="Basculamento — distribuição de duração",
        x_label=x_label,
        out_path=dump_svg,
        color="#2E7D32",
    )
    write_html(html, load_svg=load_svg, dump_svg=dump_svg)

    load_stats = compute_stats(load_values)
    dump_stats = compute_stats(dump_values)
    unit_label = "seg" if args.unit == "sec" else "min"
    print(f"Carregamento: n={load_stats.n} mean={load_stats.mean:.2f}{unit_label} std={load_stats.std:.2f}{unit_label}")
    print(f"Basculamento: n={dump_stats.n} mean={dump_stats.mean:.2f}{unit_label} std={dump_stats.std:.2f}{unit_label}")
    print(f"Gerado: {load_svg} | {dump_svg} | {html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
