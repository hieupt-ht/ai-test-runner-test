"use client"

import { useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { Run } from "@/lib/api/types"
import { useCreateRegressionRun, useFinishRegressionRun, useOpenRegressionRuns } from "@/lib/use-results"

type DialogProps = {
  projectId: string
  /** Gọi sau khi tạo xong để trang chọn sẵn bộ lọc theo run mới */
  onCreated: (run: Run) => void
}

/** Nút + hộp thoại "Chạy bộ regression": nhập bản build rồi tạo một lần chạy. */
export function RegressionDialog({ projectId, onCreated }: DialogProps) {
  const t = useTranslations("results.regression")
  const tc = useTranslations("common")
  const create = useCreateRegressionRun(projectId)
  const [open, setOpen] = useState(false)
  const [build, setBuild] = useState("")
  const buildVersion = build.trim()

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!buildVersion) return
    try {
      const run = await create.mutateAsync({ build_version: buildVersion })
      toast.success(t("created", { run: run.id }))
      setOpen(false)
      setBuild("")
      onCreated(run)
    } catch (error) {
      toast.error(error instanceof Error && error.message ? error.message : t("createError"))
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button type="button" variant="outline" />}>{t("open")}</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>{t("description")}</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="regression-build">{t("fieldBuild")}</Label>
            <Input
              id="regression-build"
              value={build}
              maxLength={50}
              placeholder={t("buildPlaceholder")}
              onChange={(event) => setBuild(event.target.value)}
            />
          </div>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button" />}>{tc("cancel")}</DialogClose>
            <Button type="submit" disabled={!buildVersion || create.isPending}>
              {t("submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

type OpenRunsProps = {
  projectId: string
  /** Chỉ QA Lead/Admin được kết thúc lần chạy */
  canManage: boolean
}

/** Danh sách lần chạy regression đang mở; mỗi dòng có nút "Kết thúc" (nếu có quyền). */
export function OpenRegressionRuns({ projectId, canManage }: OpenRunsProps) {
  const t = useTranslations("results.regression")
  const { data: runs = [] } = useOpenRegressionRuns(projectId)
  const finish = useFinishRegressionRun(projectId)

  if (runs.length === 0) return null

  async function finishRun(runId: string) {
    try {
      await finish.mutateAsync(runId)
      toast.success(t("finished"))
    } catch (error) {
      toast.error(error instanceof Error && error.message ? error.message : t("finishError"))
    }
  }

  return (
    <ul className="space-y-2">
      {runs.map((run) => (
        <li
          key={run.id}
          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-muted/30 px-4 py-2 text-sm"
        >
          <span>
            {t("running", {
              run: run.id,
              build: run.build_version,
              done: run.passed + run.failed,
              total: run.total,
            })}
          </span>
          {canManage && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={finish.isPending}
              aria-label={t("finishLabel", { run: run.id })}
              onClick={() => finishRun(run.id)}
            >
              {t("finish")}
            </Button>
          )}
        </li>
      ))}
    </ul>
  )
}
