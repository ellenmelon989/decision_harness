import type { Metadata } from "next";
import { Fraunces, Hanken_Grotesk, JetBrains_Mono } from "next/font/google";

import "./globals.css";
import { AuthGate } from "../components/AuthGate";
import { AuthProvider } from "../lib/auth";

// "The Deliberation Room" type system: a characterful editorial serif for
// authority (wordmark, verdict, section heads), a warm humanist grotesque for
// body, and a mono for live telemetry / scores / the inspectable record.
const display = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});
const body = Hanken_Grotesk({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});
const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Decision Harness — the AI deliberation room",
  description:
    "Convene a configurable AI council, put a decision to the floor, and watch them debate it out loud — with a full, inspectable audit trail and a weighted verdict.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>
        <div className="grain" aria-hidden />
        <AuthProvider>
          <AuthGate>{children}</AuthGate>
        </AuthProvider>
      </body>
    </html>
  );
}
