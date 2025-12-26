export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ||
  process.env.INGEST_API_URL?.trim() ||
  "http://localhost:8080";
