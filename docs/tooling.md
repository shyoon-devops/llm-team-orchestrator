# Claude 작업 환경 명세 — Skills + MCP + 작업별 매핑

> 이 문서는 Claude가 구현 작업을 수행할 때 사용하는 도구 환경을 정의한다.

---

## 1. 필요 Skills

### 글로벌 Skills (~/.claude/skills/)

| Skill | 용도 | 사용 Phase |
|-------|------|-----------|
| `frontend-design` | React 대시보드 UI 품질 | Phase 5 (대시보드) |
| `react-best-practices` | React 성능 최적화 57규칙 | Phase 5 (대시보드) |
| `web-design-guidelines` | 접근성/성능 100+ 규칙 | Phase 5 (대시보드) |

### 프로젝트 Skills (.claude/skills/)

| Skill | 파일 | 용도 |
|-------|------|------|
| `python-conventions` | `.claude/skills/python-conventions.md` | Python 코드 컨벤션 (conventions.md 기반) |
| `spec-compliance` | `.claude/skills/spec-compliance.md` | 명세 준수 검증 절차 |
| `testing-patterns` | `.claude/skills/testing-patterns.md` | 테스트 작성 패턴 (testing.md 기반) |

## 2. 필요 MCP 서버

| MCP 서버 | 용도 | 사용 시점 |
|----------|------|----------|
| `@anthropic-ai/mcp-filesystem` | 파일 시스템 탐색/조작 | 전 Phase |
| `@anthropic-ai/mcp-git` | Git 작업 (branch, commit, diff) | 전 Phase |

## 3. Task별 도구 매핑

| Phase | Task | Skills | MCP | 참고 명세 |
|-------|------|--------|-----|----------|
| 1 | 3-Layer 구조 전환 | python-conventions, spec-compliance | git | [file-structure.md](file-structure.md), [architecture.md](architecture.md) |
| 1 | OrchestratorEngine | python-conventions | - | [functions.md](functions.md#orchestratorengine), [data-models.md](data-models.md) |
| 1 | CLI thin client | python-conventions | - | [api-spec.md](api-spec.md), [deployment.md](deployment.md) |
| 2 | 프리셋 시스템 | python-conventions, spec-compliance | - | [presets-guide.md](presets-guide.md), [data-models.md](data-models.md#프리셋) |
| 3 | Hybrid 오케스트레이션 | python-conventions | - | [architecture.md](architecture.md#hybrid), [functions.md](functions.md#taskboard) |
| 4 | 에러 핸들링 | python-conventions | - | [errors.md](errors.md), [functions.md](functions.md) |
| 5 | 대시보드 | frontend-design, react-best-practices, web-design-guidelines | - | [websocket-protocol.md](websocket-protocol.md), [api-spec.md](api-spec.md) |
| 6 | E2E 테스트 | testing-patterns, spec-compliance | git | [testing.md](testing.md#e2e), [api-spec.md](api-spec.md) |
| 7 | CI/CD + 릴리스 | - | git | [cicd.md](cicd.md), [deployment.md](deployment.md) |
