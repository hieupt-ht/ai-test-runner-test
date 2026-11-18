"use client"

import { Archive, ArchiveRestore, Lock } from "lucide-react"
import { useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { ProjectDetail } from "@/lib/api/types"
import { useProjectId } from "@/lib/use-project-id"
import { useGithubBranches, useProject, useUpdateProject } from "@/lib/use-projects"

export default function ProjectSettingsPage() {
  const projectId = useProjectId()
  const { data: project } = useProject(projectId)

  if (!project || !project.permissions.includes("MANAGE_PROJECT_SETTINGS")) return null
  const isAdmin = project.permissions.includes("MANAGE_PROJECTS")
  // key: dựng lại form khi dữ liệu dự án đổi (ví dụ vừa lưu xong)
  const formKey = `${project.name}|${project.branch}|${project.staging_url}`
  return (
    <div className="flex flex-col gap-6">
      {isAdmin && <SettingsForm key={formKey} project={project} />}
      <ReviewAndAppIdsCard
        key={`${project.require_review}|${project.android_app_id}|${project.ios_bundle_id}`}
        project={project}
      />
    </div>
  )
}

const APP_ID_PATTERN = /^[A-Za-z0-9._-]*$/

/** Công tắc "Cần QA duyệt" và mã app mobile: QA Lead cũng sửa được. */
function ReviewAndAppIdsCard({ project }: { project: ProjectDetail }) {
  const t = useTranslations("projects")
  const [androidId, setAndroidId] = useState(project.android_app_id)
  const [iosId, setIosId] = useState(project.ios_bundle_id)
  const updateProject = useUpdateProject(project.id)
  const idsValid = APP_ID_PATTERN.test(androidId.trim()) && APP_ID_PATTERN.test(iosId.trim())

  async function save(changes: Parameters<typeof updateProject.mutateAsync>[0]) {
    try {
      await updateProject.mutateAsync(changes)
      toast.success(t("saved"))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <Card>
      <CardContent className="flex max-w-lg flex-col gap-4 pt-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <Label htmlFor="require-review">{t("requireReview")}</Label>
            <p className="text-xs text-muted-foreground">{t("requireReviewHint")}</p>
          </div>
          <Switch
            id="require-review"
            checked={project.require_review}
            disabled={project.archived || updateProject.isPending}
            onCheckedChange={(checked) => void save({ require_review: checked })}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="android-app-id">{t("fieldAndroidAppId")}</Label>
          <Input
            id="android-app-id"
            value={androidId}
            disabled={project.archived}
            onChange={(e) => setAndroidId(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="ios-bundle-id">{t("fieldIosBundleId")}</Label>
          <Input
            id="ios-bundle-id"
            value={iosId}
            disabled={project.archived}
            onChange={(e) => setIosId(e.target.value)}
          />
        </div>
        {!idsValid && <p className="text-xs text-destructive">{t("appIdInvalid")}</p>}
        <div>
          <Button
            disabled={!idsValid || updateProject.isPending || project.archived}
            onClick={() =>
              void save({ android_app_id: androidId.trim(), ios_bundle_id: iosId.trim() })
            }
          >
            {t("save")}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function SettingsForm({ project }: { project: ProjectDetail }) {
  const t = useTranslations("projects")
  const [name, setName] = useState(project.name)
  const [branch, setBranch] = useState<string | null>(project.branch)
  const [stagingUrl, setStagingUrl] = useState(project.staging_url)
  const branches = useGithubBranches(project.repo_full_name)
  const updateProject = useUpdateProject(project.id)

  const branchItems = (branches.data ?? [project.branch]).map((item) => ({
    value: item,
    label: item,
  }))

  async function save(changes: Parameters<typeof updateProject.mutateAsync>[0]) {
    try {
      await updateProject.mutateAsync(changes)
      toast.success(t("saved"))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  function submit(event: React.FormEvent) {
    event.preventDefault()
    void save({ name: name.trim(), branch: branch ?? project.branch, staging_url: stagingUrl.trim() })
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{t("settingsTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="flex max-w-lg flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="settings-name">{t("fieldName")}</Label>
              <Input
                id="settings-name"
                value={name}
                disabled={project.archived}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>{t("fieldBranch")}</Label>
              <Select
                items={branchItems}
                value={branch}
                onValueChange={setBranch}
                disabled={project.archived}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {branchItems.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="settings-staging">{t("fieldStagingUrl")}</Label>
              <Input
                id="settings-staging"
                type="url"
                value={stagingUrl}
                disabled={project.archived}
                onChange={(e) => setStagingUrl(e.target.value)}
              />
            </div>
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Lock className="size-3.5" /> {t("repoLocked")}
            </p>
            <div>
              <Button type="submit" disabled={updateProject.isPending || project.archived}>
                {t("save")}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col gap-3 pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">{t("archiveConfirm")}</p>
          {project.archived ? (
            <Button variant="outline" onClick={() => save({ archived: false })}>
              <ArchiveRestore /> {t("unarchive")}
            </Button>
          ) : (
            <Dialog>
              <DialogTrigger render={<Button variant="destructive" />}>
                <Archive /> {t("archive")}
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{t("archiveConfirmTitle")}</DialogTitle>
                  <DialogDescription>{t("archiveConfirm")}</DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <DialogClose render={<Button variant="outline" />}>{t("cancel")}</DialogClose>
                  <DialogClose
                    render={<Button variant="destructive" />}
                    onClick={() => save({ archived: true })}
                  >
                    {t("confirm")}
                  </DialogClose>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
