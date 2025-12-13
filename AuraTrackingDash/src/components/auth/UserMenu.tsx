"use client"

import { useEffect, useState } from "react"
import { createBrowserSupabaseClient } from "@/lib/supabase/clientAuth"
import { Button } from "@/components/ui/button"
import { LogOut } from "lucide-react"

interface UserMenuProps {
  className?: string
}

export function UserMenu({ className }: UserMenuProps) {
  const [email, setEmail] = useState<string | null>(null)
  const supabase = createBrowserSupabaseClient()

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setEmail(data.user?.email ?? null)
    })
  }, [supabase])

  const handleLogout = async () => {
    await supabase.auth.signOut()
    window.location.href = "/login"
  }

  if (!email) {
    return null
  }

  return (
    <div className={`flex items-center gap-3 ${className ?? ""}`}>
      <span className="text-sm text-muted-foreground truncate max-w-[200px]">{email}</span>
      <Button variant="outline" size="sm" onClick={handleLogout}>
        <LogOut className="h-4 w-4 mr-2" />
        Sair
      </Button>
    </div>
  )
}
