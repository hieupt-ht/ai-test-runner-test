"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useQueryClient } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { useEffect, useState } from "react"
import { Controller, useForm } from "react-hook-form"
import { toast } from "sonner"

import { EnumSelect } from "@/components/test-cases/enum-select"
import { ConflictDialog } from "@/components/test-cases/conflict-dialog"
import { MediaPicker } from "@/components/media/media-picker"
import { StepsEditor } from "@/components/test-cases/steps-editor"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import type {
  Platform,
  Priority,
  Screen,
  Severity,
  TestCase,
  TestCaseContent,
  TestType,
} from "@/lib/api/types"
import { useProject } from "@/lib/use-projects"
import { conflictFrom } from "@/lib/test-cases/conflict"
import { testCaseFormSchema } from "@/lib/test-cases/form-schema"
import {
  useCreateTestCase,
  useRefreshCases,
  useTransitionTestCase,
  useUpdateTestCase,
} from "@/lib/use-test-cases"

const SEVERITIES: Severity[] = ["LOW", "MEDIUM", "HIGH"]
const PRIORITIES: Priority[] = ["P1", "P2", "P3"]
const PLATFORMS: Platform[] = ["WEB", "ANDROID", "IOS"]
const TEST_TYPES: TestType[] = ["FUNCTIONAL", "UI"]

const EMPTY: TestCaseContent = {
  title: "",
  precondition: "",
  test_data: "",
  steps: [{ action: "", expected: "", guide_media: [] }],
  expected_result: "",
  severity: "MEDIUM",
  priority: "P2",
  platform: "WEB",
  test_type: "FUNCTIONAL",
  regression: false,
  start_point: "",
  guide_media: [],
  postcondition: "",
  requirement_ref: "",
}

function contentOf(testCase: TestCase): TestCaseContent {
  return {
    title: testCase.title,
    precondition: testCase.precondition,
    test_data: testCase.test_data,
    // Bước cũ có thể chưa có guide_media: bù mảng rỗng để form luôn đủ trường
    steps: testCase.steps.map((step) => ({ ...step, guide_media: step.guide_media ?? [] })),
    expected_result: testCase.expected_result,
    severity: testCase.severity,
    priority: testCase.priority,
    platform: testCase.platform ?? "WEB",
    test_type: testCase.test_type ?? "FUNCTIONAL",
    regression: testCase.regression ?? false,
    start_point: testCase.start_point ?? "",
    guide_media: testCase.guide_media ?? [],
    postcondition: testCase.postcondition ?? "",
    requirement_ref: testCase.requirement_ref ?? "",
  }
}

type Props = {
  projectId: string
  /** Có thì là sửa case này; không có thì là tạo mới */
  testCase?: TestCase
  /** Chỉ dùng khi tạo mới */
  screens?: Screen[]
  defaultScreenId?: string
  /** Báo cho trang cha biết form có thay đổi chưa lưu */
  onDirtyChange?: (dirty: boolean) => void
  /** Dự án có bước QA duyệt không (mặc định có). Tắt thì "Gửi" là duyệt luôn. */
  reviewEnabled?: boolean
}

