import type { Metadata } from "next"
import type { ReactNode } from "react"
import { Be_Vietnam_Pro, Geist_Mono } from "next/font/google"

import { Providers } from "@/app/providers"

import "./globals.css"

// Font có đủ dấu tiếng Việt
const sans = Be_Vietnam_Pro({
  variable: "--font-sans",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
})

const mono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: "AI Test Runner",
  description: "Quản lý test case và để AI chạy test",
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="vi" suppressHydrationWarning className={`${sans.variable} ${mono.variable} h-full antialiased`}>
      <body className="min-h-full bg-background font-sans text-foreground">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
