import { Suspense, type ReactNode } from "react"

import { ProjectHeader } from "@/components/projects/project-header"
import { Skeleton } from "@/components/ui/skeleton"

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
