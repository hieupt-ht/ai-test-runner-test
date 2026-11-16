"use client"

import { useTranslations } from "next-intl"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ROLES, type Role } from "@/lib/api/types"

type Props = {
  value: Role
  onChange: (role: Role) => void
  disabled?: boolean
  /** Tên đọc cho trình đọc màn hình, ví dụ "Vai trò của an@x.com" */
  label: string
}

export function RoleSelect({ value, onChange, disabled = false, label }: Props) {
  const t = useTranslations("roles")
  const items = ROLES.map((role) => ({ value: role, label: t(role) }))

  return (
    <Select
      items={items}
      value={value}
      disabled={disabled}
      onValueChange={(next) => {
        if (next && next !== value) onChange(next as Role)
      }}
    >
      <SelectTrigger size="sm" className="w-32" aria-label={label}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {items.map((item) => (
          <SelectItem key={item.value} value={item.value}>
            {item.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
