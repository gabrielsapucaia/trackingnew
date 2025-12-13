"use client"

import { useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { createBrowserSupabaseClient } from "@/lib/supabase/clientAuth"
import { Button } from "@/components/ui/button"
import { AlertCircle, LogIn } from "lucide-react"

export default function LoginPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [mode, setMode] = useState<"login" | "signup">("login")
  const redirectTo = searchParams.get("redirectedFrom") || "/monitoramento"

  useEffect(() => {
    const err = searchParams.get("error")
    if (err === "domain") {
      setError("Apenas emails @auraminerals.com podem acessar.")
    }
  }, [searchParams])

  const handleSubmit = async () => {
    setError(null)
    setLoading(true)
    const supabase = createBrowserSupabaseClient()
    const normalizedEmail = email.trim().toLowerCase()
    if (!normalizedEmail.endsWith("@auraminerals.com")) {
      setError("Use um email @auraminerals.com")
      setLoading(false)
      return
    }

    if (mode === "login") {
      const { error } = await supabase.auth.signInWithPassword({
        email: normalizedEmail,
        password,
      })
      if (error) {
        setError(error.message)
        setLoading(false)
        return
      }
      router.push(redirectTo)
    } else {
      const { error } = await supabase.auth.signUp({
        email: normalizedEmail,
        password,
      })
      if (error) {
        setError(error.message)
        setLoading(false)
        return
      }
      router.push("/aguardando?reason=pending")
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-950 to-black text-white px-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/60 p-8 shadow-2xl">
        <div className="flex items-center gap-2 mb-4">
          <div className="rounded-full bg-primary/20 p-2">
            <LogIn className="h-5 w-5 text-primary" />
          </div>
          <h1 className="text-2xl font-bold">Acesso ao Dashboard</h1>
        </div>
        <p className="text-sm text-slate-300 mb-6">
          Use sua conta corporativa <span className="font-semibold">@auraminerals.com</span>. Novos cadastros ficam pendentes para aprovação.
        </p>

        {error && (
          <div className="mb-4 flex items-start gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="space-y-3">
          <div>
            <label className="text-sm text-slate-300 block mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-primary focus:ring-1 focus:ring-primary"
              placeholder="seu.nome@auraminerals.com"
            />
          </div>
          <div>
            <label className="text-sm text-slate-300 block mb-1">Senha</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-primary focus:ring-1 focus:ring-primary"
              placeholder="Sua senha"
            />
          </div>
          <Button className="w-full" size="lg" onClick={handleSubmit} disabled={loading}>
            <LogIn className="h-4 w-4 mr-2" />
            {loading ? "Processando..." : mode === "login" ? "Entrar" : "Cadastrar"}
          </Button>
          <button
            type="button"
            className="w-full text-center text-sm text-slate-300 hover:text-white transition"
            onClick={() => {
              setError(null)
              setMode(mode === "login" ? "signup" : "login")
            }}
          >
            {mode === "login" ? "Criar conta corporativa" : "Já tenho conta, entrar"}
          </button>
        </div>

        <p className="text-xs text-slate-400 mt-4">
          Novos cadastros ficam em "pendente" até um administrador liberar. Se já foi aprovado, entre com sua senha.
        </p>
      </div>
    </div>
  )
}
