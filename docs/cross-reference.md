# 명세 교차 검증 매트릭스

> 구현 전 반드시 이 문서의 모든 항목이 ✅인지 확인한다.
> ❌ 항목이 있으면 해당 명세를 보강한 후 구현을 시작한다.

---

## 1. architecture.md → functions.md 매핑

architecture.md에 언급된 모든 컴포넌트가 functions.md에 함수 명세를 가지고 있는가?

| architecture.md 컴포넌트 | functions.md 섹션 | 상태 |
|-------------------------|------------------|------|
| OrchestratorEngine | §1 (15 methods + lifecycle) | ✅ |
| OrchestratorEngine.start() | §13.1 | ✅ |
| OrchestratorEngine.shutdown() | §13.2 | ✅ |
| TaskBoard | §2 (10 methods) | ✅ |
| AgentWorker | §3 (4 methods) | ✅ |
| PresetRegistry | §4 (8 methods) | ✅ |
| TeamPlanner | §6 | ✅ |
| Synthesizer | §7 | ✅ |
| WorktreeManager | §8 | ✅ |
| FileDiffCollector | §9 | ✅ |
| AdapterFactory | §5 | ✅ |
| CLIAdapter (Claude/Codex/Gemini) | §10 | ✅ |
| FastAPI create_app() | §11.1 | ✅ |
| FastAPI lifespan | §11.2 | ✅ |
| API deps (get_engine) | §11.3 | ✅ |
| API routes | §11.4 | ✅ |
| WebSocketManager | §11.5 | ✅ |
| CLI run() | §12.1 | ✅ |
| CLI serve() | §12.2 | ✅ |
| FallbackChain | §(errors.md) | ✅ |
| RetryPolicy | §(errors.md) | ✅ |
| CheckpointStore | §(architecture.md) | ✅ |

## 2. file-structure.md → functions.md 매핑

file-structure.md의 모든 소스 파일이 functions.md에 대응 함수를 가지고 있는가?

| 소스 파일 | functions.md | 상태 |
|----------|-------------|------|
| core/engine.py | §1 + §13 | ✅ |
| core/queue/board.py | §2 | ✅ |
| core/queue/worker.py | §3 | ✅ |
| core/queue/models.py | data-models.md | ✅ |
| core/presets/registry.py | §4 | ✅ |
| core/presets/models.py | data-models.md | ✅ |
| core/adapters/factory.py | §5 | ✅ |
| core/adapters/base.py | §10.1 | ✅ |
| core/adapters/claude.py | §10.2 | ✅ |
| core/adapters/codex.py | §10.3 | ✅ |
| core/adapters/gemini.py | §10.4 | ✅ |
| core/planner/team_planner.py | §6 | ✅ |
| core/executor/base.py | data-models.md | ✅ |
| core/executor/cli_executor.py | data-models.md | ✅ |
| ~~core/executor/mcp_executor.py~~ | ~~삭제됨~~ — 모든 에이전트는 CLI 실행 | ✅ |
| core/events/synthesizer.py | §7 | ✅ |
| core/events/bus.py | §(data-models.md) | ✅ |
| core/events/types.py | data-models.md | ✅ |
| core/worktree/manager.py | §8 | ✅ |
| core/worktree/collector.py | §9 | ✅ |
| core/context/artifact_store.py | §(data-models.md) | ✅ |
| core/context/checkpoint.py | §(architecture.md) | ✅ |
| core/auth/provider.py | data-models.md | ✅ |
| core/config/schema.py | data-models.md | ✅ |
| core/errors/exceptions.py | errors.md | ✅ |
| core/errors/fallback.py | errors.md | ✅ |
| core/errors/retry.py | errors.md | ✅ |
| core/models/schemas.py | data-models.md | ✅ |
| core/models/pipeline.py | data-models.md | ✅ |
| api/app.py | §11.1 + §11.2 | ✅ |
| api/deps.py | §11.3 | ✅ |
| api/routes.py | §11.4 | ✅ |
| api/ws.py | §11.5 | ✅ |
| cli.py | §12 | ✅ |

## 3. api-spec.md → functions.md 매핑

| API 엔드포인트 | functions.md route 함수 | 상태 |
|---------------|----------------------|------|
| POST /api/tasks | §11.4 → engine.submit_task | ✅ |
| GET /api/tasks | §11.4 → engine.list_pipelines | ✅ |
| GET /api/tasks/{id} | §11.4 → engine.get_pipeline | ✅ |
| POST /api/tasks/{id}/resume | §11.4 → engine.resume_task | ✅ |
| DELETE /api/tasks/{id} | §11.4 → engine.cancel_task | ✅ |
| GET /api/board | §11.4 → engine.get_board_state | ✅ |
| GET /api/board/lanes | §11.4 → board specific | ✅ |
| GET /api/board/tasks/{id} | §11.4 → board specific | ✅ |
| GET /api/agents | §11.4 → engine.list_agents | ✅ |
| GET /api/presets/agents | §11.4 → engine.list_agent_presets | ✅ |
| GET /api/presets/teams | §11.4 → engine.list_team_presets | ✅ |
| POST /api/presets/agents | §11.4 → engine.save_agent_preset | ✅ |
| POST /api/presets/teams | §11.4 → engine.save_team_preset | ✅ |
| GET /api/artifacts/{task_id} | §11.4 | ✅ |
| GET /api/events | §11.4 → engine.get_events | ✅ |
| GET /api/health | §11.4 | ✅ |
| WS /ws/events | §11.5 | ✅ |

## 4. deployment.md CLI → functions.md 매핑

| CLI 옵션 (deployment.md) | functions.md 파라미터 | 상태 |
|--------------------------|---------------------|------|
| `orchestrator run TASK` | §12.1 `task: str` | ✅ |
| `--repo PATH` | §12.1 `repo: str \| None` | ✅ |
| `--team TEXT` | §12.1 `team_preset: str \| None` | ✅ |
| `--timeout INTEGER` | §12.1 `timeout: int = 600` | ✅ |
| `--wait/--no-wait` | §12.1 `wait: bool = True` | ✅ |
| `orchestrator serve --port` | §12.2 `port: int = 9000` | ✅ |
| `orchestrator serve --host` | §12.2 `host: str` | ✅ |
| `orchestrator serve --reload` | §12.2 `reload: bool` | ✅ |
| `orchestrator status` | §12.2 | ✅ |
| `orchestrator cancel` | §12.3 | ✅ |
| `orchestrator resume` | §12.4 | ✅ |
| `orchestrator presets list` | §12.5 | ✅ |
| `orchestrator presets show` | §12.6 | ✅ |
