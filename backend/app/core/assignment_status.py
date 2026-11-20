"""Trạng thái việc được giao, tự suy ra từ các test case của tester."""

from app.core.models.assignment import AssignmentStatus
from app.core.models.test_case import ExecutionMode, TestCase, TestCaseStatus
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.test_cases import TestCaseRepository


def derive_assignment_status(
    cases: list[TestCase],
    *,
    screen_id: str,
    tester_email: str,
    tested_case_ids: frozenset[str] = frozenset(),
) -> AssignmentStatus:
    """Tính trạng thái việc của màn hình `screen_id` (hàm thuần, không đọc Sheet).

    Xét mọi case của màn hình, bất kể ai tạo (kể cả case nhập từ Excel), bỏ qua DEPRECATED.
    `tester_email` giữ cho tương thích, mọi tester cùng màn hình có chung trạng thái.
    """
    mine = [
        case
        for case in cases
        if case.screen_id == screen_id and case.status != TestCaseStatus.DEPRECATED
    ]
    if not mine:
        return AssignmentStatus.TODO
    statuses = {case.status for case in mine}
    if TestCaseStatus.DRAFT in statuses:
        return AssignmentStatus.WRITING
    if TestCaseStatus.IN_REVIEW in statuses:
        return AssignmentStatus.IN_REVIEW
    # Mọi case đều là test tay đã chạy xong thì việc đã test (không cần chờ duyệt).
    if all(
        case.execution_mode == ExecutionMode.MANUAL and case.status == TestCaseStatus.TESTED
        for case in mine
    ):
        return AssignmentStatus.TESTED
    # Còn lại toàn APPROVED: đã chạy hết thì TESTED.
    if all(case.id in tested_case_ids for case in mine):
        return AssignmentStatus.TESTED
    return AssignmentStatus.APPROVED


class AssignmentStatusUpdater:
    def __init__(self, assignments: AssignmentRepository, test_cases: TestCaseRepository) -> None:
        self._assignments = assignments
        self._test_cases = test_cases

    def refresh_screen(self, screen_id: str) -> None:
        """Tính lại trạng thái mọi việc của một màn hình, chỉ ghi những dòng có đổi.

        Đọc test case và assignment BÊN TRONG khoá: nếu đọc trước khi lấy khoá thì một lần
        tính cũ có thể ghi đè kết quả của lần tính mới hơn.
        """
        with self._assignments.lock():
            cases = self._test_cases.list_all()
            for assignment in self._assignments.list_all():
                if assignment.screen_id != screen_id:
                    continue
                new_status = derive_assignment_status(
                    cases, screen_id=screen_id, tester_email=assignment.assignee_email
                )
                if new_status != assignment.status:
                    self._assignments.update(assignment.model_copy(update={"status": new_status}))
