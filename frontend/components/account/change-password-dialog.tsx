"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
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
import { api, ApiError, errorMessage } from "@/lib/api/client"

const changeSchema = z
  .object({
    current: z.string().min(1, { error: "Nhập mật khẩu hiện tại" }),
    next: passwordSchema,
    confirm: z.string(),
  })
  .refine((values) => values.next === values.confirm, {
    path: ["confirm"],
    error: "Hai mật khẩu mới chưa khớp nhau",
  })
type ChangeValues = z.infer<typeof changeSchema>

function useChangePassword() {
  return useMutation({
    mutationFn: async (input: { current: string; next: string }): Promise<void> => {
      const { error, response } = await api.POST("/api/auth/change-password", {
        body: { current_password: input.current, new_password: input.next },
      })
      if (!response.ok) {
        throw new ApiError(response.status, errorMessage(error, "Có lỗi xảy ra, vui lòng thử lại."))
      }
    },
  })
}

function PasswordField({
  id,
  label,
  error,
  autoComplete,
  registration,
}: {
  id: string
  label: string
  error?: string
  autoComplete: string
  registration: ReturnType<ReturnType<typeof useForm<ChangeValues>>["register"]>
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="password"
        autoComplete={autoComplete}
        aria-invalid={Boolean(error)}
        {...registration}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}

type Props = { open: boolean; onOpenChange: (open: boolean) => void }

/** Người dùng tự đổi mật khẩu của mình. Đổi xong, các trình duyệt khác bị đăng xuất. */
export function ChangePasswordDialog({ open, onOpenChange }: Props) {
  const t = useTranslations("account")
  const changePassword = useChangePassword()
  const [serverError, setServerError] = useState<string | null>(null)
  const form = useForm<ChangeValues>({
    resolver: zodResolver(changeSchema),
    defaultValues: { current: "", next: "", confirm: "" },
  })
  const { errors, isSubmitting } = form.formState

  function close(nextOpen: boolean) {
    if (!nextOpen) {
      form.reset()
      setServerError(null)
    }
    onOpenChange(nextOpen)
  }

  async function onSubmit({ current, next }: ChangeValues) {
    setServerError(null)
    try {
      await changePassword.mutateAsync({ current, next })
      toast.success(t("done"))
      close(false)
    } catch (error) {
      setServerError(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>{t("description")}</DialogDescription>
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
          <PasswordField
            id="current-password"
            label={t("current")}
            autoComplete="current-password"
            error={errors.current?.message}
            registration={form.register("current")}
          />
          <PasswordField
            id="new-password"
            label={t("new")}
            autoComplete="new-password"
            error={errors.next?.message}
            registration={form.register("next")}
          />
          <PasswordField
            id="confirm-password"
            label={t("confirm")}
            autoComplete="new-password"
            error={errors.confirm?.message}
            registration={form.register("confirm")}
          />
          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button" />}>
              {t("cancel")}
            </DialogClose>
            <Button type="submit" disabled={isSubmitting}>
              {t("submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
