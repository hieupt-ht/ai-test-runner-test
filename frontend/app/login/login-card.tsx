"use client"

import { FlaskConical, TriangleAlert } from "lucide-react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { useState, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api, errorMessage } from "@/lib/api/client"

export function LoginCard() {
  const t = useTranslations()
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const { error: apiError, response } = await api.POST("/api/auth/login", {
        body: { email, password },
      })
      if (response.ok) {
        router.replace("/")
        return
      }
      // Hiện nguyên câu báo lỗi của server (sai mật khẩu, bị khoá tạm...).
      setError(errorMessage(apiError, t("errors.generic")))
    } catch {
      setError(t("errors.generic"))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card className="w-full max-w-sm">
      <CardHeader className="items-center text-center">
        <div className="mx-auto mb-2 flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <FlaskConical className="size-6" />
        </div>
        <CardTitle className="text-xl">{t("app.name")}</CardTitle>
        <CardDescription>{t("app.tagline")}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          {error && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
            >
              <TriangleAlert className="mt-0.5 size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          <p className="text-center text-sm text-muted-foreground">{t("login.subtitle")}</p>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="login-email">{t("login.email")}</Label>
            <Input
              id="login-email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="login-password">{t("login.password")}</Label>
            <Input
              id="login-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <Button type="submit" size="lg" className="w-full" disabled={submitting}>
            {t("login.button")}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
