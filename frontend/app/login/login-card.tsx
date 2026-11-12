"use client"

import { FlaskConical, TriangleAlert } from "lucide-react"
import { useSearchParams } from "next/navigation"
import { useTranslations } from "next-intl"

import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export function LoginCard() {
  const t = useTranslations()
  const isNotAllowed = useSearchParams().get("error") === "not_allowed"

  return (
    <Card className="w-full max-w-sm">
      <CardHeader className="items-center text-center">
        <div className="mx-auto mb-2 flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <FlaskConical className="size-6" />
        </div>
        <CardTitle className="text-xl">{t("app.name")}</CardTitle>
        <CardDescription>{t("app.tagline")}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {isNotAllowed && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
          >
            <TriangleAlert className="mt-0.5 size-4 shrink-0" />
            <span>{t("login.notAllowed")}</span>
          </div>
        )}
        <p className="text-center text-sm text-muted-foreground">{t("login.subtitle")}</p>
        {/* Dùng thẻ <a> thường: đây là chuyển hướng sang Google, không phải điều hướng trong app */}
        <a href="/api/auth/login" className={buttonVariants({ size: "lg", className: "w-full" })}>
          {t("login.button")}
        </a>
      </CardContent>
    </Card>
  )
}
