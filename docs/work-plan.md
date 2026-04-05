# 구현 작업 계획서

> 작업 주체: Claude
> 진입점: 이 문서를 읽고 Phase 순서대로 실행
> 명세 브랜치: `mvp` (이 문서가 있는 곳)
> 구현 브랜치: `mvp-impl/{phase}` (Phase별 분기)

---

## 작업 전 체크리스트 (매 Task 시작 시)

```
□ 지침 22개 항목 리마인드
□ 명세 교차 검증 (docs/cross-reference.md 전체 ✅ 확인)
□ 명세 Dry-Run 수행 (docs/dry-run.md에 결과 기록)
□ 필요 skills 활성화 확인
□ 구현 브랜치 확인 (mvp-impl/{phase})
□ 참고 명세 링크 열기
```

---

## Phase 1: 3-Layer 구조 전환 (Week 1)

> 구현 브랜치: `mvp-impl/phase-1`
> Skills: `python-conventions`, `spec-compliance`

### T1.1 프로젝트 스캐폴딩

| 항목 | 값 |
|------|-----|
| **산출물** | `pyproject.toml`, `.python-version`, `src/orchestrator/__init__.py`, `src/orchestrator/__main__.py` |
| **참고 명세** | [dependencies.md](dependencies.md) — pyproject.toml 전체 내용 복사, [file-structure.md](file-structure.md) — 루트 파일 목록 |
| **Skills** | `python-conventions` |
| **검증** | `uv sync --dev` 성공, `uv pip install -e .` 성공, `orchestrator --help` 동작, `uv run orchestrator --help` 동작 |
| **주의** | `uv sync`만으로는 CLI 진입점 미등록. 반드시 `uv pip install -e .` 필요. 참고: [deployment.md](deployment.md#12-cli-설치-필수) |

### T1.2 Core 계층 — models + errors

| 항목 | 값 |
|------|-----|
| **산출물** | `src/orchestrator/core/models/schemas.py`, `src/orchestrator/core/models/pipeline.py`, `src/orchestrator/core/errors/exceptions.py` |
| **참고 명세** | [data-models.md](data-models.md#coremodelsschemaspy) — AgentResult, AdapterConfig 정확한 필드, [data-models.md](data-models.md#coremodels) — Pipeline, SubTask, WorkerResult, [errors.md](errors.md) — 24개 에러 클래스 전체 |
| **Skills** | `python-conventions` |
| **검증** | `uv run mypy src/orchestrator/core/models/ src/orchestrator/core/errors/` |

### T1.3 Core 계층 — events

| 항목 | 값 |
|------|-----|
| **산출물** | `src/orchestrator/core/events/types.py`, `src/orchestrator/core/events/bus.py` |
| **참고 명세** | [data-models.md](data-models.md#coreeventstypespy) — EventType 28개, OrchestratorEvent, [functions.md](functions.md#eventbus) — publish, subscribe, unsubscribe |
| **Skills** | `python-conventions` |
| **검증** | `uv run pytest tests/unit/test_events.py` |

### T1.4 Core 계층 — adapters

| 항목 | 값 |
|------|-----|
| **산출물** | `src/orchestrator/core/adapters/base.py`, `claude.py`, `codex.py`, `gemini.py`, `factory.py` |
| **참고 명세** | [data-models.md](data-models.md#coreexecutorbasepy) — CLIAdapter ABC, [functions.md](functions.md#cliadapter-서브클래스) — run(), health_check() CLI별 구현, [functions.md](functions.md#adapterfactory) — create() 흐름 |
| **Skills** | `python-conventions` |
| **검증** | `uv run pytest tests/unit/test_adapters.py` |

### T1.5 Core 계층 — executor

| 항목 | 값 |
|------|-----|
| **산출물** | `src/orchestrator/core/executor/base.py`, `cli_executor.py`, `mcp_executor.py`, `synthesizer.py` |
| **참고 명세** | [data-models.md](data-models.md#coreexecutor) — AgentExecutor ABC, CLIAgentExecutor, CLIAgentExecutor, [functions.md](functions.md#synthesizer) — synthesize() 전략별 |
| **Skills** | `python-conventions` |
| **검증** | `uv run pytest tests/unit/test_executor.py tests/unit/test_synthesizer.py` |

### T1.6 Core 계층 — queue

| 항목 | 값 |
|------|-----|
| **산출물** | `src/orchestrator/core/queue/models.py`, `board.py`, `worker.py` |
| **참고 명세** | [data-models.md](data-models.md#corequeuemodelspy) — TaskState, TaskItem, [functions.md](functions.md#taskboard) — submit, claim, complete, fail, [functions.md](functions.md#agentworker) — start, stop, _run_loop |
| **Skills** | `python-conventions` |
| **검증** | `uv run pytest tests/unit/test_board.py tests/unit/test_worker.py` |

### T1.7 Core 계층 — auth, config, context, worktree

| 항목 | 값 |
|------|-----|
| **산출물** | `auth/provider.py`, `auth/key_pool.py`, `config/schema.py`, `config/loader.py`, `context/artifact_store.py`, `worktree/manager.py`, `worktree/collector.py` |
| **참고 명세** | [data-models.md](data-models.md#coreauthproviderpy) — AuthProvider, [data-models.md](data-models.md#coreconfigschemapy) — OrchestratorConfig, [functions.md](functions.md#worktreemanager) — create, cleanup, merge |
| **Skills** | `python-conventions` |
| **검증** | `uv run pytest tests/unit/test_auth.py tests/unit/test_config.py tests/unit/test_artifact_store.py tests/unit/test_worktree.py` |

### T1.8 Core 계층 — OrchestratorEngine

| 항목 | 값 |
|------|-----|
| **산출물** | `src/orchestrator/core/engine.py` |
| **참고 명세** | [functions.md](functions.md#orchestratorengine) — 15개 메서드 전체, [architecture.md](architecture.md) — Engine 역할 |
| **Skills** | `python-conventions` |
| **듀얼 검증** | **필수** — 핵심 모듈. 2개 병렬 구현 → diff |
| **검증** | `uv run pytest tests/unit/test_engine.py` |

### T1.9 API 계층

| 항목 | 값 |
|------|-----|
| **산출물** | `src/orchestrator/api/app.py`, `routes.py`, `ws.py`, `deps.py` |
| **참고 명세** | [api-spec.md](api-spec.md) — 18개 엔드포인트 전체, [websocket-protocol.md](websocket-protocol.md) — WS 메시지 포맷, [architecture.md](architecture.md#api-계층) — 의존성 주입 |
| **Skills** | `python-conventions` |
| **검증** | `uv run pytest tests/api/` |

### T1.10 Interface 계층 — CLI

| 항목 | 값 |
|------|-----|
| **산출물** | `src/orchestrator/cli.py` |
| **참고 명세** | [deployment.md](deployment.md#cli-명령어) — 8개 커맨드 그룹, [api-spec.md](api-spec.md) — CLI가 호출할 엔드포인트 |
| **Skills** | `python-conventions` |
| **검증** | `orchestrator --help` 동작 |

### T1.11 테스트 인프라

| 항목 | 값 |
|------|-----|
| **산출물** | `tests/conftest.py`, `tests/unit/conftest.py`, `tests/api/conftest.py`, `tests/fixtures/*.json` |
| **참고 명세** | [testing.md](testing.md#fixtures) — 모든 fixture 정의, conftest 코드 |
| **Skills** | `testing-patterns` |
| **검증** | `uv run pytest tests/ --co` (test collection 성공) |

### T1.12 Phase 1 검증

| 항목 | 값 |
|------|-----|
| **산출물** | `CHECKLIST.md` |
| **참고 명세** | 전체 명세 |
| **Skills** | `spec-compliance` |
| **검증** | 모든 `- [x]` 체크, `uv run ruff check`, `uv run mypy`, `uv run pytest` |

---

## Phase 2: 프리셋 시스템 (Week 2)

> 구현 브랜치: `mvp-impl/phase-2`
> Skills: `python-conventions`, `spec-compliance`

### T2.1 프리셋 모델 + 레지스트리

| 항목 | 값 |
|------|-----|
| **산출물** | `src/orchestrator/core/presets/models.py`, `registry.py` |
| **참고 명세** | [data-models.md](data-models.md#corepresetsmodelspy) — PersonaDef, AgentPreset, TeamPreset, [functions.md](functions.md#presetregistry) — load, list, merge, [presets-guide.md](presets-guide.md) — YAML 스키마 |
| **듀얼 검증** | **필수** |
| **검증** | `uv run pytest tests/unit/test_presets.py` |

### T2.2 기본 프리셋 번들

| 항목 | 값 |
|------|-----|
| **산출물** | `presets/agents/*.yaml` (5개), `presets/teams/*.yaml` (3개) |
| **참고 명세** | [presets-guide.md](presets-guide.md#예제-프리셋) — 5개 에이전트 + 3개 팀 정확한 YAML |
| **검증** | `uv run pytest tests/unit/test_preset_loading.py` |

### T2.3 TeamPlanner

| 항목 | 값 |
|------|-----|
| **산출물** | `src/orchestrator/core/planner/team_planner.py` |
| **참고 명세** | [functions.md](functions.md#teamplanner) — plan_team() 흐름, [architecture.md](architecture.md#hybrid) — LangGraph planning |
| **검증** | `uv run pytest tests/unit/test_planner.py` |

### T2.4 프리셋 API + CLI

| 항목 | 값 |
|------|-----|
| **산출물** | API routes에 프리셋 엔드포인트 추가, CLI에 `presets` 커맨드 추가 |
| **참고 명세** | [api-spec.md](api-spec.md#presets) — GET/POST presets 엔드포인트 |
| **검증** | `uv run pytest tests/api/test_presets.py`, `orchestrator presets list` |

### T2.5 Phase 2 검증

| 산출물 | `CHECKLIST.md` 업데이트 |

---

## Phase 3: Hybrid 오케스트레이션 (Week 3-4)

> 구현 브랜치: `mvp-impl/phase-3`

### T3.1 HybridOrchestrator Engine 통합

| 항목 | 값 |
|------|-----|
| **산출물** | `engine.py` 업데이트 — submit_task가 HybridOrchestrator 사용 |
| **참고 명세** | [architecture.md](architecture.md#hybrid-오케스트레이션-모델) — 전체 흐름, [functions.md](functions.md#orchestratorengine) — submit_task, _execute_pipeline |
| **듀얼 검증** | **필수** |

### T3.2 LangGraph Planning 그래프

| 항목 | 값 |
|------|-----|
| **산출물** | `src/orchestrator/core/graph/planner_graph.py` |
| **참고 명세** | [architecture.md](architecture.md#langgraph-planning) — compose_team → decompose_task → submit_to_board |

### T3.3 Worktree + FileDiff 통합

| 항목 | 값 |
|------|-----|
| **산출물** | AgentWorker에 worktree 생성/정리 로직 통합 |
| **참고 명세** | [functions.md](functions.md#worktreemanager), [architecture.md](architecture.md#데이터-흐름) |

### T3.4 Phase 3 검증

---

## Phase 4: 에러 핸들링 + Synthesizer (Week 5)

> 구현 브랜치: `mvp-impl/phase-4`

### T4.1 폴백 체인

| 참고 명세 | [errors.md](errors.md#폴백-체인) |

### T4.2 RetryPolicy

| 참고 명세 | [errors.md](errors.md#retry-설정) |

### T4.3 Synthesizer 프로덕션

| 참고 명세 | [functions.md](functions.md#synthesizer), [data-models.md](data-models.md#teampreset) — synthesis_strategy |

### T4.4 Phase 4 검증

---

## Phase 5: 체크포인팅 + 대시보드 (Week 6)

> 구현 브랜치: `mvp-impl/phase-5`
> Skills: `frontend-design`, `react-best-practices`, `web-design-guidelines`

### T5.1 LangGraph 체크포인터

| 참고 명세 | [architecture.md](architecture.md#체크포인팅) |

### T5.2 Resume 기능

| 참고 명세 | [api-spec.md](api-spec.md#post-apitasksidresume), [functions.md](functions.md#resume_task) |

### T5.3 React 대시보드

| 참고 명세 | [websocket-protocol.md](websocket-protocol.md), [api-spec.md](api-spec.md#get-apiboard) — 칸반 보드 API |
| **Skills** | `frontend-design`, `react-best-practices`, `web-design-guidelines` |

### T5.4 Phase 5 검증

---

## Phase 6: 실 에이전트 E2E (Week 7-8)

> 구현 브랜치: `mvp-impl/phase-6`
> Skills: `testing-patterns`, `spec-compliance`

### T6.1-T6.4 E2E 시나리오

| 참고 명세 | [testing.md](testing.md#e2e-시나리오) — 4개 시나리오 (코딩/장애분석/실패폴백/중단재개) |
| **CLI sandbox** | 모든 CLI 호출 시 `cwd=tempdir` 필수 |

### T6.5 Phase 6 검증

---

## Phase 7: 안정화 + 릴리스 (Week 9)

> 구현 브랜치: `mvp-impl/phase-7`

### T7.1 문서 + CI

| 참고 명세 | [cicd.md](cicd.md) — GitHub Actions 전체, [deployment.md](deployment.md) |

### T7.2 최종 검증

| 산출물 | 최종 `CHECKLIST.md` — 전체 명세 대비 완전 검증 |
| **필수 수동 검증** | `uv pip install -e .` 후 `orchestrator serve` → `orchestrator run "hello" --team-preset feature-team` 실제 실행 확인 |
| **주의** | Claude CLI `--bare` 플래그 사용 금지 (firstParty 인증 충돌). 참고: [functions.md](functions.md) ClaudeAdapter Known issues |

### T7.3 v1.0.0 릴리스

| 참고 명세 | [cicd.md](cicd.md#릴리스-프로세스) |
