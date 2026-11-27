"use client"

import { useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import { MediaPicker } from "@/components/media/media-picker"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type {
  ManualResultResponse,
  Media,
  StepResult,
  TestCase,
} from "@/lib/api/types"
import type { Storage } from "@/lib/media/upload"
import {
  isValidAssignee,
  limitEvidence,
  normalizeAssignee,
  splitEvidence,
} from "@/lib/test-cases/manual-run"
import { useSubmitManualResult } from "@/lib/use-manual-result"

type StepStatus = StepResult["status"]
type CaseResult = "PASS" | "FAIL" | "BLOCKED"

const STEP_OPTIONS: { status: StepStatus; key: "stepPass" | "stepFail" | "stepSkipped" }[] = [
  { status: "PASS", key: "stepPass" },
  { status: "FAIL", key: "stepFail" },
  { status: "SKIPPED", key: "stepSkipped" },
]
const RESULT_OPTIONS: { value: CaseResult; key: "resultPass" | "resultFail" | "resultBlocked" }[] = [
  { value: "PASS", key: "resultPass" },
  { value: "FAIL", key: "resultFail" },
  { value: "BLOCKED", key: "resultBlocked" },
]
const ENVIRONMENT_KEY = "manual-run-environment"

// Trình duyệt có thể chặn lưu trữ (cửa sổ riêng tư...): lỗi thì coi như không có.
function loadEnvironment(): string {
  try {
    return localStorage.getItem(ENVIRONMENT_KEY) ?? ""
  } catch {
    return ""
  }
}
function saveEnvironment(value: string) {
  try {
    localStorage.setItem(ENVIRONMENT_KEY, value)
  } catch {
    /* không nhớ được thì thôi */
  }
}

type Props = {
  projectId: string
  /** Nơi lưu ảnh/video của dự án. */
  storage?: Storage
  testCase: TestCase
  /** Người được giao khi Fail: mặc định là dev phụ trách màn hình. */
  defaultAssignee?: string
  onDone?: (reply: ManualResultResponse) => void
}

/** Khung tester làm theo từng bước của case test tay rồi gửi kết quả kèm bằng chứng. */
export function ManualRunPanel({
  projectId,
  storage = "cloudinary",
  testCase,
  defaultAssignee = "",
  onDone,
}: Props) {
  const t = useTranslations("manualRun")
  const submit = useSubmitManualResult(projectId, testCase.id)
  const steps = testCase.steps

  const [environment, setEnvironment] = useState(loadEnvironment)
  const [buildVersion, setBuildVersion] = useState("")
  const [stepStatus, setStepStatus] = useState<Record<number, StepStatus>>({})
  const [stepActual, setStepActual] = useState<Record<number, string>>({})
  const [stepShot, setStepShot] = useState<Record<number, Media>>({})
  // Người dùng tự chọn thì giữ; chưa chọn thì dùng gợi ý tính từ kết quả các bước.
  const [resultChoice, setResultChoice] = useState<CaseResult | null>(null)
  const [failedChoice, setFailedChoice] = useState<number | null>(null)
  const [reason, setReason] = useState("")
  const [actualResult, setActualResult] = useState("")
  const [evidence, setEvidence] = useState<Media[]>([])
  const [assignee, setAssignee] = useState(defaultAssignee)
  const [uploading, setUploading] = useState<Record<string, boolean>>({})

  const stepNumbers = steps.map((_, index) => index + 1)
  const allAnswered = stepNumbers.every((n) => stepStatus[n] !== undefined)
  const firstFail = stepNumbers.find((n) => stepStatus[n] === "FAIL") ?? null
  const hasSkipped = stepNumbers.some((n) => stepStatus[n] === "SKIPPED")
  const suggestedResult: CaseResult | null = firstFail
    ? "FAIL"
    : allAnswered && !hasSkipped
      ? "PASS"
      : null
  const result = resultChoice ?? suggestedResult
  const failedStep = failedChoice ?? firstFail

  const cleanAssignee = normalizeAssignee(assignee)
  const assigneeOk = isValidAssignee(cleanAssignee)
  const isUploading = Object.values(uploading).some(Boolean)
  // Fail phải có ít nhất một ảnh/video: ở phần bằng chứng chung hoặc ảnh của từng bước
  const hasMedia = evidence.length > 0 || Object.keys(stepShot).length > 0
  const failOk =
    result !== "FAIL" || (reason.trim() !== "" && failedStep !== null)
  const canSubmit =
    allAnswered &&
    environment.trim() !== "" &&
    result !== null &&
    failOk &&
    assigneeOk &&
    !isUploading &&
    !submit.isPending

  function reportUploading(key: string, busy: boolean) {
    setUploading((prev) => (Boolean(prev[key]) === busy ? prev : { ...prev, [key]: busy }))
  }

  function chooseStep(step: number, status: StepStatus) {
    setStepStatus((prev) => ({ ...prev, [step]: status }))
    // Bước lỗi đã chọn mà nay hết "Không đạt" thì bỏ, để gợi ý lấy lại bước Không đạt đầu tiên còn lại
    if (failedChoice === step && status !== "FAIL") setFailedChoice(null)
  }

  function changeEvidence(next: Media[]) {
    const limited = limitEvidence(next)
    if (limited.length < next.length) toast.warning(t("evidenceLimit"))
    setEvidence(limited)
  }

  function reset() {
    setStepStatus({})
    setStepActual({})
    setStepShot({})
    setResultChoice(null)
    setFailedChoice(null)
    setReason("")
    setActualResult("")
    setEvidence([])
  }

  async function send() {
    if (!canSubmit || result === null) return
    const stepResults: StepResult[] = stepNumbers.map((n) => {
      const shot = stepShot[n]
      return {
        step_no: n,
        status: stepStatus[n],
        actual: stepActual[n] ?? "",
        ...(shot ? { screenshot: shot } : {}),
      }
    })
    try {
      const reply = await submit.mutateAsync({
        status: result,
        step_results: stepResults,
        actual_result: actualResult,
        reason,
        failed_step: result === "FAIL" ? failedStep : null,
        evidence: splitEvidence(evidence),
        environment: environment.trim(),
        build_version: buildVersion.trim(),
        assignee: cleanAssignee,
        version: testCase.version,
      })
      saveEnvironment(environment.trim())
      toast.success(t("success", { runId: reply.run_id }))
      reset()
      onDone?.(reply)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <section className="flex flex-col gap-4 rounded-lg border p-4" aria-label={t("title")}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">{t("title")}</h2>
          <p className="text-xs text-muted-foreground">{t("hint")}</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="run-environment">{t("environment")}</Label>
            <Input
              id="run-environment"
              className="w-60"
              value={environment}
              placeholder={t("environmentPlaceholder")}
              maxLength={200}
              onChange={(event) => setEnvironment(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="run-build">{t("buildVersion")}</Label>
            <Input
              id="run-build"
              className="w-44"
              value={buildVersion}
              maxLength={50}
              onChange={(event) => setBuildVersion(event.target.value)}
            />
          </div>
        </div>
      </div>

      <ol className="flex flex-col gap-3">
        {steps.map((step, index) => {
          const n = index + 1
          return (
            <li key={n} className="flex flex-col gap-2 rounded-md border p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    B{n} {step.action}
                  </p>
                  {step.expected && (
                    <p className="text-xs text-muted-foreground">{step.expected}</p>
                  )}
                </div>
                <div className="flex gap-3 text-sm" role="radiogroup" aria-label={`${t("step")} ${n}`}>
                  {STEP_OPTIONS.map((option) => (
                    <label key={option.status} className="flex items-center gap-1">
                      <input
                        type="radio"
                        name={`step-${n}`}
                        checked={stepStatus[n] === option.status}
                        aria-label={`${t("step")} ${n}: ${t(option.key)}`}
                        onChange={() => chooseStep(n, option.status)}
                      />
                      {t(option.key)}
                    </label>
                  ))}
                </div>
              </div>
              <Input
                value={stepActual[n] ?? ""}
                placeholder={`${t("stepActual")} ${n}`}
                aria-label={`${t("stepActual")} ${n}`}
                maxLength={500}
                onChange={(event) => setStepActual((prev) => ({ ...prev, [n]: event.target.value }))}
              />
              <div aria-label={`${t("stepScreenshot")} ${n}`}>
                <MediaPicker
                  value={stepShot[n] ? [stepShot[n]] : []}
                  onChange={(next) =>
                    setStepShot((prev) => {
                      const copy = { ...prev }
                      if (next[0]) copy[n] = next[0]
                      else delete copy[n]
                      return copy
                    })
                  }
                  max={1}
                  projectId={projectId}
                  storage={storage}
                  purpose="evidence"
                  onBusyChange={(busy) => reportUploading(`step-${n}`, busy)}
                />
              </div>
            </li>
          )
        })}
      </ol>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="run-actual">{t("actualResult")}</Label>
        <Textarea
          id="run-actual"
          rows={2}
          maxLength={2000}
          value={actualResult}
          onChange={(event) => setActualResult(event.target.value)}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label>{t("evidence")}</Label>
        <MediaPicker
          value={evidence}
          onChange={changeEvidence}
          max={21}
          projectId={projectId}
          storage={storage}
          purpose="evidence"
          onBusyChange={(busy) => reportUploading("evidence", busy)}
        />
        {result === "FAIL" && !hasMedia && (
          <p className="text-xs text-amber-700 dark:text-amber-400">{t("failEvidenceHint")}</p>
        )}
      </div>

      <fieldset className="flex flex-wrap items-center gap-4">
        <legend className="mb-1 text-sm font-medium">{t("result")}</legend>
        {RESULT_OPTIONS.map((option) => (
          <label key={option.value} className="flex items-center gap-1 text-sm">
            <input
              type="radio"
              name="case-result"
              checked={result === option.value}
              onChange={() => setResultChoice(option.value)}
            />
            {t(option.key)}
          </label>
        ))}
      </fieldset>

      {result === "FAIL" && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="run-failed-step">{t("failedStep")}</Label>
          <select
            id="run-failed-step"
            className="h-8 w-48 rounded-lg border border-input bg-transparent px-2 text-sm"
            value={failedStep === null ? "" : String(failedStep)}
            onChange={(event) =>
              setFailedChoice(event.target.value ? Number(event.target.value) : null)
            }
          >
            <option value="">{t("failedStepPlaceholder")}</option>
            {stepNumbers.map((n) => (
              <option key={n} value={String(n)}>
                {t("step")} {n}
              </option>
            ))}
          </select>
        </div>
      )}

      {(result === "FAIL" || result === "BLOCKED") && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="run-reason">{result === "FAIL" ? t("reason") : t("reasonBlocked")}</Label>
          <Textarea
            id="run-reason"
            rows={2}
            maxLength={2000}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="run-assignee">{t("assignee")}</Label>
        <Input
          id="run-assignee"
          className="w-60"
          value={assignee}
          maxLength={40}
          aria-invalid={!assigneeOk}
          onChange={(event) => setAssignee(event.target.value)}
        />
        {!assigneeOk && <p className="text-xs text-destructive">{t("assigneeInvalid")}</p>}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" disabled={!canSubmit} onClick={() => void send()}>
          {submit.isPending ? t("submitting") : t("submit")}
        </Button>
        {!canSubmit && !submit.isPending && (
          <p className="text-xs text-muted-foreground">{t("incomplete")}</p>
        )}
      </div>
    </section>
  )
}
