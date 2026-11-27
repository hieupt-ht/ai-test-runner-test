# Nhập kết quả — Phần 1 (nút nhập, tester tạo module, bằng chứng tuỳ chọn) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nút "Nhập từ Excel" luôn hiện cho người tạo được case; tester tự tạo module (tự nhận luôn); Fail không còn bắt buộc ảnh/video.

**Architecture:** Backend: route `POST /modules` đổi quyền sang `EDIT_TEST_CASE`, tester tạo xong thì gọi `ModuleWorkService.assign` để tự nhận (lỗi thì xoá module vừa tạo); bỏ một luật 422 ở `manual_results`. Frontend: đổi điều kiện `canImport`, thêm nút tạo module cho tester ở trang Màn hình và lối tắt trong hộp thoại nhập, `ManualRunPanel` đổi lỗi thành cảnh báo.

**Tech Stack:** FastAPI + pytest (fakeredis, `FakeSheetsGateway`); Next.js 16 + TanStack Query + vitest + next-intl.

**Spec:** `docs/superpowers/specs/2026-11-27-import-results-batch-run-design.md` (mục 3)

## Global Constraints

- Tiếng Việt đơn giản trong comment và chữ hiện ra; chữ giao diện chỉ thêm vào `frontend/messages/vi.json`.
- TDD: test đỏ trước. Chạy cả hai bộ test trước khi báo xong.
- Commit Conventional Commits, type tiếng Anh, nội dung tiếng Việt có dấu, heredoc Git Bash, kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Không push.
- Chỉ `ruff format` đúng các file mình sửa (chạy cho cả thư mục sẽ đụng nhiều file không liên quan).
- Test frontend chạy với `npx vitest run --testTimeout=60000 --maxWorkers=3` (máy chậm).
- Đổi tên/sửa mô tả/xoá module vẫn chỉ QA Lead/Admin (`MANAGE_SCREENS`).
- Tester tạo module: hạn nhận mặc định hôm nay (giờ Việt Nam) + 7 ngày.
- Chữ cảnh báo khi Fail không có ảnh: "Nên thêm ảnh hoặc video để dev dễ tìm lỗi."

## Review Focus

1. Tester tạo module trùng tên (khác hoa thường) → 422 "Đã có module tên này", không có dòng nhận module nào được tạo.
2. Nhận module lỗi sau khi đã tạo module → module bị xoá, không để module mồ côi không ai làm.
3. QA tạo module → **không** tự nhận (QA không phải tester, `assign` sẽ báo lỗi nếu gọi).
4. Tester mở hộp thoại nhập khi chưa có module nào → vẫn thấy nút và lối tắt tạo module; tạo xong ô chọn đúng module mới.
5. Fail không ảnh vẫn ghi kết quả và tạo issue như Fail có ảnh (chỉ bỏ luật chặn, không đổi luồng sau đó).

---

### Task 1: Backend — tester tạo module và tự nhận

**Files:**
- Modify: `backend/app/api/routers/modules.py` (route `create_module`)
- Test: `backend/tests/test_module_work_api.py` (thêm test; dùng sẵn fixture `lead`, `tester`, `project`, helper `base`, `NEXT_WEEK`)

**Interfaces:**
- Consumes: `ModuleService.create_module(actor, *, name, description) -> Module`, `ModuleService.delete_module(actor, module_id)`, `work_service_for(services, user, project_id, action) -> ModuleWorkService`, `ModuleWorkService.assign(actor, *, module_id, emails, deadline) -> list[ModuleAssignment]`, `today_in_vietnam()`.
- Produces: `POST /api/projects/{pid}/modules` nhận cả tester; trả `Module` như cũ (201).

- [ ] **Step 1: Viết test đỏ**

