import { z } from "zod"

import type { TestCaseContent } from "@/lib/api/types"
import { autoNeedsTarget, autoNeedsValue } from "@/lib/test-cases/steps"

// Giới hạn độ dài khớp với backend; message là khoá trong messages/vi.json (testCases.form.errors.*).
export const LIMITS = {
  title: 200,
  text: 2000,
  stepAction: 500,
  stepExpected: 500,
  steps: 50,
  autoValue: 500,
}

// Phần tự động của một bước; luật khớp backend (AutoStep trong core/models/test_case.py).
const autoSchema = z
  .object({
    type: z.enum(["goto", "fill", "click", "select", "see_text", "not_see_text", "url_is"]),
    target: z
      .object({
        by: z.enum(["text", "label", "css"]),
        value: z
          .string()
          .trim()
          .min(1, "autoTargetRequired")
          .max(LIMITS.autoValue, "autoValueTooLong"),
      })
      .nullish(),
    value: z.string().max(LIMITS.autoValue, "autoValueTooLong"),
  })
  .superRefine((auto, ctx) => {
    if (autoNeedsTarget(auto.type) && !auto.target) {
      ctx.addIssue({ code: "custom", message: "autoTargetRequired" })
    }
    if (autoNeedsValue(auto.type) && !auto.value.trim()) {
      ctx.addIssue({ code: "custom", message: "autoValueRequired" })
    }
  })

const stepSchema = z.object({
  action: z.string().trim().min(1, "stepActionRequired").max(LIMITS.stepAction, "stepActionTooLong"),
  expected: z.string().max(LIMITS.stepExpected, "stepExpectedTooLong"),
  auto: autoSchema.nullish(),
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
})
