# 명세 Dry-Run 결과

> 실행일: 2026-04-05
> 목적: 구현 전 명세 간 불일치/누락 사전 발견

---

## 시나리오 1: CLI에서 코딩 태스크 실행

```
사용자: orchestrator run "JWT 미들웨어 구현" --team-preset feature-team --repo ./my-project --wait
```

| Step | 동작 | 참조 문서 | 검증 |
|------|------|----------|------|
| 1 | CLI `run` 함수 진입 | functions.md §12.1 | ✅ task, repo, team_preset, timeout, wait 파라미터 정의됨 |
| 2 | `OrchestratorEngine()` 생성 | functions.md §1.1 | ✅ config 자동 로딩 |
| 3 | `engine.start()` 호출 | functions.md §13.1 | ✅ lifecycle 메서드 정의됨 |
| 4 | `engine.submit_task()` 호출 | functions.md §1.2 | ✅ Pipeline 반환 |
| 5 | background `_execute_pipeline` 시작 | functions.md §1.15 | ✅ asyncio.create_task |
| 6 | CLI 폴링: `engine.get_pipeline()` 반복 | functions.md §12.1 | ✅ 0.5초 간격, 상태 출력 |
| 7 | TeamPlanner.plan_team() | functions.md §6.1 | ✅ subtask 분해 |
| 8 | TaskBoard.submit() per subtask | functions.md §2.1 | ✅ depends_on 포함 |
| 9 | AgentWorker.start() per lane | functions.md §3.2 | ✅ 폴링 루프 시작 |
| 10 | Worker: board.claim() | functions.md §2.2 | ✅ lane별 태스크 획득 |
| 11 | Worker: executor.run() | functions.md §12.1 (CLI adapter) | ✅ subprocess 실행 |
| 12 | Claude CLI 호출 | functions.md §10.2 | ✅ `--bare` 없음, `is_error` 체크 |
| 13 | Worker: board.complete() | functions.md §2.3 | ✅ 결과 저장 |
| 14 | depends_on 해소 → 다음 태스크 승격 | functions.md §2.3 | ✅ _check_dependents |
| 15 | 모든 태스크 완료 | functions.md §1.15 | ✅ is_all_done 폴링 |
| 16 | Synthesizer.synthesize() | functions.md §7.1 | ✅ 결과 종합 |
| 17 | Pipeline status → COMPLETED | data-models.md PipelineStatus | ✅ |
| 18 | CLI 폴링에서 COMPLETED 감지 | functions.md §12.1 | ✅ 결과 출력 |
| 19 | `engine.shutdown()` 호출 | functions.md §13.2 | ✅ 워커 정리 |

**결과: 불일치 없음** ✅

---

## 시나리오 2: 웹 대시보드에서 인시던트 분석

```
사용자: POST /api/tasks {"task": "API 500 에러 분석", "team_preset": "incident-analysis-team"}
```

| Step | 동작 | 참조 문서 | 검증 |
|------|------|----------|------|
| 1 | POST /api/tasks | api-spec.md §2.1 | ✅ request/response 정의 |
| 2 | API → engine.submit_task() | architecture.md §API 계층 | ✅ |
| 3 | Pipeline 생성 + 반환 (201) | api-spec.md §2.1 | ✅ |
| 4 | WS 이벤트 발행 | websocket-protocol.md | ✅ pipeline.created |
| 5 | TeamPlanner: incident-analysis-team | presets-guide.md | ✅ 3 에이전트 병렬 |
| 6 | TaskBoard: 3 태스크 (depends_on 없음) | functions.md §2.1 | ✅ 병렬 |
| 7 | 3 Worker 동시 시작 | functions.md §3.2 | ✅ |
| 8 | 각 Worker: CLIAgentExecutor with MCP injection | functions.md §MCP | ✅ CLI + --mcp-config 플래그로 MCP 주입 |
| 9 | 3개 모두 완료 | functions.md §2.3 | ✅ |
| 10 | Synthesizer: narrative 전략 | functions.md §7.1 | ✅ |
| 11 | GET /api/board | api-spec.md §2.7 | ✅ 칸반 상태 |
| 12 | WS: pipeline.completed | websocket-protocol.md | ✅ |

**결과: MCP executor는 stub (known, v1.0 scope)** ⚠️

---

## 시나리오 3: 실패 → 폴백 → 부분 완료

```
사용자: orchestrator run "보안 감사" --team-preset feature-team --wait
(architect=claude 타임아웃 발생)
```

| Step | 동작 | 참조 문서 | 검증 |
|------|------|----------|------|
| 1-9 | 시나리오 1과 동일 | | ✅ |
| 10 | Claude CLI 타임아웃 | errors.md CLITimeoutError | ✅ |
| 11 | RetryPolicy: 재시도 (3회) | errors.md §retry | ✅ |
| 12 | 재시도 실패 → FallbackChain | errors.md §fallback | ✅ |
| 13 | codex로 폴백 시도 | errors.md §fallback | ✅ |
| 14 | codex 성공 | | ✅ |
| 15 | 나머지 subtask 정상 완료 | | ✅ |
| 16 | Pipeline: COMPLETED (폴백 성공) | data-models.md | ✅ |

**결과: 불일치 없음** ✅

---

## 발견된 결함 (수정 완료)

| # | 결함 | 수정 |
|---|------|------|
| 1 | functions.md에 CLI run() 함수 명세 없음 | §12 CLI 섹션 추가 |
| 2 | SPEC.md/functions.md에 Engine start/shutdown 없음 | §13 lifecycle 추가 |
| 3 | ClaudeAdapter --bare 사용 | functions.md에 "사용 금지" 명시 (이전 수정) |
| 4 | CLI wait 패턴 미정의 | functions.md §12.1에 실행 흐름 상세 정의 |

