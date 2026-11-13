"use client"

import { FolderKanban } from "lucide-react"
import { useTranslations } from "next-intl"

import { Card, CardContent } from "@/components/ui/card"
import { useMe } from "@/lib/use-me"

export default function OverviewPage() {
  const t = useTranslations("overview")
  const { user } = useMe()

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <p className="text-2xl font-semibold">{t("greeting", { name: user?.name ?? "" })}</p>
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
          <div className="flex size-12 items-center justify-center rounded-full bg-muted">
            <FolderKanban className="size-6 text-muted-foreground" />
          </div>
          <p className="font-medium">{t("emptyTitle")}</p>
          <p className="max-w-md text-sm text-muted-foreground">{t("emptyDescription")}</p>
        </CardContent>
      </Card>
    </div>
  )
}
