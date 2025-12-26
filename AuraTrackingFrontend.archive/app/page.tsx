"use client";

import Link from "next/link";

export default function HomePage() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        gap: "1rem"
      }}
    >
      <h1>Aura Tracking Frontend</h1>
      <Link
        href="/map"
        style={{
          padding: "0.75rem 1.5rem",
          borderRadius: "8px",
          background: "#2563eb",
          color: "#fff",
          fontWeight: 600
        }}
      >
        Go to Map
      </Link>
    </main>
  );
}
