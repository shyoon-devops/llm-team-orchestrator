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


---

## 시나리오 7: v2 — 컨텍스트 체이닝 + cwd 격리 + 서브태스크 UI

```
사용자: "웹 3d 물리엔진 플레이그라운드 만들어줘" / feature-team / /home/yoon/repository/my-project
```

| Step | 동작 | 참조 문서 | 검증 |
|------|------|----------|------|
| 1 | POST /api/tasks → engine.submit_task() | api-spec.md | ✅ |
| 2 | target_repo가 git repo 아님 → 자동 git init | v2-spec.md §2, functions.md §1.2 | ✅ |
| 3 | **cwd 자기보호**: target_repo ≠ 오케스트레이터 디렉토리 확인 | v2-spec.md §2 | ✅ |
| 4 | TeamPlanner.plan_team() → 4 subtask (architect→impl→review→test) | functions.md §5.2 | ✅ |
| 5 | subtask description = 프리셋설명 + 사용자태스크 | functions.md §5.2 step 3 | ✅ |
| 6 | worktree 생성 → cwd = worktree_path | functions.md §1.15 step 2 | ✅ |
| 7 | architect 워커 시작 → executor.run(prompt, cwd=worktree) | v2-spec.md §2 | ✅ |
| 8 | Claude CLI 실행 in cwd=worktree (오케스트레이터 디렉토리 아님) | functions.md §10.2 | ✅ |
| 9 | architect 완료 → board.complete(result) → result 저장 | functions.md §2.3 | ✅ |
| 10 | implementer 승격 → **_build_prompt(): architect 결과를 프롬프트에 주입** | v2-spec.md §3 | ✅ |
| 11 | implementer 실행 (architect 결과 + 사용자 태스크 포함 프롬프트) | v2-spec.md §3 | ✅ |
| 12 | implementer 완료 → reviewer/tester 승격 (각각 implementer 결과 주입) | v2-spec.md §3 | ✅ |
| 13 | 모든 subtask 완료 → Synthesizer | functions.md §7.1 | ✅ |
| 14 | GET /api/tasks/{id}/subtasks → 서브태스크 상세 | v2-spec.md §4 | ✅ |
| 15 | GET /api/tasks/{id}/files → 생성된 파일 목록 | v2-spec.md §4 | ✅ |
| 16 | 프론트엔드: PipelineDetail → SubtaskList + FileExplorer | v2-spec.md §4 | ✅ |
| 17 | my-project/ 에 파일 생성 확인, 오케스트레이터 디렉토리 오염 없음 | v2-spec.md §6 | ✅ |

**결과: 불일치 없음** ✅

**교차 검증:**
- v2-spec.md §2 cwd 자기보호 ↔ functions.md submit_task pre-conditions | ✅
- v2-spec.md §3 _build_prompt ↔ functions.md §3.4 _run_loop | ✅ (v2에서 추가)
- v2-spec.md §4 subtask API ↔ api-spec.md | ⚠️ api-spec.md에 아직 추가 안 됨 → v2 구현 시 추가

---

## 시나리오 8: v2 반복 — worktree 결과물 수집 + merge

```
사용자: "add 함수 작성" / feature-team / /home/yoon/repository/my-project
```

