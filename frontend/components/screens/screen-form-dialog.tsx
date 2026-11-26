"use client"

import { Plus, X } from "lucide-react"
import { useTranslations } from "next-intl"
import { useState, type ReactElement } from "react"
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
import { MediaPicker } from "@/components/media/media-picker"
import { MAX_CODE_PATHS, codePathError } from "@/components/screens/code-path"
import type { Media, Screen } from "@/lib/api/types"
import { useModules } from "@/lib/use-modules"
import { useSaveScreen } from "@/lib/use-project-data"
import { useProject } from "@/lib/use-projects"

// Tên GitHub: chữ/số, gạch ngang ở giữa, tối đa 39 ký tự (khớp luật của backend)
const GITHUB_NAME = /^[A-Za-z0-9]+(-[A-Za-z0-9]+)*$/

/** Bỏ khoảng trắng và dấu @ ở đầu, giống backend. */
function cleanDevOwner(value: string): string {
  return value.trim().replace(/^@/, "")
}

type Props = {
  projectId: string
  /** Có thì là sửa, không có thì là thêm mới */
  screen?: Screen
  trigger: ReactElement
  triggerLabel: React.ReactNode
}

export function ScreenFormDialog({ projectId, screen, trigger, triggerLabel }: Props) {
  const t = useTranslations()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(screen?.name ?? "")
  const [description, setDescription] = useState(screen?.description ?? "")
  const [route, setRoute] = useState(screen?.route ?? "")
  const [devOwner, setDevOwner] = useState(screen?.dev_owner ?? "")
  const [codePaths, setCodePaths] = useState<string[]>(screen?.code_paths ?? [])
  const [media, setMedia] = useState<Media[]>(screen?.media ?? [])
  const [moduleId, setModuleId] = useState(screen?.module_id ?? "")
  const [uploading, setUploading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const storage = useProject(projectId).data?.storage ?? "cloudinary"
  const saveScreen = useSaveScreen(projectId)
  const modules = useModules(projectId).data ?? []

  const pathErrors = codePaths.map((path) => codePathError(path))
  const nameError = name.trim() ? null : t("screens.nameRequired")
  const cleanedOwner = cleanDevOwner(devOwner)
  const ownerError =
    cleanedOwner === "" || (cleanedOwner.length <= 39 && GITHUB_NAME.test(cleanedOwner))
      ? null
      : t("screens.devOwnerInvalid")
  const hasErrors = Boolean(nameError) || Boolean(ownerError) || pathErrors.some(Boolean)

  // Mỗi lần mở lại thì nạp lại từ dữ liệu đã lưu, để ảnh/chữ bỏ dở lần trước không bị lưu nhầm
  function handleOpenChange(next: boolean) {
    if (next && screen) {
      setName(screen.name)
      setDescription(screen.description)
      setRoute(screen.route)
      setDevOwner(screen.dev_owner)
      setCodePaths(screen.code_paths)
      setMedia(screen.media ?? [])
      setModuleId(screen.module_id ?? "")
      setUploading(false)
      setSubmitted(false)
    }
    setOpen(next)
  }

  function updatePath(index: number, value: string) {
    setCodePaths((paths) => paths.map((path, i) => (i === index ? value : path)))
  }

  function removePath(index: number) {
    setCodePaths((paths) => paths.filter((_, i) => i !== index))
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (hasErrors) return
    try {
      await saveScreen.mutateAsync({
        id: screen?.id,
        name: name.trim(),
        description: description.trim(),
        route: route.trim(),
        code_paths: codePaths.map((path) => path.trim()),
        dev_owner: cleanedOwner,
        media,
        module_id: moduleId,
      })
      toast.success(t("common.saved"))
      setOpen(false)
      if (!screen) {
        setName("")
        setDescription("")
        setRoute("")
        setDevOwner("")
        setCodePaths([])
        setMedia([])
        setModuleId("")
        setSubmitted(false)
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={trigger}>{triggerLabel}</DialogTrigger>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-x-hidden overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>
            {screen ? t("screens.formEdit", { id: screen.id }) : t("screens.formAdd")}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="screen-name">{t("screens.fieldName")}</Label>
            <Input id="screen-name" value={name} onChange={(e) => setName(e.target.value)} />
            {submitted && nameError && <p className="text-xs text-destructive">{nameError}</p>}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="screen-route">{t("screens.fieldRoute")}</Label>
            <Input
              id="screen-route"
              placeholder="/login"
              value={route}
              onChange={(e) => setRoute(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="screen-module">{t("modules.fieldModule")}</Label>
            <select
              id="screen-module"
              value={moduleId}
              onChange={(e) => setModuleId(e.target.value)}
              className="h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm"
            >
              <option value="">{t("modules.noModule")}</option>
              {modules.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="screen-dev-owner">{t("screens.fieldDevOwner")}</Label>
            <Input
              id="screen-dev-owner"
              placeholder="nguyenvana"
              value={devOwner}
              aria-invalid={submitted && Boolean(ownerError)}
              onChange={(e) => setDevOwner(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">{t("screens.devOwnerHint")}</p>
            {submitted && ownerError && <p className="text-xs text-destructive">{ownerError}</p>}
          </div>

          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label htmlFor="screen-description">{t("screens.fieldDescription")}</Label>
            <textarea
              id="screen-description"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>{t("screens.fieldMedia")}</Label>
            <MediaPicker
              value={media}
              onChange={setMedia}
              projectId={projectId}
              storage={storage}
              pasteScope="page"
              onBusyChange={setUploading}
            />
            <p className="text-xs text-muted-foreground">{t("screens.mediaHint")}</p>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>{t("screens.fieldCodePaths")}</Label>
            <DialogDescription>{t("screens.codePathsHint")}</DialogDescription>
            {codePaths.map((path, index) => (
              <div key={index} className="flex flex-col gap-1">
                <div className="flex gap-2">
                  <Input
                    value={path}
                    placeholder="src/pages/login.tsx"
                    className="font-mono text-xs"
                    aria-invalid={Boolean(pathErrors[index])}
                    onChange={(e) => updatePath(index, e.target.value)}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={t("common.delete")}
                    onClick={() => removePath(index)}
                  >
                    <X />
                  </Button>
                </div>
                {pathErrors[index] && (
                  <p className="text-xs text-destructive">
                    {t(`screens.codePathErrors.${pathErrors[index]}`)}
                  </p>
                )}
              </div>
            ))}
            <div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={codePaths.length >= MAX_CODE_PATHS}
                onClick={() => setCodePaths((paths) => [...paths, ""])}
              >
                <Plus /> {t("screens.addCodePath")}
              </Button>
            </div>
          </div>

          <DialogFooter className="sm:col-span-2">
            <DialogClose render={<Button variant="outline" type="button" />}>
              {t("common.cancel")}
            </DialogClose>
            <Button type="submit" disabled={saveScreen.isPending || uploading}>
              {t("common.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