```python
def test_tester_creates_module_and_claims_it(tester: TestClient, project: Project) -> None:
    response = tester.post(f"{base(project)}/modules", json={"name": "Thanh toán"})

    assert response.status_code == 201
    module = tester.get(f"{base(project)}/modules").json()[0]
    assert [w["email"] for w in module["workers"]] == ["tester@x.com"]
    assert module["workers"][0]["deadline"] == NEXT_WEEK


def test_tester_cannot_create_duplicate_module(
    lead: TestClient, tester: TestClient, project: Project
) -> None:
    lead.post(f"{base(project)}/modules", json={"name": "Thanh toán"})

    response = tester.post(f"{base(project)}/modules", json={"name": "THANH TOÁN"})

    assert response.status_code == 422
    assert response.json()["detail"] == "Đã có module tên này"
    assert tester.get(f"{base(project)}/modules").json()[0]["workers"] == []


def test_lead_creating_module_does_not_claim_it(lead: TestClient, project: Project) -> None:
    lead.post(f"{base(project)}/modules", json={"name": "Thanh toán"})

    assert lead.get(f"{base(project)}/modules").json()[0]["workers"] == []


def test_tester_still_cannot_rename_or_delete_module(
    lead: TestClient, tester: TestClient, project: Project
) -> None:
    module_id = tester.post(f"{base(project)}/modules", json={"name": "Thanh toán"}).json()["id"]

    assert tester.patch(f"{base(project)}/modules/{module_id}", json={"name": "X"}).status_code == 403
    assert tester.delete(f"{base(project)}/modules/{module_id}").status_code == 403


def test_failed_claim_removes_new_module(
    tester: TestClient, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self, *args, **kwargs):
        raise RuntimeError("Google lỗi")

    monkeypatch.setattr(ModuleWorkService, "assign", boom)

    with pytest.raises(RuntimeError):
        tester.post(f"{base(project)}/modules", json={"name": "Thanh toán"})

    monkeypatch.undo()
    assert tester.get(f"{base(project)}/modules").json() == []
```

(Import `ModuleWorkService` từ `app.core.services.module_work`. Viewer vẫn bị 403 nhờ `EDIT_TEST_CASE` không có Viewer — đã có sẵn trong luật quyền, không cần test mới.)

- [ ] **Step 2: Chạy, xem đỏ**

Run: `cd backend && uv run pytest tests/test_module_work_api.py -q -k "creates_module or duplicate_module or does_not_claim or rename_or_delete or failed_claim"`
Expected: test tester tạo module FAIL (403); `test_lead_creating_module_does_not_claim_it` và `test_tester_still_cannot_rename_or_delete_module` có thể đã qua hoặc đỏ vì tester chưa tạo được (403 ở bước tạo).

- [ ] **Step 3: Sửa route `create_module`**

- `load_project`/`_service` dùng `Action.EDIT_TEST_CASE` thay cho `MANAGE_SCREENS` (chỉ route tạo).
- Sau khi tạo, nếu `user.role == Role.TESTER`: `work_service_for(...).assign(user, module_id=module.id, emails=[user.email], deadline=today_in_vietnam() + timedelta(days=7))`. Bất kỳ lỗi nào ở bước nhận: `service.delete_module(user, module.id)` (bọc try, lỗi khi xoá chỉ log) rồi `raise` lại lỗi gốc. `LockTimeout` từ bước nhận vẫn thành 409 như hiện nay (sau khi đã xoá module).

- [ ] **Step 4: Chạy lại, xem xanh**

Run: `cd backend && uv run pytest tests/test_module_work_api.py tests/test_modules_api.py -q`
Expected: tất cả PASS. Nếu `test_modules_api.py` có test "tester không tạo được module" (403) thì đó là luật cũ: đổi test đó thành kỳ vọng 201 kèm ghi chú trong ledger.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routers/modules.py backend/tests/test_module_work_api.py backend/tests/test_modules_api.py
git commit -F - <<'EOF'
feat(backend): tester tự tạo module và tự nhận luôn

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

### Task 2: Backend — Fail không bắt buộc bằng chứng

