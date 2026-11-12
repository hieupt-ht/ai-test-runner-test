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
]
PROJECT_MEMBER_COLUMNS = ["project_id", "email", "added_at"]
AUDIT_LOG_COLUMNS = ["at", "actor", "action", "entity", "entity_id", "diff_json"]

SYSTEM_TABS: dict[str, list[str]] = {
    USERS_TAB: USER_COLUMNS,
    PROJECTS_TAB: PROJECT_COLUMNS,
    PROJECT_MEMBERS_TAB: PROJECT_MEMBER_COLUMNS,
    AUDIT_LOG_TAB: AUDIT_LOG_COLUMNS,
}
