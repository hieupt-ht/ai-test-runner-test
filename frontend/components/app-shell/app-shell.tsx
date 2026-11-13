"use client"

import { usePathname, useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { useEffect, type ReactNode } from "react"

import { Sidebar } from "@/components/app-shell/sidebar"
import { Topbar } from "@/components/app-shell/topbar"
import { Skeleton } from "@/components/ui/skeleton"
import { NAV_ITEMS } from "@/lib/nav"
import { useMe } from "@/lib/use-me"

export function ShellSkeleton() {
  return (
    <div className="flex min-h-screen">
      <div className="hidden w-60 border-r p-4 md:block">
        <Skeleton className="mb-6 h-6 w-32" />
        <Skeleton className="mb-2 h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
      <div className="flex-1 p-6">
        <Skeleton className="mb-6 h-8 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    </div>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const t = useTranslations()
  const router = useRouter()
  const pathname = usePathname()
  const { user, isLoading } = useMe()

  useEffect(() => {
    if (!isLoading && !user) router.replace("/login")
  }, [isLoading, user, router])

  if (isLoading || !user) return <ShellSkeleton />

  const current = NAV_ITEMS.find((item) =>
    item.href === "/" ? pathname === "/" : pathname.startsWith(item.href),
  )
  const isProjectPage = pathname.startsWith("/projects/")
  const title = current
    ? t(`nav.${current.labelKey}`)
    : t(isProjectPage ? "nav.projects" : "app.name")

  return (
    <div className="flex min-h-screen">
      <Sidebar role={user.role} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar user={user} title={title} />
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  )
}
