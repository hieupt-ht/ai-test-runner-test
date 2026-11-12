import { useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import type { Role } from "@/lib/api/types"
import { cn } from "@/lib/utils"

// Mỗi vai trò một màu, dùng nhất quán trong toàn app.
const ROLE_COLORS: Record<Role, string> = {
  ADMIN: "bg-violet-100 text-violet-800 dark:bg-violet-500/20 dark:text-violet-200",
  QA_LEAD: "bg-sky-100 text-sky-800 dark:bg-sky-500/20 dark:text-sky-200",
  TESTER: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200",
  VIEWER: "bg-zinc-100 text-zinc-700 dark:bg-zinc-500/20 dark:text-zinc-300",
}

export function RoleBadge({ role }: { role: Role }) {
  const t = useTranslations("roles")
  return (
    <Badge variant="outline" className={cn("border-transparent", ROLE_COLORS[role])}>
      {t(role)}
    </Badge>
  )
}
