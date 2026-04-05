# 배포 + 운영 명세

> v1.0 | 2026-04-05
> SPEC.md 기준 작성

---

## 1. 서버 시작 순서

### 1.1 시작 시퀀스

```
1. uvicorn 프로세스 시작
   ├── FastAPI app 인스턴스 생성
   └── lifespan context manager 진입
   
2. OrchestratorEngine 초기화
   ├── Settings 로드 (환경변수 + YAML)
   ├── structlog 설정
   ├── PresetRegistry 초기화
   │   ├── 시스템 프리셋 로드 (presets/ 번들)
   │   ├── 사용자 전역 프리셋 로드 (~/.config/orchestrator/presets/)
   │   └── 프로젝트 프리셋 로드 (.orchestrator/presets/)
   ├── EventBus 초기화
   ├── TaskBoard 초기화
   │   └── 체크포인트 복원 (있으면)
   ├── AuthProvider 초기화
   │   └── KeyPool 구성 (환경변수에서 API 키 로드)
   └── WorktreeManager 초기화
   
3. Lane 등록 (에이전트 레인)
   ├── 등록된 에이전트 프리셋별 Lane 생성
   ├── 각 Lane에 AgentExecutor 인스턴스 바인딩
   └── health_check 실행 (CLI 가용성 확인)
   
4. Worker 시작
   ├── 각 Lane별 AgentWorker asyncio.Task 생성
   ├── Worker run_loop 시작 (TaskBoard 폴링)
   └── EventBus 구독 (이벤트 브로드캐스트)
   
5. API 엔드포인트 활성화
   ├── REST 라우터 등록
   ├── WebSocket 핸들러 등록
   └── CORS 미들웨어 적용
   
6. 서버 준비 완료
   └── /api/health 200 OK 반환 시작
```

### 1.2 CLI 설치 (필수)

`pyproject.toml`의 `[project.scripts]`에 정의된 `orchestrator` 명령어를 사용하려면 패키지를 editable 설치해야 한다:

```bash
# 방법 1: uv pip install (권장)
uv pip install -e .

# 방법 2: uv run으로 실행 (설치 없이)
uv run orchestrator serve

# 확인
orchestrator --help   # 방법 1 후
uv run orchestrator --help  # 방법 2
```

> **주의:** `uv sync --dev`만으로는 `orchestrator` CLI 진입점이 PATH에 등록되지 않는다. 반드시 `uv pip install -e .` 또는 `uv run` 접두어를 사용해야 한다.

### 1.3 시작 명령어

```bash
# 기본 시작 (개발) — 기본 포트: 9000
orchestrator serve

# 포트 지정
orchestrator serve --port 8080

# 호스트 바인딩
orchestrator serve --host 0.0.0.0 --port 8080

# 리로드 모드 (개발용)
orchestrator serve --reload

# 직접 uvicorn 실행
uvicorn orchestrator.api.app:app --host 127.0.0.1 --port 9000 --reload

# 프로덕션 (workers 지정)
uvicorn orchestrator.api.app:app --host 0.0.0.0 --port 9000 --workers 1
```

> **주의:** `--workers` 값은 반드시 **1**이어야 한다. OrchestratorEngine은 in-process 상태(TaskBoard, EventBus)를 유지하므로 멀티 프로세스에서 동작하지 않는다.

