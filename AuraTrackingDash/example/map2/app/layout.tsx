import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aura Tracking",
  description: "Telemetry map viewer for Aura Tracking"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ minHeight: "100vh", margin: 0 }}>{children}</body>
    </html>
  );
}
