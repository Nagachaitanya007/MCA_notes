import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "NoteForge — AI-Powered Study Engine",
  description:
    "An automated knowledge base that grows daily. Powered by Gemini AI and GitHub Actions, NoteForge generates, publishes, and delivers interview-grade technical notes on Java, System Design, and AI/ML.",
  keywords: ["study notes", "FAANG interview prep", "AI generated notes", "system design", "Java"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-gray-950 text-gray-100">
        {/* Navbar */}
        <nav className="sticky top-0 z-50 border-b border-gray-800/60 bg-gray-950/80 backdrop-blur-xl">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2.5 group">
              <span className="text-2xl">🔥</span>
              <span className="text-lg font-bold tracking-tight text-white group-hover:text-indigo-400 transition-colors">
                NoteForge
              </span>
            </Link>
            <div className="flex items-center gap-4 sm:gap-6">
              <Link
                href="/"
                className="text-sm font-medium text-gray-400 hover:text-white transition-colors"
              >
                Notes
              </Link>
              <Link
                href="/quizzes"
                className="text-sm font-medium text-gray-400 hover:text-white transition-colors"
              >
                Quizzes
              </Link>
              <a
                href="https://github.com/Nagachaitanya007/MCA_notes"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-gray-400 hover:text-white transition-colors flex items-center gap-1.5"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
                <span className="hidden sm:inline">GitHub</span>
              </a>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="flex-1 bg-gray-950">{children}</main>

        {/* Footer */}
        <footer className="border-t border-gray-800/60 bg-gray-950">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col sm:flex-row items-center justify-between gap-6 text-center sm:text-left">
            <p className="text-xs text-gray-500 leading-relaxed max-w-xs sm:max-w-none">
              Built by Naga Chaitanya &middot; Powered by Gemini AI &amp; GitHub Actions
            </p>
            <div className="flex items-center gap-1.5 text-xs text-gray-600">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              Auto-publishing daily
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}

