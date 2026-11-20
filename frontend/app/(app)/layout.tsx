import { Suspense, type ReactNode } from "react"

import { AppShell, ShellSkeleton } from "@/components/app-shell/app-shell"
import { MusicProvider } from "@/components/music/music-provider"

// Mọi trang trong nhóm (app) đều cần đăng nhập và có sidebar + topbar.
// AppShell đọc đường dẫn hiện tại; ở trang có mã dự án trên URL thì đường dẫn chỉ biết lúc chạy,
// nên phải bọc trong <Suspense> (đang bật cacheComponents).
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <MusicProvider>
      <Suspense fallback={<ShellSkeleton />}>
        <AppShell>{children}</AppShell>
      </Suspense>
    </MusicProvider>
  )
}