### 1.3 Lifespan 구현

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작/종료 시 Engine 생명주기를 관리한다."""
    # 시작
    engine = OrchestratorEngine()
    await engine.start()
    app.state.engine = engine
    logger.info("engine_started")

    yield

    # 종료
    await engine.shutdown()
    logger.info("engine_stopped")


app = FastAPI(lifespan=lifespan)
```

---

## 2. 환경변수 목록

### 2.1 서버 설정

| 환경변수 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `ORCH_HOST` | `str` | `"127.0.0.1"` | 서버 바인드 호스트 |
| `ORCH_PORT` | `int` | `9000` | 서버 바인드 포트 |
| `ORCH_LOG_LEVEL` | `str` | `"info"` | 로그 레벨 (`debug`, `info`, `warning`, `error`) |
| `ORCH_LOG_FORMAT` | `str` | `"console"` | 로그 포맷 (`console`, `json`) |
| `ORCH_CONFIG_PATH` | `str` | `""` | YAML 설정 파일 경로 (미지정 시 환경변수만 사용) |
| `ORCH_DATA_DIR` | `str` | `"~/.local/share/orchestrator"` | 데이터 저장 경로 (체크포인트, 아티팩트) |
| `ORCH_CORS_ORIGINS` | `str` | `"http://localhost:3000"` | CORS 허용 origin (쉼표 구분) |
| `ORCH_CORS_ALLOW_ALL` | `bool` | `false` | 모든 origin 허용 (개발용) |

### 2.2 에이전트 API 키

| 환경변수 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `ANTHROPIC_API_KEY` | `str` | (필수) | Claude Code API 키 |
| `OPENAI_API_KEY` | `str` | `""` | Codex CLI API 키 |
| `GEMINI_API_KEY` | `str` | `""` | Gemini CLI API 키 (또는 `GOOGLE_API_KEY`) |
| `GOOGLE_API_KEY` | `str` | `""` | Gemini CLI API 키 (대체) |

### 2.3 LLM 설정 (오케스트레이터/Synthesizer 용)

| 환경변수 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `ORCH_PLANNER_MODEL` | `str` | `"claude-sonnet-4-20250514"` | 태스크 분해에 사용할 LLM 모델 |
| `ORCH_PLANNER_TEMPERATURE` | `float` | `0.3` | Planner LLM temperature |
| `ORCH_PLANNER_MAX_TOKENS` | `int` | `4096` | Planner LLM max tokens |
| `ORCH_SYNTHESIZER_MODEL` | `str` | `"claude-sonnet-4-20250514"` | 결과 종합에 사용할 LLM 모델 |
| `ORCH_SYNTHESIZER_TEMPERATURE` | `float` | `0.5` | Synthesizer LLM temperature |
| `ORCH_SYNTHESIZER_MAX_TOKENS` | `int` | `8192` | Synthesizer LLM max tokens |

### 2.4 실행 제한

| 환경변수 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `ORCH_DEFAULT_TIMEOUT` | `int` | `300` | 에이전트 기본 타임아웃(초) |
| `ORCH_MAX_RETRIES` | `int` | `3` | 태스크 최대 재시도 횟수 |
| `ORCH_MAX_CONCURRENT_AGENTS` | `int` | `5` | 동시 실행 에이전트 최대 수 |
| `ORCH_MAX_SUBTASKS` | `int` | `10` | 단일 파이프라인 최대 서브태스크 수 |
| `ORCH_QUEUE_POLL_INTERVAL` | `float` | `0.5` | Worker 큐 폴링 간격(초) |

### 2.5 Git Worktree

| 환경변수 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `ORCH_WORKTREE_BASE` | `str` | `"/tmp/orchestrator-worktrees"` | worktree 생성 기본 경로 |
| `ORCH_WORKTREE_CLEANUP` | `bool` | `true` | 파이프라인 완료 시 worktree 자동 삭제 |
| `ORCH_GIT_MAIN_BRANCH` | `str` | `"main"` | 레포지토리 기본 브랜치 이름 |

### 2.6 CLI 도구 경로

| 환경변수 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `ORCH_CLAUDE_PATH` | `str` | `"claude"` | Claude Code CLI 실행 파일 경로 |
| `ORCH_CODEX_PATH` | `str` | `"codex"` | Codex CLI 실행 파일 경로 |
| `ORCH_GEMINI_PATH` | `str` | `"gemini"` | Gemini CLI 실행 파일 경로 |

### 2.7 체크포인트

| 환경변수 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `ORCH_CHECKPOINT_ENABLED` | `bool` | `true` | 체크포인트 저장 활성화 |
| `ORCH_CHECKPOINT_DIR` | `str` | `"$ORCH_DATA_DIR/checkpoints"` | 체크포인트 저장 경로 |
| `ORCH_CHECKPOINT_INTERVAL` | `int` | `30` | 자동 체크포인트 간격(초) |

### 2.8 Settings 모델 (pydantic-settings)

```python
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """전체 설정 — 환경변수 + YAML에서 로드."""

    model_config = SettingsConfigDict(
        env_prefix="ORCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 서버
    host: str = "127.0.0.1"
    port: int = 9000
    log_level: str = "info"
    log_format: str = "console"  # "console" | "json"
    config_path: str = ""
    data_dir: Path = Path("~/.local/share/orchestrator").expanduser()
    cors_origins: str = "http://localhost:3000"
    cors_allow_all: bool = False

    # LLM — planner
    planner_model: str = "claude-sonnet-4-20250514"
    planner_temperature: float = 0.3
    planner_max_tokens: int = 4096

    # LLM — synthesizer
    synthesizer_model: str = "claude-sonnet-4-20250514"
    synthesizer_temperature: float = 0.5
    synthesizer_max_tokens: int = 8192

    # 실행 제한
    default_timeout: int = 300
    max_retries: int = 3
    max_concurrent_agents: int = 5
    max_subtasks: int = 10
    queue_poll_interval: float = 0.5

    # worktree
    worktree_base: str = "/tmp/orchestrator-worktrees"
    worktree_cleanup: bool = True
    git_main_branch: str = "main"

    # CLI 경로
    claude_path: str = "claude"
    codex_path: str = "codex"
    gemini_path: str = "gemini"

    # 체크포인트
    checkpoint_enabled: bool = True
    checkpoint_dir: str = ""
    checkpoint_interval: int = 30
```

> **참고:** `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`는 `ORCH_` 접두사 없이 각 CLI 도구가 직접 인식하는 환경변수다. `Settings` 모델에 포함하지 않고, `AuthProvider`가 별도로 로드한다.

---

## 3. YAML 설정 파일

`ORCH_CONFIG_PATH` 환경변수로 YAML 설정 파일을 지정할 수 있다. 환경변수가 YAML 값을 오버라이드한다.

### 3.1 전체 스키마

```yaml
# orchestrator.yaml — 전체 설정 스키마
# 모든 필드는 선택 사항이며, 미지정 시 기본값 사용

server:
  host: "127.0.0.1"         # str, 서버 바인드 호스트
  port: 9000                 # int, 서버 바인드 포트
  log_level: "info"          # str, debug | info | warning | error
  log_format: "console"      # str, console | json
  data_dir: "~/.local/share/orchestrator"  # str, 데이터 저장 경로
  cors:
    origins:                 # list[str], CORS 허용 origin
      - "http://localhost:3000"
    allow_all: false         # bool, 모든 origin 허용

planner:
  model: "claude-sonnet-4-20250514"  # str, LLM 모델 ID (litellm 포맷)
  temperature: 0.3           # float, 0.0-1.0
  max_tokens: 4096           # int

synthesizer:
  model: "claude-sonnet-4-20250514"
  temperature: 0.5
  max_tokens: 8192

execution:
  default_timeout: 300       # int, 에이전트 기본 타임아웃(초)
  max_retries: 3             # int, 태스크 최대 재시도 횟수
  max_concurrent_agents: 5   # int, 동시 실행 에이전트 최대 수
  max_subtasks: 10           # int, 파이프라인당 최대 서브태스크 수
  queue_poll_interval: 0.5   # float, Worker 큐 폴링 간격(초)

worktree:
  base_dir: "/tmp/orchestrator-worktrees"  # str
  cleanup: true              # bool, 완료 시 자동 삭제
  main_branch: "main"        # str, 레포지토리 기본 브랜치

cli_paths:
  claude: "claude"           # str, Claude Code CLI 경로
  codex: "codex"             # str, Codex CLI 경로
  gemini: "gemini"           # str, Gemini CLI 경로

checkpoint:
  enabled: true              # bool
  dir: ""                    # str, 미지정 시 $data_dir/checkpoints
  interval: 30               # int, 자동 체크포인트 간격(초)

presets:
  search_paths:              # list[str], 추가 프리셋 검색 경로
    - "/opt/orchestrator/presets"
```

### 3.2 최소 설정 예제

```yaml
# orchestrator.yaml — 최소 설정
server:
  port: 9000

planner:
  model: "claude-sonnet-4-20250514"
```

### 3.3 프로덕션 설정 예제

```yaml
# orchestrator-prod.yaml
server:
  host: "0.0.0.0"
  port: 9000
  log_level: "info"
  log_format: "json"
  data_dir: "/var/lib/orchestrator"
  cors:
    origins:
      - "https://dashboard.example.com"
    allow_all: false

planner:
  model: "claude-sonnet-4-20250514"
  temperature: 0.2
  max_tokens: 4096

synthesizer:
  model: "claude-sonnet-4-20250514"
  temperature: 0.4
  max_tokens: 8192

execution:
  default_timeout: 600
  max_retries: 3
  max_concurrent_agents: 10
  max_subtasks: 15

worktree:
  base_dir: "/var/tmp/orchestrator-worktrees"
  cleanup: true
  main_branch: "main"

checkpoint:
  enabled: true
  dir: "/var/lib/orchestrator/checkpoints"
  interval: 15
```

### 3.4 설정 우선순위

```
1. 환경변수 (최고 우선)
2. .env 파일
3. YAML 설정 파일 (ORCH_CONFIG_PATH)
4. 기본값 (최저 우선)
```

---

## 4. CLI 명령어 전체 목록

### 4.1 서버 관리

```bash
# 서버 시작
orchestrator serve [OPTIONS]

Options:
  --host TEXT        서버 바인드 호스트 [default: 127.0.0.1]
  --port INTEGER     서버 바인드 포트 [default: 9000]
  --reload           자동 리로드 (개발용)
  --config PATH      YAML 설정 파일 경로
  --log-level TEXT   로그 레벨 (debug|info|warning|error) [default: info]
```

### 4.2 태스크 실행

```bash
# 태스크 실행 (서버 실행 중 필요)
orchestrator run TASK [OPTIONS]

Arguments:
  TASK  TEXT         태스크 설명 (필수)

Options:
  --team TEXT        팀 프리셋 이름 (미지정 시 자동 구성)
  --repo PATH        대상 레포지토리 경로
  --timeout INTEGER  전체 타임아웃(초) [default: 600]
  --wait             완료까지 대기 (기본: 백그라운드 실행)
  --json             JSON 출력

# 예시
orchestrator run "JWT 인증 미들웨어 구현" --repo ./my-project --team feature-team
orchestrator run "프로덕션 API 500 에러 분석" --team incident-analysis --wait
orchestrator run "보안 감사" --json
```

### 4.3 태스크 관리

```bash
# 파이프라인 목록
orchestrator status [OPTIONS]

Options:
  --all              모든 파이프라인 표시 (기본: 활성만)
  --json             JSON 출력

# 파이프라인 상세
orchestrator status PIPELINE_ID [OPTIONS]

Arguments:
  PIPELINE_ID  TEXT  파이프라인 ID (필수)

Options:
  --json             JSON 출력
  --board            칸반 보드 형태로 표시

# 태스크 재개
orchestrator resume PIPELINE_ID

Arguments:
  PIPELINE_ID  TEXT  재개할 파이프라인 ID (필수)

# 태스크 취소
orchestrator cancel PIPELINE_ID

Arguments:
  PIPELINE_ID  TEXT  취소할 파이프라인 ID (필수)
```

### 4.4 프리셋 관리

```bash
# 에이전트 프리셋 목록
orchestrator presets list [OPTIONS]

Options:
  --type TEXT        에이전트|팀 [default: 모두]
  --json             JSON 출력

# 에이전트 프리셋 상세
orchestrator presets show PRESET_NAME [OPTIONS]

Arguments:
  PRESET_NAME  TEXT  프리셋 이름 (필수)

Options:
  --json             JSON 출력

# 에이전트 프리셋 생성 (YAML 파일에서)
orchestrator presets create PATH [OPTIONS]

Arguments:
  PATH  PATH         YAML 프리셋 파일 경로 (필수)

Options:
  --global           사용자 전역에 저장 (~/.config/orchestrator/presets/)
  --project          프로젝트에 저장 (.orchestrator/presets/)

# 프리셋 검증
orchestrator presets validate PATH

Arguments:
  PATH  PATH         검증할 YAML 파일 경로 (필수)
```

### 4.5 에이전트 관리

```bash
# 에이전트 상태 확인
orchestrator agents [OPTIONS]

Options:
  --json             JSON 출력

# 에이전트 헬스 체크
orchestrator agents health [OPTIONS]

Options:
  --name TEXT        특정 에이전트만 체크
  --json             JSON 출력
```

### 4.6 아티팩트 조회

```bash
# 아티팩트 목록
orchestrator artifacts PIPELINE_ID [OPTIONS]

Arguments:
  PIPELINE_ID  TEXT  파이프라인 ID (필수)

Options:
  --json             JSON 출력

# 아티팩트 내용 출력
orchestrator artifacts show PIPELINE_ID ARTIFACT_NAME

Arguments:
  PIPELINE_ID    TEXT  파이프라인 ID (필수)
  ARTIFACT_NAME  TEXT  아티팩트 이름 (필수)
```

### 4.7 이벤트 조회

```bash
# 이벤트 목록
orchestrator events [OPTIONS]

Options:
  --pipeline TEXT    파이프라인 ID로 필터
  --type TEXT        이벤트 타입으로 필터
  --limit INTEGER    최대 출력 수 [default: 50]
  --json             JSON 출력
  --follow           실시간 이벤트 스트림 (WebSocket)
```

### 4.8 버전/설정 확인

```bash
# 버전 출력
orchestrator version

# 현재 설정 출력
orchestrator config [OPTIONS]

Options:
  --json             JSON 출력
```

### 4.9 CLI 출력 예시

```
$ orchestrator status

  Pipeline ID       Status       Team              Created
  ─────────────────────────────────────────────────────────────
  01JABC123DEF      running      feature-team      2026-04-05 14:30:22
  01JABC456GHI      done         incident-analysis 2026-04-05 13:15:10
  01JABC789JKL      failed       (auto)            2026-04-05 12:00:05

$ orchestrator status 01JABC123DEF --board

  Pipeline: 01JABC123DEF | Status: running | Team: feature-team

  ┌─────────────┬──────────────┬──────────────┬──────────────┐
  │   BACKLOG   │     TODO     │ IN_PROGRESS  │     DONE     │
  ├─────────────┼──────────────┼──────────────┼──────────────┤
  │             │              │ [architect]  │              │
  │             │ implement-   │ API 설계     │              │
  │             │ auth         │              │              │
  │             │              │              │              │
  └─────────────┴──────────────┴──────────────┴──────────────┘
```

---

## 5. 포트/네트워크

### 5.1 기본 포트

| 서비스 | 포트 | 프로토콜 | 설명 |
|--------|------|----------|------|
| API 서버 | `9000` | HTTP/WS | REST API + WebSocket |
| 프론트엔드 (dev) | `3000` | HTTP | React dev server (Vite) |

### 5.2 CORS 설정

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # 환경변수에서 파싱
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

| 환경 | `ORCH_CORS_ORIGINS` 값 |
|------|------------------------|
| 개발 | `"http://localhost:3000"` |
| 프로덕션 | `"https://dashboard.example.com"` |
| 테스트 | `ORCH_CORS_ALLOW_ALL=true` |

### 5.3 네트워크 바인딩

| 환경 | Host | Port | 비고 |
|------|------|------|------|
| 개발 | `127.0.0.1` | `9000` | 로컬만 접근 |
| Docker | `0.0.0.0` | `9000` | 컨테이너 외부 접근 |
| 프로덕션 | `0.0.0.0` | `9000` | 리버스 프록시 뒤 배치 |

---

## 6. 로그 설정

### 6.1 structlog 초기화

```python
import logging
import sys

import structlog


def configure_logging(log_level: str = "info", log_format: str = "console") -> None:
    """structlog + stdlib logging 통합 설정."""

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # uvicorn 로그도 structlog 포맷 적용
    for uvicorn_logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
```

### 6.2 로그 레벨

| 레벨 | 용도 | 예시 |
|------|------|------|
| `debug` | 개발 디버깅 | CLI 명령어 전체 출력, 큐 상태 변경 |
| `info` | 운영 정보 | 태스크 제출, 에이전트 시작/완료, 파이프라인 상태 변경 |
| `warning` | 주의 필요 | 타임아웃, 재시도, 폴백 |
| `error` | 에러 | CLI 실행 실패, 파싱 에러, 모든 프로바이더 실패 |

### 6.3 로그 출력 대상

| 포맷 | 출력 대상 | 설명 |
|------|-----------|------|
| `console` | `stderr` | 색상 포함, 개발용 |
| `json` | `stderr` | 구조화된 JSON, 프로덕션/로그 수집 용 |

### 6.4 Console 포맷 예시

```
2026-04-05T14:30:22.123Z [info     ] task_submitted             pipeline_id=01JABC123 team=feature-team
2026-04-05T14:30:22.456Z [info     ] decomposition_started      pipeline_id=01JABC123 subtask_count=3
2026-04-05T14:30:25.789Z [info     ] worker_started             agent=architect lane=architect
2026-04-05T14:30:30.012Z [warning  ] agent_timeout              agent=gemini timeout=300
2026-04-05T14:30:30.345Z [info     ] task_retried               task_id=sub-002 retry_count=1
```

### 6.5 JSON 포맷 예시

```json
{"event":"task_submitted","pipeline_id":"01JABC123","team":"feature-team","level":"info","timestamp":"2026-04-05T14:30:22.123456Z"}
{"event":"agent_timeout","agent":"gemini","timeout":300,"level":"warning","timestamp":"2026-04-05T14:30:30.012345Z"}
```

---

## 7. 헬스 체크

### 7.1 엔드포인트

```
GET /api/health
```

### 7.2 응답 포맷

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "uptime_seconds": 3600,
  "engine": {
    "status": "running",
    "active_pipelines": 2,
    "total_pipelines": 15
  },
  "agents": {
    "claude": {
      "status": "available",
      "executor_type": "cli",
      "last_health_check": "2026-04-05T14:30:00Z",
      "active_tasks": 1
    },
    "codex": {
      "status": "available",
      "executor_type": "cli",
      "last_health_check": "2026-04-05T14:30:00Z",
      "active_tasks": 0
    },
    "gemini": {
      "status": "unavailable",
      "executor_type": "cli",
      "last_health_check": "2026-04-05T14:29:55Z",
      "error": "CLI not found in PATH",
      "active_tasks": 0
    },
    "elk-analyst": {
      "status": "available",
      "executor_type": "mcp",
      "last_health_check": "2026-04-05T14:30:00Z",
      "active_tasks": 0
    }
  },
  "board": {
    "total_tasks": 8,
    "by_state": {
      "backlog": 0,
      "todo": 2,
      "in_progress": 3,
      "done": 2,
      "failed": 1
    }
  }
}
```

### 7.3 상태 코드

| HTTP Status | `status` 값 | 조건 |
|-------------|-------------|------|
| `200` | `"healthy"` | Engine 정상 + 최소 1개 에이전트 available |
| `200` | `"degraded"` | Engine 정상 + 일부 에이전트 unavailable |
| `503` | `"unhealthy"` | Engine 미시작 또는 모든 에이전트 unavailable |

### 7.4 에이전트 가용성 확인 방법

각 에이전트의 `health_check()`는 다음을 검증한다:

| Executor Type | 확인 내용 |
|---------------|-----------|
| CLI (`claude`) | `claude --version` 실행 성공 + `ANTHROPIC_API_KEY` 존재 |
| CLI (`codex`) | `codex --version` 실행 성공 + `OPENAI_API_KEY` 존재 |
| CLI (`gemini`) | `gemini --version` 실행 성공 + `GEMINI_API_KEY`/`GOOGLE_API_KEY` 존재 |
| MCP | MCP 서버 연결 성공 + tools 목록 조회 성공 |

### 7.5 주기적 헬스 체크

```python
# 백그라운드 태스크로 주기적 헬스 체크 실행
HEALTH_CHECK_INTERVAL = 60  # 초

async def periodic_health_check(engine: OrchestratorEngine) -> None:
    while True:
        for agent in engine.list_agents():
            try:
                available = await agent.executor.health_check()
                agent.status = "available" if available else "unavailable"
            except Exception as e:
                agent.status = "unavailable"
                agent.error = str(e)
            agent.last_health_check = datetime.now(UTC)
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
```

---

## 8. Graceful Shutdown

### 8.1 SIGTERM 처리 시퀀스

```
SIGTERM 수신
    │
    ├── 1. 새 태스크 수락 중지
    │   └── /api/tasks POST → 503 반환
    │
    ├── 2. 실행 중인 Worker에 shutdown 신호
    │   ├── Worker가 현재 태스크 완료 대기 (grace period)
    │   └── grace period 초과 시 강제 중단
    │
    ├── 3. 체크포인트 저장
    │   ├── TaskBoard 현재 상태 직렬화
    │   ├── 각 Pipeline 상태 저장
    │   └── 파일시스템에 JSON 기록
    │
    ├── 4. WebSocket 연결 정리
    │   ├── 모든 클라이언트에 shutdown 이벤트 전송
    │   └── 연결 종료
    │
    ├── 5. 리소스 정리
    │   ├── Worktree 정리 (설정에 따라)
    │   ├── 임시 파일 삭제
    │   └── EventBus 구독 해제
    │
    └── 6. 프로세스 종료
```

### 8.2 구현

```python
class OrchestratorEngine:
    SHUTDOWN_GRACE_PERIOD = 30  # 초

    async def shutdown(self) -> None:
        """Graceful shutdown을 수행한다."""
        logger.info("shutdown_initiated")

        # 1. 새 태스크 수락 중지
        self._accepting_tasks = False

        # 2. Worker 중단
        for worker in self._workers:
            worker.request_shutdown()

        # 3. 실행 중인 태스크 완료 대기
        try:
            await asyncio.wait_for(
                self._wait_all_workers(),
                timeout=self.SHUTDOWN_GRACE_PERIOD,
            )
            logger.info("workers_stopped_gracefully")
        except TimeoutError:
            logger.warning(
                "workers_force_stopped",
                grace_period=self.SHUTDOWN_GRACE_PERIOD,
            )
            for worker in self._workers:
                worker.force_stop()

        # 4. 체크포인트 저장
        if self._settings.checkpoint_enabled:
            await self._save_checkpoint()
            logger.info("checkpoint_saved")

        # 5. WebSocket 연결 정리
        await self._event_bus.shutdown()

        # 6. Worktree 정리
        if self._settings.worktree_cleanup:
            await self._worktree_manager.cleanup_all()

        logger.info("shutdown_completed")
```

### 8.3 체크포인트 포맷

```json
{
  "version": "1",
  "timestamp": "2026-04-05T14:30:00Z",
  "pipelines": [
    {
      "id": "01JABC123DEF",
      "status": "running",
      "task": "JWT 인증 미들웨어 구현",
      "team_preset": "feature-team",
      "subtasks": [
        {
          "id": "sub-001",
          "title": "API 설계",
          "state": "done",
          "lane": "architect",
          "result": "..."
        },
        {
          "id": "sub-002",
          "title": "구현",
          "state": "in_progress",
          "lane": "implementer",
          "result": ""
        }
      ]
    }
  ]
}
```

### 8.4 재시작 후 복원

```
서버 시작
    │
    ├── 체크포인트 파일 확인
    │   └── $ORCH_CHECKPOINT_DIR/*.json
    │
    ├── 체크포인트 로드
    │   ├── Pipeline 상태 복원
    │   ├── TaskBoard 상태 복원
    │   └── "in_progress" 상태 태스크 → "todo"로 재설정
    │
    └── Worker 재시작
        └── "todo" 상태 태스크 자동 재실행
```

| 이전 상태 | 복원 후 상태 | 이유 |
|-----------|-------------|------|
| `backlog` | `backlog` | 변경 없음 |
| `todo` | `todo` | 변경 없음, Worker가 자동 소비 |
| `in_progress` | `todo` | 중단된 작업은 처음부터 재실행 |
| `done` | `done` | 변경 없음 |
| `failed` | `failed` | 변경 없음, `resume`으로 수동 재시도 |

### 8.5 SIGTERM vs SIGINT

| 시그널 | 동작 |
|--------|------|
| `SIGTERM` | Graceful shutdown (위 시퀀스) |
| `SIGINT` (Ctrl+C) | Graceful shutdown (동일) |
| `SIGKILL` | 즉시 종료 (체크포인트 저장 불가) |
| 2번째 `SIGINT` | 강제 종료 (uvicorn 기본 동작) |