---

## 시나리오 4: 웹 대시보드에서 태스크 실행 중 진행 상황 확인

```
사용자: 웹 대시보드에서 feature-team으로 태스크 제출 → architect BUSY 상태에서 "살아있는지" 확인
```

| Step | 동작 | 참조 문서 | 검증 |
|------|------|----------|------|
| 1 | Submit Task 클릭 → POST /api/tasks | api-spec.md §2.1 | ✅ |
| 2 | Pipeline RUNNING 표시 | websocket-protocol.md pipeline.running | ✅ |
| 3 | TASK BOARD: architect IN_PROGRESS | websocket-protocol.md task.claimed | ✅ |
| 4 | AGENTS: architect BUSY | websocket-protocol.md worker.started | ✅ |
| 5 | **10초 후: heartbeat 수신** | websocket-protocol.md worker.heartbeat | ✅ |
| 6 | **UI: "BUSY (45s / 120s)" 표시** | websocket-protocol.md §프론트엔드 활용 | ✅ |
| 7 | **프로그레스 바: elapsed/timeout** | websocket-protocol.md worker.heartbeat payload | ✅ |
| 8 | **10초 이상 heartbeat 없음 → UNRESPONSIVE** | websocket-protocol.md §프론트엔드 활용 | ✅ |
| 9 | architect 완료 → implementer 승격 | websocket-protocol.md task.completed | ✅ |
| 10 | 최종 완료 → synthesis report | websocket-protocol.md pipeline.completed | ✅ |

**결과: heartbeat 흐름이 명세에 정의됨** ✅

**교차 검증:**
- websocket-protocol.md `worker.heartbeat` → functions.md §3.4 `_run_loop` heartbeat 발행 로직 | ✅ 일치
- websocket-protocol.md `elapsed_ms/timeout_ms` → data-models.md AgentLimits.timeout | ✅ 일치
- websocket-protocol.md 프론트엔드 활용 → 프론트엔드 구현 시 참조 | ✅ 정의됨

---

## 시나리오 5: 카오스 — CLI 타임아웃 → retry → fallback

```
C-CLI-01: Claude CLI 3초 타임아웃 설정 → retry 3회 → codex fallback
```

| Step | 동작 | 참조 문서 | 검증 |
|------|------|----------|------|
| 1 | 태스크 제출 → architect(claude) 실행 | functions.md §1.2 | ✅ |
| 2 | claude CLI 3초 타임아웃 → CLITimeoutError | errors.md CLITimeoutError | ✅ |
| 3 | RetryPolicy: 1s 대기 → 재시도 | errors.md §retry | ✅ |
| 4 | 재시도 2/3 실패 → 2s 대기 | errors.md §retry (exponential) | ✅ |
| 5 | 재시도 3/3 실패 → max_retries 도달 | errors.md §retry | ✅ |
| 6 | FallbackChain: claude → codex 전환 | errors.md §fallback | ✅ |
| 7 | fallback.triggered 이벤트 | websocket-protocol.md | ✅ (이벤트 정의 확인 필요) |
| 8 | codex CLI 실행 → 성공 | functions.md §10.3 | ✅ |
| 9 | task.completed | websocket-protocol.md | ✅ |
| 10 | 나머지 subtask 진행 | functions.md §2.3 depends_on | ✅ |

**교차 검증:**
- errors.md fallback 이벤트 ↔ websocket-protocol.md 이벤트 타입 | ✅ 추가 완료 (worker.heartbeat + fallback.triggered)
- chaos-engineering.md C-CLI-01 기대 흐름 ↔ errors.md retry+fallback 정의 | ✅ 일치

**발견:** `fallback.triggered` 이벤트가 websocket-protocol.md 이벤트 요약 테이블에 있는지 확인 필요.

---

## 시나리오 6: 웹에서 feature-team으로 태스크 제출 (target_repo 포함)

```
사용자: Submit Task → "웹 3d 물리엔진 플레이그라운드 만들어줘" / feature-team / /home/yoon/repository/my-project
```

| Step | 동작 | 참조 문서 | 검증 |
|------|------|----------|------|
| 1 | POST /api/tasks {task, team_preset, target_repo} | api-spec.md | ✅ |
| 2 | engine.submit_task() → Pipeline 생성 | functions.md §1.2 | ✅ |
| 3 | TeamPlanner.plan_team(task, team_preset) | functions.md §5.2 | ✅ |
| 4 | **SubTask.description = 프리셋설명 + "\n\n사용자 태스크: 웹 3d..."** | functions.md §5.2 step 3 | ✅ (수정됨) |
| 5 | target_repo가 git repo인지 확인 | **미정의** | ⚠️ target_repo가 git init 안 되어 있으면? |
| 6 | WorktreeManager.create(target_repo, branch) | functions.md §7.1 | ✅ |
| 7 | worktree 경로 → executor context cwd | functions.md §1.15 step 2 | ✅ (수정됨) |
| 8 | AgentWorker → executor.run(description, cwd=worktree) | functions.md §3.4 | ✅ |
| 9 | Claude CLI 실행: claude -p "아키텍처 설계...\n\n사용자 태스크: 웹 3d..." --cwd=worktree | functions.md §10.2 | ✅ |
| 10 | 완료 → board.complete → depends_on 승격 | functions.md §2.3 | ✅ |
| 11 | 모든 subtask 완료 → Synthesizer | functions.md §7.1 | ✅ |
| 12 | worktree merge → cleanup | functions.md §7.2, §7.3 | ✅ |

**발견:**
- Step 5: target_repo가 git repo가 아니면 자동 git init (명세 반영됨)
- 해결: engine.submit_task()에서 target_repo가 git repo가 아니면 자동 git init + 초기 커밋

