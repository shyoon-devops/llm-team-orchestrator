# MVP v2 실행 계획

> 기반: v2-spec.md
> 구현 브랜치: `mvp-impl/v2`

---

## Phase 순서

| Phase | 내용 | 참고 명세 |
|-------|------|----------|
| V2-1 | cwd 격리 + 자기보호 | v2-spec.md §2 |
| V2-2 | 컨텍스트 체이닝 (_build_prompt) | v2-spec.md §3 |
| V2-3 | 서브태스크 상세 API | v2-spec.md §4 |
| V2-4 | 프론트엔드 PipelineDetail | v2-spec.md §4 |
| V2-5 | E2E 테스트 (파이프라인 COMPLETED까지) | v2-spec.md §6 |

---

## V2-1: cwd 격리 + 자기보호

| Task | 상세 | 참고 |
|------|------|------|
| T1.1 | engine.py에 오케스트레이터 디렉토리 보호 로직 추가 | v2-spec.md §2 |
| T1.2 | worker._run_with_heartbeat()에서 cwd 존재 확인 | v2-spec.md §2 |
| T1.3 | 각 CLI adapter의 subprocess에 cwd 전달 검증 | functions.md §10 |
| T1.4 | 테스트: cwd가 오케스트레이터 디렉토리면 에러 | testing.md |
| **검증** | `grep -rn "ORCHESTRATOR_DIR" src/` → 보호 로직 존재 확인 |

## V2-2: 컨텍스트 체이닝

| Task | 상세 | 참고 |
|------|------|------|
| T2.1 | worker.py에 `_build_prompt()` 메서드 추가 | v2-spec.md §3 |
| T2.2 | board.get_task(dep_id)로 선행 태스크 결과 조회 | functions.md §2 |
| T2.3 | 프롬프트 = 원본 description + 선행 결과 | v2-spec.md §3 |
| T2.4 | 테스트: depends_on 태스크의 result가 프롬프트에 포함 | testing.md |
| **검증** | implementer 프롬프트에 "이전 단계 결과" 섹션 존재 확인 |

## V2-3: 서브태스크 상세 API

| Task | 상세 | 참고 |
|------|------|------|
| T3.1 | GET /api/tasks/{id}/subtasks | v2-spec.md §4 |
| T3.2 | GET /api/tasks/{id}/subtasks/{sub_id} | v2-spec.md §4 |
| T3.3 | GET /api/tasks/{id}/files | v2-spec.md §4 |
| T3.4 | GET /api/tasks/{id}/files/{path} | v2-spec.md §4 |
| T3.5 | api-spec.md에 엔드포인트 추가 | api-spec.md |
| **검증** | curl로 4개 엔드포인트 응답 확인 |

## V2-4: 프론트엔드 PipelineDetail

| Task | 상세 | 참고 |
|------|------|------|
| T4.1 | PipelineDetail 컴포넌트 (클릭 시 열림) | v2-spec.md §4 |
| T4.2 | SubtaskList + SubtaskRow (상태 뱃지, 경과 시간) | v2-spec.md §4 |
| T4.3 | SubtaskResultViewer (결과 텍스트) | v2-spec.md §4 |
| T4.4 | FileExplorer + FileViewer (코드 표시) | v2-spec.md §4 |
| T4.5 | ProgressBar (heartbeat 기반) | websocket-protocol.md |
| **검증** | 브라우저에서 서브태스크 클릭 → 결과 확인 |

## V2-5: E2E 테스트

| Task | 상세 | 참고 |
|------|------|------|
| T5.1 | Playwright 테스트: Submit → COMPLETED까지 대기 | v2-spec.md §6 |
| T5.2 | my-project/에 파일 생성 확인 | v2-spec.md §6 |
| T5.3 | 오케스트레이터 디렉토리 오염 없음 확인 (git status clean) | v2-spec.md §2 |
| T5.4 | 서브태스크 상세 API 응답 확인 | v2-spec.md §4 |
| **검증** | 파이프라인 COMPLETED + my-project에 파일 + 오케스트레이터 clean |
