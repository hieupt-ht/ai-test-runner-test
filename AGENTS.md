# AGENTS.md

Đọc [HANDOFF.md](HANDOFF.md) trước: nó nói dự án đang ở đâu, việc còn dở và quy ước.

Tóm tắt các quy tắc không được quên:

- Giải thích bằng **tiếng Việt đơn giản** (chủ dự án là sinh viên đang học); code dễ đọc, comment tiếng Việt.
- **Không push, không tạo PR khi chưa được đồng ý.** Không commit thẳng vào `main`.
- Commit theo Conventional Commits: type tiếng Anh, nội dung tiếng Việt có dấu. Trên Windows viết message bằng heredoc Git Bash.
- Viết test trước, xem nó đỏ, rồi mới viết code (TDD). Chạy cả hai bộ test trước khi báo xong.
- Không in hay commit giá trị trong `.env` và `worker-projects.json`.
- Frontend dùng Next.js 16: xem `frontend/AGENTS.md` trước khi viết route.
