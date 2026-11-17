/** Hiển thị lịch sử phiên bản của một test case. */

// Tên tiếng Việt của các trường nội dung (khớp CHANGED_FIELD_LABELS ở backend)
export const CHANGED_FIELD_LABELS: Record<string, string> = {
  title: "Tiêu đề",
  precondition: "Điều kiện trước",
  test_data: "Dữ liệu test",
  steps: "Các bước",
  expected_result: "Kết quả mong đợi",
  severity: "Mức độ nghiêm trọng",
  priority: "Độ ưu tiên",
  platform: "Nền tảng",
  test_type: "Loại test",
  regression: "Regression",
  start_point: "Điểm bắt đầu",
  guide_media: "Ảnh/video hướng dẫn",
  postcondition: "Điều kiện sau",
  requirement_ref: "Mã yêu cầu",
  status: "Trạng thái",
}

/** Tên tiếng Việt của các trường có trong diff (bỏ khoá lạ như `comment`). */
export function changedLabels(diff: Record<string, unknown>): string[] {
  return Object.keys(diff)
    .filter((key) => key in CHANGED_FIELD_LABELS)
    .map((key) => CHANGED_FIELD_LABELS[key])
}

/** Giờ Việt Nam dạng "16/11/2026 14:05" (giờ UTC từ server được đổi sang UTC+7). */
export function formatVietnamTime(iso: string): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso))
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? ""
  return `${get("day")}/${get("month")}/${get("year")} ${get("hour")}:${get("minute")}`
}

/**
 * Mỗi lần ghi case (tạo, sửa, đổi trạng thái) là một phiên bản và một dòng lịch sử,
 * nên phiên bản của dòng = vị trí khi xếp từ cũ đến mới. `index` tính trong danh sách
 * mới nhất lên đầu, `total` là tổng số dòng.
 */
export function versionOfEntry(index: number, total: number): number {
  return total - index
}