**Files:**
- Modify: `backend/app/api/routers/manual_results.py` (`_check_steps`, bỏ nhánh `if not _all_media(body)` khi FAIL; giữ `_all_media` vì `_check_media` còn dùng)
- Modify: `DECISIONS.md` (thêm mục ngày 2026-11-27: Fail chạy tay không còn bắt buộc ảnh/video; lý do: tester test theo file Excel, ảnh là "có thì tốt")
- Test: `backend/tests/test_manual_results_api.py`

- [ ] **Step 1: Đổi test cũ thành test đỏ**

Đổi `test_fail_without_evidence_is_rejected` thành:

```python
def test_fail_without_evidence_is_accepted(
    an: TestClient, project: Project, gateway: FakeSheetsGateway
) -> None:
    case = new_case(an, project)

    response = submit(an, project, case["id"], fail_body(project, evidence={}))

    assert response.status_code == 201
    assert rows(gateway, project, "Results")[0]["status"] == "FAIL"
```

- [ ] **Step 2: Chạy, xem đỏ**

Run: `cd backend && uv run pytest tests/test_manual_results_api.py -q -k without_evidence`
Expected: FAIL (422).

- [ ] **Step 3: Bỏ luật trong `_check_steps`** (mô tả lỗi và bước lỗi khi Fail vẫn bắt buộc ở phần này; Phần 2 mới bỏ bước lỗi).

- [ ] **Step 4: Chạy cả file, xem xanh**

