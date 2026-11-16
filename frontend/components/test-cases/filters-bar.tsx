"use client"

import { useTranslations } from "next-intl"

import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { Priority, Screen, Severity, TestCaseStatus } from "@/lib/api/types"
import type { CaseFilters } from "@/lib/test-cases/filter"

const STATUSES: TestCaseStatus[] = ["DRAFT", "IN_REVIEW", "APPROVED", "TESTED", "ARCHIVED", "DEPRECATED"]
const SEVERITIES: Severity[] = ["LOW", "MEDIUM", "HIGH"]
const PRIORITIES: Priority[] = ["P1", "P2", "P3"]
const ALL = "__all__"

type Option = { value: string; label: string }

/** Một ô chọn có lựa chọn "Tất cả" (giá trị ALL ↔ bỏ lọc). */
function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string | undefined
  options: Option[]
  onChange: (value: string | undefined) => void
}) {
  const items = [{ value: ALL, label }, ...options]
  return (
    <Select
      items={items}
      value={value ?? ALL}
      onValueChange={(next) => onChange(next && next !== ALL ? next : undefined)}
    >
      <SelectTrigger size="sm" className="w-40" aria-label={label}>
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

export function FiltersBar({
  filters,
  onChange,
  screens,
  creators,
}: {
  filters: CaseFilters
  onChange: (filters: CaseFilters) => void
  screens: Screen[]
  /** Email những người đã tạo case. */
  creators: string[]
}) {
  const t = useTranslations("testCases")
  const set = (patch: Partial<CaseFilters>) => onChange({ ...filters, ...patch })

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        value={filters.query}
        onChange={(event) => set({ query: event.target.value })}
        placeholder={t("searchPlaceholder")}
        aria-label={t("searchPlaceholder")}
        className="w-64"
      />
      <FilterSelect
        label={t("filterScreen")}
        value={filters.screenId}
        options={screens.map((s) => ({ value: s.id, label: `${s.id} · ${s.name}` }))}
        onChange={(screenId) => set({ screenId })}
      />
      <FilterSelect
        label={t("filterStatus")}
        value={filters.status}
        options={STATUSES.map((s) => ({ value: s, label: t(`status.${s}`) }))}
        onChange={(status) => set({ status: status as TestCaseStatus | undefined })}
      />
      <FilterSelect
        label={t("filterSeverity")}
        value={filters.severity}
        options={SEVERITIES.map((s) => ({ value: s, label: t(`severity.${s}`) }))}
        onChange={(severity) => set({ severity: severity as Severity | undefined })}
      />
      <FilterSelect
        label={t("filterPriority")}
        value={filters.priority}
        options={PRIORITIES.map((p) => ({ value: p, label: p }))}
        onChange={(priority) => set({ priority: priority as Priority | undefined })}
      />
      <FilterSelect
        label={t("filterCreator")}
        value={filters.createdBy}
        options={creators.map((email) => ({ value: email, label: email }))}
        onChange={(createdBy) => set({ createdBy })}
      />
    </div>
  )
}
