"use client"

import { Bell } from "lucide-react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useMarkAllRead, useMarkRead, useNotifications } from "@/lib/use-notifications"

export function NotificationBell() {
  const t = useTranslations("notifications")
  const router = useRouter()
  const { data } = useNotifications()
  const markRead = useMarkRead()
  const markAllRead = useMarkAllRead()

  async function openNotification(id: string, link: string) {
    try {
      await markRead.mutateAsync(id)
      // Liên kết thông báo chỉ được dẫn tới một trang nội bộ.
      if (link.startsWith("/") && !link.startsWith("//")) router.push(link)
    } catch {
      toast.error(t("readError"))
    }
  }

  async function readAll() {
    try {
      await markAllRead.mutateAsync()
    } catch {
      toast.error(t("readError"))
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={t("title")}
        className="relative flex size-9 shrink-0 items-center justify-center rounded-lg hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Bell className="size-5" />
        {Boolean(data?.unread) && (
          <span className="absolute -top-1 -right-1 flex min-w-5 items-center justify-center rounded-full bg-destructive px-1 text-xs font-semibold text-white">
            {data!.unread}
          </span>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[min(22rem,calc(100vw-2rem))]">
        <div className="flex items-center justify-between gap-2 px-2 py-1">
          <span className="font-medium">{t("title")}</span>
          {Boolean(data?.unread) && (
            <Button type="button" size="sm" variant="ghost" onClick={readAll}>
              {t("readAll")}
            </Button>
          )}
        </div>
        {data?.items.length ? (
          data.items.map((item) => (
            <DropdownMenuItem
              key={item.id}
              className={item.read ? "text-muted-foreground" : "font-medium"}
              onClick={() => void openNotification(item.id, item.link)}
            >
              <span className="min-w-0 truncate">{item.title}</span>
            </DropdownMenuItem>
          ))
        ) : (
          <p className="px-2 py-4 text-center text-sm text-muted-foreground">{t("empty")}</p>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
