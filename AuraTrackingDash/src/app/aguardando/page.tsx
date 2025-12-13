"use client"

import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Hourglass, LogOut } from "lucide-react"
import { createBrowserSupabaseClient } from "@/lib/supabase/clientAuth"

export default function AguardandoPage() {
  const params = useSearchParams()
  const router = useRouter()
  const reason = params.get("reason") || "pending"
  const supabase = createBrowserSupabaseClient()

  const handleLogout = async () => {
    await supabase.auth.signOut()
    router.push("/login")
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-950 to-black text-white px-4">
      <div className="w-full max-w-lg rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-2xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="rounded-full bg-primary/20 p-2">
            <Hourglass className="h-5 w-5 text-primary" />
          </div>
          <h1 className="text-2xl font-bold">Aguardando aprovação</h1>
        </div>
        <p className="text-sm text-slate-200 mb-3">
          Sua conta está marcada como <span className="font-semibold">{reason}</span>.
        </p>
        <p className="text-sm text-slate-300 mb-6">
          Um administrador precisa liberar seu acesso. Caso já tenha sido aprovado, tente sair e entrar novamente.
        </p>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => router.push("/login")}>
            Voltar ao login
          </Button>
          <Button variant="secondary" onClick={handleLogout}>
            <LogOut className="h-4 w-4 mr-2" />
            Sair
          </Button>
        </div>
      </div>
    </div>
  )
}
