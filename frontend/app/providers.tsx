"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { NextIntlClientProvider } from "next-intl"
import { ThemeProvider } from "next-themes"
import { useState, type ReactNode } from "react"

import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import messages from "@/messages/vi.json"

// Hiện chỉ có tiếng Việt. Thêm ngôn ngữ khác: tạo messages/<mã>.json rồi chọn theo người dùng.
const LOCALE = "vi"
const TIME_ZONE = "Asia/Ho_Chi_Minh"

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient())

  return (
    <NextIntlClientProvider locale={LOCALE} messages={messages} timeZone={TIME_ZONE}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
        <QueryClientProvider client={queryClient}>
          <TooltipProvider>
            {children}
            <Toaster richColors position="top-right" />
          </TooltipProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </NextIntlClientProvider>
  )
}
