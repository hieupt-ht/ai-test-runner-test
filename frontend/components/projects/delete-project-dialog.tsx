"use client"

import { Trash2 } from "lucide-react"
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
import type { Project } from "@/lib/api/types"
import { useDeleteProject } from "@/lib/use-projects"

/** Nút "Xoá vĩnh viễn" của dự án trong thùng rác: phải gõ đúng tên dự án mới xoá được. */
export function DeleteProjectDialog({ project }: { project: Project }) {
  const t = useTranslations("projects")
  const tc = useTranslations("common")
  const remove = useDeleteProject(project.id)
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState("")

  const matches = typed.trim() === project.name

  function handleOpenChange(next: boolean) {
    if (next) setTyped("") // mở lại thì ô gõ tên luôn trống
    setOpen(next)
  }

  async function confirm() {
    try {
      await remove.mutateAsync(project.name)
      toast.success(t("deleteDone", { name: project.name }))
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("actionFailed"))
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={<Button variant="destructive" size="sm" />}>
        <Trash2 /> {t("deleteForever")}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("deleteTitle", { name: project.name })}</DialogTitle>
          <DialogDescription>{t("deleteWarning")}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2">
          <Label htmlFor={`delete-${project.id}`}>{t("deleteTypeName")}</Label>
          <Input
            id={`delete-${project.id}`}
            value={typed}
            placeholder={project.name}
            onChange={(event) => setTyped(event.target.value)}
          />
        </div>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>{tc("cancel")}</DialogClose>
          <Button
            variant="destructive"
            disabled={!matches || remove.isPending}
            onClick={() => void confirm()}
          >
            {t("deleteForever")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
