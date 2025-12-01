/**
 * SpeedChart Component
 * ============================================================
 * Real-time speed chart using uPlot
 * Supports downsample for large datasets
 */

import { 
  createSignal, 
  createEffect, 
  onMount, 
  onCleanup,
  Show 
} from "solid-js";

interface SpeedChartProps {
  data?: { timestamp: number; speed: number }[];
  title?: string;
  height?: number;
  showAverage?: boolean;
  showMax?: boolean;
  class?: string;
}

const DOWNSAMPLE_THRESHOLD = 1000;

export default function SpeedChart(props: SpeedChartProps) {
  let containerRef: HTMLDivElement | undefined;
  let chart: any = null;
  
  const [isLoaded, setIsLoaded] = createSignal(false);
  const [stats, setStats] = createSignal({
    current: 0,
    average: 0,
    max: 0,
  });
  
  // Calculate statistics
  const calculateStats = (data: { speed: number }[]) => {
    if (data.length === 0) {
      return { current: 0, average: 0, max: 0 };
    }
    
    const speeds = data.map(d => d.speed * 3.6); // Convert to km/h
    const current = speeds[speeds.length - 1];
    const average = speeds.reduce((a, b) => a + b, 0) / speeds.length;
    const max = Math.max(...speeds);
    
    return { current, average, max };
  };
  
  // LTTB Downsample algorithm
  const downsample = (data: { timestamp: number; speed: number }[], threshold: number) => {
    if (data.length <= threshold) return data;
    
    const sampled: typeof data = [];
    const bucketSize = (data.length - 2) / (threshold - 2);
    
    let a = 0;
    sampled.push(data[a]); // First point
    
    for (let i = 0; i < threshold - 2; i++) {
      const bucketStart = Math.floor((i + 1) * bucketSize) + 1;
      const bucketEnd = Math.min(Math.floor((i + 2) * bucketSize) + 1, data.length - 1);
      
      // Calculate average point in next bucket
      let avgX = 0, avgY = 0;
      for (let j = bucketStart; j < bucketEnd; j++) {
        avgX += data[j].timestamp;
        avgY += data[j].speed;
      }
      avgX /= (bucketEnd - bucketStart);
      avgY /= (bucketEnd - bucketStart);
      
      // Find point with largest triangle area
      const rangeStart = Math.floor(i * bucketSize) + 1;
      const rangeEnd = bucketStart;
      
      let maxArea = -1;
      let maxIdx = rangeStart;
      
      for (let j = rangeStart; j < rangeEnd; j++) {
        const area = Math.abs(
          (data[a].timestamp - avgX) * (data[j].speed - data[a].speed) -
          (data[a].timestamp - data[j].timestamp) * (avgY - data[a].speed)
        );
        
        if (area > maxArea) {
          maxArea = area;
          maxIdx = j;
        }
      }
      
      sampled.push(data[maxIdx]);
      a = maxIdx;
    }
    
    sampled.push(data[data.length - 1]); // Last point
    return sampled;
  };
  
  onMount(async () => {
    if (typeof window === "undefined") return;
    
    try {
      const uPlot = (await import("uplot")).default;
      await import("uplot/dist/uPlot.min.css");
      
      if (!containerRef) return;
      
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
        series: [
          {},
          {
            label: "Velocidade (km/h)",
            stroke: "#f59e0b",
            width: 2,
            fill: "rgba(245, 158, 11, 0.1)",
          },
        ],
      };
      
      chart = new uPlot(opts, [[], []], containerRef);
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
    
    let data = props.data;
    
    // Downsample if necessary
    if (data.length > DOWNSAMPLE_THRESHOLD) {
      data = downsample(data, DOWNSAMPLE_THRESHOLD);
    }
    
    // Update stats
    setStats(calculateStats(data));
    
    // Prepare data for uPlot (timestamps in seconds, speed in km/h)
    const timestamps = data.map(d => d.timestamp / 1000);
    const speeds = data.map(d => d.speed * 3.6);
    
    chart.setData([timestamps, speeds]);
  });
  
  // Cleanup
  onCleanup(() => {
    if (chart) {
      chart.destroy();
      chart = null;
    }
  });
  
  return (
    <div class={props.class}>
      {/* Header */}
      <div class="flex items-center justify-between mb-4">
        <h4 style={{ "font-weight": "600" }}>
          {props.title || "Velocidade"}
        </h4>
        <div class="flex gap-4 text-sm">
          <div>
            <span class="text-muted">Atual: </span>
            <span style={{ 
              "font-weight": "600", 
              color: "var(--color-accent-primary)" 
            }}>
              {stats().current.toFixed(1)} km/h
            </span>
          </div>
          <Show when={props.showAverage !== false}>
            <div>
              <span class="text-muted">Média: </span>
              <span style={{ "font-weight": "600" }}>
                {stats().average.toFixed(1)} km/h
              </span>
            </div>
          </Show>
          <Show when={props.showMax !== false}>
            <div>
              <span class="text-muted">Máx: </span>
              <span style={{ 
                "font-weight": "600", 
                color: stats().max > 80 ? "var(--color-error)" : "inherit" 
              }}>
                {stats().max.toFixed(1)} km/h
              </span>
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
    </div>
  );
}

