# iter21 — Frontend Enhancements + Multi-Worker Engine

> 작성일: 2026-04-06

## Summary

프론트엔드 UX 개선(팀 프리셋 드롭다운, 접이식 패널, 태스크 상세 모달)과
엔진의 레인당 복수 워커 지원을 구현한다.

## Part A: Frontend

### A1. TaskSubmitForm — team preset dropdown
- 텍스트 입력을 `<select>` 드롭다운으로 교체
- `GET /api/presets/teams` 에서 목록 fetch
- 기본값: `""` (None — 미선택)
- 기존 테스트 호환: label 텍스트 유지

### A2. TeamPresetsPanel (신규 컴포넌트)
- `GET /api/presets/teams` fetch
- 팀 이름, description, agent 수, workflow 타입 표시
- 클릭 시 accordion 확장: agents 목록, tasks 목록 (depends_on 포함)
- 기본 접힘 상태
- App.tsx 사이드바에서 AgentStatusPanel 위에 배치

### A3. AgentStatusPanel — collapsible
- panel-header 클릭 시 panel-body 토글
- 기본 접힘 상태

### A4. KanbanBoard — task detail modal
- 카드 클릭 시 모달 표시
- `GET /api/board/tasks/{task_id}` fetch
- description, status, assigned_to, depends_on, result, error, started_at, completed_at, elapsed time 표시
- react-markdown으로 description/result 렌더링

## Part B: Engine

### B1. max_workers_per_lane config
```python
max_workers_per_lane: int = Field(default=2, ge=1, le=10, description="레인당 최대 워커 수")
```

### B2. Multi-worker creation
`engine._execute_pipeline()`에서 레인별 태스크 수에 따라 복수 워커 생성:
```python
for lane in lanes_needed:
    lane_tasks = [t for t in subtasks if (t.assigned_preset or "default") == lane]
    num_workers = min(len(lane_tasks), self.config.max_workers_per_lane)
    for i in range(num_workers):
        worker_id = f"worker-{task_id[:8]}-{lane}-{i}"
```

### B3. TaskBoard
기존 `claim()` 메서드가 이미 다수 워커의 동일 레인 폴링을 지원하므로 변경 불필요.

## Files Changed

| File | Change |
|------|--------|
| `src/orchestrator/core/config/schema.py` | `max_workers_per_lane` 필드 추가 |
| `src/orchestrator/core/engine.py` | 레인당 복수 워커 생성 로직 |
| `frontend/src/components/TaskSubmitForm.tsx` | 드롭다운 교체 |
| `frontend/src/components/TeamPresetsPanel.tsx` | 신규 |
| `frontend/src/components/AgentStatusPanel.tsx` | 접이식 래핑 |
| `frontend/src/components/KanbanBoard.tsx` | 카드 클릭 + 모달 |
| `frontend/src/components/TaskDetailModal.tsx` | 신규 |
| `frontend/src/App.tsx` | TeamPresetsPanel 추가 |
| `frontend/src/index.css` | 모달 + 접이식 스타일 |
| `tests/unit/test_config.py` | max_workers_per_lane 테스트 |
| `tests/unit/test_engine_multi_worker.py` | 복수 워커 테스트 |
