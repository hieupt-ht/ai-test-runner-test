"use client"

import { useTranslations } from "next-intl"

import type { AutoStep, TestCase } from "@/lib/api/types"

/** Hiển thị nội dung case ở chế độ chỉ đọc (không có quyền sửa, hoặc case đã ngừng dùng). */
export function CaseReadOnly({ testCase }: { testCase: TestCase }) {
  const t = useTranslations("testCases")

  /** Một dòng tóm tắt phần tự động, ví dụ: Nhập "qa@x.com" vào ô "Email". */
  function describeAuto(auto: AutoStep): string {
    const target = auto.target ? t(`auto.targets.${auto.target.by}`, { value: auto.target.value }) : ""
    return t(`auto.summary.${auto.type}`, { value: auto.value, target })
  }

  return (
    <div className="flex flex-col gap-4 text-sm">
      <h2 className="text-lg font-semibold">{testCase.title}</h2>
      <p className="text-xs text-muted-foreground">
        {testCase.screen_id} · {t(`severity.${testCase.severity}`)} · {testCase.priority}
      </p>
      <Field label={t("form.precondition")} value={testCase.precondition} />
      <Field label={t("form.testData")} value={testCase.test_data} />
      <div>
        <p className="mb-1 font-medium">{t("form.steps")}</p>
        <ol className="flex flex-col gap-2">
          {testCase.steps.map((step, index) => (
            <li key={index} className="rounded-lg border p-2">
              <p className="whitespace-pre-wrap">
                <span className="mr-2 font-mono text-xs text-muted-foreground">{index + 1}</span>
                {step.action}
              </p>
              {step.auto && (
                <p className="mt-1 text-xs text-muted-foreground">
                  <span aria-hidden className="mr-1">
                    ⚙
                  </span>
                  {describeAuto(step.auto)}
                </p>
              )}
              {step.expected && (
                <p className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">
                  {step.expected}
                </p>
              )}
            </li>
          ))}
        </ol>
      </div>
      <Field label={t("form.expectedResult")} value={testCase.expected_result} />
    </div>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  if (!value) return null
  return (
    <div>
      <p className="mb-1 font-medium">{label}</p>
      <p className="whitespace-pre-wrap">{value}</p>
    </div>
  )
}
