"use client"

import { useRouter } from "next/navigation"
import { useEffect } from "react"

import { useProjectId } from "@/lib/use-project-id"

// Mở /projects/<id> thì chuyển sang tab đầu tiên: Tổng quan.
export default function ProjectIndexPage() {
  const projectId = useProjectId()
  const router = useRouter()

  useEffect(() => {
    router.replace(`/projects/${projectId}/overview`)
  }, [projectId, router])

  return null
}
