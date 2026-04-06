# MVP v2 명세

> v2.0 | 2026-04-06
> 기반: mvp v1 (Phase 7 v4) 실행 결과 + 사용자 피드백

---

## 1. v2 목표

v1에서 확인된 3가지 근본 문제를 해결한다:

| # | 문제 (v1) | 해결 (v2) |
|---|----------|----------|
| **P1** | CLI가 프로젝트 디렉토리에서 실행 — 오케스트레이터 레포 오염 | **cwd 강제 격리**: worktree 또는 target_repo 경로에서만 CLI 실행 |
| **P2** | 이전 subtask 결과가 다음 subtask에 전달 안 됨 | **컨텍스트 체이닝**: architect 결과 → implementer 프롬프트에 주입 |
| **P3** | 서브태스크 상세/산출물을 UI에서 볼 수 없음 | **서브태스크 상세 UI**: 결과 로그, 산출물, 진행 상태 표시 |

---

## 2. P1: cwd 강제 격리

### 문제 상세

v1에서 codex CLI가 오케스트레이터 프로젝트 디렉토리에서 실행되어 `frontend/src/App.tsx`, `frontend/src/index.css` 등을 수정함. worktree가 생성되었지만 CLI에 cwd가 전달되지 않거나 CLI가 무시.

### 해결 설계

```
1. target_repo 필수화 (코딩 태스크 시)
   - target_repo 없이 코딩 태스크 실행 시 경고
   - git repo가 아니면 자동 git init (v1에서 구현)

2. CLI별 cwd 전달 방법
   - Claude: asyncio.create_subprocess_exec(..., cwd=worktree_path)
   - Codex: asyncio.create_subprocess_exec(..., cwd=worktree_path)
     + --cwd 플래그가 있으면 사용
   - Gemini: asyncio.create_subprocess_exec(..., cwd=worktree_path)

3. cwd 검증
   - worker._run_with_heartbeat()에서 executor.run() 호출 전 cwd 존재 확인
   - cwd가 오케스트레이터 프로젝트 디렉토리와 같으면 에러 발생 (자기 보호)
```

### 자기 보호 규칙

```python
# engine.py 또는 worker.py에서
ORCHESTRATOR_DIR = Path(__file__).resolve().parent.parent.parent
if cwd and Path(cwd).resolve() == ORCHESTRATOR_DIR:
    raise ValueError(
        f"CLI cannot run in orchestrator directory: {cwd}. "
        f"Use --repo to specify target repository."
    )
```

### P1.5: worktree 결과물 수집 + target_repo 반영

**문제:** CLI가 worktree에서 파일을 생성/수정하지만, 파이프라인 완료 후 target_repo에 반영되지 않음. my-project에 `.gitkeep`만 남고 CLI가 만든 코드가 없음.

**해결:**

```
1. 각 worker 완료 후:
   - FileDiffCollector.snapshot() → diff → 변경 파일 목록
   - 변경 파일을 WorkerResult.files_changed에 저장
   
2. 모든 subtask 완료 후 (_execute_pipeline):
   - 각 worktree 브랜치를 target_repo의 main에 merge
   - WorktreeManager.merge_to_target(branch_name) 호출
   - merge 충돌 시 → PARTIALLY_COMPLETED + 에러 메시지
   
3. worktree cleanup:
   - merge 후 WorktreeManager.cleanup(branch_name)
```

**핵심:** CLI가 `cwd=worktree_path`에서 실행되어 파일을 생성하면, 그 파일들이 worktree의 git 변경사항으로 남음. 이걸 commit → merge → target_repo 반영.

```python
# engine._execute_pipeline 내부, 모든 subtask 완료 후:
for branch in worktree_branches:
    # worktree에서 변경사항 커밋
    await self._commit_worktree_changes(branch, f"agent: {branch}")
    # target_repo의 main에 merge
    merged = await self._worktree_manager.merge_to_target(branch)
    if not merged:
        pipeline.error += f"merge conflict on {branch}; "
```

### 컨텍스트 체이닝 로그

워커가 _build_prompt()를 호출할 때 **로그를 남겨야** 컨텍스트 체이닝이 실제로 동작하는지 확인 가능:

```python
# worker._build_prompt() 내부:
if task.depends_on:
    logger.info(
        "context_chaining",
        task_id=task.id,
        depends_on=task.depends_on,
        context_length=len(context_text),
    )
```

---

## 3. P2: 컨텍스트 체이닝

### 문제 상세

feature-team의 DAG: architect → implementer → reviewer → tester
현재: 각 subtask가 독립적으로 실행 — implementer는 architect가 뭘 설계했는지 모름.

### 해결 설계

```
architect 실행
  → 결과: "JWT 미들웨어 설계 문서"
  → board.complete(task_id, result_output)

implementer 태스크 승격 (depends_on 해소)
  → 프롬프트 구성:
    f"{preset_description}\n\n"
    f"사용자 태스크: {user_task}\n\n"
    f"이전 단계 결과:\n"
    f"[architect] {architect_result_output[:3000]}"
  → 실행
```

### 구현 위치

**TaskBoard.complete()** 시점에 결과를 저장하고, **AgentWorker._run_with_heartbeat()** 에서 태스크 실행 전 선행 태스크의 결과를 프롬프트에 주입.

```python
# worker.py - _run_with_heartbeat 내부
async def _build_prompt(self, task: TaskItem) -> str:
    """선행 태스크 결과를 포함한 프롬프트 구성."""
    prompt = task.description

    # depends_on 태스크의 결과 수집
    if task.depends_on:
        context_parts = ["\n\n--- 이전 단계 결과 ---"]
        for dep_id in task.depends_on:
            dep_task = self.board.get_task(dep_id)
            if dep_task and dep_task.result:
                context_parts.append(
                    f"\n[{dep_task.lane}] {dep_task.result[:3000]}"
                )
        prompt += "\n".join(context_parts)

    return prompt
```

### 데이터 흐름

```
TaskItem.result (board.complete 시 저장)
  ↓
다음 TaskItem의 depends_on에서 참조
  ↓
worker._build_prompt()에서 프롬프트에 주입
  ↓
executor.run(enriched_prompt)
```

---

## 4. P3: 서브태스크 상세 UI

### 필요 기능

| 기능 | 설명 |
|------|------|
| **서브태스크 목록** | 파이프라인 내 모든 서브태스크, 상태, 경과 시간 |
| **서브태스크 결과** | 각 서브태스크의 CLI 출력 (result 텍스트) |
| **산출물 뷰어** | worktree에서 생성/수정된 파일 목록 + 내용 |
| **의존성 그래프** | DAG 시각화 (architect → implementer → ...) |
| **진행 프로그레스** | heartbeat 기반 경과 시간 + 타임아웃 대비 퍼센트 |

### API 추가/수정

```
GET /api/tasks/{id}/subtasks           # 서브태스크 상세 목록
GET /api/tasks/{id}/subtasks/{sub_id}  # 서브태스크 결과 + 산출물
GET /api/tasks/{id}/files              # 생성된 파일 목록
GET /api/tasks/{id}/files/{path}       # 파일 내용
```

### 프론트엔드 컴포넌트

```
PipelineDetail (새 페이지/모달)
├── SubtaskList            # 서브태스크 목록 + 상태 뱃지
│   └── SubtaskRow         # 개별 서브태스크 (lane, status, elapsed, result preview)
├── DependencyGraph        # DAG 시각화 (간단한 화살표 다이어그램)
├── SubtaskResultViewer    # 선택된 서브태스크의 전체 결과
├── FileExplorer           # 생성된 파일 트리
│   └── FileViewer         # 파일 내용 (코드 하이라이팅)
└── ProgressBar            # heartbeat 기반 전체 진행률
```

---

## 4.5 P4: CLI가 실제 파일을 생성하도록 프롬프트 지시

### 문제 상세

CLI(claude/codex/gemini)는 프롬프트에 "파일을 생성하라"는 명시적 지시가 없으면 **stdout으로 코드를 출력**할 뿐 **파일을 직접 생성하지 않는다.** 이로 인해 worktree에 변경사항이 없고, commit/merge할 것도 없어서 my-project에 파일이 남지 않음.

### 해결 설계

1. **프리셋 description에 파일 생성 지시를 포함:**
   - implementer: "반드시 파일을 직접 생성/수정하라. stdout으로 코드를 출력하지 말고 실제 파일을 만들어라."
   - tester: "반드시 tests/ 디렉토리에 테스트 파일을 생성하라."

