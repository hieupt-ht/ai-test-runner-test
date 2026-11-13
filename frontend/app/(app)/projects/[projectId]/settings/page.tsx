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

  if (!project || !project.permissions.includes("MANAGE_PROJECTS")) return null
  // key: dựng lại form khi dữ liệu dự án đổi (ví dụ vừa lưu xong)
  return <SettingsForm key={`${project.name}|${project.branch}|${project.staging_url}`} project={project} />
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
