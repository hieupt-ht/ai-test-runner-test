"use client"

import { Controller, type Control } from "react-hook-form"

import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { TestCaseContent } from "@/lib/api/types"

/** Ô chọn một giá trị trong danh sách cố định (mức độ, ưu tiên). */
export function EnumSelect({
  control,
  name,
  label,
  options,
}: {
  control: Control<TestCaseContent>
  name: "severity" | "priority" | "platform" | "test_type"
  label: string
  options: { value: string; label: string }[]
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <Select items={options} value={field.value} onValueChange={field.onChange}>
            <SelectTrigger className="w-40" aria-label={label}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      />
    </div>
  )
}
