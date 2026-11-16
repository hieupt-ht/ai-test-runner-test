"""Tên tab và danh sách cột của file Sheet hệ thống (spec mục 8.1)."""

USERS_TAB = "Users"
PROJECTS_TAB = "Projects"
PROJECT_MEMBERS_TAB = "ProjectMembers"
AUDIT_LOG_TAB = "AuditLog"

USER_COLUMNS = ["email", "name", "role", "active", "created_at"]
PROJECT_COLUMNS = [
    "id",
    "name",
    "repo_full_name",
    "branch",
    "staging_url",
    "spreadsheet_id",
    "archived",
    "created_at",
    # Cột thêm sau: luôn nối vào CUỐI để Sheet cũ được tự nâng cấp
    "android_app_id",
    "ios_bundle_id",
    "require_review",
]
PROJECT_MEMBER_COLUMNS = ["project_id", "email", "added_at"]
AUDIT_LOG_COLUMNS = ["at", "actor", "action", "entity", "entity_id", "diff_json"]

SYSTEM_TABS: dict[str, list[str]] = {
    USERS_TAB: USER_COLUMNS,
    PROJECTS_TAB: PROJECT_COLUMNS,
    PROJECT_MEMBERS_TAB: PROJECT_MEMBER_COLUMNS,
    AUDIT_LOG_TAB: AUDIT_LOG_COLUMNS,
}


# ===== Sheet riêng của từng dự án (spec mục 8.2) =====
META_TAB = "Meta"
SCREENS_TAB = "Screens"
ASSIGNMENTS_TAB = "Assignments"
TEST_CASES_TAB = "TestCases"
RUNS_TAB = "Runs"
RESULTS_TAB = "Results"

META_COLUMNS = ["key", "value"]
SCREEN_COLUMNS = ["id", "name", "description", "route", "code_paths", "created_at", "dev_owner"]
ASSIGNMENT_COLUMNS = ["id", "screen_id", "assignee_email", "deadline", "status", "updated_at"]
TEST_CASE_COLUMNS = [
    "id",
    "screen_id",
    "title",
    "precondition",
    "test_data",
    "steps",
    "expected_result",
    "severity",
    "priority",
    "status",
    "created_by",
    "updated_by",
    "created_at",
    "updated_at",
    "version",
]
RUN_COLUMNS = [
    "id",
    "triggered_by",
    "scope",
    "branch",
    "commit_sha",
    "status",
    "started_at",
    "finished_at",
    "total",
    "passed",
    "failed",
    "tokens_used",
]
RESULT_COLUMNS = [
    "id",
    "run_id",
    "test_case_id",
    "status",
    "reason",
    "failed_step",
    "evidence_json",
    "tokens_used",
    "issue_url",
    "reviewed_by",
    "review_note",
    "created_at",
]

PROJECT_TABS: dict[str, list[str]] = {
    META_TAB: META_COLUMNS,
    SCREENS_TAB: SCREEN_COLUMNS,
    ASSIGNMENTS_TAB: ASSIGNMENT_COLUMNS,
    TEST_CASES_TAB: TEST_CASE_COLUMNS,
    RUNS_TAB: RUN_COLUMNS,
    RESULTS_TAB: RESULT_COLUMNS,
    AUDIT_LOG_TAB: AUDIT_LOG_COLUMNS,
}