2. **worker._build_prompt()에서 cwd 안내를 프롬프트에 추가:**
   ```
   f"\n\n작업 디렉토리: {cwd}\n"
   f"이 디렉토리에서 직접 파일을 생성/수정하세요. stdout으로 코드를 출력하지 마세요."
   ```

3. **프리셋 YAML 수정:**
   ```yaml
   # presets/agents/implementer.yaml
   persona:
     constraints:
       - "반드시 파일을 직접 생성하고 수정한다 — stdout으로 코드를 출력하지 않는다"
       - "작업 디렉토리에 실제 파일을 만든다"
   ```

### 적용 범위

| 프리셋 | 파일 생성 필요 | 수정 |
|--------|--------------|------|
| architect | ❌ (설계 문서는 stdout OK) | 수정 없음 |
| implementer | ✅ (코드 파일 생성) | constraints에 파일 생성 지시 추가 |
| tester | ✅ (테스트 파일 생성) | constraints에 파일 생성 지시 추가 |
| reviewer | ❌ (리뷰는 stdout OK) | 수정 없음 |

---

## 5. 추가 개선

### 5.1 오케스트레이터의 역할별 세부 지시

현재 프리셋의 고정 설명만 전달. v2에서는 오케스트레이터가 태스크를 분석하여 **역할별 맞춤 지시**를 생성:

```
사용자: "웹 3d 물리엔진 플레이그라운드 만들어줘"

오케스트레이터 분해:
  architect: "Three.js + Rapier.js 기반 3D 물리 시뮬레이터 아키텍처를 설계해.
              컴포넌트: SceneCanvas, PhysicsEngine, ObjectLibrary, InspectorPanel"
  implementer: "architect의 설계에 따라 React + Three.js 프로젝트를 구현해.
                {architect_결과}"
  reviewer: "implementer가 작성한 코드를 리뷰해. {implementer_결과}"
  tester: "implementer의 코드에 대한 테스트를 작성해. {implementer_결과}"
```

이를 위해 **TeamPlanner가 LLM을 호출하여 역할별 세부 지시를 생성**해야 함 (v1은 스텁).

### 5.2 태스크 실행 로그 스트리밍

CLI stdout을 실시간으로 WebSocket에 스트리밍하여 사용자가 에이전트가 뭘 하고 있는지 볼 수 있게 함.

---

## 6. v2 성공 기준

```
1. "웹 3d 물리엔진 플레이그라운드 만들어줘" --team feature-team --repo ./my-project
   → architect가 설계 → implementer가 설계 기반으로 구현
   → reviewer가 구현 결과를 리뷰 → tester가 테스트 작성
   → my-project/에 실제 파일 생성됨
   → 오케스트레이터 프로젝트 디렉토리는 오염 없음

2. 웹 대시보드에서:
   → 서브태스크별 상태/결과/산출물 확인 가능
   → DAG 의존성 시각화
   → heartbeat 기반 진행률 표시

3. 컨텍스트 체이닝:
   → implementer의 프롬프트에 architect 결과가 포함됨
   → reviewer의 프롬프트에 implementer 결과가 포함됨
```

---

## 7. v2 영향 범위

| 모듈 | 변경 |
|------|------|
| `core/queue/worker.py` | _build_prompt() 추가, cwd 자기보호 |
| `core/engine.py` | cwd 검증, 오케스트레이터 디렉토리 보호 |
| `core/planner/team_planner.py` | LLM 기반 역할별 세부 지시 (v2.1) |
| `api/routes.py` | subtask 상세 API 4개 추가 |
| `api/ws.py` | subtask 결과 이벤트 |
| `frontend/` | PipelineDetail, SubtaskList, FileExplorer 컴포넌트 |
| `docs/` | 명세 업데이트 |

---

## 8. P5: Codex --ephemeral 제거

### 문제

`codex exec --ephemeral`은 임시 sandbox에서 작업하고 결과를 stdout으로만 반환. worktree의 cwd를 무시하여 파일이 target_repo에 생성되지 않음.

### 해결

`--ephemeral` 플래그를 제거한다. codex가 `cwd=worktree_path`에서 직접 파일을 생성하도록 한다.

