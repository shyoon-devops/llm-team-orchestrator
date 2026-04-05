# 의존성 명세서

> v1.0 | 2026-04-05
> SPEC.md v2.0 기반

---

## 1. 시스템 의존성

### 1.1 런타임 요구사항

| 항목 | 최소 버전 | 권장 버전 | 용도 | 확인 명령 |
|------|----------|----------|------|----------|
| **Python** | 3.12 | 3.12.x | 메인 런타임 (asyncio 네이티브) | `python --version` |
| **uv** | 0.5.0 | latest | 패키지 매니저 (빌드/가상환경/락파일) | `uv --version` |
| **Git** | 2.40 | 2.44+ | worktree 격리, 버전 관리 | `git --version` |
| **Node.js** | 20.x | 22.x LTS | CLI 도구 실행 (npm), 프론트엔드 빌드 | `node --version` |
| **npm** | 10.x | latest | CLI 도구 설치 | `npm --version` |

### 1.2 CLI 도구 (에이전트 실행용)

| 도구 | 설치 명령 | 인증 | 확인 명령 | 필수 여부 |
|------|----------|------|----------|----------|
| **Claude Code** | `npm install -g @anthropic-ai/claude-code` | `ANTHROPIC_API_KEY` | `claude --version` | Phase 1 필수 |
| **Codex CLI** | `npm install -g @openai/codex` | `CODEX_API_KEY` (OpenAI) | `codex --version` | Phase 2 필수 |
| **Gemini CLI** | `npm install -g @anthropic-ai/claude-code` (placeholder) | `GEMINI_API_KEY` | `gemini --version` | Phase 2 필수 |

> **참고:** Gemini CLI 설치 경로는 변경될 수 있다. 실제 설치 명령은 릴리스 시점에 확인 필요.

---

## 2. Python 의존성 (pyproject.toml)

### 2.1 핵심 의존성 (dependencies)

| 패키지 | 버전 제약 | 용도 | 사용 모듈 | 대안 비교 |
|--------|----------|------|----------|----------|
| **langgraph** | `>=0.6.0,<1.0.0` | StateGraph 기반 오케스트레이션, 조건부 엣지, 체크포인터 | `core/planner/decomposer.py`, `core/planner/team_planner.py` | CrewAI(역할 기반, 유연성 부족), AutoGen(설정 복잡) |
| **langchain-core** | `>=0.3.0,<1.0.0` | LangGraph 의존성 (BaseMessage, RunnableConfig 등) | langgraph 내부 의존 | langgraph 필수 의존성 |
| **litellm** | `>=1.60.0,<2.0.0` | 멀티 프로바이더 LLM 호출 통합, Router 로드밸런싱 | `core/planner/decomposer.py`, `core/events/synthesizer.py`, `core/executor/mcp_executor.py` | 직접 SDK 사용 시 100+ 프로바이더 개별 관리 필요 |
| **pydantic** | `>=2.10.0,<3.0.0` | 입출력 스키마 런타임 검증, 직렬화 | `core/models/schemas.py`, `core/presets/models.py`, 전 모듈 | dataclasses(검증 없음), attrs(에코시스템 작음) |
| **pydantic-settings** | `>=2.7.0,<3.0.0` | 환경변수 기반 설정 로딩 (.env 지원) | `core/config/schema.py` | python-dotenv(타입 미지원), dynaconf(과도한 기능) |
| **fastapi** | `>=0.115.0,<1.0.0` | REST API + WebSocket 서버 | `api/app.py`, `api/routes.py`, `api/ws.py` | Flask(async 부족), Django(과도), Starlette(FastAPI가 래핑) |
| **uvicorn** | `>=0.32.0` | ASGI 서버 (FastAPI 실행) | `cli.py` serve 명령 | hypercorn(기능 유사), gunicorn+uvicorn(프로덕션용) |
| **typer** | `>=0.15.0,<1.0.0` | CLI 프레임워크 (타입힌트 기반 선언적) | `cli.py` | argparse(보일러플레이트), click(typer가 래핑) |
| **rich** | `>=13.9.0` | 터미널 출력 포맷팅 (테이블, 프로그레스 바, 구문 강조) | `cli.py` | colorama(기능 빈약), tabulate(테이블만) |
| **httpx** | `>=0.27.0` | 비동기 HTTP 클라이언트 (CLI → API 통신) | `cli.py` | aiohttp(무거움), requests(동기만) |
| **structlog** | `>=24.4.0` | 구조화 로깅 (JSON 출력, 컨텍스트 바인딩) | `core/utils.py`, 전 모듈 | 표준 logging(구조화 불편), loguru(프로덕션 약함) |
| **tenacity** | `>=9.0.0` | 범용 재시도 데코레이터 (지수 백오프, 커스텀 조건) | `core/errors/retry.py` | 직접 구현 대비 async 지원, 다양한 전략 내장 |
| **aiofiles** | `>=24.1.0` | 비동기 파일 I/O | `core/context/artifact_store.py` | 표준 open()(블로킹), anyio(과도) |
| **pyyaml** | `>=6.0.0` | YAML 프리셋 파일 파싱/저장 | `core/presets/registry.py` | toml(YAML이 프리셋에 더 자연스러움) |

