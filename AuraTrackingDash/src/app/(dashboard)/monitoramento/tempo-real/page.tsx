"use client"

import { ExternalLink, Loader2, MapPin, Radio, ShieldCheck } from "lucide-react"
import { useState } from "react"

// Mapa já pronto no projeto AuraTrackingFrontend (rota /map) rodando em 3001
const REALTIME_URL = "http://localhost:3001/map"

export default function MonitoramentoTempoRealPage() {
  const [isLoaded, setIsLoaded] = useState(false)

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Radio className="h-4 w-4 text-primary" />
          Monitoramento · Tempo real
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Telemetria em tempo real</h1>
          <p className="text-muted-foreground">
            Consuma a visualização em tempo real hospedada na instância frontend (porta 3002) sem sair do
            dashboard.
          </p>
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
              <MapPin className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold">Mapa dedicado</p>
              <p className="text-xs text-muted-foreground">Fonte: localhost:3001/map</p>
            </div>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-orange-500/10 text-orange-500">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold">Render isolado</p>
              <p className="text-xs text-muted-foreground">
                Conteúdo roda no app frontend, mantendo dependências de mapa separadas.
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div className="flex flex-col">
              <p className="text-sm font-semibold">Abrir em nova aba</p>
              <p className="text-xs text-muted-foreground">Use caso o sandbox bloqueie o iframe.</p>
            </div>
            <a
              href={REALTIME_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary hover:text-primary"
            >
              Abrir <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border bg-card shadow-sm">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div className="flex flex-col">
            <span className="text-sm font-semibold">Visualização embutida</span>
            <span className="text-xs text-muted-foreground">
              Você está vendo o mapa de tempo real servido pelo app frontend (porta 3001).
            </span>
          </div>
          <a
            href={REALTIME_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary hover:text-primary"
          >
            Abrir em nova aba <ExternalLink className="h-4 w-4" />
          </a>
        </div>

        <div className="relative bg-muted">
          {!isLoaded && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/70 backdrop-blur-sm">
              <div className="flex items-center gap-3 rounded-lg border bg-card px-4 py-3 shadow">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                <span className="text-sm text-muted-foreground">Carregando visualização em tempo real…</span>
              </div>
            </div>
          )}

          <iframe
            src={REALTIME_URL}
            title="Monitoramento em tempo real"
            className="h-[720px] w-full border-0"
            loading="lazy"
            allowFullScreen
            onLoad={() => setIsLoaded(true)}
          />
        </div>
      </div>
    </div>
  )
}
