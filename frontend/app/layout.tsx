// =============================================================================
// DevBrain AI — Root Layout
// Setup: cd frontend && npx create-next-app@latest . --typescript --tailwind --app
//        --no-src-dir --import-alias "@/*"
//        npm install @monaco-editor/react recharts lucide-react axios
// =============================================================================

import type { Metadata } from "next";
import { Space_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "DevBrain AI — Know Your Real Skill Gaps",
  description:
    "AI-powered developer growth platform. Analyze your GitHub, get personalized roadmaps, daily coding challenges, and AI code review.",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${jetbrainsMono.variable}`}
    >
      <body className="bg-[#0f1117] text-white antialiased font-sans">
        <div className="flex h-screen overflow-hidden">
          {/* Sidebar — client component so it can use hooks */}
          <Sidebar />

          {/* Main content area */}
          <main className="flex-1 overflow-y-auto">
            <div className="min-h-full">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}