### 2.2 개발 의존성 (dev group)

| 패키지 | 버전 제약 | 용도 | 사용 위치 |
|--------|----------|------|----------|
| **pytest** | `>=8.3.0` | 테스트 프레임워크 | `tests/` 전체 |
| **pytest-asyncio** | `>=0.24.0` | async 테스트 지원 (`asyncio_mode = "auto"`) | `tests/` async 테스트 |
| **pytest-cov** | `>=6.0.0` | 커버리지 측정 + 리포트 | CI, 로컬 테스트 |
| **pytest-timeout** | `>=2.3.0` | 테스트별 타임아웃 설정 | 전체 테스트 (기본 30초) |
| **pytest-mock** | `>=3.14.0` | `mocker` fixture (unittest.mock 래퍼) | 유닛 테스트 mock |
| **ruff** | `>=0.8.0` | 린터 + 포맷터 (black+isort+flake8 통합) | pre-commit, CI |
| **mypy** | `>=1.13.0` | 정적 타입 검사 (strict mode) | pre-commit, CI |
| **pre-commit** | `>=4.0.0` | pre-commit 훅 관리 | Git pre-commit |
| **ipython** | `>=8.30.0` | 대화형 디버깅 | 로컬 개발 |
| **coverage** | `>=7.6.0` | 커버리지 분석 (pytest-cov 의존) | CI 커버리지 리포트 |

---

## 3. 프론트엔드 의존성 (package.json)

### 3.1 Production Dependencies

| 패키지 | 버전 | 용도 | 사용 위치 |
|--------|------|------|----------|
| **react** | `^19.0.0` | UI 라이브러리 | 전체 컴포넌트 |
| **react-dom** | `^19.0.0` | DOM 렌더링 | `main.tsx` |
| **react-router-dom** | `^7.0.0` | 클라이언트 라우팅 | `App.tsx` |
| **react-markdown** | `^9.0.0` | 마크다운 렌더링 (결과 뷰어) | `ResultViewer.tsx` |

### 3.2 DevDependencies

| 패키지 | 버전 | 용도 | 사용 위치 |
|--------|------|------|----------|
| **typescript** | `^5.7.0` | TypeScript 컴파일러 | 전체 |
| **vite** | `^6.0.0` | 빌드 도구 (dev server + 번들링) | 빌드 시스템 |
| **@vitejs/plugin-react** | `^4.3.0` | Vite React 플러그인 (Fast Refresh) | `vite.config.ts` |
| **tailwindcss** | `^4.0.0` | 유틸리티 CSS 프레임워크 | `global.css`, 전체 컴포넌트 |
| **@types/react** | `^19.0.0` | React 타입 정의 | TypeScript |
| **@types/react-dom** | `^19.0.0` | ReactDOM 타입 정의 | TypeScript |
| **eslint** | `^9.0.0` | JavaScript/TypeScript 린터 | 개발 시 |
| **@eslint/js** | `^9.0.0` | ESLint 기본 규칙 | ESLint 설정 |
| **typescript-eslint** | `^8.0.0` | TypeScript ESLint 플러그인 | ESLint 설정 |

