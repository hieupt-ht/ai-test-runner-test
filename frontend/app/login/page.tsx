import { Suspense } from "react"

import { LoginCard } from "@/app/login/login-card"

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      {/* LoginCard đọc ?error= trên URL (dữ liệu lúc chạy) nên cần Suspense */}
      <Suspense>
        <LoginCard />
      </Suspense>
    </main>
  )
}
