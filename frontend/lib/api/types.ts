// Kiểu dữ liệu lấy từ OpenAPI của backend (file schema.d.ts được sinh tự động bằng `npm run gen:api`).
import type { components } from "@/lib/api/schema"

type Schemas = components["schemas"]

export type Role = Schemas["Role"]
export type User = Schemas["User"]
export type Action = Schemas["Action"]
export type Project = Schemas["Project"]
export type ProjectDetail = Schemas["ProjectDetail"]
export type RepoInfo = Schemas["RepoInfo"]
export type Screen = Schemas["Screen"]
export type Assignment = Schemas["Assignment"]
export type AssignmentStatus = Schemas["AssignmentStatus"]
export type MyAssignment = Schemas["MyAssignment"]
export type MemberView = Schemas["MemberView"]

export const ROLES: Role[] = ["ADMIN", "QA_LEAD", "TESTER", "VIEWER"]
