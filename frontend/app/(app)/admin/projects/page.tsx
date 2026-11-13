"use client"

import { ShieldAlert } from "lucide-react"
import Link from "next/link"
import { useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
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
import { useMe } from "@/lib/use-me"
import { useProjects } from "@/lib/use-projects"

export default function AdminProjectsPage() {
  const t = useTranslations("projects")
  const { user } = useMe()
  const projectsQuery = useProjects()

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

  const projects = projectsQuery.data ?? []

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <p className="text-sm text-muted-foreground">{t("description")}</p>
        <CreateProjectDialog />
      </div>

      {projectsQuery.isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("colName")}</TableHead>
                <TableHead>{t("colRepo")}</TableHead>
                <TableHead>{t("colBranch")}</TableHead>
                <TableHead>{t("colStatus")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {projects.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="py-10 text-center text-muted-foreground">
                    {t("empty")}
                  </TableCell>
                </TableRow>
              )}
              {projects.map((project) => (
                <TableRow key={project.id}>
                  <TableCell className="font-medium">
                    <Link href={`/projects/${project.id}`} className="hover:underline">
                      {project.name}
                    </Link>
                    <span className="ml-2 text-xs text-muted-foreground">{project.id}</span>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{project.repo_full_name}</TableCell>
                  <TableCell className="font-mono text-xs">{project.branch}</TableCell>
                  <TableCell>
                    <Badge variant={project.archived ? "secondary" : "outline"}>
                      {project.archived ? t("archived") : t("active")}
                    </Badge>
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
