/**
 * ReplayControls Component
 * ============================================================
 * UI controls for replay playback
 */

import { For, Show } from "solid-js";
import type { ReplayState } from "./ReplayEngine";

interface ReplayControlsProps {
  state: ReplayState;
  onPlay: () => void;
  onPause: () => void;
  onSeek: (progress: number) => void;
  onSpeedChange: (speed: number) => void;
  onSkipForward: () => void;
  onSkipBackward: () => void;
  class?: string;
}

const SPEED_OPTIONS = [0.5, 1, 2, 4, 8];

export default function ReplayControls(props: ReplayControlsProps) {
  const formatTime = (ms: number): string => {
    const totalSeconds = Math.floor(ms / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    
    return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
  };
  
  const handleSeek = (e: Event) => {
    const target = e.target as HTMLInputElement;
    props.onSeek(parseFloat(target.value));
  };
  
  const duration = () => props.state.endTime - props.state.startTime;
  
  return (
    <div class={`replay-controls ${props.class || ""}`}>
      {/* Timeline */}
      <div class="flex items-center gap-4 mb-4">
        <span style={{ 
          width: "80px",
          "font-family": "var(--font-sans)",
          "font-size": "var(--text-sm)"
        }}>
          {formatTime(props.state.currentTime - props.state.startTime)}
        </span>
        
        <div class="flex-1" style={{ position: "relative" }}>
          <input
            type="range"
            min="0"
            max="100"
            step="0.1"
            value={props.state.progress}
            onInput={handleSeek}
            style={{
              width: "100%",
              height: "8px",
              "accent-color": "var(--color-accent-primary)",
              cursor: "pointer",
            }}
          />
          
          {/* Progress indicator */}
          <div style={{
            position: "absolute",
            top: "-24px",
            left: `${props.state.progress}%`,
            transform: "translateX(-50%)",
            background: "var(--color-bg-secondary)",
            padding: "2px 8px",
            "border-radius": "var(--radius-md)",
            "font-size": "var(--text-xs)",
            "white-space": "nowrap",
            "pointer-events": "none",
            opacity: props.state.isPlaying ? 1 : 0,
            transition: "opacity 0.2s",
          }}>
            {props.state.progress.toFixed(1)}%
          </div>
        </div>
        
        <span style={{ 
          width: "80px",
          "text-align": "right",
          "font-family": "var(--font-sans)",
          "font-size": "var(--text-sm)",
          color: "var(--color-text-tertiary)"
        }}>
          {formatTime(duration())}
        </span>
      </div>
      
      {/* Controls */}
      <div class="flex items-center justify-center gap-4">
        {/* Skip backward */}
        <button 
          class="btn btn-ghost btn-icon"
          onClick={props.onSkipBackward}
          title="Voltar 10 segundos"
        >
          <SkipBackIcon />
        </button>
        
        {/* Play/Pause */}
        <button
          class="btn btn-primary"
          style={{
            width: "56px",
            height: "56px",
            "border-radius": "var(--radius-full)",
          }}
          onClick={() => props.state.isPlaying ? props.onPause() : props.onPlay()}
        >
          <Show when={props.state.isPlaying} fallback={<PlayIcon />}>
            <PauseIcon />
          </Show>
        </button>
        
        {/* Skip forward */}
        <button 
          class="btn btn-ghost btn-icon"
          onClick={props.onSkipForward}
          title="Avançar 10 segundos"
        >
          <SkipForwardIcon />
        </button>
        
        {/* Speed selector */}
        <div 
          class="flex items-center gap-1 ml-4"
          style={{
            background: "var(--color-bg-tertiary)",
            padding: "var(--space-1)",
            "border-radius": "var(--radius-lg)",
            border: "1px solid var(--color-border-primary)",
          }}
        >
          <For each={SPEED_OPTIONS}>
            {(speed) => (
              <button
                class={`btn ${props.state.playbackSpeed === speed ? "btn-primary" : "btn-ghost"}`}
                style={{ "min-width": "48px" }}
                onClick={() => props.onSpeedChange(speed)}
              >
                {speed}x
              </button>
            )}
          </For>
        </div>
      </div>
    </div>
  );
}

// Icons
function PlayIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  );
}

function PauseIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="4" width="4" height="16" />
      <rect x="14" y="4" width="4" height="16" />
    </svg>
  );
}

function SkipBackIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polygon points="19 20 9 12 19 4 19 20" />
      <line x1="5" y1="19" x2="5" y2="5" />
    </svg>
  );
}

function SkipForwardIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polygon points="5 4 15 12 5 20 5 4" />
      <line x1="19" y1="5" x2="19" y2="19" />
    </svg>
  );
}


