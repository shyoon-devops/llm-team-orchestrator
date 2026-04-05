# CLAUDE.md — Agent Team Orchestrator (MVP)

## Project Overview

범용 AI 에이전트 팀 플랫폼. 인간 팀과 동일한 방식으로 작업을 분해하고, 에이전트를 할당하며, 결과를 종합한다.

## 현재 상태

- **브랜치**: `mvp` (기획/설계 문서만)
- **PoC**: `main` 브랜치 (v0.8.0-poc, 171 tests)
- **기획서**: `docs/SPEC.md`
- **실행 계획**: `MVP-PLAN.md`

## 핵심 설계

- **3-Layer**: Core (Engine) → API (FastAPI) → Interface (CLI + Web)
- **Hybrid 오케스트레이션**: LangGraph(planning) + TaskBoard(execution)
- **AgentExecutor**: CLI subprocess + MCP tool call 통합
- **프리셋**: YAML로 에이전트/팀 정의·재사용
- **칸반 TaskBoard**: 느슨한 결합, DAG 의존성, 큐 retry

## 문서 구조

| 문서 | 내용 |
|------|------|
| `docs/SPEC.md` | 전체 기획서 (비전, 아키텍처, 도메인 모델, API 스펙) |
| `MVP-PLAN.md` | 7 Phase / 9 Week 실행 계획 |
| `README.md` | 프로젝트 소개 |

## Conventions

- Commits: Conventional Commits
- 문서: 한국어 (기술 용어 영어)