### 3.3 `package.json` 전체 내용

```json
{
  "name": "orchestrator-dashboard",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint ."
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.0.0",
    "react-markdown": "^9.0.0"
  },
  "devDependencies": {
    "@eslint/js": "^9.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "eslint": "^9.0.0",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.7.0",
    "typescript-eslint": "^8.0.0",
    "vite": "^6.0.0"
  }
}
```

---

## 4. 내부 의존성 그래프

### 4.1 모듈 간 의존 관계

순환 참조(circular import)를 방지하기 위한 계층별 의존 규칙.

```
                    ┌─────────────────────────────────┐
                    │        Interface Layer           │
                    │  cli.py, __main__.py              │
                    └──────────┬──────────────────────┘
                               │ import
                    ┌──────────▼──────────────────────┐
                    │          API Layer                │
                    │  api/app.py, api/routes.py        │
                    │  api/ws.py, api/deps.py           │
                    └──────────┬──────────────────────┘
                               │ import (engine.py만)
                    ┌──────────▼──────────────────────┐
                    │     Core Entry (Layer 9)          │
                    │  core/engine.py                   │
                    └──────────┬──────────────────────┘
                               │ import
          ┌────────────────────┼────────────────────┐
          │                    │                    │
┌─────────▼─────────┐ ┌───────▼─────────┐ ┌───────▼──────────┐
│ Orchestration (L8) │ │ Error Handling  │ │ Context Builder  │
│ planner/decomposer │ │ errors/retry    │ │ context/prompt_  │
│ planner/team_plan  │ │ errors/fallback │ │   builder        │
└─────────┬─────────┘ └───────┬─────────┘ └───────┬──────────┘
          │                    │                    │
          │         ┌─────────▼────────────────────▼──────┐
          │         │     Domain Services (Layer 5-7)      │
          │         │ presets/registry, presets/models      │
          │         │ queue/worker, worktree/collector      │
          │         │ events/tracker, events/synthesizer    │
          │         └──────────┬───────────────────────────┘
          │                    │
┌─────────▼────────────────────▼──────────────────────────┐
│              Core Services (Layer 3-5)                    │
│ queue/board, executor/cli_executor, adapters/factory      │
│ adapters/{claude,codex,gemini}, context/artifact_store    │
│ worktree/manager                                          │
└─────────┬───────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────┐
│              Foundation (Layer 1-2)                        │
│ executor/base, adapters/base, auth/provider, events/bus   │
│ config/schema.py, config/loader.py, utils.py              │
└─────────┬───────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────┐
│              Base Models (Layer 0)                         │
│ models/schemas.py, models/pipeline.py, queue/models.py    │
│ errors/exceptions.py, events/types.py                     │
└─────────────────────────────────────────────────────────┘
```

### 4.2 의존 규칙

| 규칙 | 설명 |
|------|------|
| **Layer 0은 독립적** | `models/schemas.py`, `errors/exceptions.py`, `events/types.py`는 외부 모듈을 import 하지 않는다 (pydantic, enum 등 라이브러리만) |
| **하위 → 상위 금지** | 낮은 Layer는 높은 Layer를 import 할 수 없다 |
| **API → Engine만** | `api/` 계층은 `core/engine.py`만 직접 import (Core 내부 모듈 직접 참조 금지) |
| **CLI → Engine 또는 API** | `cli.py`는 `engine.py`를 직접 사용하거나 httpx로 API 호출 |
| **Cross-cutting 허용** | `models/`, `errors/`, `events/types.py`는 모든 Layer에서 import 가능 |
| **순환 금지** | A → B이면 B → A 불가. mypy strict 모드로 검증 |

### 4.3 모듈별 import 명세

