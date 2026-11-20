"use client"

import dynamic from "next/dynamic"

import { Skeleton } from "@/components/ui/skeleton"

// Recharts khá nặng nên chỉ tải khi trang cần vẽ đồ thị (và chỉ chạy ở trình duyệt).
const loading = () => <Skeleton className="h-56 w-full" />

export const LazyPassFailChart = dynamic(() => import("@/components/charts/pass-fail-chart"), {
  ssr: false,
  loading,
})

export const LazyCaseStatusDonut = dynamic(() => import("@/components/charts/case-status-donut"), {
  ssr: false,
  loading,
})
