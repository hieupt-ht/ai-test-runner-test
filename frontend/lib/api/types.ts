// Kiểu dữ liệu lấy từ OpenAPI của backend (file schema.d.ts được sinh tự động bằng `npm run gen:api`).
import type { components } from "@/lib/api/schema"

export type Role = components["schemas"]["Role"]
export type User = components["schemas"]["User"]

export const ROLES: Role[] = ["ADMIN", "QA_LEAD", "TESTER", "VIEWER"]
