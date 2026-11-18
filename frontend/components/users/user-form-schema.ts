import { z } from "zod"

import { ROLES } from "@/lib/api/types"

// Backend cũng giới hạn 8–128 ký tự. Mật khẩu không trim: khoảng trắng có thể là một phần của nó.
export const passwordSchema = z
  .string()
  .min(8, { error: "Mật khẩu tối thiểu 8 ký tự" })
  .max(128, { error: "Mật khẩu tối đa 128 ký tự" })

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
  password: passwordSchema,
})

export type UserFormValues = z.infer<typeof userFormSchema>
