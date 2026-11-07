import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "BVMT Trading Intelligence — Tunis Bourse Decision Support",
  description:
    "Local-first decision-support dashboard for the Tunis Bourse Challenge virtual equity competition.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased selection:bg-emerald-500/30 selection:text-emerald-200">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
