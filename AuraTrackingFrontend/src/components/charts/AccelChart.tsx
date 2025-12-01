/**
 * AccelChart Component
 * ============================================================
 * Real-time acceleration chart using uPlot
 * Shows magnitude and/or individual axes
 */

import { 
  createSignal, 
  createEffect, 
  onMount, 
  onCleanup,
  Show 
} from "solid-js";

interface AccelData {
  timestamp: number;
  accelX: number;
  accelY: number;
  accelZ: number;
  magnitude: number;
}

interface AccelChartProps {
  data?: AccelData[];
  title?: string;
  height?: number;
  showAxes?: boolean;
  showMagnitude?: boolean;
  impactThreshold?: number;
  class?: string;
}

const GRAVITY = 9.81;
const IMPACT_THRESHOLD = 15;

export default function AccelChart(props: AccelChartProps) {
  let containerRef: HTMLDivElement | undefined;
  let chart: any = null;
  
  const [isLoaded, setIsLoaded] = createSignal(false);
  const [stats, setStats] = createSignal({
    current: 0,
    max: 0,
    impactCount: 0,
  });
  
  // Calculate statistics
  const calculateStats = (data: AccelData[]) => {
    if (data.length === 0) {
      return { current: 0, max: 0, impactCount: 0 };
    }
    
    const magnitudes = data.map(d => d.magnitude);
    const current = magnitudes[magnitudes.length - 1];
    const max = Math.max(...magnitudes);
    const threshold = props.impactThreshold || IMPACT_THRESHOLD;
    const impactCount = magnitudes.filter(m => m > threshold).length;
    
    return { current, max, impactCount };
  };
  
  onMount(async () => {
    if (typeof window === "undefined") return;
    
    try {
      const uPlot = (await import("uplot")).default;
      await import("uplot/dist/uPlot.min.css");
      
      if (!containerRef) return;
      
      const series: any[] = [{}];
      
      if (props.showMagnitude !== false) {
        series.push({
          label: "Magnitude (m/s²)",
          stroke: "#f59e0b",
          width: 2,
          fill: "rgba(245, 158, 11, 0.1)",
        });
      }
      
      if (props.showAxes) {
        series.push(
          {
            label: "X",
            stroke: "#ef4444",
            width: 1.5,
          },
          {
            label: "Y",
            stroke: "#22c55e",
            width: 1.5,
          },
          {
            label: "Z",
            stroke: "#3b82f6",
            width: 1.5,
          }
        );
      }
      
      const opts: any = {
        width: containerRef.clientWidth,
        height: props.height || 200,
        cursor: {
          show: true,
          x: true,
          y: true,
        },
        scales: {
          x: { time: true },
          y: { auto: true },
        },
        axes: [
          {
            stroke: "#71717a",
            grid: { stroke: "#27272a", width: 1 },
            ticks: { stroke: "#27272a", width: 1 },
          },
          {
            stroke: "#71717a",
            grid: { stroke: "#27272a", width: 1 },
            ticks: { stroke: "#27272a", width: 1 },
            values: (u: any, vals: number[]) => vals.map(v => v.toFixed(1)),
          },
        ],
        series,
      };
      
      const initialData = [[]];
      if (props.showMagnitude !== false) initialData.push([]);
      if (props.showAxes) {
        initialData.push([], [], []);
      }
      
      chart = new uPlot(opts, initialData, containerRef);
      setIsLoaded(true);
      
      // Handle resize
      const resizeObserver = new ResizeObserver(() => {
        if (chart && containerRef) {
          chart.setSize({
            width: containerRef.clientWidth,
            height: props.height || 200,
          });
        }
      });
      resizeObserver.observe(containerRef);
      
      onCleanup(() => {
        resizeObserver.disconnect();
      });
      
    } catch (err) {
      console.error("Failed to initialize chart:", err);
    }
  });
  
  // Update chart data
  createEffect(() => {
    if (!chart || !props.data) return;
    
    const data = props.data;
    
    // Update stats
    setStats(calculateStats(data));
    
    // Prepare data for uPlot
    const timestamps = data.map(d => d.timestamp / 1000);
    const chartData: number[][] = [timestamps];
    
    if (props.showMagnitude !== false) {
      chartData.push(data.map(d => d.magnitude));
    }
    
    if (props.showAxes) {
      chartData.push(
        data.map(d => d.accelX),
        data.map(d => d.accelY),
        data.map(d => d.accelZ)
      );
    }
    
    chart.setData(chartData);
  });
  
  // Cleanup
  onCleanup(() => {
    if (chart) {
      chart.destroy();
      chart = null;
    }
  });
  
  const getDeviationFromGravity = () => {
    const current = stats().current;
    return Math.abs(current - GRAVITY);
  };
  
  return (
    <div class={props.class}>
      {/* Header */}
      <div class="flex items-center justify-between mb-4">
        <h4 style={{ "font-weight": "600" }}>
          {props.title || "Aceleração"}
        </h4>
        <div class="flex gap-4 text-sm">
          <div>
            <span class="text-muted">Atual: </span>
            <span style={{ "font-weight": "600" }}>
              {stats().current.toFixed(2)} m/s²
            </span>
          </div>
          <div>
            <span class="text-muted">Máx: </span>
            <span style={{ 
              "font-weight": "600", 
              color: stats().max > IMPACT_THRESHOLD ? "var(--color-error)" : "inherit" 
            }}>
              {stats().max.toFixed(2)} m/s²
            </span>
          </div>
          <Show when={stats().impactCount > 0}>
            <div class="badge badge-error">
              {stats().impactCount} impactos
            </div>
          </Show>
        </div>
      </div>
      
      {/* Chart container */}
      <div 
        ref={containerRef}
        style={{
          width: "100%",
          height: `${props.height || 200}px`,
          background: "var(--color-bg-tertiary)",
          "border-radius": "var(--radius-lg)",
        }}
      >
        <Show when={!isLoaded()}>
          <div style={{
            height: "100%",
            display: "flex",
            "align-items": "center",
            "justify-content": "center",
          }}>
            <span class="text-muted">Carregando gráfico...</span>
          </div>
        </Show>
      </div>
      
      {/* Axes legend */}
      <Show when={props.showAxes}>
        <div class="flex justify-center gap-4 mt-2 text-xs">
          <div class="flex items-center gap-1">
            <span style={{ 
              width: "12px", 
              height: "3px", 
              background: "#ef4444",
              "border-radius": "2px"
            }} />
            <span class="text-muted">X</span>
          </div>
          <div class="flex items-center gap-1">
            <span style={{ 
              width: "12px", 
              height: "3px", 
              background: "#22c55e",
              "border-radius": "2px"
            }} />
            <span class="text-muted">Y</span>
          </div>
          <div class="flex items-center gap-1">
            <span style={{ 
              width: "12px", 
              height: "3px", 
              background: "#3b82f6",
              "border-radius": "2px"
            }} />
            <span class="text-muted">Z</span>
          </div>
        </div>
      </Show>
    </div>
  );
}


