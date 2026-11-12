import { Suspense, type ReactNode } from "react"

import { ProjectHeader } from "@/components/projects/project-header"
import { Skeleton } from "@/components/ui/skeleton"

// Không chờ `params` ở đây: mã dự án chỉ biết lúc chạy, nên phần đọc nó (ProjectHeader và
// các trang con) nằm trong <Suspense> để phần khung còn lại vẫn được dựng sẵn.
export default function ProjectLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Suspense fallback={<Skeleton className="h-24 w-full" />}>
        <ProjectHeader />
      </Suspense>
      <Suspense fallback={<Skeleton className="h-48 w-full" />}>{children}</Suspense>
    </div>
  )
}
