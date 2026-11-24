import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { ModeProvider } from "@/components/mode-context";
import { AppShell } from "@/components/AppShell";

export const metadata: Metadata = {
  title: "BVMT Trading Intelligence V2",
  description:
    "Reproducible, human-supervised Tunisian equity research and manual decision-support terminal.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Suspense fallback={<div className="min-h-screen bg-[#F8F9FA]" />}>
          <ModeProvider>
            <AppShell>{children}</AppShell>
          </ModeProvider>
        </Suspense>
      </body>
    </html>
  );
}
