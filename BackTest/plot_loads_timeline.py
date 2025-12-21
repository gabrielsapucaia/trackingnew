#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class LoadEvent:
    idx: int
    cycle_id: Optional[int]
    start: datetime
    end: datetime
    duration_sec: int
    lat: float
    lon: float
    cluster_key: str
    is_complete: bool

    @property
    def start_ms(self) -> int:
        return int(self.start.timestamp() * 1000)

    @property
    def end_ms(self) -> int:
        return int(self.end.timestamp() * 1000)


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def try_int(value: str) -> Optional[int]:
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def try_float(value: str) -> float:
    if value is None:
        return float("nan")
    value = value.strip()
    if value == "":
        return float("nan")
    try:
        return float(value)
    except ValueError:
        return float("nan")


HTML_TEMPLATE = """<!doctype html>
<html lang="pt-br">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Linha do tempo — carregamentos</title>
    <style>
      :root {{
        --lane-height: 50px;
        --lane-gap: 15px;
        --axis-height: 40px;
      }}

      body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        margin: 18px;
        color: #111;
        background: #fafafa;
      }}

      h1 {{
        font-size: 20px;
        margin: 0 0 10px 0;
      }}

      .summary {{
        font-size: 14px;
        color: #333;
        margin: 0 0 15px 0;
        padding: 12px;
        background: white;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      }}

      .summary strong {{
        color: #0066cc;
      }}

      .toolbar {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px 14px;
        align-items: center;
        margin: 0 0 12px 0;
      }}

      .toolbar label {{
        font-size: 13px;
        color: #222;
      }}

      .toolbar select, .toolbar input {{
        font-size: 13px;
        padding: 6px 8px;
        border: 1px solid #D0D7DE;
        border-radius: 8px;
        background: white;
      }}

      .toolbar button {{
        font-size: 13px;
        padding: 6px 10px;
        border: 1px solid #D0D7DE;
        border-radius: 8px;
        background: #F6F8FA;
        cursor: pointer;
      }}
      .toolbar button:hover {{ background: #EEF1F4; }}

      .hint {{
        font-size: 13px;
        color: #444;
        margin: 0 0 14px 0;
      }}

      .legend {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px 14px;
        font-size: 12px;
        color: #222;
        margin: 0 0 10px 0;
      }}
      .legend-item {{
        display: inline-flex;
        gap: 8px;
        align-items: center;
      }}
      .swatch {{
        width: 28px;
        height: 16px;
        border: 1px solid #1113;
        border-radius: 4px;
      }}
      .swatch.complete {{
        background: linear-gradient(135deg, rgba(34, 139, 34, 0.7), rgba(50, 205, 50, 0.7));
        border-color: rgba(34, 139, 34, 0.8);
      }}
      .swatch.incomplete {{
        background: linear-gradient(135deg, rgba(220, 20, 60, 0.6), rgba(255, 99, 71, 0.6));
        border-color: rgba(220, 20, 60, 0.8);
      }}

      .timeline {{
        border: 1px solid #E6E6E6;
        border-radius: 12px;
        overflow: hidden;
        background: white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }}

      .scroll {{
        overflow-x: auto;
        overflow-y: hidden;
        background: white;
      }}

      .svg-wrap {{
        position: relative;
        height: calc(var(--axis-height) + var(--lane-height) + 20px);
      }}

      svg {{
        display: block;
      }}

      .topbar {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        margin: 0 0 10px 0;
        font-size: 12px;
        color: #333;
      }}
      .topbar code {{
        background: #F6F8FA;
        padding: 2px 6px;
        border-radius: 6px;
      }}

      .tooltip {{
        position: fixed;
        z-index: 9999;
        pointer-events: none;
        display: none;
        max-width: 360px;
        background: rgba(20, 20, 20, 0.95);
        color: #fff;
        padding: 10px 12px;
        border-radius: 10px;
        font-size: 12px;
        line-height: 1.4;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
      }}
      .tooltip .k {{
        color: rgba(255,255,255,0.75);
      }}
      .tooltip .status {{
        font-weight: 600;
        padding: 2px 6px;
        border-radius: 4px;
        display: inline-block;
        margin-top: 4px;
      }}
      .tooltip .status.complete {{
        background: rgba(34, 139, 34, 0.3);
        color: #90EE90;
      }}
      .tooltip .status.incomplete {{
        background: rgba(220, 20, 60, 0.3);
        color: #FFB6C1;
      }}
    </style>
  </head>
  <body>
    <h1>Linha do tempo dos carregamentos</h1>
    
    <div class="summary">
      Total: <strong>{total_loads}</strong> carregamentos detectados • 
      Completos: <strong style="color: #228B22;">{complete_loads}</strong> • 
      Incompletos: <strong style="color: #DC143C;">{incomplete_loads}</strong>
    </div>

    <div class="toolbar">
      <label>Janela visível:
        <select id="windowHours">
          <option value="0.25">15 min</option>
          <option value="0.5">30 min</option>
          <option value="1" selected>1 hora</option>
          <option value="2">2 horas</option>
          <option value="4">4 horas</option>
          <option value="6">6 horas</option>
          <option value="8">8 horas</option>
          <option value="10">10 horas</option>
          <option value="12">12 horas</option>
        </select>
      </label>
      <button id="backBtn" type="button">← Voltar 1 janela</button>
      <button id="fwdBtn" type="button">Avançar 1 janela →</button>
      <label>Ir para ciclo:
        <input id="gotoCycle" type="number" min="1" step="1" style="width: 90px" placeholder="ex: 7" />
      </label>
      <button id="gotoCycleBtn" type="button">Ir</button>
      <label style="display:inline-flex; gap: 8px; align-items:center;">
        <input id="toggleIncomplete" type="checkbox" checked />
        mostrar incompletos
      </label>
    </div>
    <p class="hint">Dica: a janela visível é proporcional à largura da sua tela. Use trackpad/scroll horizontal para navegar. Passe o mouse sobre um bloco para ver detalhes.</p>

    <div class="legend">
      <span class="legend-item"><span class="swatch complete"></span>carregamento completo (com basculamento)</span>
      <span class="legend-item"><span class="swatch incomplete"></span>carregamento incompleto (sem basculamento)</span>
    </div>

    <div class="topbar">
      <div>Arquivo: <code>carregamentos_detectados.csv</code></div>
      <div id="visibleRange"></div>
    </div>

    <div class="timeline">
      <div class="scroll" id="scroll">
        <div class="svg-wrap">
          <svg id="svg" xmlns="http://www.w3.org/2000/svg"></svg>
        </div>
      </div>
    </div>

    <div class="tooltip" id="tooltip"></div>

    <script>
      const LOADS = {loads_data};

      const svg = document.getElementById("svg");
      const scroll = document.getElementById("scroll");
      const tooltip = document.getElementById("tooltip");
      const visibleRange = document.getElementById("visibleRange");
      const windowHoursEl = document.getElementById("windowHours");
      const backBtn = document.getElementById("backBtn");
      const fwdBtn = document.getElementById("fwdBtn");
      const gotoCycleEl = document.getElementById("gotoCycle");
      const gotoCycleBtn = document.getElementById("gotoCycleBtn");
      const toggleIncompleteEl = document.getElementById("toggleIncomplete");

      function msToHhmm(ms) {{
        const d = new Date(ms);
        const hh = String(d.getHours()).padStart(2, "0");
        const mm = String(d.getMinutes()).padStart(2, "0");
        return `${{hh}}:${{mm}}`;
      }}

      function msToPtBr(ms) {{
        const d = new Date(ms);
        const fmt = new Intl.DateTimeFormat("pt-BR", {{
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }});
        return fmt.format(d);
      }}

      function niceTickStepMs(pxPerMs) {{
        const targetPx = 110;
        const raw = targetPx / pxPerMs;
        const steps = [
          60_000, 2*60_000, 5*60_000, 10*60_000, 15*60_000, 30*60_000,
          60*60_000, 2*60*60_000, 4*60*60_000,
        ];
        for (const s of steps) {{
          if (s >= raw) return s;
        }}
        return steps[steps.length - 1];
      }}

      function clearSvg() {{
        while (svg.firstChild) svg.removeChild(svg.firstChild);
      }}

      function createSvgEl(name) {{
        return document.createElementNS("http://www.w3.org/2000/svg", name);
      }}

      function render() {{
        if (!LOADS.length) return;

        const showIncomplete = toggleIncompleteEl.checked;
        const filtered = showIncomplete 
          ? LOADS 
          : LOADS.filter(l => l.is_complete === 1);

        const minStart = Math.min(...LOADS.map(l => l.start_ms));
        const maxEnd = Math.max(...LOADS.map(l => l.end_ms));

        const viewHours = parseFloat(windowHoursEl.value || "1");
        const viewMs = viewHours * 3600 * 1000;

        const viewWidth = Math.max(1, scroll.clientWidth - 2);
        const pxPerMs = viewWidth / viewMs;
        const totalWidth = Math.ceil((maxEnd - minStart) * pxPerMs) + 1;

        const axisH = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--axis-height"));
        const laneH = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--lane-height"));

        const height = Math.ceil(axisH + laneH + 20);

        const currentScrollRatio = (scroll.scrollLeft || 0) / Math.max(1, (svg.viewBox?.baseVal?.width || totalWidth));

        clearSvg();
        svg.setAttribute("width", String(totalWidth));
        svg.setAttribute("height", String(height));
        svg.setAttribute("viewBox", `0 0 ${{totalWidth}} ${{height}}`);

        // Gradients (must be created before use)
        const defs = createSvgEl("defs");
        const gradComplete = createSvgEl("linearGradient");
        gradComplete.setAttribute("id", "grad-complete");
        gradComplete.setAttribute("x1", "0%");
        gradComplete.setAttribute("y1", "0%");
        gradComplete.setAttribute("x2", "100%");
        gradComplete.setAttribute("y2", "100%");
        const stop1 = createSvgEl("stop");
        stop1.setAttribute("offset", "0%");
        stop1.setAttribute("stop-color", "rgba(34, 139, 34, 0.7)");
        const stop2 = createSvgEl("stop");
        stop2.setAttribute("offset", "100%");
        stop2.setAttribute("stop-color", "rgba(50, 205, 50, 0.7)");
        gradComplete.appendChild(stop1);
        gradComplete.appendChild(stop2);
        defs.appendChild(gradComplete);

        const gradIncomplete = createSvgEl("linearGradient");
        gradIncomplete.setAttribute("id", "grad-incomplete");
        gradIncomplete.setAttribute("x1", "0%");
        gradIncomplete.setAttribute("y1", "0%");
        gradIncomplete.setAttribute("x2", "100%");
        gradIncomplete.setAttribute("y2", "100%");
        const stop3 = createSvgEl("stop");
        stop3.setAttribute("offset", "0%");
        stop3.setAttribute("stop-color", "rgba(220, 20, 60, 0.6)");
        const stop4 = createSvgEl("stop");
        stop4.setAttribute("offset", "100%");
        stop4.setAttribute("stop-color", "rgba(255, 99, 71, 0.6)");
        gradIncomplete.appendChild(stop3);
        gradIncomplete.appendChild(stop4);
        defs.appendChild(gradIncomplete);
        svg.appendChild(defs);

        // Background
        const bg = createSvgEl("rect");
        bg.setAttribute("x", "0");
        bg.setAttribute("y", "0");
        bg.setAttribute("width", String(totalWidth));
        bg.setAttribute("height", String(height));
        bg.setAttribute("fill", "#FFFFFF");
        svg.appendChild(bg);

        // Grid + axis
        const tickStep = niceTickStepMs(pxPerMs);
        const firstTick = Math.floor(minStart / tickStep) * tickStep;

        for (let t = firstTick; t <= maxEnd; t += tickStep) {{
          const x = (t - minStart) * pxPerMs;
          const line = createSvgEl("line");
          line.setAttribute("x1", String(x));
          line.setAttribute("x2", String(x));
          line.setAttribute("y1", "0");
          line.setAttribute("y2", String(height));
          line.setAttribute("stroke", "#EDEDED");
          line.setAttribute("stroke-width", "1");
          svg.appendChild(line);

          const txt = createSvgEl("text");
          txt.textContent = msToHhmm(t);
          txt.setAttribute("x", String(x + 4));
          txt.setAttribute("y", String(24));
          txt.setAttribute("font-size", "12");
          txt.setAttribute("fill", "#333");
          txt.setAttribute("font-family", "inherit");
          svg.appendChild(txt);
        }}

        // Lane band
        const band = createSvgEl("rect");
        band.setAttribute("x", "0");
        band.setAttribute("y", String(axisH));
        band.setAttribute("width", String(totalWidth));
        band.setAttribute("height", String(laneH + 12));
        band.setAttribute("fill", "#FBFCFD");
        svg.appendChild(band);

        // Loads
        for (const load of filtered) {{
          const x = Math.max(0, (load.start_ms - minStart) * pxPerMs);
          const w = Math.max(1, (load.end_ms - load.start_ms) * pxPerMs);
          const y = axisH + 8;
          const h = laneH;

          const rect = createSvgEl("rect");
          rect.setAttribute("x", String(x));
          rect.setAttribute("y", String(y));
          rect.setAttribute("width", String(w));
          rect.setAttribute("height", String(h));
          rect.setAttribute("rx", "8");
          rect.setAttribute("ry", "8");
          
          if (load.is_complete === 1) {{
            rect.setAttribute("fill", "url(#grad-complete)");
            rect.setAttribute("stroke", "#228B22");
            rect.setAttribute("stroke-width", "2");
          }} else {{
            rect.setAttribute("fill", "url(#grad-incomplete)");
            rect.setAttribute("stroke", "#DC143C");
            rect.setAttribute("stroke-width", "2");
            rect.setAttribute("stroke-dasharray", "4,2");
          }}

          rect.style.cursor = "pointer";

          // Native tooltip
          const title = createSvgEl("title");
          const status = load.is_complete === 1 ? "completo" : "incompleto";
          title.textContent = `Carregamento ${{status}} (ciclo: ${{load.cycle_id ?? "-"}}) • ${{load.duration_sec}}s`;
          rect.appendChild(title);

          rect.addEventListener("mousemove", (ev) => {{
            tooltip.style.display = "block";
            tooltip.style.left = `${{ev.clientX + 12}}px`;
            tooltip.style.top = `${{ev.clientY + 12}}px`;
            const status = load.is_complete === 1 ? "completo" : "incompleto";
            const statusClass = load.is_complete === 1 ? "complete" : "incomplete";
            tooltip.innerHTML = `
              <div><span class="k">evento:</span> <b>carregamento</b></div>
              <div><span class="k">status:</span> <span class="status ${{statusClass}}">${{status}}</span></div>
              <div><span class="k">ciclo:</span> <b>${{load.cycle_id ?? "-"}}</b></div>
              <div><span class="k">início:</span> ${{msToPtBr(load.start_ms)}}</div>
              <div><span class="k">fim:</span> ${{msToPtBr(load.end_ms)}}</div>
              <div><span class="k">duração:</span> ${{load.duration_sec}}s</div>
              <div><span class="k">lat/lon:</span> ${{load.lat.toFixed(6)}}, ${{load.lon.toFixed(6)}}</div>
              <div><span class="k">cluster:</span> ${{load.cluster_key}}</div>
            `;
          }});
          rect.addEventListener("mouseleave", () => {{
            tooltip.style.display = "none";
          }});

          svg.appendChild(rect);
        }}

        // Keep scroll roughly where it was
        const desiredLeft = Math.floor(currentScrollRatio * totalWidth);
        scroll.scrollLeft = Math.max(0, Math.min(totalWidth - viewWidth, desiredLeft));

        function updateVisibleRange() {{
          const leftMs = minStart + (scroll.scrollLeft / pxPerMs);
          const rightMs = leftMs + viewMs;
          visibleRange.textContent = `visível: ${{msToPtBr(leftMs)}} → ${{msToPtBr(rightMs)}}`;
        }}
        scroll.onscroll = updateVisibleRange;
        updateVisibleRange();

        backBtn.onclick = () => {{
          scroll.scrollLeft = Math.max(0, scroll.scrollLeft - viewWidth);
        }};
        fwdBtn.onclick = () => {{
          scroll.scrollLeft = Math.min(totalWidth, scroll.scrollLeft + viewWidth);
        }};

        gotoCycleBtn.onclick = () => {{
          const cid = parseInt(gotoCycleEl.value || "", 10);
          if (!Number.isFinite(cid)) return;
          const first = filtered.find(load => load.cycle_id === cid);
          if (!first) return;
          const x = (first.start_ms - minStart) * pxPerMs;
          scroll.scrollLeft = Math.max(0, x - 30);
        }};
      }}

      let resizeTimer = null;
      window.addEventListener("resize", () => {{
        if (resizeTimer) clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => render(), 120);
      }});
      windowHoursEl.addEventListener("change", () => render());
      toggleIncompleteEl.addEventListener("change", () => render());

      render();
    </script>
  </body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera HTML com linha do tempo de todos os carregamentos detectados"
    )
    parser.add_argument(
        "--loads",
        default="carregamentos_detectados.csv",
        help="CSV de carregamentos (padrão: carregamentos_detectados.csv)",
    )
    parser.add_argument(
        "--out",
        default="plots/loads_timeline.html",
        help="HTML de saída (padrão: plots/loads_timeline.html)",
    )
    args = parser.parse_args()

    loads_path = Path(args.loads)
    out_path = Path(args.out)

    if not loads_path.exists():
        raise SystemExit(f"Arquivo não encontrado: {loads_path}")

    loads: list[LoadEvent] = []
    with loads_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            start_raw = (row.get("start") or "").strip()
            end_raw = (row.get("end") or "").strip()
            if not start_raw or not end_raw:
                continue
            try:
                start = parse_iso(start_raw)
                end = parse_iso(end_raw)
            except Exception:
                continue

            cycle_id = try_int(row.get("cycle_id", ""))
            is_complete = (row.get("is_complete", "0") or "0").strip() == "1"

            loads.append(
                LoadEvent(
                    idx=idx,
                    cycle_id=cycle_id,
                    start=start,
                    end=end,
                    duration_sec=int((row.get("duration_sec") or "0").strip() or "0"),
                    lat=try_float(row.get("latitude", "")),
                    lon=try_float(row.get("longitude", "")),
                    cluster_key=(row.get("cluster_key") or "").strip(),
                    is_complete=is_complete,
                )
            )

    loads.sort(key=lambda l: (l.start_ms, l.end_ms))

    total_loads = len(loads)
    complete_loads = sum(1 for l in loads if l.is_complete)
    incomplete_loads = total_loads - complete_loads

    payload = [
        {
            "idx": l.idx,
            "cycle_id": l.cycle_id,
            "start_ms": l.start_ms,
            "end_ms": l.end_ms,
            "duration_sec": l.duration_sec,
            "lat": l.lat,
            "lon": l.lon,
            "cluster_key": l.cluster_key,
            "is_complete": 1 if l.is_complete else 0,
        }
        for l in loads
    ]

    html = HTML_TEMPLATE.format(
        total_loads=total_loads,
        complete_loads=complete_loads,
        incomplete_loads=incomplete_loads,
        loads_data=json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Gerado: {out_path}")
    print(f"  Total: {total_loads} carregamentos")
    print(f"  Completos: {complete_loads}")
    print(f"  Incompletos: {incomplete_loads}")

    return 0


if __name__ == "__main__":
    exit(main())

