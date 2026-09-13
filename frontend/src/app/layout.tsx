// Root layout — shared nav/shell across pages

import type { Metadata } from "next";
import Link from "next/link";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "DrivePulse AI",
  description:
    "Explainable vehicle health digital twin and predictive maintenance platform.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-6 focus:top-4 focus:z-50 focus:bg-panel focus:p-4"
        >
          Skip to content
        </a>
        <header className="border-b border-line">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-5 px-6 py-6 sm:px-10">
            <Link href="/" aria-label="DrivePulse AI home" className="text-lg font-semibold tracking-tight">
              DrivePulse <span className="font-normal text-muted">AI</span>
            </Link>
            <nav aria-label="Main navigation">
              <Link href="/" className="text-sm text-silver transition-colors hover:text-accent">
                Overview
              </Link>
            </nav>
            <span className="rounded-full border border-line px-3 py-1 text-xs text-muted">
              Prototype · Offline
            </span>
          </div>
        </header>
        {children}
        <footer className="mx-auto max-w-7xl px-6 py-8 text-xs leading-6 text-muted sm:px-10">
          DrivePulse AI · Independent vehicle-health prototype. No vehicle data connected.
        </footer>
      </body>
    </html>
  );
}
