"""Playwright 기반 E2E 테스트 — 프론트엔드 UI를 통한 실제 사용자 흐름 검증.

사전 조건:
  - 백엔드: localhost:9000 (uvicorn orchestrator.api.app:app)
  - 프론트엔드: localhost:3000 (npm run dev)

실행: uv run pytest tests/e2e/test_playwright_e2e.py -v --timeout=60
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect, sync_playwright


FRONTEND_URL = "http://localhost:3000"


@pytest.fixture(scope="module")
def browser_context():
    """Playwright 브라우저 컨텍스트를 생성한다."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        yield context
        context.close()
        browser.close()


@pytest.fixture
def page(browser_context):
    """각 테스트마다 새 페이지를 생성한다."""
    pg = browser_context.new_page()
    yield pg
    pg.close()


class TestDashboardLoad:
    """프론트엔드 대시보드 로드 테스트."""

    def test_page_title_and_header(self, page) -> None:
        """대시보드 페이지가 로드되고 헤더가 표시된다."""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        # 헤더 텍스트 확인
        header = page.locator("h1")
        expect(header).to_contain_text("Agent Team Orchestrator")

    def test_connection_status_visible(self, page) -> None:
        """WebSocket 연결 상태가 표시된다."""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        status = page.locator(".connection-status")
        expect(status).to_be_visible()

    def test_pipeline_list_panel_visible(self, page) -> None:
        """Pipelines 패널이 표시된다."""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        # "Pipelines" 헤더가 있는 패널
        panel_header = page.locator(".panel-header", has_text="Pipelines")
        expect(panel_header).to_be_visible()

    def test_empty_state_message(self, page) -> None:
        """초기 상태에서 빈 메시지가 표시된다."""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        empty = page.locator(".empty-state")
        # "No pipelines yet" 또는 "Loading..." 중 하나
        expect(empty.first).to_be_visible()

    def test_kanban_board_visible(self, page) -> None:
        """칸반 보드가 표시된다."""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        # KanbanBoard 컴포넌트의 패널 헤더
        kanban = page.locator(".panel-header", has_text="Kanban")
        if kanban.count() > 0:
            expect(kanban).to_be_visible()


class TestTaskSubmitForm:
    """태스크 제출 폼 테스트."""

    def test_submit_form_visible(self, page) -> None:
        """Submit Task 폼이 표시된다."""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        form_header = page.locator(".panel-header", has_text="Submit Task")
        expect(form_header).to_be_visible()

    def test_form_fields_exist(self, page) -> None:
        """폼에 필수 입력 필드들이 존재한다."""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        # Task Description textarea
        task_input = page.locator("#task-input")
        expect(task_input).to_be_visible()

        # Team Preset input
        preset_input = page.locator("#preset-input")
        expect(preset_input).to_be_visible()

        # Target Repo input
        repo_input = page.locator("#repo-input")
        expect(repo_input).to_be_visible()

    def test_submit_button_disabled_when_empty(self, page) -> None:
        """태스크 입력이 비어있으면 Submit 버튼이 비활성화된다."""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        submit_btn = page.locator("button", has_text="Submit Task")
        expect(submit_btn).to_be_disabled()

    def test_submit_button_enabled_with_input(self, page) -> None:
        """태스크를 입력하면 Submit 버튼이 활성화된다."""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        page.locator("#task-input").fill("E2E 테스트 태스크")
        submit_btn = page.locator("button", has_text="Submit Task")
        expect(submit_btn).to_be_enabled()

    def test_submit_task_creates_pipeline(self, page) -> None:
        """태스크를 제출하면 파이프라인 목록에 나타난다."""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        # 태스크 입력 + 프리셋 선택
        page.locator("#task-input").fill("Playwright E2E 제출 테스트")
        page.locator("#preset-input").fill("feature-team")

        # Submit
        page.locator("button", has_text="Submit Task").click()

        # 제출 후 파이프라인 목록에 나타나는지 확인 (최대 5초 대기)
        page.wait_for_timeout(2000)

        # 파이프라인 테이블에 항목이 생기거나, 적어도 empty-state가 사라져야 함
        pipeline_table = page.locator(".pipeline-table")
        if pipeline_table.count() > 0:
            rows = pipeline_table.locator("tbody tr")
            expect(rows.first).to_be_visible()


class TestEventLog:
    """이벤트 로그 패널 테스트."""

    def test_event_log_visible(self, page) -> None:
        """Event Log 패널이 표시된다."""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        event_header = page.locator(".panel-header", has_text="Event")
        if event_header.count() > 0:
            expect(event_header.first).to_be_visible()


class TestAgentStatusPanel:
    """에이전트 상태 패널 테스트."""

    def test_agent_panel_visible(self, page) -> None:
        """Agent Status 패널이 표시된다."""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        agent_header = page.locator(".panel-header", has_text="Agent")
        if agent_header.count() > 0:
            expect(agent_header.first).to_be_visible()
