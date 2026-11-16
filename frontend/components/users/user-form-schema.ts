import { z } from "zod"

import { ROLES } from "@/lib/api/types"

// Kiểm tra form ngay khi gõ để báo lỗi sớm. Backend vẫn kiểm tra lại lần nữa.
export const userFormSchema = z.object({
  email: z
    .string()
    .trim()
    .toLowerCase()
    .pipe(z.email({ error: "Email không hợp lệ" })),
  name: z
    .string()
    .trim()
    .min(1, { error: "Vui lòng nhập tên" })
    .max(100, { error: "Tên tối đa 100 ký tự" }),
  role: z.enum(ROLES as [string, ...string[]], { error: "Vui lòng chọn vai trò" }),
})

export type UserFormValues = z.infer<typeof userFormSchema>
