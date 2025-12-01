// @refresh reload
import { Router } from "@solidjs/router";
import { FileRoutes } from "@solidjs/start/router";
import { Suspense } from "solid-js";
import { MetaProvider } from "@solidjs/meta";
import { MqttProvider } from "./providers/MqttProvider";
import { TelemetryProvider } from "./providers/TelemetryProvider";
import "./app.css";

export default function App() {
  return (
    <MetaProvider>
      <MqttProvider>
        <TelemetryProvider>
          <Router
            root={(props) => (
              <Suspense fallback={<LoadingScreen />}>
                {props.children}
              </Suspense>
            )}
          >
            <FileRoutes />
          </Router>
        </TelemetryProvider>
      </MqttProvider>
    </MetaProvider>
  );
}

function LoadingScreen() {
  return (
    <div
      style={{
        display: "flex",
        "align-items": "center",
        "justify-content": "center",
        height: "100vh",
        background: "var(--color-bg-primary, #0a0a0b)",
        color: "var(--color-text-primary, #fafafa)",
      }}
    >
      <div style={{ "text-align": "center" }}>
        <div
          style={{
            width: "48px",
            height: "48px",
            margin: "0 auto 16px",
            background: "linear-gradient(135deg, #f59e0b, #b45309)",
            "border-radius": "12px",
            display: "flex",
            "align-items": "center",
            "justify-content": "center",
            "font-weight": "700",
            "font-size": "24px",
            color: "#0a0a0b",
          }}
        >
          A
        </div>
        <p style={{ color: "#71717a" }}>Carregando...</p>
      </div>
    </div>
  );
}

