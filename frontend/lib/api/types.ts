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
export type OverviewSummary = Schemas["OverviewSummary"]
export type MemberView = Schemas["MemberView"]

export type TestCase = Schemas["TestCase"]
export type TestCaseDetail = Schemas["TestCaseDetail"]
export type TestStep = Schemas["TestStep"]
/** Ảnh/video hướng dẫn hoặc bằng chứng (nằm trên Cloudinary). */
export type Media = Schemas["Media"]
export type MediaKind = Schemas["MediaKind"]
export type SignedUpload = Schemas["SignedUpload"]
/** Phần nội dung người dùng nhập của một test case (không gồm mã, trạng thái, version...). */
export type TestCaseContent = Pick<
  Schemas["TestCase"],
  | "title"
  | "precondition"
  | "test_data"
  | "steps"
  | "expected_result"
  | "severity"
  | "priority"
  | "platform"
  | "test_type"
  | "regression"
  | "start_point"
  | "guide_media"
  | "postcondition"
  | "requirement_ref"
>
export type TestCaseStatus = Schemas["TestCaseStatus"]
export type Severity = Schemas["Severity"]
export type Priority = Schemas["Priority"]
export type AuditEntry = Schemas["AuditEntry"]
export type BatchApproveResponse = Schemas["BatchApproveResponse"]
export type SyncIssuesResult = Schemas["SyncIssuesResult"]
export type ConflictResponse = Schemas["ConflictResponse"]
export type ResultItem = Schemas["ResultItem"]
export type ResultStatus = Schemas["ResultStatus"]

export const ROLES: Role[] = ["ADMIN", "QA_LEAD", "TESTER", "VIEWER"]