```
Before: codex exec --json --ephemeral --full-auto "{prompt}"
After:  codex exec --json --full-auto "{prompt}"
```

### 주의

`--ephemeral` 없이 실행하면 codex가 현재 디렉토리의 파일을 직접 수정할 수 있다. 따라서 **반드시 cwd=worktree_path**로 실행해야 한다 (P1 cwd 격리와 연동).

---

## 9. P6: 프롬프트에 구체적 파일 생성 지시

### 문제

CLI(codex/claude)에 "add 함수를 작성해"라고만 보내면 **stdout으로 코드를 출력**하지 **파일을 생성하지 않음.** 빈 프로젝트 디렉토리에서는 더더욱 아무것도 만들지 않음.

### 해결

worker._build_prompt()에서 **구체적 파일 생성 지시**를 프롬프트에 주입:

```python
# worker._build_prompt() 추가:
if cwd:
    prompt += (
        f"\n\n작업 디렉토리: {cwd}\n"
        f"반드시 이 디렉토리에 실제 파일을 생성하세요.\n"
        f"예시: src/main.py, tests/test_main.py 등\n"
        f"stdout으로 코드를 출력하지 말고 파일로 저장하세요.\n"
        f"파일을 생성한 뒤 어떤 파일을 만들었는지 알려주세요."
    )
```

### architect에게 파일 구조 결정 위임

architect의 설계 결과에 **파일 구조 목록**이 포함되도록 프리셋 수정:

```yaml
# presets/agents/architect.yaml constraints 추가:
- "설계 결과에 반드시 생성할 파일 목록과 각 파일의 역할을 포함한다"
- "예: src/add.py — add 함수 구현, tests/test_add.py — 단위 테스트"
```

이러면 implementer가 architect 결과(컨텍스트 체이닝)에서 파일 목록을 보고 해당 파일을 생성할 수 있음.

---

## 10. P7: CLI stdout에서 코드 추출 → 파일 저장

### 문제

CLI(`claude -p`, `codex exec`)는 프롬프트 모드에서 **파일을 직접 생성하지 않는다.** 코드를 markdown 코드 블록으로 stdout에 출력할 뿐이다. "파일을 만들어라"고 지시해도 텍스트로 답변한다.

### 해결: 결과 파싱 + 파일 추출

오케스트레이터가 CLI stdout에서 **코드 블록을 파싱**하여 파일로 저장한다.

