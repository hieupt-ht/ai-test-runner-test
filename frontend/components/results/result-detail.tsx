"use client"

import { useState } from "react"
import { useTranslations } from "next-intl"

import { MediaLightbox } from "@/components/media/media-lightbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"
import { safeEvidenceUrl } from "@/lib/safe-url"
import type { Media, ResultItem } from "@/lib/api/types"

type Props = {
  result: ResultItem | null
  onClose: () => void
}

/** Bảng chi tiết một kết quả, trượt ra bên phải (toàn màn hình trên điện thoại). */
export function ResultDetail({ result, onClose }: Props) {
  const [zoomed, setZoomed] = useState<Media | null>(null)

  return (
    <>
      <Dialog open={result !== null} onOpenChange={(open) => !open && onClose()}>
        <DialogContent
          className="top-0 right-0 left-auto h-dvh max-w-none translate-x-0 translate-y-0 content-start overflow-y-auto rounded-none sm:max-w-xl"
        >
          {result && <Body result={result} onZoom={setZoomed} />}
        </DialogContent>
      </Dialog>
      <MediaLightbox media={zoomed} onClose={() => setZoomed(null)} />
    </>
  )
}

function Body({ result, onZoom }: { result: ResultItem; onZoom: (media: Media) => void }) {
  const t = useTranslations("results")
  const summary = [
    result.status,
    result.case_version === null ? null : `v${result.case_version}`,
    result.environment || null,
  ]
    .filter(Boolean)
    .join(" · ")
  const { evidence } = result
  const screenshots = evidence.screenshots ?? []
  const legacyUrl = evidence.legacy_url ? safeEvidenceUrl(evidence.legacy_url) : null

  return (
    <>
      <div className="space-y-1">
        <DialogTitle>
          {result.case_id} · {result.case_title}
        </DialogTitle>
        <DialogDescription>{summary}</DialogDescription>
        {result.dev_owner && (
          <p className="text-sm">{t("detail.devOwner", { name: result.dev_owner })}</p>
        )}
        {result.executed_by && (
          <p className="text-sm text-muted-foreground">
            {t("detail.executedBy", { name: result.executed_by })}
          </p>
        )}
      </div>

      {result.reason && (
        <p className="text-sm">
          <span className="font-medium">{t("reasonColumn")}:</span> {result.reason}
        </p>
      )}
      {result.actual_result && (
        <p className="text-sm">
          <span className="font-medium">{t("detail.actualResult")}:</span> {result.actual_result}
        </p>
      )}

      {evidence.pruned && (
        <p className="rounded-lg border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
          {t("detail.pruned")}
        </p>
      )}
      {legacyUrl && (
        <a
          href={legacyUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm underline-offset-2 hover:underline"
        >
          {t("detail.legacyEvidence")}
        </a>
      )}
      {evidence.video && (
        <video controls src={evidence.video.url} className="max-h-72 w-full rounded-lg bg-black" />
      )}

      {result.step_results.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground">
              <th className="py-1 pr-2">{t("detail.step")}</th>
              <th className="py-1 pr-2">{t("detail.stepStatus")}</th>
              <th className="py-1 pr-2">{t("detail.stepActual")}</th>
              <th className="py-1">{t("detail.stepImage")}</th>
            </tr>
          </thead>
          <tbody>
            {result.step_results.map((step) => (
              <tr key={step.step_no} className="border-b align-top">
                <td className="py-1.5 pr-2">{step.step_no}</td>
                <td className="py-1.5 pr-2">
                  {step.status === "SKIPPED" ? t("detail.skipped") : step.status}
                </td>
                <td className="py-1.5 pr-2 whitespace-normal">{step.actual || "—"}</td>
                <td className="py-1.5">
                  {step.screenshot && (
                    <button
                      type="button"
                      aria-label={t("detail.viewStepImage", { step: step.step_no })}
                      onClick={() => step.screenshot && onZoom(step.screenshot)}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element -- ảnh ngoài từ Cloudinary */}
                      <img
                        src={step.screenshot.url}
                        alt=""
                        className="h-12 w-20 rounded border object-cover"
                      />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {screenshots.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {screenshots.map((shot) => (
            <button
              key={shot.public_id}
              type="button"
              aria-label={t("detail.viewScreenshot")}
              onClick={() => onZoom(shot)}
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- ảnh ngoài từ Cloudinary */}
              <img src={shot.url} alt="" className="h-16 w-24 rounded border object-cover" />
            </button>
          ))}
        </div>
      )}

      {safeEvidenceUrl(result.issue_url) && (
        <a
          href={result.issue_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm underline-offset-2 hover:underline"
        >
          {t("detail.openIssue")}
        </a>
      )}
    </>
  )
}
