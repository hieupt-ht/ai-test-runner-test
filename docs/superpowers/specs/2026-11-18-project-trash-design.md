# Thùng rác dự án (xoá vĩnh viễn dự án) — thiết kế ngắn

Ngày: 2026-11-18 · Nhánh: `feature/ai-agent-runner` · Cỡ: nhỏ (một đợt)

## Vì sao làm

Chủ dự án thấy danh sách dự án ở trang Admin quá dài ("nhiều dự án quá nhìn rồi"). Hiện dự án
chỉ có **Lưu trữ** (cờ `archived`, làm ở trang Cài đặt từng dự án), không có cách xoá, và
dự án lưu trữ vẫn nằm lẫn trong danh sách Admin.

## Quyết định (chủ dự án đã đồng ý cách A)

**Lưu trữ = bỏ vào thùng rác.** Dự án đã lưu trữ chuyển sang tab "Thùng rác" ở trang Admin;
từ đó khôi phục được hoặc xoá vĩnh viễn.

## Mục tiêu

1. Trang Admin → Dự án có 2 tab: **Đang dùng (n)** (mặc định) và **Thùng rác (n)**.
2. Dòng dự án đang dùng có nút "Chuyển vào thùng rác" (đặt `archived=true`, dùng PATCH có sẵn).
3. Tab Thùng rác: nút **Khôi phục** (`archived=false`, PATCH có sẵn) và **Xoá vĩnh viễn**.
4. Xoá vĩnh viễn: hộp xác nhận, phải gõ đúng tên dự án mới bấm được nút Xoá.

## Không làm / chống mục tiêu

- **Không đụng dữ liệu bên ngoài:** file Google Sheet riêng của dự án, issue GitHub, ảnh/video
  trên Cloudinary/Drive đều giữ nguyên. Xoá chỉ làm app "quên" dự án.
- Không cho xoá dự án đang dùng: phải vào thùng rác trước (chống bấm nhầm).
- Không hẹn giờ tự xoá thùng rác; không xoá hàng loạt.

## Thiết kế

**Backend**
- `DELETE /api/projects/{project_id}`, quyền `MANAGE_PROJECTS` (chỉ Admin), body
  `{ "name": "<tên dự án>" }`.
  - 404 nếu không có dự án; 409 nếu dự án chưa lưu trữ ("Hãy chuyển dự án vào thùng rác
    trước"); 422 nếu `name` không khớp tên dự án; 409 khi hệ thống bận (khoá).
  - Thành công: 204.
- `ProjectRepository.delete(project_id)`: trong khoá, tìm dòng theo `id`, xoá dòng, huỷ cache;
  không có thì `ProjectNotFoundError`.
- `ProjectMemberRepository.remove_all_for_project(project_id)`: xoá mọi dòng thành viên của
  dự án (xoá từ dòng cuối lên để số dòng không lệch), huỷ cache.
- `ProjectService.delete_project(actor, project)`: kiểm tra đã lưu trữ → xoá thành viên →
  xoá dự án → ghi `AuditLog` (`DELETE`, `project`, mã dự án, diff có tên/repo/spreadsheet_id
  để còn dấu vết). Thành viên xoá trước dự án: nếu lỡ lỗi giữa chừng thì dự án vẫn còn
  trong thùng rác và xoá lại được.
- Danh sách `GET /projects` giữ nguyên (Admin thấy cả dự án lưu trữ; frontend tự chia tab).

**Frontend** (`app/(app)/admin/projects/page.tsx`, `lib/use-projects.ts`)
- Hook `useDeleteProject`; chia tab theo `project.archived`; nút "Chuyển vào thùng rác" /
  "Khôi phục" gọi `useUpdateProject`.
- Hộp thoại xoá vĩnh viễn: ô gõ tên, nút Xoá bị khoá tới khi khớp tên; giải thích ngắn
  "Chỉ xoá khỏi app, file Google Sheet và issue GitHub vẫn còn".
- Chuỗi tiếng Việt vào `messages/vi.json`. Sinh lại API bằng `npm run gen:api`.
- Trang Cài đặt dự án giữ nút Lưu trữ như hiện tại (đổi chữ thành "Chuyển vào thùng rác").

**Lưu ý khi làm:** `admin/projects/page.tsx`, `vi.json` và vài file khác đang có sửa dở chưa
commit của chủ dự án — chỉ stage phần của mình (xem cách đã làm ở đợt trước).

## Để lại cho người xây

Tên component, chia file, cách đếm số trên tab.
