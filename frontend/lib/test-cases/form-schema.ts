import { z } from "zod"

import type { TestCaseContent } from "@/lib/api/types"

// Giới hạn độ dài khớp với backend; message là khoá trong messages/vi.json (testCases.form.errors.*).
export const LIMITS = { title: 200, text: 2000, stepAction: 500, stepExpected: 500, steps: 50 }

// Ảnh/video lưu trên Cloudinary; backend kiểm tra lại link, ở đây chỉ giữ nguyên dữ liệu.
const mediaSchema = z.object({
  kind: z.enum(["image", "video"]),
  url: z.string(),
  public_id: z.string(),
  note: z.string(),
})
const mediaListSchema = z.array(mediaSchema).max(5)

const stepSchema = z.object({
  action: z.string().trim().min(1, "stepActionRequired").max(LIMITS.stepAction, "stepActionTooLong"),
  expected: z.string().max(LIMITS.stepExpected, "stepExpectedTooLong"),
  guide_media: mediaListSchema,
})

export const testCaseFormSchema: z.ZodType<TestCaseContent, TestCaseContent> = z.object({
  title: z.string().trim().min(1, "titleRequired").max(LIMITS.title, "titleTooLong"),
  precondition: z.string().max(LIMITS.text, "textTooLong"),
  test_data: z.string().max(LIMITS.text, "textTooLong"),
  steps: z.array(stepSchema).min(1, "stepsRequired").max(LIMITS.steps, "stepsTooMany"),
  expected_result: z
    .string()
    .trim()
    .min(1, "expectedResultRequired")
    .max(LIMITS.text, "textTooLong"),
  severity: z.enum(["LOW", "MEDIUM", "HIGH"]),
  priority: z.enum(["P1", "P2", "P3"]),
  platform: z.enum(["WEB", "ANDROID", "IOS"]),
  test_type: z.enum(["FUNCTIONAL", "UI"]),
  regression: z.boolean(),
  start_point: z.string().max(500, "textTooLong"),
  guide_media: mediaListSchema,
  postcondition: z.string().max(LIMITS.text, "textTooLong"),
  requirement_ref: z.string().max(200, "textTooLong"),
  execution_mode: z.enum(["MANUAL", "AUTOMATION"]),
})
