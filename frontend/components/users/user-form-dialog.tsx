"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { UserPlus } from "lucide-react"
import { useTranslations } from "next-intl"
import { useState } from "react"
import { Controller, useForm } from "react-hook-form"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { userFormSchema, type UserFormValues } from "@/components/users/user-form-schema"
import { useCreateUser } from "@/components/users/use-users"
import { ROLES, type Role } from "@/lib/api/types"

function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return <p className="text-xs text-destructive">{message}</p>
}

export function UserFormDialog() {
  const t = useTranslations()
  const [open, setOpen] = useState(false)
  const createUser = useCreateUser()

  const form = useForm<UserFormValues>({
    resolver: zodResolver(userFormSchema),
    defaultValues: { email: "", name: "", role: "TESTER", password: "" },
  })
  const { errors, isSubmitting } = form.formState
  const roleItems = ROLES.map((role) => ({ value: role, label: t(`roles.${role}`) }))

  async function onSubmit(values: UserFormValues) {
    try {
      const user = await createUser.mutateAsync({ ...values, role: values.role as Role })
      toast.success(t("users.created", { email: user.email }))
      form.reset()
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("errors.generic"))
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}>
        <UserPlus /> {t("users.add")}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("users.formTitle")}</DialogTitle>
          <DialogDescription>{t("users.formDescription")}</DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="user-email">{t("users.fieldEmail")}</Label>
            <Input
              id="user-email"
              type="email"
              autoComplete="off"
              placeholder="ten@congty.com"
              aria-invalid={Boolean(errors.email)}
              {...form.register("email")}
            />
            <FieldError message={errors.email?.message} />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="user-name">{t("users.fieldName")}</Label>
            <Input id="user-name" aria-invalid={Boolean(errors.name)} {...form.register("name")} />
            <FieldError message={errors.name?.message} />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>{t("users.fieldRole")}</Label>
            <Controller
              control={form.control}
              name="role"
              render={({ field }) => (
                <Select
                  items={roleItems}
                  value={field.value}
                  onValueChange={(value) => field.onChange(value ?? "TESTER")}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {roleItems.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            <FieldError message={errors.role?.message} />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="user-password">{t("users.fieldPassword")}</Label>
            <Input
              id="user-password"
              type="text"
              autoComplete="off"
              aria-invalid={Boolean(errors.password)}
              {...form.register("password")}
            />
            <p className="text-xs text-muted-foreground">{t("users.passwordHint")}</p>
            <FieldError message={errors.password?.message} />
          </div>

          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button" />}>
              {t("users.cancel")}
            </DialogClose>
            <Button type="submit" disabled={isSubmitting}>
              {t("users.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