Run: `cd backend && uv run pytest tests/test_manual_results_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit** (`fix(backend): kết quả Fail chạy tay không còn bắt buộc ảnh hoặc video`, kèm `DECISIONS.md`).

### Task 3: Frontend — ManualRunPanel cảnh báo thay vì chặn

**Files:**
- Modify: `frontend/components/test-cases/manual-run-panel.tsx` (bỏ `hasMedia` khỏi `failOk`; dòng nhắc đổi sang màu vàng `text-amber-700 dark:text-amber-400`, dùng khoá mới)
- Modify: `frontend/messages/vi.json`: xoá `failNeedsEvidence`, thêm `failEvidenceHint`: "Nên thêm ảnh hoặc video để dev dễ tìm lỗi."
- Test: `frontend/components/test-cases/manual-run-panel.test.tsx` (sửa test đang kỳ vọng nút Gửi mờ / chữ "Kết quả Fail cần ít nhất một ảnh…")

- [ ] **Step 1: Test đỏ** — `it("Fail không có ảnh vẫn gửi được, chỉ hiện nhắc")`: điền đủ bước, chọn Fail, mô tả lỗi, bước lỗi, môi trường, không thêm ảnh → `expect(screen.getByText("Nên thêm ảnh hoặc video để dev dễ tìm lỗi.")).toBeInTheDocument()` và nút Gửi `toBeEnabled()`; thêm ảnh thì dòng nhắc biến mất.
- [ ] **Step 2: Chạy, xem đỏ** — `cd frontend && npx vitest run components/test-cases/manual-run-panel.test.tsx --testTimeout=60000` → FAIL.
- [ ] **Step 3: Sửa `failOk` và dòng nhắc.**
- [ ] **Step 4: Chạy lại, xem xanh** (cùng lệnh).
- [ ] **Step 5: Commit** (`fix(frontend): Fail không có ảnh chỉ nhắc, không chặn gửi`).

### Task 4: Frontend — nút nhập luôn hiện, tester tạo module (trang Màn hình + hộp thoại nhập)

**Files:**
- Modify: `frontend/app/(app)/projects/[projectId]/test-cases/page.tsx` (`canImport = canCreate`; bỏ phụ thuộc `selectableScreens` cho nút này; giữ comment giải thích)
- Modify: `frontend/app/(app)/projects/[projectId]/screens/page.tsx` (nút "Tạo module" hiện cho `canManage || canClaim`; nút "Thêm màn hình" vẫn chỉ `canManage`)
- Modify: `frontend/components/modules/module-form-dialog.tsx` (thêm prop `onSaved?: (module: Module) => void`, gọi sau khi lưu thành công)
- Modify: `frontend/components/test-cases/import-dialog.tsx` (dưới ô chọn module: `ModuleFormDialog` với nút chữ "+ Tạo module mới", `onSaved={(m) => onChooseModule(m.id)}`; module vừa tạo luôn có trong danh sách chọn kể cả khi danh sách module chưa tải lại xong)
- Modify: `frontend/messages/vi.json` (`testCases.import.createModule`: "+ Tạo module mới")
- Test: `frontend/app/(app)/projects/[projectId]/test-cases/page.test.tsx`, `frontend/app/(app)/projects/[projectId]/screens/page.test.tsx` (nếu chưa có thì tạo theo mẫu test trang khác), `frontend/components/test-cases/import-dialog.test.tsx`, `frontend/components/modules/module-form-dialog.test.tsx`

**Interfaces:**
- Consumes: Task 1 (tester gọi được `POST /modules`; module trả về đã có tester trong `workers` sau khi tải lại).
- Produces: `ModuleFormDialog` prop `onSaved?: (module: Module) => void`.

- [ ] **Step 1: Test đỏ**
  - page.test: đổi `"tester chưa được giao màn hình nào thì không thấy nút Nhập từ Excel"` thành `"tester chưa được giao màn hình nào vẫn thấy nút Nhập từ Excel"` (`getByRole("button", { name: "Nhập từ Excel" })`). Test dự án lưu trữ giữ nguyên.
  - module-form-dialog.test: `it("gọi onSaved với module vừa tạo")` — mock `useSaveModule().mutateAsync` trả `{ id: "MD-0009", name: "Thanh toán", ... }` → `onSaved` được gọi với object đó.
  - import-dialog.test: `it("tạo module mới từ hộp thoại thì chọn luôn module đó")` — tester, `mocks.modules = []`; bấm "+ Tạo module mới", nhập tên, lưu (mock trả `MD-0009`) → `screen.getByLabelText("Module")` có value `"MD-0009"` và ô chọn file không còn `disabled`.
  - screens page test: tester (không `MANAGE_SCREENS`) thấy nút "Tạo module", không thấy nút thêm màn hình.
- [ ] **Step 2: Chạy, xem đỏ** — `cd frontend && npx vitest run "app/(app)/projects/[projectId]/test-cases/page.test.tsx" components/test-cases/import-dialog.test.tsx components/modules/module-form-dialog.test.tsx "app/(app)/projects/[projectId]/screens" --testTimeout=60000 --maxWorkers=3` → các test mới FAIL.
- [ ] **Step 3: Sửa code như phần Files.** Trong `import-dialog.tsx`, mock `useSaveModule` trong test cần có thêm ở `vi.mock("@/lib/use-modules", ...)`.
- [ ] **Step 4: Chạy lại, xem xanh** (cùng lệnh), rồi `npm run typecheck` và `npm run lint` sạch.
- [ ] **Step 5: Commit** (`feat(frontend): tester tạo module, nút nhập Excel luôn hiện`).

### Task 5: Kiểm tra cuối và HANDOFF

- [ ] Backend: `cd backend && uv run pytest -q` → tất cả PASS; `uv run ruff check .` sạch.
- [ ] Frontend: `npx vitest run --testTimeout=60000 --maxWorkers=3` (chạy nền, mất ~10 phút), `npm run typecheck`, `npm run lint` sạch.
- [ ] `HANDOFF.md`: thêm mục "Đã xong (2026-11-27): nhập kết quả — Phần 1" (3 thay đổi, số test), và ghi Phần 2 còn chờ kế hoạch riêng.
- [ ] Commit `docs: cập nhật HANDOFF sau Phần 1`.
