#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
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
    <title>Linha do tempo — eventos</title>
    <style>
      :root {{
        --lane-height: 34px;
        --lane-gap: 10px;
        --axis-height: 34px;
      }}

      body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        margin: 18px;
        color: #111;
      }}

      h1 {{
        font-size: 18px;
        margin: 0 0 10px 0;
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
        width: 22px;
        height: 12px;
        border: 1px solid #1113;
        border-radius: 3px;
        background-size: 12px 12px;
      }}
      .swatch.load {{
        background-image: repeating-linear-gradient(45deg, rgba(210,0,0,.55), rgba(210,0,0,.55) 2px, rgba(255,0,0,.10) 2px, rgba(255,0,0,.10) 8px);
      }}
      .swatch.dump {{
        background-image: repeating-linear-gradient(-45deg, rgba(0,128,0,.55), rgba(0,128,0,.55) 2px, rgba(0,255,0,.10) 2px, rgba(0,255,0,.10) 8px);
      }}
      .swatch.wait {{
        background-image: repeating-linear-gradient(0deg, rgba(179,143,0,.55), rgba(179,143,0,.55) 2px, rgba(255,212,0,.14) 2px, rgba(255,212,0,.14) 8px);
      }}

      .timeline {{
        border: 1px solid #E6E6E6;
        border-radius: 12px;
        overflow: hidden;
      }}

      .scroll {{
        overflow-x: auto;
        overflow-y: hidden;
        background: white;
      }}

      .svg-wrap {{
        position: relative;
        height: calc(var(--axis-height) + 2 * var(--lane-height) + var(--lane-gap) + 18px);
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
        background: rgba(20, 20, 20, 0.92);
        color: #fff;
        padding: 8px 10px;
        border-radius: 10px;
        font-size: 12px;
        line-height: 1.35;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
      }}
      .tooltip .k {{
        color: rgba(255,255,255,0.75);
      }}
    </style>
  </head>
  <body>
    <h1>Linha do tempo dos eventos (rolagem horizontal)</h1>
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
        <input id="toggleWait" type="checkbox" checked />
        mostrar aguardando
      </label>
    </div>
    <p class="hint">Dica: a janela visível é proporcional à largura da sua tela. Use trackpad/scroll horizontal para navegar. Passe o mouse sobre um bloco para ver detalhes.</p>

    <div class="legend">
      <span class="legend-item"><span class="swatch load"></span>carregamento</span>
      <span class="legend-item"><span class="swatch dump"></span>basculamento</span>
      <span class="legend-item"><span class="swatch wait"></span>aguardando</span>
    </div>

    <div class="topbar">
      <div>Arquivo de eventos: <code>{events_path}</code></div>
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
      const EVENTS = {events_json};

      const WAIT_KINDS = new Set(["espera_carregamento", "espera_basculamento"]);

      const PATTERN_BY_KIND = {{
        carregamento: {{ id: "pat-load", stroke: "#D00000", bg: "#FF0000" }},
        basculamento: {{ id: "pat-dump", stroke: "#006E1A", bg: "#00FF00" }},
        aguardando: {{ id: "pat-wait", stroke: "#B38F00", bg: "#FFD400" }},
      }};

      const svg = document.getElementById("svg");
      const scroll = document.getElementById("scroll");
      const tooltip = document.getElementById("tooltip");
      const visibleRange = document.getElementById("visibleRange");
      const windowHoursEl = document.getElementById("windowHours");
      const backBtn = document.getElementById("backBtn");
      const fwdBtn = document.getElementById("fwdBtn");
      const gotoCycleEl = document.getElementById("gotoCycle");
      const gotoCycleBtn = document.getElementById("gotoCycleBtn");
      const toggleWaitEl = document.getElementById("toggleWait");

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
        // Choose a step so ticks are ~80-140px apart.
        const targetPx = 110;
        const raw = targetPx / pxPerMs; // ms
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

      function addPatterns(defs) {{
        const makePat = (id, bg, bgOpacity, stroke, strokeOpacity, mode) => {{
          const pat = createSvgEl("pattern");
          pat.setAttribute("id", id);
          pat.setAttribute("patternUnits", "userSpaceOnUse");
          pat.setAttribute("width", "12");
          pat.setAttribute("height", "12");
          const rect = createSvgEl("rect");
          rect.setAttribute("width", "12");
          rect.setAttribute("height", "12");
          rect.setAttribute("fill", bg);
          rect.setAttribute("fill-opacity", String(bgOpacity));
          pat.appendChild(rect);

          const path = createSvgEl("path");
          if (mode === "diag45") {{
            path.setAttribute("d", "M-3,9 L9,-3 M0,12 L12,0 M3,15 L15,3");
          }} else if (mode === "diag-45") {{
            path.setAttribute("d", "M-3,3 L3,-3 M0,12 L12,0 M9,15 L15,9 M-3,15 L15,-3");
          }} else if (mode === "horiz") {{
            path.setAttribute("d", "M0,2 L12,2 M0,6 L12,6 M0,10 L12,10");
          }} else if (mode === "vert") {{
            path.setAttribute("d", "M2,0 L2,12 M6,0 L6,12 M10,0 L10,12");
          }} else {{
            path.setAttribute("d", "M0,0 L12,12");
          }}
          path.setAttribute("stroke", stroke);
          path.setAttribute("stroke-width", "2");
          path.setAttribute("stroke-opacity", String(strokeOpacity));
          pat.appendChild(path);
          defs.appendChild(pat);
        }};

        makePat("pat-load", "#FF0000", 0.10, "#D00000", 0.55, "diag45");
        makePat("pat-dump", "#00FF00", 0.08, "#006E1A", 0.55, "diag-45");
        makePat("pat-wait", "#FFD400", 0.14, "#B38F00", 0.55, "horiz");
      }}

      function displayKind(rawKind) {{
        return WAIT_KINDS.has(rawKind) ? "aguardando" : rawKind;
      }}

      function render() {{
        if (!EVENTS.length) return;

        const showWait = toggleWaitEl.checked;
        const visibleKinds = new Set(["carregamento", "basculamento", "espera_carregamento", "espera_basculamento"]);
        if (!showWait) {{
          visibleKinds.delete("espera_carregamento");
          visibleKinds.delete("espera_basculamento");
        }}

        // Mantém o eixo de tempo fixo (mesmo se esconder esperas).
        const minStart = Math.min(...EVENTS.map(e => e.start_ms));
        const maxEnd = Math.max(...EVENTS.map(e => e.end_ms));

        const filtered = EVENTS.filter(e => visibleKinds.has(e.kind));

        const viewHours = parseFloat(windowHoursEl.value || "1");
        const viewMs = viewHours * 3600 * 1000;

        const viewWidth = Math.max(1, scroll.clientWidth - 2);
        const pxPerMs = viewWidth / viewMs;
        const totalWidth = Math.ceil((maxEnd - minStart) * pxPerMs) + 1;

        const axisH = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--axis-height"));
        const laneH = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--lane-height"));
        const laneGap = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--lane-gap"));

        const height = Math.ceil(axisH + 2 * laneH + laneGap + 18);

        const currentScrollRatio = (scroll.scrollLeft || 0) / Math.max(1, (svg.viewBox?.baseVal?.width || totalWidth));

        clearSvg();
        svg.setAttribute("width", String(totalWidth));
        svg.setAttribute("height", String(height));
        svg.setAttribute("viewBox", `0 0 ${{totalWidth}} ${{height}}`);

        const defs = createSvgEl("defs");
        addPatterns(defs);
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
          txt.setAttribute("y", String(22));
          txt.setAttribute("font-size", "12");
          txt.setAttribute("fill", "#333");
          txt.setAttribute("font-family", "inherit");
          svg.appendChild(txt);
        }}

        // Bands: operações (carregamento/basculamento) + aguardando
        const bandOps = createSvgEl("rect");
        bandOps.setAttribute("x", "0");
        bandOps.setAttribute("y", String(axisH));
        bandOps.setAttribute("width", String(totalWidth));
        bandOps.setAttribute("height", String(laneH + 12));
        bandOps.setAttribute("fill", "#FBFCFD");
        svg.appendChild(bandOps);

        const bandWait = createSvgEl("rect");
        bandWait.setAttribute("x", "0");
        bandWait.setAttribute("y", String(axisH + laneH + laneGap));
        bandWait.setAttribute("width", String(totalWidth));
        bandWait.setAttribute("height", String(laneH + 12));
        bandWait.setAttribute("fill", "#FFFFFF");
        svg.appendChild(bandWait);

        // Events
        for (const e of filtered) {{
          const dk = displayKind(e.kind);
          const lane = dk === "aguardando" ? 1 : 0;
          const x = Math.max(0, (e.start_ms - minStart) * pxPerMs);
          const w = Math.max(1, (e.end_ms - e.start_ms) * pxPerMs);
          const y = axisH + 6 + lane * (laneH + laneGap);
          const h = laneH;

          const rect = createSvgEl("rect");
          rect.setAttribute("x", String(x));
          rect.setAttribute("y", String(y));
          rect.setAttribute("width", String(w));
          rect.setAttribute("height", String(h));
          rect.setAttribute("rx", "6");
          rect.setAttribute("ry", "6");
          rect.setAttribute("fill", `url(#${{PATTERN_BY_KIND[dk].id}})`);
          rect.setAttribute("stroke", PATTERN_BY_KIND[dk].stroke);
          rect.setAttribute("stroke-opacity", "0.55");
          rect.setAttribute("stroke-width", "1");
          rect.style.cursor = "default";

          const kindLabel = dk;

          // Native tooltip (fallback).
          const title = createSvgEl("title");
          title.textContent = `${{kindLabel}} • ciclo: ${{e.cycle_id ?? "-"}} • ${{e.duration_sec}}s`;
          rect.appendChild(title);

          rect.addEventListener("mousemove", (ev) => {{
            tooltip.style.display = "block";
            tooltip.style.left = `${{ev.clientX + 12}}px`;
            tooltip.style.top = `${{ev.clientY + 12}}px`;
            tooltip.innerHTML = `
              <div><span class=\"k\">evento:</span> <b>${{kindLabel}}</b></div>
              <div><span class=\"k\">ciclo:</span> <b>${{e.cycle_id ?? "-"}}</b></div>
              <div><span class=\"k\">início:</span> ${{msToPtBr(e.start_ms)}}</div>
              <div><span class=\"k\">fim:</span> ${{msToPtBr(e.end_ms)}}</div>
              <div><span class=\"k\">duração:</span> ${{e.duration_sec}}s</div>
              <div><span class=\"k\">lat/lon:</span> ${{e.lat.toFixed(6)}}, ${{e.lon.toFixed(6)}}</div>
              <div><span class=\"k\">cluster:</span> ${{e.cluster_key}}</div>
            `;\n          }});
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
          const cid = parseInt(gotoCycleEl.value || \"\", 10);\n          if (!Number.isFinite(cid)) return;\n          const first = filtered.find(ev => ev.cycle_id === cid);\n          if (!first) return;\n          const x = (first.start_ms - minStart) * pxPerMs;\n          scroll.scrollLeft = Math.max(0, x - 30);\n        }};\n      }}\n\n      let resizeTimer = null;\n      window.addEventListener(\"resize\", () => {{\n        if (resizeTimer) clearTimeout(resizeTimer);\n        resizeTimer = setTimeout(() => render(), 120);\n      }});\n      windowHoursEl.addEventListener(\"change\", () => render());\n      toggleWaitEl.addEventListener(\"change\", () => render());\n\n      render();\n    </script>\n  </body>\n</html>\n"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera um HTML interativo (scroll horizontal) com a linha do tempo dos eventos.")
    parser.add_argument("--events", default="events_detected.csv", help="CSV de eventos detectados (padrão: events_detected.csv)")
    parser.add_argument("--out", default="plots/timeline_viewer.html", help="HTML de saída (padrão: plots/timeline_viewer.html)")
    args = parser.parse_args()

    events_path = Path(args.events)
    if not events_path.exists():
        raise SystemExit(f"Arquivo não encontrado: {events_path}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    events: list[Event] = []
    with events_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            kind = (row.get("event") or "").strip()
            if not kind:
                continue
            start_raw = (row.get("start") or "").strip()
            end_raw = (row.get("end") or "").strip()
            if not start_raw or not end_raw:
                continue
            try:
                start = parse_iso(start_raw)
                end = parse_iso(end_raw)
            except Exception:
                continue
            duration_sec = int((row.get("duration_sec") or "0").strip() or "0")
            events.append(
                Event(
                    idx=idx,
                    cycle_id=try_int(row.get("cycle_id", "")),
                    kind=kind,
                    start=start,
                    end=end,
                    duration_sec=duration_sec,
                    lat=try_float(row.get("latitude", "")),
                    lon=try_float(row.get("longitude", "")),
                    cluster_key=(row.get("cluster_key") or "").strip(),
                )
            )

    events.sort(key=lambda e: (e.start_ms, e.end_ms))

    payload = [
        {
            "idx": e.idx,
            "cycle_id": e.cycle_id,
            "kind": e.kind,
            "start_ms": e.start_ms,
            "end_ms": e.end_ms,
            "duration_sec": e.duration_sec,
            "lat": e.lat,
            "lon": e.lon,
            "cluster_key": e.cluster_key,
        }
        for e in events
    ]

    html = HTML_TEMPLATE.format(
        events_path=str(events_path),
        events_json=json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
    )
    out_path.write_text(html, encoding="utf-8")
    print(f"Gerado: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
