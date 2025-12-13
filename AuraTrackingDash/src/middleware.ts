import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"
import { createServerClient } from "@supabase/ssr"

const ALLOWED_DOMAIN = "@auraminerals.com"

export async function middleware(req: NextRequest) {
  const res = NextResponse.next()
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseKey) {
    return res
  }

  const supabase = createServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      get(name: string) {
        return req.cookies.get(name)?.value
      },
      set(name: string, value: string, options: any) {
        res.cookies.set({
          name,
          value,
          ...options,
        })
      },
      remove(name: string, options: any) {
        res.cookies.set({
          name,
          value: "",
          ...options,
          maxAge: 0,
        })
      },
    },
  })

  const pathname = req.nextUrl.pathname

  const {
    data: { session },
  } = await supabase.auth.getSession()

  if (!session) {
    const loginUrl = new URL("/login", req.url)
    loginUrl.searchParams.set("redirectedFrom", pathname)
    return NextResponse.redirect(loginUrl)
  }

  const email = session.user.email?.toLowerCase() || ""
  if (!email.endsWith(ALLOWED_DOMAIN)) {
    // Enforce domain restriction
    const loginUrl = new URL("/login", req.url)
    loginUrl.searchParams.set("error", "domain")
    return NextResponse.redirect(loginUrl)
  }

  // Check profile status/permission
  const { data: profile } = await supabase
    .from("profiles")
    .select("status, permission")
    .eq("id", session.user.id)
    .maybeSingle()

  if (profile && profile.status && profile.status !== "active") {
    const waitUrl = new URL("/aguardando", req.url)
    waitUrl.searchParams.set("reason", profile.status)
    return NextResponse.redirect(waitUrl)
  }

  return res
}

export const config = {
  // Protege tudo, exceto rotas de login/aguardando, assets e API
  matcher: [
    "/((?!login|aguardando|_next/static|_next/image|favicon.ico|api).*)",
  ],
}
