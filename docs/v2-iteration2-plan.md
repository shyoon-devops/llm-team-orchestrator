# v2 반복 2차 — worktree 결과물 수집 + 컨텍스트 체이닝 로그

## Tasks

| Task | 상세 | 참고 |
|------|------|------|
| T1 | engine._execute_pipeline: subtask 완료 후 worktree 변경사항 commit | v2-spec.md §P1.5 |
| T2 | engine._execute_pipeline: 모든 subtask 완료 후 worktree→target_repo merge | v2-spec.md §P1.5 |
| T3 | worker._build_prompt: context_chaining 로그 추가 | v2-spec.md §P1.5 |
| T4 | 테스트: worktree commit + merge 검증 | testing.md |
| T5 | E2E: feature-team → my-project에 파일 존재 + 오케스트레이터 clean 확인 | v2-spec.md §6 |