```python
# === Layer 0: Base Models ===
# models/schemas.py
from pydantic import BaseModel
from enum import StrEnum

# errors/exceptions.py
# (표준 라이브러리만)

# events/types.py
from pydantic import BaseModel
from enum import StrEnum

# === Layer 1: Foundation ===
# config/schema.py
from pydantic_settings import BaseSettings

# config/loader.py
from orchestrator.core.config.schema import OrchestratorConfig

# utils.py
import structlog
import asyncio
import uuid

# === Layer 2: Foundation Services ===
# auth/provider.py
from orchestrator.core.config.schema import OrchestratorConfig

# events/bus.py
from orchestrator.core.events.types import Event

# === Layer 3: Abstractions ===
# executor/base.py
from pydantic import BaseModel  # AgentResult

# adapters/base.py
import asyncio
from orchestrator.core.executor.base import AgentResult

# === Layer 4: Implementations ===
# adapters/claude.py
from orchestrator.core.adapters.base import CLIAdapter

# adapters/codex.py
from orchestrator.core.adapters.base import CLIAdapter

# adapters/gemini.py
from orchestrator.core.adapters.base import CLIAdapter

# adapters/factory.py
from orchestrator.core.adapters.base import CLIAdapter
from orchestrator.core.auth.provider import AuthProvider
from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.presets.models import AgentPreset

# executor/cli_executor.py
from orchestrator.core.executor.base import AgentExecutor, AgentResult
from orchestrator.core.adapters.base import CLIAdapter

# === Layer 5: Domain Services ===
# queue/models.py
from pydantic import BaseModel
from enum import StrEnum

# queue/board.py
from orchestrator.core.queue.models import TaskItem
from orchestrator.core.events.bus import EventBus

# context/artifact_store.py
import aiofiles

# worktree/manager.py
import asyncio
from orchestrator.core.errors.exceptions import WorktreeError

# === Layer 6: Composed Services ===
# queue/worker.py
from orchestrator.core.executor.base import AgentExecutor
from orchestrator.core.queue.board import TaskBoard
from orchestrator.core.events.bus import EventBus

# worktree/collector.py (FileDiffCollector)
import asyncio  # subprocess git

# events/tracker.py
from orchestrator.core.events.bus import EventBus

# events/synthesizer.py
import litellm
from orchestrator.core.executor.base import AgentResult

# === Layer 7: Presets ===
# presets/models.py
from pydantic import BaseModel

# presets/registry.py
import yaml
from orchestrator.core.presets.models import AgentPreset, TeamPreset

# === Layer 8: Orchestration ===
# planner/decomposer.py
import litellm
from orchestrator.core.queue.models import TaskItem
from orchestrator.core.presets.models import TeamPreset

# planner/team_planner.py
import litellm
from orchestrator.core.presets.registry import PresetRegistry
from orchestrator.core.presets.models import TeamPreset

# errors/retry.py
import tenacity

# errors/fallback.py
from orchestrator.core.adapters.base import CLIAdapter
from orchestrator.core.errors.retry import RetryPolicy
from orchestrator.core.events.bus import EventBus

# context/prompt_builder.py
from orchestrator.core.presets.models import PersonaDef
from orchestrator.core.context.artifact_store import ArtifactInfo

# === Layer 9: Engine ===
# engine.py
from orchestrator.core.queue.board import TaskBoard
from orchestrator.core.presets.registry import PresetRegistry
from orchestrator.core.events.bus import EventBus
from orchestrator.core.events.synthesizer import Synthesizer
from orchestrator.core.executor.base import AgentExecutor
from orchestrator.core.planner.decomposer import TaskDecomposer
from orchestrator.core.models.pipeline import Pipeline
from orchestrator.core.queue.models import TaskItem

# === API Layer ===
# api/deps.py
from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.events.bus import EventBus

# api/app.py
from fastapi import FastAPI
from orchestrator.core.engine import OrchestratorEngine
from orchestrator.api.routes import router
from orchestrator.api.ws import ws_router

# api/routes.py
from fastapi import APIRouter, Depends
from orchestrator.api.deps import get_engine

# api/ws.py
from fastapi import WebSocket
from orchestrator.api.deps import get_event_bus

# === Interface Layer ===
# cli.py
import typer
from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.config.schema import OrchestratorConfig
```

