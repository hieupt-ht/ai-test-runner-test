"use client"

import { Search, ShieldAlert } from "lucide-react"
import { useTranslations } from "next-intl"
import { useState } from "react"

import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { UserFormDialog } from "@/components/users/user-form-dialog"
import { UserTable } from "@/components/users/user-table"
import { useUsers } from "@/components/users/use-users"
import { useMe } from "@/lib/use-me"

export default function UsersPage() {
  const t = useTranslations("users")
  const { user: me } = useMe()
  const isAdmin = me?.role === "ADMIN"
  // Chỉ gọi API khi là Admin, tránh request chắc chắn bị 403
  const usersQuery = useUsers({ enabled: isAdmin })
  const [search, setSearch] = useState("")

  if (!isAdmin) {
    return (
      <Card className="mx-auto max-w-md">
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <ShieldAlert className="size-8 text-muted-foreground" />
          <p>{t("noPermission")}</p>
        </CardContent>
      </Card>
    )
  }

  const keyword = search.trim().toLowerCase()
  const users = (usersQuery.data ?? []).filter(
    (user) =>
      user.email.includes(keyword) || user.name.toLowerCase().includes(keyword),
  )

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <p className="text-sm text-muted-foreground">{t("description")}</p>
        <UserFormDialog />
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t("search")}
          className="pl-8"
        />
      </div>

      {usersQuery.isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : usersQuery.isError ? (
        <p className="text-sm text-destructive">{usersQuery.error.message}</p>
      ) : (
        <UserTable users={users} currentUserEmail={me.email} />
      )}
    </div>
  )
}
