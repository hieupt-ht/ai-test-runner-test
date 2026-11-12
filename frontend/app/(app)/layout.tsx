import type { ReactNode } from "react"

import { AppShell } from "@/components/app-shell/app-shell"

// Mọi trang trong nhóm (app) đều cần đăng nhập và có sidebar + topbar.
export default function AppLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>
}