---

## 5. `pyproject.toml` 전체 내용

```toml
[project]
name = "agent-team-orchestrator"
version = "0.1.0"
description = "Multi-LLM agent team orchestrator: coordinate Claude Code, Codex CLI, and Gemini CLI as a collaborative team"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.12"
authors = [{ name = "yoon" }]

dependencies = [
    # === 오케스트레이션 ===
    "langgraph>=0.6.0,<1.0.0",           # StateGraph, 조건부 엣지, 체크포인터
    "langchain-core>=0.3.0,<1.0.0",      # LangGraph 의존성 (BaseMessage 등)

    # === 모델 추상화 ===
    "litellm>=1.60.0,<2.0.0",            # 100+ 프로바이더, Router 로드밸런싱

    # === 데이터 검증 ===
    "pydantic>=2.10.0,<3.0.0",           # 입출력 스키마 런타임 검증
    "pydantic-settings>=2.7.0,<3.0.0",   # 환경변수 기반 설정 로딩

    # === API 서버 ===
    "fastapi>=0.115.0,<1.0.0",           # REST + WebSocket API
    "uvicorn[standard]>=0.32.0",         # ASGI 서버

    # === CLI 인터페이스 ===
    "typer>=0.15.0,<1.0.0",              # CLI 앱 프레임워크
    "rich>=13.9.0",                       # 터미널 출력 포맷팅
    "httpx>=0.27.0",                      # 비동기 HTTP 클라이언트

    # === 유틸리티 ===
    "structlog>=24.4.0",                  # 구조화된 로깅
    "tenacity>=9.0.0",                    # 범용 재시도 데코레이터
    "aiofiles>=24.1.0",                   # 비동기 파일 I/O (아티팩트 스토어)
    "pyyaml>=6.0.0",                      # YAML 프리셋 파일 파싱
]

[project.optional-dependencies]
dev = [
    # === 테스트 ===
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",             # async 테스트 지원
    "pytest-cov>=6.0.0",                  # 커버리지
    "pytest-timeout>=2.3.0",              # 테스트 타임아웃
    "pytest-mock>=3.14.0",                # mocker fixture

    # === 코드 품질 ===
    "ruff>=0.8.0",                        # linter + formatter (black/isort 대체)
    "mypy>=1.13.0",                       # 정적 타입 검사
    "pre-commit>=4.0.0",                  # pre-commit 훅

    # === 개발 도구 ===
    "ipython>=8.30.0",                    # 대화형 디버깅
    "coverage>=7.6.0",                    # 커버리지 분석
]

[project.scripts]
orchestrator = "orchestrator.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/orchestrator"]

# === Ruff (linter + formatter) ===
[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E", "W",       # pycodestyle
    "F",             # pyflakes
    "I",             # isort
    "N",             # pep8-naming
    "UP",            # pyupgrade
    "ASYNC",         # flake8-async
    "B",             # flake8-bugbear
    "SIM",           # flake8-simplify
    "RUF",           # Ruff-specific
]

[tool.ruff.lint.isort]
known-first-party = ["orchestrator"]

# === Pytest ===
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "integration: 실 CLI 호출이 필요한 통합 테스트 (deselect by default)",
    "integration_claude: Claude CLI 통합 테스트",
    "integration_codex: Codex CLI 통합 테스트",
    "integration_gemini: Gemini CLI 통합 테스트",
    "slow: 실행 시간이 긴 테스트",
    "e2e: 전체 파이프라인 E2E 테스트",
]
addopts = "-m 'not integration and not e2e' --timeout=30"

# === MyPy ===
[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["langgraph.*", "litellm.*", "aiofiles.*"]
ignore_missing_imports = true

# === Coverage ===
[tool.coverage.run]
source = ["src/orchestrator"]
omit = ["*/tests/*", "*/__main__.py"]

[tool.coverage.report]
fail_under = 75
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "@abstractmethod",
]
```

---