export function CaseForm({
  projectId,
  testCase,
  screens = [],
  defaultScreenId,
  onDirtyChange,
  reviewEnabled = true,
}: Props) {
  const t = useTranslations("testCases")
  const tc = useTranslations("common")
  const tm = useTranslations("media")
  const router = useRouter()
  const queryClient = useQueryClient()
  // Nơi lưu ảnh/video do Admin chọn cho dự án
  const storage = useProject(projectId).data?.storage ?? "cloudinary"
  const isEdit = Boolean(testCase)

  const form = useForm<TestCaseContent>({
    resolver: zodResolver(testCaseFormSchema),
    defaultValues: testCase ? contentOf(testCase) : EMPTY,
  })
  const { register, control, handleSubmit, reset, formState } = form
  const { errors } = formState

  const [screenId, setScreenId] = useState(defaultScreenId ?? "")
  const [screenMissing, setScreenMissing] = useState(false)
  // Version đang có: gửi kèm khi lưu, khác bản trên server thì bị 409.
  const [version, setVersion] = useState(testCase?.version ?? 0)
  const [conflict, setConflict] = useState<{ message: string; latest: TestCase } | null>(null)

  const caseId = testCase?.id ?? ""
  // Không tự làm mới sau từng bước: làm mới giữa chừng sẽ nạp lại form khi còn đang "lưu rồi gửi duyệt".
  const create = useCreateTestCase(projectId, { refresh: false })
  const update = useUpdateTestCase(projectId, caseId, { refresh: false })
  const transition = useTransitionTestCase(projectId, { refresh: false })
  const refreshCases = useRefreshCases(projectId)
  const isDirty = formState.isDirty
  useEffect(() => {
    onDirtyChange?.(isDirty)
    return () => onDirtyChange?.(false)
  }, [isDirty, onDirtyChange])
  // Ô chọn ảnh/video nào đang tải lên thì khoá nút Lưu/Gửi, kẻo lưu thiếu file.
  const [uploading, setUploading] = useState<Record<string, boolean>>({})
  function reportUploading(key: string, busy: boolean) {
    setUploading((prev) => (Boolean(prev[key]) === busy ? prev : { ...prev, [key]: busy }))
  }
  const isUploading = Object.values(uploading).some(Boolean)
  const busy = create.isPending || update.isPending || transition.isPending || isUploading

  function fail(error: unknown) {
    const found = conflictFrom(error)
    if (found) setConflict(found)
    else toast.error(error instanceof Error ? error.message : String(error))
  }

  function reloadFromLatest() {
    if (!conflict) return
    reset(contentOf(conflict.latest)) // bỏ phần đang sửa, đúng spec: không so sánh hay gộp
    setVersion(conflict.latest.version)
    setConflict(null)
    void queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
  }

  async function save(values: TestCaseContent, thenSubmit: boolean) {
    if (!isEdit && !screenId) {
      setScreenMissing(true)
      return
    }
    let saved: TestCase
    try {
      if (testCase) {
        saved = await update.mutateAsync({ ...values, version })
        setVersion(saved.version)
      } else {
        saved = await create.mutateAsync({ ...values, screen_id: screenId })
      }
    } catch (error) {
      fail(error)
      return
    }

    if (thenSubmit) {
      try {
        // Mã lấy từ kết quả lưu (case mới tạo chưa có mã trước đó).
        saved = await transition.mutateAsync({
          caseId: saved.id,
          action: "submit",
          version: saved.version,
        })
        setVersion(saved.version)
      } catch (error) {
        // Đã lưu nhưng chưa gửi duyệt được. Toast vẫn hiện dù form có bị nạp lại.
        toast.warning(t("form.savedNotSubmitted"))
        if (isEdit) {
          fail(error) // không làm mới ở đây để hộp thoại xung đột (nếu có) không bị mất
        } else {
          refreshCases()
          fail(error)
          router.push(`/projects/${projectId}/test-cases/${saved.id}`)
        }
        return
      }
    }
    toast.success(
      thenSubmit ? t("form.submitted") : isEdit ? tc("saved") : t("form.created", { id: saved.id }),
    )
    refreshCases()
    router.push(`/projects/${projectId}/test-cases/${saved.id}`)
  }

  const stepErrors = Array.isArray(errors.steps)
    ? errors.steps.map((e) => ({ action: e?.action?.message, expected: e?.expected?.message }))
    : []
  const fieldError = (message?: string) =>
    message ? <p className="text-xs text-destructive">{t(`form.errors.${message}`)}</p> : null
  const showSubmitButton = !isEdit || testCase?.status === "DRAFT"

  return (
    <form
      onSubmit={handleSubmit((values) => save(values, false))}
      className="flex flex-col gap-3"
      noValidate
    >
      {/* Thanh nút dính ở trên: cuộn đến đâu vẫn bấm Lưu được */}
      <div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b bg-background py-2">
        <Button type="submit" variant="outline" disabled={busy}>
          {t("form.saveDraft")}
        </Button>
        {showSubmitButton && (
          <Button
            type="button"
            disabled={busy}
            onClick={handleSubmit((values) => save(values, true))}
          >
            {reviewEnabled ? t("form.saveAndSubmit") : t("form.saveAndSend")}
          </Button>
        )}
        {reviewEnabled && isEdit && testCase?.status !== "DRAFT" && (
          <p className="text-sm text-amber-700 dark:text-amber-300">{t("form.resetWarning")}</p>
        )}
      </div>

      {/* Hai cột trên màn hình rộng; chỉ phần bên trong cột cuộn, cả trang không cuộn */}
      <div className="grid gap-5 lg:h-[calc(100dvh-15rem)] lg:min-h-96 lg:grid-cols-2">
        <div className="flex min-h-0 flex-col gap-4 lg:overflow-y-auto lg:pr-2">
          {!isEdit && (
            <div className="flex flex-col gap-1.5">
              <Label>{t("form.screen")}</Label>
              <Select
                items={screens.map((s) => ({ value: s.id, label: `${s.id} · ${s.name}` }))}
                value={screenId || null}
                onValueChange={(next) => {
                  setScreenId(next ?? "")
                  setScreenMissing(false)
                }}
              >
                <SelectTrigger className="w-full" aria-label={t("form.screen")}>
                  <SelectValue placeholder={t("form.screenPlaceholder")} />
                </SelectTrigger>
                <SelectContent>
                  {screens.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.id} · {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {screens.length === 0 && (
                <p className="text-sm text-muted-foreground">{t("form.noScreens")}</p>
              )}
              {screenMissing && fieldError("screenRequired")}
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="case-title">{t("form.title")}</Label>
            <Input id="case-title" aria-invalid={Boolean(errors.title)} {...register("title")} />
            {fieldError(errors.title?.message)}
          </div>

          <div className="flex flex-wrap items-end gap-4">
            <EnumSelect
              control={control}
              name="platform"
              label={t("form.platform")}
              options={PLATFORMS.map((value) => ({ value, label: t(`platform.${value}`) }))}
            />
            <EnumSelect
              control={control}
              name="test_type"
              label={t("form.testType")}
              options={TEST_TYPES.map((value) => ({ value, label: t(`testType.${value}`) }))}
            />
            <EnumSelect
              control={control}
              name="severity"
              label={t("form.severity")}
              options={SEVERITIES.map((value) => ({ value, label: t(`severity.${value}`) }))}
            />
            <EnumSelect
              control={control}
              name="priority"
              label={t("form.priority")}
              options={PRIORITIES.map((value) => ({ value, label: value }))}
            />
            <div className="flex h-8 items-center gap-2">
              <input
                id="case-regression"
                type="checkbox"
                className="size-4"
                {...register("regression")}
              />
              <Label htmlFor="case-regression">{t("form.regression")}</Label>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="case-start-point">{t("form.startPoint")}</Label>
            <Input id="case-start-point" {...register("start_point")} />
            <p className="text-xs text-muted-foreground">{t("form.startPointHint")}</p>
            {fieldError(errors.start_point?.message)}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>{t("form.guideMedia")}</Label>
            <Controller
              control={control}
              name="guide_media"
              render={({ field }) => (
                <MediaPicker
                  value={field.value ?? []}
                  onChange={field.onChange}
                  projectId={projectId}
                  storage={storage}
                  onBusyChange={(busy) => reportUploading("case", busy)}
                />
              )}
            />
            <p className="text-xs text-muted-foreground">{tm("safetyNote")}</p>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="case-expected">{t("form.expectedResult")}</Label>
            <Textarea
              id="case-expected"
              rows={3}
              aria-invalid={Boolean(errors.expected_result)}
              {...register("expected_result")}
            />
            {fieldError(errors.expected_result?.message)}
          </div>

          <details className="rounded-lg border p-3">
            <summary className="cursor-pointer text-sm font-medium">{t("form.more")}</summary>
            <div className="mt-3 flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="case-precondition">{t("form.precondition")}</Label>
                <Textarea id="case-precondition" rows={3} {...register("precondition")} />
                {fieldError(errors.precondition?.message)}
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="case-test-data">{t("form.testData")}</Label>
                <Textarea id="case-test-data" rows={3} {...register("test_data")} />
                {fieldError(errors.test_data?.message)}
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="case-postcondition">{t("form.postcondition")}</Label>
                <Textarea id="case-postcondition" rows={3} {...register("postcondition")} />
                {fieldError(errors.postcondition?.message)}
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="case-requirement-ref">{t("form.requirementRef")}</Label>
                <Input id="case-requirement-ref" {...register("requirement_ref")} />
                {fieldError(errors.requirement_ref?.message)}
              </div>
            </div>
          </details>
        </div>

        {/* Cột phải: các bước, cuộn riêng */}
        <div className="flex min-h-0 flex-col gap-1.5 lg:overflow-y-auto lg:pr-2">
          <Label>{t("form.steps")}</Label>
          <Controller
            control={control}
            name="steps"
            render={({ field }) => (
              <StepsEditor
                steps={field.value}
                onChange={field.onChange}
                errors={stepErrors}
                projectId={projectId}
                storage={storage}
                onBusyChange={reportUploading}
              />
            )}
          />
          {!Array.isArray(errors.steps) && fieldError(errors.steps?.message)}
        </div>
      </div>

      <ConflictDialog
        message={conflict?.message ?? null}
        onReload={reloadFromLatest}
        onClose={() => setConflict(null)}
      />
    </form>
  )
}