```python
# worker.py 또는 engine.py에서:
import re

def extract_files_from_output(output: str, target_dir: str) -> list[str]:
    """CLI 출력에서 ```파일명 코드블록```을 찾아 파일로 저장."""
    # 패턴: ```python:src/add.py 또는 ```# src/add.py 또는 파일명이 명시된 코드블록
    pattern = r'```(?:\w+)?(?::|\s*#\s*)([\w/.\-]+)\n(.*?)```'
    files_created = []
    
    for match in re.finditer(pattern, output, re.DOTALL):
        filepath = match.group(1).strip()
        content = match.group(2)
        
        full_path = os.path.join(target_dir, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
        files_created.append(filepath)
    
    return files_created
```

### 적용 위치

**worker._run_with_heartbeat()** 에서 `executor.run()` 완료 후:

```
result = await executor.run(prompt, ...)
# CLI stdout에서 코드 추출 → 파일 저장
if cwd:
    files = extract_files_from_output(result.output, cwd)
    if files:
        logger.info("files_extracted", count=len(files), files=files)
```

### 프롬프트 지시 변경

파일을 직접 만들라는 대신, **코드를 파일명과 함께 코드블록으로 출력하라**고 지시:

```
코드를 작성할 때 반드시 다음 형식으로 출력하세요:
```python:src/add.py
def add(a, b):
    return a + b
`` `
파일 경로를 코드블록 언어 뒤에 콜론(:)으로 표시하세요.
```

---

## 11. P8: Worktree merge conflict 해결

### 문제

architect와 implementer가 같은 파일(src/add.py)을 각각 생성. merge 시 conflict markers가 파일에 남음.

### 해결: 순차 merge + theirs 전략

DAG 순서대로 merge하되, 후행 브랜치가 우선(--strategy-option theirs):

```python
# engine._execute_pipeline, merge 시:
for branch in worktree_branches:
    # theirs 전략: 나중 브랜치(implementer)가 architect를 덮어씀
    proc = await asyncio.create_subprocess_exec(
        "git", "merge", "--no-ff", "-X", "theirs", branch,
        "-m", f"merge {branch}",
        cwd=pipeline.target_repo,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
```

**이유:** DAG에서 implementer는 architect 결과를 이미 포함하므로 implementer 버전이 더 완전. architect의 스텁 코드보다 implementer의 실제 구현이 우선.

### architect 역할 제한

architect는 코드 파일을 만들지 말고 DESIGN.md만 생성하도록 constraint 강화:

```yaml
# architect.yaml constraints 추가:
- "코드 파일(.py, .ts 등)은 생성하지 않는다 — DESIGN.md와 인터페이스 정의만 작성한다"
```

---

## 12. P9: 결과 수집 + 품질 평가 + 후속작업 할당

### 현재 동작

```
architect → implementer → reviewer (병렬) + tester (병렬)
                           ↓                    ↓
                        결과 수집              결과 수집
                           ↓
                        Synthesizer
```

reviewer가 "reject" 또는 "changes requested"를 반환해도 **오케스트레이터는 무시하고 COMPLETED 처리.**

### 필요 동작

```
architect → implementer → reviewer + tester
                           ↓           ↓
                        결과 평가     결과 평가
                           ↓
                     approve? ──→ yes ──→ Synthesizer ──→ COMPLETED
                        ↓ no
                     implementer 재작업 (reviewer 피드백 포함)
                        ↓
                     reviewer 재리뷰
                        ↓
                     max_iterations 도달 → COMPLETED (with warnings)
```

### 구현 설계

**1. 결과 평가 (QualityGate)**

```python
class QualityGate:
    """subtask 결과를 평가하여 후속 작업이 필요한지 판단."""
    
    def evaluate(self, result: str, role: str) -> QualityVerdict:
        """결과를 평가한다.
        
        Returns:
            QualityVerdict with approved: bool, feedback: str
        """
        # reviewer 결과에서 키워드 탐색
        lower = result.lower()
        if any(kw in lower for kw in ["reject", "request_changes", "changes requested", "수정 필요"]):
            return QualityVerdict(approved=False, feedback=result)
        return QualityVerdict(approved=True, feedback="")

class QualityVerdict(BaseModel):
    approved: bool
    feedback: str = ""
```

**2. 후속작업 할당 (engine._execute_pipeline)**

```python
# 모든 subtask 완료 후:
reviewer_task = board.get_task(reviewer_subtask_id)
if reviewer_task and reviewer_task.result:
    verdict = quality_gate.evaluate(reviewer_task.result, "reviewer")
    if not verdict.approved and iteration < max_review_iterations:
        # implementer 재작업 태스크 생성
        rework_task = TaskItem(
            title=f"재작업: {reviewer_task.result[:50]}",
            description=f"리뷰어 피드백:\n{verdict.feedback}\n\n이전 구현을 수정하세요.",
            lane="implementer",
            depends_on=[],  # 즉시 실행
            pipeline_id=task_id,
        )
        await board.submit(rework_task)
        # reviewer 재리뷰 태스크도
        re_review_task = TaskItem(...)
        await board.submit(re_review_task)
        iteration += 1
        continue  # 대기 루프 계속
```

**3. 병렬 처리 확인**

현재 feature-team에서 reviewer+tester가 implement에 의존 → **둘 다 implement 완료 후 병렬 실행**. 이 동작은 이미 정상.

추가로 **독립적인 subtask 감지**: depends_on이 없는 태스크는 모두 병렬 실행. 이것도 TaskBoard가 자동 처리.

### max_review_iterations

```yaml
# team preset에 추가:
max_review_iterations: 2  # 최대 2번 재작업 후 강제 완료
```

기본값: 1 (재작업 없이 바로 완료 — 현재 동작과 동일)

---

## 13. P10: 구조화된 리뷰 verdict + 큐-컨슘 검증

### 연구 결론 (Part 18)

**오케스트레이터가 판단하고 할당한다** (Option B).
- 에이전트는 결과만 반환, TaskBoard를 직접 조작하지 않음
- 오케스트레이터(engine)가 QualityGate로 결과 평가 → 후속 태스크 생성
- 에이전트 간 직접 통신 없음 (느슨한 결합 유지)

### 개선: 구조화된 verdict

reviewer 프리셋에 JSON verdict 출력 지시 추가:

```yaml
# reviewer.yaml constraints 추가:
- "리뷰 결과를 반드시 JSON verdict로 시작한다: {\"verdict\": \"approve\" | \"reject\", \"feedback\": \"...\"}"
```

QualityGate가 JSON verdict를 우선 파싱, 실패 시 키워드 fallback:

```python
def evaluate(self, result, role):
    # 1차: JSON verdict 파싱
    try:
        verdict_json = json.loads(result.split('\n')[0])
        return QualityVerdict(
            approved=(verdict_json["verdict"] == "approve"),
            feedback=verdict_json.get("feedback", ""),
        )
    except (json.JSONDecodeError, KeyError):
        pass
    # 2차: 키워드 fallback
    ...
```

### 큐-컨슘 검증 항목

| 검증 | 방법 |
|------|------|
| worker가 board.claim()으로 소비 | grep "board.claim" worker.py |
| 독립 폴링 루프 | worker._run_loop while self._running |
| depends_on=[]이면 병렬 | review-team 2 agent 동시 실행 확인 |
| 워커 추가/제거 코드 변경 없이 | lanes_needed set에서 동적 생성 |

---

## 14. P11: 오케스트레이터 명시적 설정

### 현재 문제

오케스트레이터의 동작을 제어하는 설정이 코드에 흩어져 있음. 사용자가 어떤 값을 설정할 수 있는지 불명확.

### 필요한 명시적 설정

```yaml
# team-config.yaml 또는 환경변수로 제어 가능한 설정
orchestrator:
  # 품질 게이트
  quality_gate:
    enabled: true                    # QualityGate 활성화 여부
    max_review_iterations: 2         # 최대 재작업 횟수
    verdict_format: "json"           # "json" | "keyword"
  
  # 작업 분배
  execution:
    default_timeout: 300             # CLI 타임아웃 (초)
    poll_interval: 0.5               # 파이프라인 상태 폴링 간격
    worktree_cleanup: true           # 완료 후 worktree 자동 삭제
    merge_strategy: "theirs"         # "theirs" | "ours" | "manual"
  
  # 로깅
  logging:
    level: "info"                    # "debug" | "info" | "warning"
    progress_interval: 15            # 진행 상황 로그 간격 (초)
    show_cli_output: false           # CLI stdout 실시간 표시
```

---

## 15. P12: 작업 진행 과정 표시

### 현재 문제

CLI에서 `orchestrator run --wait` 실행 시 상태만 표시 (PENDING→RUNNING→COMPLETED). 어떤 subtask가 어떤 상태인지, 어떤 에이전트가 뭘 하고 있는지 보이지 않음.

### 필요한 표시 내용

```
Pipeline: pipeline-adc620cd
Task: Python 계산기 라이브러리를 만들어줘
Team: feature-team (architect → implementer → reviewer → tester)

┌──────────────┬─────────┬──────────┬────────┐
│ Subtask      │ Agent   │ Status   │ Time   │
├──────────────┼─────────┼──────────┼────────┤
│ 설계         │ claude  │ ✅ DONE  │ 120s   │
│ 구현         │ codex   │ 🔄 BUSY │ 45s    │
│ 리뷰         │ claude  │ ⏳ WAIT  │ -      │
│ 테스트       │ codex   │ ⏳ WAIT  │ -      │
└──────────────┴─────────┴──────────┴────────┘

[120s] architect ✅ 완료 (설계 문서 생성)
[165s] implementer 🔄 실행 중... (codex exec)
```

### 구현 위치

**CLI `run` 명령의 --wait 폴링 루프에서 Rich Live 또는 간단한 테이블 출력:**

```python
# cli.py run 내부, 폴링 루프:
subtasks_resp = await client.get(f"/api/tasks/{pipeline_id}/subtasks")
for st in subtasks_resp:
    status_icon = {"done": "✅", "in_progress": "🔄", "backlog": "⏳", "failed": "❌"}.get(st.state, "?")
    print(f"  {st.lane:12s} {status_icon} {st.state:12s} {st.elapsed_ms//1000}s")
```
