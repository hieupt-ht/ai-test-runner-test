"use client"

import { ArchiveRestore, ShieldAlert, Trash2 } from "lucide-react"
import Link from "next/link"
import { useTranslations } from "next-intl"

import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { CreateProjectDialog } from "@/components/projects/create-project-dialog"
import { DeleteProjectDialog } from "@/components/projects/delete-project-dialog"
import { useMe } from "@/lib/use-me"
import { toast } from "sonner"

import { useProjects, useUpdateProject } from "@/lib/use-projects"
import type { Project } from "@/lib/api/types"

/** Ô chọn nơi lưu ảnh/video của một dự án. Giá trị lấy từ danh sách nên lỗi thì tự quay về giá trị cũ. */
function StorageSelect({ project }: { project: Project }) {
  const t = useTranslations("projects")
  const update = useUpdateProject(project.id)

  async function change(storage: Project["storage"]) {
    try {
      await update.mutateAsync({ storage })
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("storageFailed"))
    }
  }

  return (
    <select
      aria-label={t("storageLabel", { name: project.name })}
      value={project.storage}
      disabled={update.isPending}
      onChange={(event) => void change(event.target.value as Project["storage"])}
      className="h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm"
    >
      <option value="cloudinary">{t("storageCloudinary")}</option>
      <option value="drive">{t("storageDrive")}</option>
    </select>
  )
}

/** Nút chuyển vào thùng rác (dự án đang dùng) hoặc khôi phục + xoá vĩnh viễn (dự án trong thùng rác). */
function ProjectActions({ project }: { project: Project }) {
  const t = useTranslations("projects")
  const update = useUpdateProject(project.id)

  async function setArchived(archived: boolean) {
    try {
      await update.mutateAsync({ archived })
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("actionFailed"))
    }
  }

  if (!project.archived) {
    return (
      <Button
        variant="outline"
        size="sm"
        disabled={update.isPending}
        onClick={() => void setArchived(true)}
      >
        <Trash2 /> {t("moveToTrash")}
      </Button>
    )
  }
  return (
    <div className="flex flex-wrap gap-2">
      <Button
        variant="outline"
        size="sm"
        disabled={update.isPending}
        onClick={() => void setArchived(false)}
      >
        <ArchiveRestore /> {t("restore")}
      </Button>
      <DeleteProjectDialog project={project} />
    </div>
  )
}

export default function AdminProjectsPage() {
  const t = useTranslations("projects")
  const { user } = useMe()
  const projectsQuery = useProjects()
  const [tab, setTab] = useState<"active" | "trash">("active")

  if (user?.role !== "ADMIN") {
    return (
      <Card className="mx-auto max-w-md">
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <ShieldAlert className="size-8 text-muted-foreground" />
          <p>{t("notFound")}</p>
        </CardContent>
      </Card>
    )
  }

  const allProjects = projectsQuery.data ?? []
  const activeCount = allProjects.filter((p) => !p.archived).length
  const trashCount = allProjects.length - activeCount
  const projects = allProjects.filter((p) => p.archived === (tab === "trash"))

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <p className="text-sm text-muted-foreground">{t("description")}</p>
        <CreateProjectDialog />
      </div>

      <div className="flex gap-2">
        <Button
          variant={tab === "active" ? "default" : "outline"}
          size="sm"
          aria-pressed={tab === "active"}
          onClick={() => setTab("active")}
        >
          {t("tabActive", { count: activeCount })}
        </Button>
        <Button
          variant={tab === "trash" ? "default" : "outline"}
          size="sm"
          aria-pressed={tab === "trash"}
          onClick={() => setTab("trash")}
        >
          {t("tabTrash", { count: trashCount })}
        </Button>
      </div>

      {projectsQuery.isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <Table className="table-fixed">
            <TableHeader>
              <TableRow>
                <TableHead>{t("colName")}</TableHead>
                <TableHead>{t("colRepo")}</TableHead>
                <TableHead>{t("colBranch")}</TableHead>
                <TableHead>{t("colStatus")}</TableHead>
                <TableHead>{t("colStorage")}</TableHead>
                <TableHead>{t("colActions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {projects.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                    {tab === "trash" ? t("trashEmpty") : t("empty")}
                  </TableCell>
                </TableRow>
              )}
              {projects.map((project) => (
                <TableRow key={project.id}>
                  {/* Cho phép xuống dòng để bảng không rộng hơn khung (không cuộn ngang) */}
                  <TableCell className="font-medium whitespace-normal break-words">
                    <Link href={`/projects/${project.id}`} className="hover:underline">
                      {project.name}
                    </Link>
                    <span className="ml-2 text-xs text-muted-foreground">{project.id}</span>
                  </TableCell>
                  <TableCell className="font-mono text-xs whitespace-normal break-all">
                    {project.repo_full_name}
                  </TableCell>
                  <TableCell className="font-mono text-xs whitespace-normal break-all">
                    {project.branch}
                  </TableCell>
                  <TableCell>
                    <Badge variant={project.archived ? "secondary" : "outline"}>
                      {project.archived ? t("archived") : t("active")}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <StorageSelect project={project} />
                  </TableCell>
                  <TableCell className="whitespace-normal">
                    <ProjectActions project={project} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
