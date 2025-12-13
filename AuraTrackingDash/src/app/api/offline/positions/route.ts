import { NextResponse } from "next/server"

const BACKEND_URL =
  process.env.INGEST_API_URL?.trim() ||
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ||
  "http://localhost:8080"

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const { equipmentId, start, end, limit = 20000 } = body || {}

    if (!start || !end) {
      return NextResponse.json({ error: "start and end are required" }, { status: 400 })
    }

    const url = new URL("/api/history", BACKEND_URL)
    if (equipmentId && equipmentId !== "all") {
      url.searchParams.set("device_id", equipmentId)
    }
    url.searchParams.set("start", start)
    url.searchParams.set("end", end)
    url.searchParams.set("limit", String(limit))

    const res = await fetch(url.toString(), {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
    })

    if (!res.ok) {
      const errText = await res.text()
      return NextResponse.json({ error: errText || "Failed to fetch history" }, { status: res.status })
    }

    const data = await res.json()
    return NextResponse.json(data)
  } catch (err: any) {
    return NextResponse.json({ error: err?.message || "Unexpected error" }, { status: 500 })
  }
}