## 6. `.pre-commit-config.yaml` 전체 내용

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic>=2.10
          - pydantic-settings>=2.7

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=500']
```

---

## 7. `.env.example` 전체 내용

```bash
# === CLI API Keys ===
# Claude Code CLI 인증
ANTHROPIC_API_KEY=sk-ant-...

# Codex CLI 인증 (OpenAI)
CODEX_API_KEY=sk-...

# Gemini CLI 인증
GEMINI_API_KEY=AI...

# === Orchestrator 설정 ===
ORCHESTRATOR_DEFAULT_TIMEOUT=300       # CLI 실행 타임아웃 (초)
ORCHESTRATOR_MAX_RETRIES=3             # 최대 재시도 횟수
ORCHESTRATOR_MAX_ITERATIONS=5          # 그래프 최대 반복
ORCHESTRATOR_LOG_LEVEL=INFO            # 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
ORCHESTRATOR_CLI_PRIORITY=claude,codex,gemini  # CLI 폴백 순서
ORCHESTRATOR_WORKTREE_BASE_DIR=/tmp/orchestrator-worktrees
ORCHESTRATOR_CLEANUP_WORKTREES=true

# === API 서버 ===
ORCHESTRATOR_API_HOST=0.0.0.0
ORCHESTRATOR_API_PORT=8000

# === 프리셋 ===
ORCHESTRATOR_PRESET_DIR=presets
```

---

## 8. 의존성 보안 및 업데이트 정책

### 8.1 버전 고정 전략

| 전략 | 적용 대상 | 예시 |
|------|----------|------|
| **호환 범위 고정** | 메이저 버전 변경 방지 | `>=1.60.0,<2.0.0` |
| **최소 버전만** | 안정적 패키지 | `>=13.9.0` (rich) |
| **락파일 고정** | 전체 의존성 트리 | `uv.lock` (자동 생성) |

### 8.2 업데이트 절차

```bash
# 의존성 업데이트 확인
uv pip list --outdated

# 특정 패키지 업데이트
uv add "langgraph>=0.7.0,<1.0.0"

# 락파일 동기화
uv sync --group dev

# 테스트 실행으로 호환성 검증
uv run pytest
```

### 8.3 알려진 의존성 제약

| 패키지 | 제약 | 이유 |
|--------|------|------|
| **langgraph** | `<1.0.0` | 1.0 릴리스 시 Breaking change 예상 |
| **litellm** | `<2.0.0` | Router API 변경 가능성 |
| **pydantic** | `>=2.10` | model_validator 데코레이터 기능 필요 |
| **fastapi** | `<1.0.0` | 1.0에서 Starlette 업그레이드 영향 |
| **aiofiles** | mypy ignore | 타입 스텁 미완성 |

---

## 9. Phase별 의존성 추가 계획

### Phase 1 (필수 최소)

```toml
dependencies = [
    "langgraph>=0.6.0,<1.0.0",
    "langchain-core>=0.3.0,<1.0.0",
    "litellm>=1.60.0,<2.0.0",
    "pydantic>=2.10.0,<3.0.0",
    "pydantic-settings>=2.7.0,<3.0.0",
    "fastapi>=0.115.0,<1.0.0",
    "uvicorn[standard]>=0.32.0",
    "typer>=0.15.0,<1.0.0",
    "rich>=13.9.0",
    "httpx>=0.27.0",
    "structlog>=24.4.0",
    "tenacity>=9.0.0",
    "aiofiles>=24.1.0",
]
```

### Phase 2 (추가)

```toml
# 신규 추가
"pyyaml>=6.0.0",  # YAML 프리셋 파싱
```

### Phase 3 (추가 없음)

Phase 3에서는 신규 패키지 추가 없이 기존 의존성으로 구현한다.
- `tenacity` — RetryPolicy 구현
- `litellm` — CLIAgentExecutor (MCP injection), TeamPlanner 구현
- `langgraph` — 체크포인터 활용

> **참고:** 비용 추적 관련 의존성은 Out of Scope (N/A)이므로 추가하지 않는다.
