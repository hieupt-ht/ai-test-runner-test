"use client"

import { Copy, FolderPlus, Info } from "lucide-react"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ApiError } from "@/lib/api/client"
import { parseSpreadsheetInput } from "@/lib/spreadsheet"
import {
  useCreateProject,
  useGithubBranches,
  useGithubRepositories,
  useServiceAccountEmail,
} from "@/lib/use-projects"

function FieldError({ message }: { message?: string | null }) {
  if (!message) return null
  return <p className="text-xs text-destructive">{message}</p>
}

/** Một ô trong form, có nhãn và chỗ báo lỗi. */
function Field({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string
  htmlFor?: string
  error?: string | null
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      <FieldError message={error} />
    </div>
  )
}

export function CreateProjectDialog() {
  const t = useTranslations("projects")
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [repo, setRepo] = useState<string | null>(null)
  const [branch, setBranch] = useState<string | null>(null)
  const [stagingUrl, setStagingUrl] = useState("")
  const [spreadsheet, setSpreadsheet] = useState("")
  const [submitted, setSubmitted] = useState(false)

  const repos = useGithubRepositories(open)
  const branches = useGithubBranches(repo)
  const serviceAccount = useServiceAccountEmail(open)
  const createProject = useCreateProject()

  const githubMissing = repos.error instanceof ApiError && repos.error.status === 503
  const spreadsheetId = parseSpreadsheetInput(spreadsheet)
  const errors = {
    name: name.trim() ? null : t("required", { field: t("fieldName").toLowerCase() }),
    repo: repo ? null : t("required", { field: t("fieldRepo").toLowerCase() }),
    branch: branch ? null : t("required", { field: t("fieldBranch").toLowerCase() }),
    spreadsheet: spreadsheetId ? null : t("invalidSpreadsheet"),
  }
  const hasErrors = Object.values(errors).some(Boolean)

  function chooseRepo(fullName: string | null) {
    setRepo(fullName)
    // Chọn sẵn branch mặc định của repo
    const info = repos.data?.find((item) => item.full_name === fullName)
    setBranch(info?.default_branch ?? null)
  }

  function reset() {
    setName("")
    setRepo(null)
    setBranch(null)
    setStagingUrl("")
    setSpreadsheet("")
    setSubmitted(false)
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (hasErrors || !repo || !branch) return
    try {
      const project = await createProject.mutateAsync({
        name: name.trim(),
        repo_full_name: repo,
        branch,
        staging_url: stagingUrl.trim(),
        spreadsheet,
      })
      toast.success(t("created", { name: project.name }))
      reset()
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  async function copyEmail() {
    if (!serviceAccount.data) return
    await navigator.clipboard.writeText(serviceAccount.data)
    toast.success(t("copied"))
  }

  const repoItems = (repos.data ?? []).map((item) => ({
    value: item.full_name,
    label: item.full_name,
  }))
  const branchItems = (branches.data ?? []).map((item) => ({ value: item, label: item }))

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}>
        <FolderPlus /> {t("create")}
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("formTitle")}</DialogTitle>
          <DialogDescription>{t("formDescription")}</DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <Field label={t("fieldName")} htmlFor="project-name" error={submitted ? errors.name : null}>
            <Input id="project-name" value={name} onChange={(e) => setName(e.target.value)} />
          </Field>

          {githubMissing ? (
            <div className="flex gap-2 rounded-lg border bg-muted/50 p-3 text-sm">
              <Info className="mt-0.5 size-4 shrink-0" />
              {t("githubMissing")}
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("fieldRepo")} error={submitted ? errors.repo : null}>
                <Select items={repoItems} value={repo} onValueChange={chooseRepo}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={t("fieldRepoPlaceholder")} />
                  </SelectTrigger>
                  <SelectContent>
                    {repoItems.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label={t("fieldBranch")} error={submitted ? errors.branch : null}>
                <Select
                  items={branchItems}
                  value={branch}
                  onValueChange={setBranch}
                  disabled={!repo}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={t("fieldBranchPlaceholder")} />
                  </SelectTrigger>
                  <SelectContent>
                    {branchItems.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </div>
          )}

          <Field label={t("fieldStagingUrl")} htmlFor="project-staging">
            <Input
              id="project-staging"
              type="url"
              placeholder="https://staging.example.com"
              value={stagingUrl}
              onChange={(e) => setStagingUrl(e.target.value)}
            />
          </Field>

          <Field
            label={t("fieldSpreadsheet")}
            htmlFor="project-sheet"
            error={submitted ? errors.spreadsheet : null}
          >
            <Input
              id="project-sheet"
              placeholder="https://docs.google.com/spreadsheets/d/..."
              value={spreadsheet}
              onChange={(e) => setSpreadsheet(e.target.value)}
            />
          </Field>
          {serviceAccount.data && (
            <div className="rounded-lg border bg-muted/50 p-3 text-sm">
              <p className="mb-2 text-muted-foreground">{t("shareHint")}</p>
              <div className="flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded bg-background px-2 py-1 text-xs">
                  {serviceAccount.data}
                </code>
                <Button type="button" size="sm" variant="outline" onClick={copyEmail}>
                  <Copy /> {t("copy")}
                </Button>
              </div>
            </div>
          )}

          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button" />}>
              {t("cancel")}
            </DialogClose>
            <Button type="submit" disabled={createProject.isPending || githubMissing}>
              {t("save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
