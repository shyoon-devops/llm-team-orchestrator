---
name: qa-verification
description: QA 검증 절차 — 구현 완료 후 반드시 수행
---

# QA 검증 절차

구현 완료 후 아래 순서로 검증한다. 하나라도 실패하면 구현 수정.

## 1. 정적 분석
```bash
uv run ruff check src/ tests/       # 0 errors
uv run ruff format --check src/ tests/  # 0 diffs
uv run mypy src/                     # 0 errors (strict)
```

## 2. 자동 테스트
```bash
uv run pytest tests/ -q --tb=short   # 전체 통과
uv run pytest tests/ -q -m "" --tb=short  # E2E 포함 전체 통과
```

## 3. CLI 수동 검증
```bash
uv pip install -e .
orchestrator --help                  # 명령어 목록 확인
orchestrator presets list            # 프리셋 목록 (6 agents, 3 teams)
orchestrator presets show feature-team  # 팀 프리셋 상세
orchestrator serve &                 # 서버 시작 (포트 9000)
curl http://localhost:9000/api/health  # {"status": "ok"}
curl http://localhost:9000/api/presets/agents  # 에이전트 프리셋 목록
orchestrator run "hello" --team-preset feature-team --timeout 30  # 실제 실행
```

## 4. 웹 대시보드 검증
```bash
cd frontend && npm install && npm run dev  # 포트 3000
# 브라우저에서 확인:
# - http://localhost:3000 접속
# - Task Board 표시
# - Submit Task 폼 동작
# - WebSocket 연결 (Connected 표시)
```

## 5. 명세 대비 검증
- CHECKLIST.md 전항목 [x] 확인
- cross-reference.md 전항목 ✅ 확인
- dry-run.md 시나리오 재트레이스

## 6. 결과물 오염 확인
```bash
git status  # 예상치 못한 파일 없는지 (node_modules, .codex, __pycache__)
git diff --stat  # 변경 범위 확인
```
