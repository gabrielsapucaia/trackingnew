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


def parse_time(value: str) -> datetime:
    # Formato: "2025-12-12 10:13:40-0300"
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S%z")


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


def read_events(events_path: Path) -> list[Event]:
    events: list[Event] = []
    with events_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            cycle_id = try_int(row.get("cycle_id", ""))
            kind = row.get("event", "").strip()
            start_str = row.get("start", "").strip()
            end_str = row.get("end", "").strip()
            lat = try_float(row.get("latitude", ""))
            lon = try_float(row.get("longitude", ""))
            cluster_key = row.get("cluster_key", "").strip()

            if not kind or not start_str or not end_str:
                continue

            try:
                start = parse_iso(start_str)
                end = parse_iso(end_str)
                duration_sec = int((end - start).total_seconds())
            except Exception:
                continue

            if not math.isfinite(lat) or not math.isfinite(lon):
                continue

            events.append(
                Event(
                    idx=idx,
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


def read_telemetry(input_path: Path) -> tuple[list[int], list[float], list[float]]:
    times: list[int] = []
    speed: list[float] = []
    vibration: list[float] = []

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t = parse_time(row.get("time", ""))
            except Exception:
                continue
            times.append(int(t.timestamp() * 1000))  # ms
            speed.append(try_float(row.get("speed_kmh", "")))
            vibration.append(try_float(row.get("linear_accel_magnitude", "")))

    return times, speed, vibration


HTML_TEMPLATE = """<!doctype html>
<html lang="pt-br">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Gráficos de Velocidade e Vibração</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
      body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        margin: 18px;
        color: #111;
        background: #fafafa;
      }}

      h1 {{
        font-size: 20px;
        margin: 0 0 20px 0;
        color: #222;
      }}

      .toolbar {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px 14px;
        align-items: center;
        margin: 0 0 20px 0;
        padding: 12px;
        background: white;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      }}

      .toolbar label {{
        font-size: 13px;
        color: #222;
      }}

      .toolbar select, .toolbar input {{
        font-size: 13px;
        padding: 6px 8px;
        border: 1px solid #D0D7DE;
        border-radius: 6px;
        background: white;
      }}

      .toolbar button {{
        font-size: 13px;
        padding: 6px 12px;
        border: 1px solid #D0D7DE;
        border-radius: 6px;
        background: #F6F8FA;
        cursor: pointer;
      }}

      .toolbar button:hover {{
        background: #EEF1F4;
      }}

      .chart-container {{
        background: white;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 20px;
        padding: 10px;
      }}

      .chart-title {{
        font-size: 16px;
        font-weight: 600;
        margin: 0 0 10px 10px;
        color: #333;
      }}

      .legend {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px 20px;
        font-size: 12px;
        color: #222;
        margin: 0 0 15px 0;
        padding: 12px;
        background: white;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      }}

      .legend-item {{
        display: inline-flex;
        gap: 8px;
        align-items: center;
      }}

      .swatch {{
        width: 24px;
        height: 16px;
        border: 1px solid rgba(0,0,0,0.2);
        border-radius: 4px;
        background-size: 8px 8px;
      }}

      .swatch.carregamento {{
        background-color: rgba(255, 182, 193, 0.4);
        background-image: repeating-linear-gradient(
          45deg,
          rgba(220, 20, 60, 0.3),
          rgba(220, 20, 60, 0.3) 2px,
          transparent 2px,
          transparent 8px
        );
      }}

      .swatch.basculamento {{
        background-color: rgba(144, 238, 144, 0.4);
        background-image: repeating-linear-gradient(
          -45deg,
          rgba(34, 139, 34, 0.3),
          rgba(34, 139, 34, 0.3) 2px,
          transparent 2px,
          transparent 8px
        );
      }}

      .swatch.aguardando {{
        background-color: rgba(255, 255, 153, 0.4);
        background-image: repeating-linear-gradient(
          0deg,
          rgba(255, 215, 0, 0.3),
          rgba(255, 215, 0, 0.3) 2px,
          transparent 2px,
          transparent 8px
        );
      }}

      .info {{
        font-size: 12px;
        color: #666;
        margin: 0 0 15px 0;
        padding: 12px;
        background: white;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      }}
    </style>
  </head>
  <body>
    <h1>Gráficos de Velocidade e Vibração</h1>

    <div class="info">
      Arquivo de dados: <code>input.csv</code> • Arquivo de eventos: <code>events_detected.csv</code>
    </div>

    <div class="legend">
      <span class="legend-item"><span class="swatch carregamento"></span>Carregamento</span>
      <span class="legend-item"><span class="swatch basculamento"></span>Basculamento</span>
      <span class="legend-item"><span class="swatch aguardando"></span>Aguardando (carregamento/basculamento)</span>
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
          <option value="12">12 horas</option>
          <option value="24">24 horas</option>
        </select>
      </label>
      <button id="backBtn" type="button">← Voltar</button>
      <button id="fwdBtn" type="button">Avançar →</button>
      <label>Ir para ciclo:
        <input id="gotoCycle" type="number" min="1" step="1" style="width: 80px" placeholder="ex: 7" />
      </label>
      <button id="gotoCycleBtn" type="button">Ir</button>
      <label style="display:inline-flex; gap: 8px; align-items:center;">
        <input id="toggleWait" type="checkbox" checked />
        mostrar esperas
      </label>
    </div>

    <div class="chart-container">
      <div class="chart-title">Velocidade (km/h)</div>
      <div id="speedChart" style="width:100%; height:400px;"></div>
    </div>

    <div class="chart-container">
      <div class="chart-title">Vibração (magnitude da aceleração linear)</div>
      <div id="vibrationChart" style="width:100%; height:400px;"></div>
    </div>

    <script>
      const TELEMETRY = {telemetry_data};
      const EVENTS = {events_data};

      const windowHoursEl = document.getElementById("windowHours");
      const backBtn = document.getElementById("backBtn");
      const fwdBtn = document.getElementById("fwdBtn");
      const gotoCycleEl = document.getElementById("gotoCycle");
      const gotoCycleBtn = document.getElementById("gotoCycleBtn");
      const toggleWaitEl = document.getElementById("toggleWait");

      let speedLayout = null;
      let vibrationLayout = null;
      let currentXRange = null;

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

      function getEventColor(kind) {{
        if (kind === "carregamento") {{
          return "rgba(255, 182, 193, 0.3)"; // rosa pastel (vermelho claro)
        }} else if (kind === "basculamento") {{
          return "rgba(144, 238, 144, 0.3)"; // verde claro pastel
        }} else {{
          return "rgba(255, 255, 153, 0.3)"; // amarelo pastel (aguardando)
        }}
      }}

      function getEventPattern(kind) {{
        if (kind === "carregamento") {{
          return "diagonal";
        }} else if (kind === "basculamento") {{
          return "diagonal-opposite";
        }} else {{
          return "horizontal";
        }}
      }}

      function createShapes(events, minTime, maxTime, showWait) {{
        const shapes = [];
        const filtered = showWait 
          ? events 
          : events.filter(e => !e.kind.startsWith("espera_"));

        for (const ev of filtered) {{
          const startMs = ev.start_ms;
          const endMs = ev.end_ms;
          
          if (endMs < minTime || startMs > maxTime) continue;

          const duration = endMs - startMs;
          const color = getEventColor(ev.kind);
          
          // Retângulo de fundo
          shapes.push({{
            type: "rect",
            xref: "x",
            yref: "paper",
            x0: startMs,
            x1: endMs,
            y0: 0,
            y1: 1,
            fillcolor: color,
            line: {{
              width: 0
            }},
            layer: "below"
          }});

          // Cria linhas de hachura baseado no tipo
          if (ev.kind === "carregamento") {{
            // Hachura diagonal 45° (vermelho)
            const step = duration / 20; // ~20 linhas
            for (let i = 0; i < 20; i++) {{
              const x = startMs + i * step;
              shapes.push({{
                type: "line",
                xref: "x",
                yref: "paper",
                x0: x,
                x1: x + step * 0.3,
                y0: 0,
                y1: 1,
                line: {{
                  color: "rgba(220, 20, 60, 0.4)",
                  width: 1.5
                }},
                layer: "below"
              }});
            }}
          }} else if (ev.kind === "basculamento") {{
            // Hachura diagonal -45° (verde)
            const step = duration / 20;
            for (let i = 0; i < 20; i++) {{
              const x = startMs + i * step;
              shapes.push({{
                type: "line",
                xref: "x",
                yref: "paper",
                x0: x,
                x1: x + step * 0.3,
                y0: 1,
                y1: 0,
                line: {{
                  color: "rgba(34, 139, 34, 0.4)",
                  width: 1.5
                }},
                layer: "below"
              }});
            }}
          }} else {{
            // Hachura horizontal (amarelo - aguardando)
            const step = duration / 15;
            for (let i = 0; i < 15; i++) {{
              const x = startMs + i * step;
              shapes.push({{
                type: "line",
                xref: "x",
                yref: "paper",
                x0: x,
                x1: x + step * 0.5,
                y0: 0.5,
                y1: 0.5,
                line: {{
                  color: "rgba(255, 215, 0, 0.5)",
                  width: 2
                }},
                layer: "below"
              }});
            }}
          }}
        }}
        return shapes;
      }}

      function createAnnotations(events, minTime, maxTime, showWait) {{
        const annotations = [];
        const filtered = showWait 
          ? events 
          : events.filter(e => !e.kind.startsWith("espera_"));

        for (const ev of filtered) {{
          const startMs = ev.start_ms;
          const endMs = ev.end_ms;
          
          if (endMs < minTime || startMs > maxTime) continue;

          const midMs = (startMs + endMs) / 2;
          annotations.push({{
            x: midMs,
            yref: "paper",
            y: 0.98,
            text: ev.kind.replace("espera_", "").replace("_", " "),
            showarrow: false,
            font: {{
              size: 10,
              color: "#333"
            }},
            bgcolor: "rgba(255, 255, 255, 0.7)",
            bordercolor: "#ccc",
            borderwidth: 1,
            borderpad: 2
          }});
        }}
        return annotations;
      }}

      function renderCharts() {{
        if (!TELEMETRY.times || TELEMETRY.times.length === 0) return;

        const showWait = toggleWaitEl.checked;
        const viewHours = parseFloat(windowHoursEl.value || "1");
        const viewMs = viewHours * 3600 * 1000;

        const minTime = Math.min(...TELEMETRY.times);
        const maxTime = Math.max(...TELEMETRY.times);

        // Se não há range atual, inicializa no início
        if (!currentXRange) {{
          currentXRange = [minTime, minTime + viewMs];
        }}

        // Cria shapes para os eventos
        const shapes = createShapes(EVENTS, minTime, maxTime, showWait);
        const annotations = createAnnotations(EVENTS, minTime, maxTime, showWait);

        // Layout comum
        const commonLayout = {{
          xaxis: {{
            type: "date",
            range: currentXRange,
            title: "Tempo",
            showgrid: true,
            gridcolor: "#e0e0e0"
          }},
          yaxis: {{
            showgrid: true,
            gridcolor: "#e0e0e0"
          }},
          shapes: shapes,
          annotations: annotations,
          hovermode: "x unified",
          margin: {{ l: 60, r: 20, t: 20, b: 50 }},
          plot_bgcolor: "#fafafa",
          paper_bgcolor: "white"
        }};

        // Gráfico de velocidade
        speedLayout = {{
          ...commonLayout,
          yaxis: {{
            ...commonLayout.yaxis,
            title: "Velocidade (km/h)"
          }},
          title: {{
            text: "",
            font: {{ size: 14 }}
          }}
        }};

        const speedData = [{{
          x: TELEMETRY.times,
          y: TELEMETRY.speed,
          type: "scatter",
          mode: "lines",
          name: "Velocidade",
          line: {{
            color: "#1f77b4",
            width: 1.5
          }},
          hovertemplate: "<b>%{{x|%d/%m/%Y %H:%M:%S}}</b><br>" +
                        "Velocidade: %{{y:.2f}} km/h<extra></extra>"
        }}];

        Plotly.newPlot("speedChart", speedData, speedLayout, {{
          responsive: true,
          displayModeBar: true,
          modeBarButtonsToRemove: ["pan2d", "lasso2d"]
        }});

        // Gráfico de vibração
        vibrationLayout = {{
          ...commonLayout,
          yaxis: {{
            ...commonLayout.yaxis,
            title: "Vibração (magnitude)"
          }},
          title: {{
            text: "",
            font: {{ size: 14 }}
          }}
        }};

        const vibrationData = [{{
          x: TELEMETRY.times,
          y: TELEMETRY.vibration,
          type: "scatter",
          mode: "lines",
          name: "Vibração",
          line: {{
            color: "#ff7f0e",
            width: 1.5
          }},
          hovertemplate: "<b>%{{x|%d/%m/%Y %H:%M:%S}}</b><br>" +
                        "Vibração: %{{y:.6f}}<extra></extra>"
        }}];

        Plotly.newPlot("vibrationChart", vibrationData, vibrationLayout, {{
          responsive: true,
          displayModeBar: true,
          modeBarButtonsToRemove: ["pan2d", "lasso2d"]
        }});

        // Sincroniza zoom/pan entre os gráficos
        document.getElementById("speedChart").on("plotly_relayout", (eventData) => {{
          if (eventData["xaxis.range[0]"] && eventData["xaxis.range[1]"]) {{
            currentXRange = [eventData["xaxis.range[0]"], eventData["xaxis.range[1]"]];
            Plotly.relayout("vibrationChart", {{
              "xaxis.range": currentXRange
            }});
          }}
        }});

        document.getElementById("vibrationChart").on("plotly_relayout", (eventData) => {{
          if (eventData["xaxis.range[0]"] && eventData["xaxis.range[1]"]) {{
            currentXRange = [eventData["xaxis.range[0]"], eventData["xaxis.range[1]"]];
            Plotly.relayout("speedChart", {{
              "xaxis.range": currentXRange
            }});
          }}
        }});
      }}

      function navigateWindow(direction) {{
        if (!currentXRange) return;
        const viewHours = parseFloat(windowHoursEl.value || "1");
        const viewMs = viewHours * 3600 * 1000;
        const step = viewMs * direction;
        
        currentXRange = [
          currentXRange[0] + step,
          currentXRange[1] + step
        ];

        Plotly.relayout("speedChart", {{ "xaxis.range": currentXRange }});
        Plotly.relayout("vibrationChart", {{ "xaxis.range": currentXRange }});
      }}

      function gotoCycle() {{
        const cid = parseInt(gotoCycleEl.value || "", 10);
        if (!Number.isFinite(cid)) return;
        
        const showWait = toggleWaitEl.checked;
        const filtered = showWait 
          ? EVENTS 
          : EVENTS.filter(e => !e.kind.startsWith("espera_"));
        
        const first = filtered.find(ev => ev.cycle_id === cid);
        if (!first) return;

        const viewHours = parseFloat(windowHoursEl.value || "1");
        const viewMs = viewHours * 3600 * 1000;
        const midMs = (first.start_ms + first.end_ms) / 2;
        
        currentXRange = [
          midMs - viewMs / 2,
          midMs + viewMs / 2
        ];

        Plotly.relayout("speedChart", {{ "xaxis.range": currentXRange }});
        Plotly.relayout("vibrationChart", {{ "xaxis.range": currentXRange }});
      }}

      // Event listeners
      windowHoursEl.addEventListener("change", () => {{
        if (!currentXRange) return;
        const viewHours = parseFloat(windowHoursEl.value || "1");
        const viewMs = viewHours * 3600 * 1000;
        const center = (currentXRange[0] + currentXRange[1]) / 2;
        currentXRange = [center - viewMs / 2, center + viewMs / 2];
        Plotly.relayout("speedChart", {{ "xaxis.range": currentXRange }});
        Plotly.relayout("vibrationChart", {{ "xaxis.range": currentXRange }});
      }});

      toggleWaitEl.addEventListener("change", () => {{
        renderCharts();
      }});

      backBtn.onclick = () => navigateWindow(-1);
      fwdBtn.onclick = () => navigateWindow(1);
      gotoCycleBtn.onclick = gotoCycle;

      // Inicializa
      renderCharts();
    </script>
  </body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera HTML com gráficos de velocidade e vibração com hachuras nos períodos de eventos"
    )
    parser.add_argument(
        "--input",
        default="input.csv",
        help="CSV de entrada com telemetria (padrão: input.csv)",
    )
    parser.add_argument(
        "--events",
        default="events_detected.csv",
        help="CSV de eventos (padrão: events_detected.csv)",
    )
    parser.add_argument(
        "--output",
        default="plots/velocity_vibration.html",
        help="Arquivo HTML de saída (padrão: plots/velocity_vibration.html)",
    )

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

    print(f"Lendo telemetria de {input_path}...")
    times, speed, vibration = read_telemetry(input_path)
    print(f"  {len(times)} pontos de dados")

    print(f"Lendo eventos de {events_path}...")
    events = read_events(events_path)
    print(f"  {len(events)} eventos")

    # Prepara dados para JSON
    telemetry_data = {
        "times": times,
        "speed": speed,
        "vibration": vibration,
    }

    events_data = [
        {
            "idx": e.idx,
            "cycle_id": e.cycle_id,
            "kind": e.kind,
            "start_ms": e.start_ms,
            "end_ms": e.end_ms,
            "duration_sec": e.duration_sec,
        }
        for e in events
    ]

    # Gera HTML
    html_content = HTML_TEMPLATE.format(
        telemetry_data=json.dumps(telemetry_data),
        events_data=json.dumps(events_data),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    print(f"HTML gerado: {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())

