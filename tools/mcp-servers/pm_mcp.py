"""Mock Project Management MCP Server — 기획자/PM 에이전트용."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pm-mock")

PROJECTS = [
    {"id": "PRJ-001", "name": "SaaS MVP 출시", "status": "in_progress",
     "start": "2026-03-01", "deadline": "2026-06-30", "progress": 45,
     "owner": "김기획", "team_size": 8},
]

TASKS = [
    {"id": "TASK-101", "title": "사용자 인증 시스템", "status": "done", "assignee": "박개발", "priority": "high", "sprint": "Sprint 3"},
    {"id": "TASK-102", "title": "결제 연동", "status": "in_progress", "assignee": "이개발", "priority": "critical", "sprint": "Sprint 4"},
    {"id": "TASK-103", "title": "대시보드 UI", "status": "todo", "assignee": "최디자인", "priority": "medium", "sprint": "Sprint 4"},
    {"id": "TASK-104", "title": "이메일 알림", "status": "todo", "assignee": "unassigned", "priority": "low", "sprint": "Sprint 5"},
    {"id": "TASK-105", "title": "관리자 페이지", "status": "backlog", "assignee": "unassigned", "priority": "medium", "sprint": "unplanned"},
]

MILESTONES = [
    {"name": "Alpha 릴리스", "date": "2026-04-30", "status": "at_risk", "blockers": ["결제 연동 지연"]},
    {"name": "Beta 릴리스", "date": "2026-05-31", "status": "on_track", "blockers": []},
    {"name": "GA 출시", "date": "2026-06-30", "status": "on_track", "blockers": []},
]


@mcp.tool()
def get_project_status(project_id: str = "PRJ-001") -> dict:
    """프로젝트 현황을 반환한다."""
    proj = next((p for p in PROJECTS if p["id"] == project_id), PROJECTS[0])
    return {**proj, "milestones": MILESTONES}


@mcp.tool()
def list_tasks(status: str = "all", sprint: str = "all") -> dict:
    """태스크 목록을 반환한다."""
    filtered = TASKS
    if status != "all":
        filtered = [t for t in filtered if t["status"] == status]
    if sprint != "all":
        filtered = [t for t in filtered if t["sprint"] == sprint]
    return {"tasks": filtered, "total": len(filtered)}


@mcp.tool()
def get_sprint_summary(sprint: str = "Sprint 4") -> dict:
    """스프린트 요약을 반환한다."""
    sprint_tasks = [t for t in TASKS if t["sprint"] == sprint]
    done = sum(1 for t in sprint_tasks if t["status"] == "done")
    return {
        "sprint": sprint, "total": len(sprint_tasks), "done": done,
        "in_progress": sum(1 for t in sprint_tasks if t["status"] == "in_progress"),
        "todo": sum(1 for t in sprint_tasks if t["status"] == "todo"),
        "completion_rate": f"{done/max(len(sprint_tasks),1)*100:.0f}%",
        "tasks": sprint_tasks,
    }


@mcp.tool()
def get_risk_assessment() -> dict:
    """프로젝트 리스크를 반환한다."""
    return {
        "risks": [
            {"level": "high", "description": "결제 연동 지연 — Alpha 마일스톤 위험", "mitigation": "추가 인력 투입 또는 스코프 축소"},
            {"level": "medium", "description": "디자인 리소스 부족 — Sprint 4 UI 태스크 지연 가능", "mitigation": "외부 디자이너 계약"},
            {"level": "low", "description": "인프라 비용 초과 가능", "mitigation": "Reserved Instance 전환"},
        ]
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
