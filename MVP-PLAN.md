# MVP 실행 계획

> v2.0 | 2026-04-05
> 기반: PoC v1-v8 검증 완료
> 브랜치: `mvp`

---

## PoC 검증 완료 항목

| PoC | 검증 | 테스트 |
|-----|------|--------|
| v1-v5 | CLI 어댑터, LangGraph, EventBus, 웹 대시보드, 3-CLI 통합(72초), worktree | 126 |
| v6 | 칸반 TaskBoard + AgentWorker (느슨한 결합) | 143 |
| v7 | Hybrid 모델 (LangGraph planning + TaskBoard execution) | 150 |
| v8 | AgentExecutor (CLI+MCP), Synthesizer, 인시던트 분석 팀 | 171 |

---

## Phase 요약

| Phase | 기간 | 핵심 |
|-------|------|------|
| **1** | Week 1 | 3-Layer 구조 전환, PoC→Core 재배치 |
| **2** | Week 2 | 프리셋 시스템 + 동적 팀 구성 |
| **3** | Week 3-4 | Hybrid 오케스트레이션 (LangGraph planning + TaskBoard execution) |
| **4** | Week 5 | 에러 핸들링 + 폴백 + Synthesizer |
| **5** | Week 6 | 체크포인팅 + 대시보드 (칸반 보드 뷰) |
| **6** | Week 7-8 | 실 에이전트 E2E (코딩 + 인시던트 분석 시나리오) |
| **7** | Week 9 | 안정화 + v1.0.0 릴리스 |

---

## Phase 1: 3-Layer 구조 전환 (Week 1)

| Task | 상세 |
|------|------|
| T1.1 | `adapters/`, `auth/`, `config/` 등 → `core/` 하위로 이동 |
| T1.2 | `executor/`, `queue/`, `hybrid/` → `core/` 하위로 이동 |
| T1.3 | `web/` → `api/` 승격 (★ 제거) |
| T1.4 | `poc/` 정리 — mock_adapters → tests/, demo 삭제 |
| T1.5 | `OrchestratorEngine` 구현 (Core 진입점) |
| T1.6 | CLI thin client (httpx로 API 호출) |
| T1.7 | import 경로 수정 + 테스트 마이그레이션 |

## Phase 2: 프리셋 시스템 (Week 2)

| Task | 상세 |
|------|------|
| T2.1 | `PersonaDef`, `AgentPreset`, `TeamPreset` Pydantic 모델 |
| T2.2 | `PresetRegistry` (YAML 로딩, 검색 경로, deep merge) |
| T2.3 | 기본 프리셋 번들 (architect, implementer, reviewer, tester, elk-analyst) |
| T2.4 | 팀 프리셋 번들 (feature-team, incident-analysis, deploy-team) |
| T2.5 | 어댑터/executor에 persona + mcp_servers 주입 |
| T2.6 | `TeamPlanner` (LLM 기반 자동 팀 구성) |
| T2.7 | 프리셋 API + CLI 명령 |

## Phase 3: Hybrid 오케스트레이션 (Week 3-4)

| Task | 상세 |
|------|------|
| T3.1 | `HybridOrchestrator` → Engine 통합 |
| T3.2 | LangGraph 축소 (orchestrate→decompose→board.submit만) |
| T3.3 | 기존 graph/nodes.py(plan→impl→review) 제거 |
| T3.4 | TaskBoard 실 통합 (Engine.submit_task → board) |
| T3.5 | AgentWorker 실 통합 (AgentExecutor 기반) |
| T3.6 | worktree + filediff 통합 |
| T3.7 | 전체 파이프라인 E2E (mock) |

## Phase 4: 에러 핸들링 + Synthesizer (Week 5)

| Task | 상세 |
|------|------|
| T4.1 | 폴백 체인 (cli_priority 기반) |
| T4.2 | RetryPolicy (tenacity, 어댑터별 설정) |
| T4.3 | 부분 실패 처리 (N개 중 일부 실패 → 성공 결과로 계속) |
| T4.4 | Synthesizer 프로덕션 구현 (LLM 호출로 종합) |
| T4.5 | 에러 시나리오 테스트 |

## Phase 5: 체크포인팅 + 대시보드 (Week 6)

| Task | 상세 |
|------|------|
| T5.1 | LangGraph SQLite 체크포인터 |
| T5.2 | `orchestrator resume <task-id>` |
| T5.3 | 대시보드 칸반 보드 뷰 (TaskBoard 상태 시각화) |
| T5.4 | 에이전트 상태 + 서브태스크 진행률 UI |

## Phase 6: 실 에이전트 E2E (Week 7-8)

| Task | 상세 |
|------|------|
| T6.1 | 코딩: "JWT 미들웨어 구현" → 3-CLI 파이프라인 |
| T6.2 | 코딩: 버그 수정 + 리팩토링 시나리오 |
| T6.3 | 인시던트: MCP 에이전트 팀 (실제 MCP 서버 연동) |
| T6.4 | 성능 측정 + 로깅 고도화 |

## Phase 7: 안정화 + 릴리스 (Week 9)

| Task | 상세 |
|------|------|
| T7.1 | README + CONTRIBUTING 재작성 |
| T7.2 | CI 완성 (lint + mypy + unit + integration) |
| T7.3 | 최종 리뷰 + 보안 점검 |
| T7.4 | v1.0.0 태그 + GitHub Release |
