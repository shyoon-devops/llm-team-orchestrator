# Agent Team Orchestrator

> 인간 팀과 동일한 방식으로 일하는 범용 AI 에이전트 팀 플랫폼.

## Status

- **MVP 기획 완료** — 구현 대기
- **PoC 검증 완료** — `main` 브랜치 (v0.8.0-poc, 171 tests)

## Documents

- [기획서 (SPEC)](docs/SPEC.md) — 비전, 아키텍처, 도메인 모델, API 스펙
- [실행 계획 (MVP-PLAN)](MVP-PLAN.md) — 7 Phase / 9 Week

## Key Features (planned)

- **에이전트 자유 정의**: 페르소나 + MCP 도구 + 제약을 YAML 프리셋으로
- **팀 자유 구성**: 프리셋 조합 또는 오케스트레이터 자동 구성
- **칸반 작업 분배**: 에이전트가 독립적으로 태스크 소비
- **결과 종합 보고**: Synthesizer로 복수 결과 합성
- **도메인 무관**: 코딩, 인프라 운영, 장애 분석, 업무 대행

## Architecture

```
[CLI / Web / MCP] → [API (FastAPI)] → [Core Engine]
                                          ├── TaskBoard (칸반 큐)
                                          ├── AgentExecutor (CLI + MCP)
                                          ├── Presets (YAML)
                                          └── Synthesizer (결과 종합)
```