| Step | 동작 | 참조 문서 | 검증 |
|------|------|----------|------|
| 1 | POST /api/tasks → pipeline 생성 | api-spec.md | ✅ |
| 2 | target_repo auto git init | v2-spec.md §2 | ✅ |
| 3 | worktree 생성 (per lane) | functions.md §1.15 | ✅ |
| 4 | architect 실행 (cwd=worktree) → stdout 수집 | functions.md §3.4 | ✅ |
| 5 | **architect 완료 → worktree에 파일 변경 있으면 commit** | v2-spec.md §P1.5 | ✅ (신규) |
| 6 | implementer 승격 → **_build_prompt에 architect 결과 포함** | v2-spec.md §3 | ✅ |
| 7 | **_build_prompt 로그: "context_chaining" 출력** | v2-spec.md §P1.5 | ✅ (신규) |
| 8 | implementer 실행 (cwd=worktree) → 코드 파일 생성 | v2-spec.md §2 | ✅ |
| 9 | **implementer 완료 → worktree 변경사항 commit** | v2-spec.md §P1.5 | ✅ (신규) |
| 10 | reviewer/tester 진행 (implementer 결과 포함) | v2-spec.md §3 | ✅ |
| 11 | **모든 subtask 완료 → worktree branches를 target_repo main에 merge** | v2-spec.md §P1.5 | ✅ (신규) |
| 12 | **merge 성공 → target_repo에 파일 반영** | v2-spec.md §P1.5 | ✅ (신규) |
| 13 | worktree cleanup | functions.md §1.15 | ✅ |
| 14 | Synthesizer → 종합 보고서 | functions.md §7.1 | ✅ |
| 15 | my-project/ 에 코드 파일 존재 확인 | v2-spec.md §6 | ✅ |

**교차 검증:**
- v2-spec.md §P1.5 commit/merge ↔ functions.md §7 WorktreeManager | ✅
- v2-spec.md §P1.5 로그 ↔ worker._build_prompt | ✅

---

## 시나리오 9: v2 iter3 — CLI에게 파일 생성 지시

```
사용자: "add 함수 작성" / feature-team / /home/yoon/repository/my-project
```

| Step | 동작 | 참조 문서 | 검증 |
|------|------|----------|------|
| 1-6 | 시나리오 8과 동일 (파이프라인 생성 → worktree → architect 실행) | | ✅ |
| 7 | architect stdout 결과 → board.complete | | ✅ |
| 8 | implementer 승격 → _build_prompt(architect 결과 포함) | v2-spec.md §3 | ✅ |
| 9 | **_build_prompt에 "작업 디렉토리: {cwd}" + "파일 직접 생성" 지시 추가** | v2-spec.md §4.5 | ✅ (신규) |
| 10 | **implementer 프리셋 constraints에 "파일 직접 생성" 포함** | v2-spec.md §4.5 | ✅ (신규) |
| 11 | implementer CLI 실행 (cwd=worktree) → **실제 파일 생성** | v2-spec.md §4.5 | ✅ |
| 12 | implementer 완료 → worktree에 변경사항 있음 | v2-spec.md §P1.5 | ✅ |
| 13 | **_commit_worktree_changes → git commit** | v2-spec.md §P1.5 | ✅ |
| 14 | tester도 파일 생성 지시 → 테스트 파일 생성 | v2-spec.md §4.5 | ✅ |
| 15 | 모든 완료 → **merge_to_target → target_repo에 파일 반영** | v2-spec.md §P1.5 | ✅ |
| 16 | my-project/ 에 코드 파일 + 테스트 파일 존재 | v2-spec.md §6 | ✅ |

**교차 검증:**
- v2-spec.md §4.5 프롬프트 지시 ↔ presets/agents/implementer.yaml constraints | ✅
- worker._build_prompt cwd 안내 ↔ executor context cwd | ✅

---

## 시나리오 10: v2 iter4 — codex --ephemeral 제거

| Step | 동작 | 검증 |
|------|------|------|
| 1-8 | 시나리오 9와 동일 | ✅ |
| 9 | codex 명령: `codex exec --json --full-auto "{prompt}"` (**--ephemeral 없음**) | ✅ |
| 10 | cwd=worktree_path에서 실행 → codex가 **실제 파일 생성** | ✅ |
| 11 | worktree에 git 변경사항 존재 | ✅ |
| 12 | _commit_worktree_changes → git commit 성공 | ✅ |
| 13 | merge_to_target → target_repo main에 파일 반영 | ✅ |
| 14 | my-project/에 코드 파일 존재 | ✅ |

**교차 검증:**
- functions.md §10.3 codex 명령 ↔ 구현 CodexAdapter._build_command | ✅ (--ephemeral 제거됨)
