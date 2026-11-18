"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { TriangleAlert } from "lucide-react"
import { useTranslations } from "next-intl"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { passwordSchema } from "@/components/users/user-form-schema"
import { useResetPassword } from "@/components/users/use-users"

const resetSchema = z.object({ password: passwordSchema })
type ResetValues = z.infer<typeof resetSchema>

type Props = { email: string; open: boolean; onOpenChange: (open: boolean) => void }

/** Admin đặt mật khẩu mới cho một người (khi họ quên). Người đó bị đăng xuất khỏi mọi nơi. */
export function ResetPasswordDialog({ email, open, onOpenChange }: Props) {
  const t = useTranslations("users")
  const resetPassword = useResetPassword()
  const [serverError, setServerError] = useState<string | null>(null)
  const form = useForm<ResetValues>({
    resolver: zodResolver(resetSchema),
    defaultValues: { password: "" },
  })
  const { errors, isSubmitting } = form.formState

  async function onSubmit({ password }: ResetValues) {
    setServerError(null)
    try {
      await resetPassword.mutateAsync({ email, password })
      toast.success(t("resetDone", { email }))
      form.reset()
      onOpenChange(false)
    } catch (error) {
      setServerError(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("resetTitle")}</DialogTitle>
          <DialogDescription>{t("resetDescription", { email })}</DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
          {serverError && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
            >
              <TriangleAlert className="mt-0.5 size-4 shrink-0" />
              <span>{serverError}</span>
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reset-password">{t("fieldNewPassword")}</Label>
            <Input
              id="reset-password"
              type="text"
              autoComplete="off"
              aria-invalid={Boolean(errors.password)}
              {...form.register("password")}
            />
            {errors.password?.message && (
              <p className="text-xs text-destructive">{errors.password.message}</p>
            )}
          </div>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button" />}>
              {t("cancel")}
            </DialogClose>
            <Button type="submit" disabled={isSubmitting}>
              {t("resetSubmit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
