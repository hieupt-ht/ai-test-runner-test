"use client"

import { useQueryClient } from "@tanstack/react-query"
import { KeyRound, LogOut, Monitor, Moon, Sun } from "lucide-react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { useTheme } from "next-themes"
import { useState } from "react"

import { ChangePasswordDialog } from "@/components/account/change-password-dialog"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { NotificationBell } from "@/components/notifications/notification-bell"
import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { api } from "@/lib/api/client"
import type { User } from "@/lib/api/types"

function initials(name: string): string {
  const words = name.trim().split(/\s+/)
  const last = words.at(-1) ?? ""
  return last.charAt(0).toUpperCase() || "?"
}

export function Topbar({ user, title }: { user: User; title: string }) {
  const t = useTranslations()
  const { setTheme } = useTheme()
  const queryClient = useQueryClient()
  const router = useRouter()
  const [changePasswordOpen, setChangePasswordOpen] = useState(false)

  async function logout() {
    await api.POST("/api/auth/logout")
    queryClient.clear()
    router.replace("/login")
  }

  return (
    <header className="flex h-14 items-center justify-between border-b bg-background px-4 md:px-6">
      <h1 className="min-w-0 truncate text-base font-semibold">{title}</h1>

      <div className="flex min-w-0 items-center gap-2">
        <NotificationBell />
        <DropdownMenu>
          <DropdownMenuTrigger className="flex items-center gap-2 rounded-lg px-2 py-1 outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring">
            <span className="hidden text-right text-sm leading-tight sm:block">
              <span className="block font-medium">{user.name}</span>
              <span className="block text-xs text-muted-foreground">{user.email}</span>
            </span>
            <Avatar className="size-8">
              <AvatarFallback>{initials(user.name)}</AvatarFallback>
            </Avatar>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuGroup>
              <DropdownMenuLabel className="flex items-center justify-between">
                {user.name}
                <Badge variant="secondary">{t(`roles.${user.role}`)}</Badge>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuLabel className="text-xs text-muted-foreground">
                {t("topbar.theme")}
              </DropdownMenuLabel>
              <DropdownMenuItem onClick={() => setTheme("light")}>
                <Sun /> {t("topbar.themeLight")}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme("dark")}>
                <Moon /> {t("topbar.themeDark")}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme("system")}>
                <Monitor /> {t("topbar.themeSystem")}
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => setChangePasswordOpen(true)}>
              <KeyRound /> {t("account.title")}
            </DropdownMenuItem>
            <DropdownMenuItem variant="destructive" onClick={logout}>
              <LogOut /> {t("topbar.logout")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {/* Đặt ngoài menu: menu đóng lại thì hộp thoại vẫn phải còn */}
      <ChangePasswordDialog open={changePasswordOpen} onOpenChange={setChangePasswordOpen} />
    </header>
  )
}
