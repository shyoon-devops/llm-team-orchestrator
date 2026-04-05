---
name: spec-compliance
description: 명세 준수 검증 절차 — 구현 후 반드시 수행
---

# 명세 준수 검증

구현 완료 후 반드시 이 절차를 수행한다.

## 검증 순서

1. **파일 존재 확인** — `docs/file-structure.md` 기준으로 모든 파일 존재 여부 체크
2. **클래스/함수 시그니처** — `docs/data-models.md`, `docs/functions.md` 기준으로 정확한 이름, 파라미터, 타입, 기본값 일치 확인
3. **API 엔드포인트** — `docs/api-spec.md` 기준으로 path, method, request/response 스키마 일치
4. **에러 코드** — `docs/errors.md` 기준으로 에러 클래스, 코드, HTTP 매핑 일치
5. **테스트** — `docs/testing.md` 기준으로 테스트 함수명, 시나리오 일치
6. **설정값** — `docs/dependencies.md`, `docs/deployment.md` 기준으로 환경변수, 기본값 일치

## CHECKLIST.md 작성 규칙

```markdown
# 명세 검증 체크리스트

## 파일 구조 (file-structure.md)
- [x] src/orchestrator/core/engine.py 존재
- [x] src/orchestrator/core/queue/board.py 존재
- [ ] src/orchestrator/core/planner/team_planner.py 존재  ← 미구현

## 클래스/함수 시그니처 (data-models.md, functions.md)
- [x] OrchestratorEngine.submit_task(task, *, team_preset, target_repo) -> Pipeline
- [x] TaskBoard.submit(task: TaskItem) -> str
...
```

## 규칙
- `- [x]` = 통과, `- [ ]` = 미통과
- 미통과 항목이 있으면 구현 수정 (명세 변경 아님)
- CHECKLIST.md는 구현 브랜치에 반드시 포함
- 명세 자체에 오류 발견 시 → 사용자에게 보고 후 승인받고 수정
