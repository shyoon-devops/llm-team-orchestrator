# CI/CD 명세서 — Agent Team Orchestrator

> v1.0 | 2026-04-05
> 기반: `docs/SPEC.md` v2.0, `MVP-PLAN.md` v2.0

---

## 목차

1. [GitHub Actions Workflows](#1-github-actions-workflows)
2. [Branch Strategy](#2-branch-strategy)
3. [Quality Gates](#3-quality-gates)
4. [Pre-commit Hooks](#4-pre-commit-hooks)
5. [Release Process](#5-release-process)
6. [Environment Matrix](#6-environment-matrix)
7. [Secrets Management in CI](#7-secrets-management-in-ci)
8. [Monitoring & Alerting (CI)](#8-monitoring--alerting-ci)

---

## 1. GitHub Actions Workflows

### 1.1 `ci.yml` — PR/Push CI Pipeline

> 모든 코드 변경에 대한 품질 검증. lint, format, type check, unit test, coverage를 수행한다.

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [mvp]
  pull_request:
    branches: [mvp]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read
  pull-requests: write

jobs:
  lint-and-type-check:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Cache uv
        uses: actions/cache@v4
        with:
          path: |
            ~/.cache/uv
            .venv
          key: uv-${{ runner.os }}-py3.12-${{ hashFiles('pyproject.toml', 'uv.lock') }}
          restore-keys: |
            uv-${{ runner.os }}-py3.12-

      - name: Install dependencies
        run: uv sync --frozen --dev

      - name: Ruff lint
        run: uv run ruff check src/ tests/

      - name: Ruff format check
        run: uv run ruff format --check src/ tests/

      - name: Mypy strict
        run: uv run mypy src/ --strict

  test:
    name: Unit Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15
    needs: lint-and-type-check

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Cache uv
        uses: actions/cache@v4
        with:
          path: |
            ~/.cache/uv
            .venv
          key: uv-${{ runner.os }}-py3.12-${{ hashFiles('pyproject.toml', 'uv.lock') }}
          restore-keys: |
            uv-${{ runner.os }}-py3.12-

      - name: Install dependencies
        run: uv sync --frozen --dev

      - name: Run unit tests with coverage
        run: |
          uv run pytest tests/ \
            -m "not integration" \
            --cov=src/orchestrator \
            --cov-report=xml:coverage.xml \
            --cov-report=html:htmlcov \
            --cov-report=term-missing \
            --cov-fail-under=75 \
            -v

      - name: Upload coverage report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: |
            coverage.xml
            htmlcov/
          retention-days: 30

      - name: Coverage PR comment
        if: github.event_name == 'pull_request'
        uses: orgoro/coverage@v3.2
        with:
          coverageFile: coverage.xml
          token: ${{ secrets.GITHUB_TOKEN }}
          thresholdAll: 0.75
          thresholdNew: 0.80
          thresholdModified: 0.75

  integration-test:
    name: Integration Tests
    runs-on: ubuntu-latest
    timeout-minutes: 30
    if: github.event_name == 'workflow_dispatch'

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Cache uv
        uses: actions/cache@v4
        with:
          path: |
            ~/.cache/uv
            .venv
          key: uv-${{ runner.os }}-py3.12-${{ hashFiles('pyproject.toml', 'uv.lock') }}
          restore-keys: |
            uv-${{ runner.os }}-py3.12-

      - name: Install dependencies
        run: uv sync --frozen --dev

      - name: Install CLI tools
        run: |
          # Claude Code
          npm install -g @anthropic-ai/claude-code
          # Codex CLI
          npm install -g @openai/codex
          # Gemini CLI
          npm install -g @anthropic-ai/gemini-cli || true

      - name: Run integration tests
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          uv run pytest tests/ \
            -m "integration" \
            --timeout=120 \
            -v

# workflow_dispatch trigger for manual integration test runs
  trigger-integration:
    name: Manual Integration Trigger
    runs-on: ubuntu-latest
    if: false  # placeholder — use workflow_dispatch below

    steps:
      - run: echo "See workflow_dispatch trigger"
```

**`on: workflow_dispatch` 추가** (integration test를 수동으로도 트리거할 수 있도록):

```yaml
# .github/workflows/integration.yml
name: Integration Tests (Manual)

on:
  workflow_dispatch:
    inputs:
      cli_tools:
        description: "CLI tools to test (comma-separated: claude,codex,gemini)"
        required: false
        default: "claude,codex,gemini"

permissions:
  contents: read

jobs:
  integration:
    name: Integration Tests
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Cache uv
        uses: actions/cache@v4
        with:
          path: |
            ~/.cache/uv
            .venv
          key: uv-${{ runner.os }}-py3.12-${{ hashFiles('pyproject.toml', 'uv.lock') }}
          restore-keys: |
            uv-${{ runner.os }}-py3.12-

      - name: Install dependencies
        run: uv sync --frozen --dev

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install CLI tools
        run: |
          CLI_TOOLS="${{ github.event.inputs.cli_tools }}"

          if echo "$CLI_TOOLS" | grep -q "claude"; then
            npm install -g @anthropic-ai/claude-code
            echo "Claude Code installed: $(claude --version)"
          fi

          if echo "$CLI_TOOLS" | grep -q "codex"; then
            npm install -g @openai/codex
            echo "Codex CLI installed: $(codex --version)"
          fi

          if echo "$CLI_TOOLS" | grep -q "gemini"; then
            npm install -g @google/gemini-cli || echo "Gemini CLI install skipped (optional)"
          fi

      - name: Run integration tests
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          TEST_CLI_TOOLS: ${{ github.event.inputs.cli_tools }}
        run: |
          uv run pytest tests/ \
            -m "integration" \
            --timeout=120 \
            -v \
            --tb=long
```

---

### 1.2 `release.yml` — Release Pipeline

> 태그 push 시 자동으로 빌드 + PyPI 배포 + GitHub Release 생성.

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - "v*"

permissions:
  contents: write
  id-token: write  # PyPI trusted publisher

jobs:
  validate:
    name: Validate Release
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # full history for changelog

      - name: Validate tag format
        run: |
          TAG="${GITHUB_REF#refs/tags/}"
          if ! echo "$TAG" | grep -qE '^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$'; then
            echo "::error::Invalid tag format: $TAG (expected vMAJOR.MINOR.PATCH[-prerelease])"
            exit 1
          fi
          echo "TAG=$TAG" >> "$GITHUB_ENV"
          echo "VERSION=${TAG#v}" >> "$GITHUB_ENV"

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync --frozen --dev

      - name: Run full test suite
        run: |
          uv run pytest tests/ \
            -m "not integration" \
            --cov=src/orchestrator \
            --cov-fail-under=75 \
            -v

      - name: Verify version consistency
        run: |
          # pyproject.toml의 version과 tag가 일치하는지 확인
          PYPROJECT_VERSION=$(uv run python -c "
          import tomllib
          with open('pyproject.toml', 'rb') as f:
              data = tomllib.load(f)
          print(data['project']['version'])
          ")
          if [ "$PYPROJECT_VERSION" != "${{ env.VERSION }}" ]; then
            echo "::error::Version mismatch: tag=${{ env.VERSION }}, pyproject.toml=$PYPROJECT_VERSION"
            exit 1
          fi

  build-and-publish:
    name: Build & Publish
    runs-on: ubuntu-latest
    timeout-minutes: 10
    needs: validate
    environment: pypi

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Build package
        run: uv build

      - name: Verify build artifacts
        run: |
          ls -la dist/
          # sdist + wheel 모두 존재해야 함
          test -f dist/*.tar.gz
          test -f dist/*.whl

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          # Trusted publisher — no API token needed
          # PyPI에서 GitHub OIDC publisher 설정 필요
          print-hash: true

  github-release:
    name: GitHub Release
    runs-on: ubuntu-latest
    timeout-minutes: 10
    needs: build-and-publish

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Extract tag
        run: |
          TAG="${GITHUB_REF#refs/tags/}"
          echo "TAG=$TAG" >> "$GITHUB_ENV"

      - name: Generate changelog
        id: changelog
        run: |
          # 이전 태그 찾기
          PREV_TAG=$(git describe --tags --abbrev=0 HEAD^ 2>/dev/null || echo "")

          if [ -z "$PREV_TAG" ]; then
            echo "First release — no previous tag"
            CHANGELOG=$(git log --pretty=format:"- %s (%h)" HEAD)
          else
            echo "Changes since $PREV_TAG"
            CHANGELOG=$(git log --pretty=format:"- %s (%h)" "$PREV_TAG"..HEAD)
          fi

          # Conventional Commits 기반 카테고리 분류
          {
            echo "CHANGELOG<<CHANGELOG_EOF"

            FEATS=$(echo "$CHANGELOG" | grep -E "^- feat" || true)
            FIXES=$(echo "$CHANGELOG" | grep -E "^- fix" || true)
            REFACTORS=$(echo "$CHANGELOG" | grep -E "^- refactor" || true)
            DOCS=$(echo "$CHANGELOG" | grep -E "^- docs" || true)
            TESTS=$(echo "$CHANGELOG" | grep -E "^- test" || true)
            OTHERS=$(echo "$CHANGELOG" | grep -vE "^- (feat|fix|refactor|docs|test)" || true)

            if [ -n "$FEATS" ]; then
              echo "### Features"
              echo "$FEATS"
              echo ""
            fi

            if [ -n "$FIXES" ]; then
              echo "### Bug Fixes"
              echo "$FIXES"
              echo ""
            fi

            if [ -n "$REFACTORS" ]; then
              echo "### Refactoring"
              echo "$REFACTORS"
              echo ""
            fi

            if [ -n "$DOCS" ]; then
              echo "### Documentation"
              echo "$DOCS"
              echo ""
            fi

            if [ -n "$TESTS" ]; then
              echo "### Tests"
              echo "$TESTS"
              echo ""
            fi

            if [ -n "$OTHERS" ]; then
              echo "### Other"
              echo "$OTHERS"
              echo ""
            fi

            echo "CHANGELOG_EOF"
          } >> "$GITHUB_ENV"

      - name: Download build artifacts
        uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
        continue-on-error: true

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ env.TAG }}
          name: ${{ env.TAG }}
          body: |
            ## Agent Team Orchestrator ${{ env.TAG }}

            ${{ env.CHANGELOG }}

            ---

            ### 설치

            ```bash
            pip install agent-team-orchestrator==${{ env.TAG }}
            ```

            또는

            ```bash
            uv add agent-team-orchestrator==${{ env.TAG }}
            ```
          draft: false
          prerelease: ${{ contains(env.TAG, '-rc') || contains(env.TAG, '-alpha') || contains(env.TAG, '-beta') }}
          files: |
            dist/*
          generate_release_notes: false
```

---

### 1.3 `frontend.yml` — Frontend CI

> `frontend/` 디렉토리 변경 시에만 트리거. lint, type-check, test, build를 수행한다.

```yaml
# .github/workflows/frontend.yml
name: Frontend CI

on:
  push:
    branches: [mvp]
    paths:
      - "frontend/**"
      - ".github/workflows/frontend.yml"
  pull_request:
    branches: [mvp]
    paths:
      - "frontend/**"
      - ".github/workflows/frontend.yml"

concurrency:
  group: frontend-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

defaults:
  run:
    working-directory: frontend

jobs:
  frontend:
    name: Lint, Type Check, Test & Build
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Cache node_modules
        uses: actions/cache@v4
        with:
          path: frontend/node_modules
          key: node-${{ runner.os }}-${{ hashFiles('frontend/package-lock.json') }}
          restore-keys: |
            node-${{ runner.os }}-

      - name: Install dependencies
        run: npm ci

      - name: ESLint
        run: npm run lint

      - name: Type check
        run: npm run type-check

      - name: Unit tests
        run: npm run test -- --run --reporter=verbose

      - name: Build
        run: npm run build

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: frontend-dist
          path: frontend/dist/
          retention-days: 7
```

**`frontend/package.json` scripts 요구 사항** (CI가 의존하는 최소 scripts):

```jsonc
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "type-check": "tsc --noEmit",
    "test": "vitest",
    "preview": "vite preview"
  }
}
```

---

### 1.4 `docs.yml` — Documentation Validation

> `docs/` 디렉토리 변경 시 markdown lint와 link check를 수행한다.

```yaml
# .github/workflows/docs.yml
name: Docs Validation

on:
  push:
    branches: [mvp]
    paths:
      - "docs/**"
      - "*.md"
      - ".github/workflows/docs.yml"
  pull_request:
    branches: [mvp]
    paths:
      - "docs/**"
      - "*.md"
      - ".github/workflows/docs.yml"

concurrency:
  group: docs-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  markdown-lint:
    name: Markdown Lint
    runs-on: ubuntu-latest
    timeout-minutes: 5

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Markdown lint
        uses: DavidAnson/markdownlint-cli2-action@v19
        with:
          globs: |
            docs/**/*.md
            *.md
          config: .markdownlint.json

  link-check:
    name: Link Check
    runs-on: ubuntu-latest
    timeout-minutes: 5

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Link check
        uses: lycheeverse/lychee-action@v2
        with:
          args: >-
            --no-progress
            --exclude-path node_modules
            --exclude-path .venv
            --exclude-mail
            --timeout 30
            "docs/**/*.md"
            "*.md"
          fail: true
```

**`.markdownlint.json`** (프로젝트 루트에 배치):

```json
{
  "default": true,
  "MD013": {
    "line_length": 200,
    "heading_line_length": 200,
    "code_block_line_length": 200,
    "tables": false
  },
  "MD024": {
    "siblings_only": true
  },
  "MD033": {
    "allowed_elements": ["br", "details", "summary"]
  },
  "MD041": false,
  "MD046": {
    "style": "fenced"
  }
}
```

---

## 2. Branch Strategy

### 브랜치 구조

```
main ─────────────────────── PoC (frozen at v0.8.0-poc, 171 tests)
 │
mvp ──┬──┬──┬──────────────── MVP 개발 (active)
      │  │  └─ feat/preset-system
      │  └─ feat/task-board-integration
      └─ fix/cli-timeout
```

### 브랜치 명명 규칙

| Prefix | 용도 | 예시 |
|--------|------|------|
| `feat/` | 새로운 기능 | `feat/preset-system`, `feat/kanban-board` |
| `fix/` | 버그 수정 | `fix/cli-timeout`, `fix/worktree-cleanup` |
| `refactor/` | 코드 구조 개선 | `refactor/executor-abc`, `refactor/event-bus` |
| `test/` | 테스트 추가/수정 | `test/integration-e2e`, `test/synthesizer` |
| `docs/` | 문서 추가/수정 | `docs/api-reference`, `docs/contributing` |

### PR 머지 전략

| 항목 | 정책 |
|------|------|
| **머지 방법** | Squash merge to `mvp` |
| **커밋 메시지** | PR 제목 사용 (Conventional Commits 형식) |
| **필수 리뷰어** | 최소 0명 (1인 개발 환경, 팀 확대 시 1명으로 변경) |
| **필수 status check** | `lint-and-type-check`, `test` |
| **브랜치 보호** | `mvp` — force push 금지, status check 필수 |
| **자동 삭제** | merge 후 소스 브랜치 자동 삭제 |

### 릴리스 플로우

```
mvp (개발) → 태그 (v1.0.0) → GitHub Release + PyPI
```

- 릴리스 브랜치는 사용하지 않음 (1인 개발 환경)
- `mvp`에서 직접 태그 → 릴리스
- RC(Release Candidate) 필요 시: `v1.0.0-rc1` 태그 사용

---

## 3. Quality Gates

### Gate 정의

| Gate | 도구 | 기준 | Blocking | 비고 |
|------|------|------|----------|------|
| Lint | `ruff check` | 0 errors | **Yes** | `src/`, `tests/` 대상 |
| Format | `ruff format --check` | 0 diff | **Yes** | `src/`, `tests/` 대상 |
| Type check | `mypy --strict` | 0 errors | **Yes** | `src/` 대상 |
| Unit tests | `pytest` | 100% pass | **Yes** | `-m "not integration"` |
| Coverage | `pytest-cov` | 75%+ | **Yes** | 70% 미만 시 error, 70-75% 시 warning |
| Integration tests | `pytest -m integration` | 100% pass | **No** | 수동 트리거 (workflow_dispatch) |
| Markdown lint | `markdownlint-cli2` | 0 errors | **No** | `docs/`, `*.md` 대상 |
| Link check | `lychee` | 0 broken links | **No** | dead link 탐지 |

### Coverage 정책

```toml
# pyproject.toml 내 pytest-cov 설정
[tool.coverage.run]
source = ["src/orchestrator"]
omit = [
    "*/tests/*",
    "*/__main__.py",
]

[tool.coverage.report]
fail_under = 75
show_missing = true
skip_empty = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
    "@overload",
    "raise NotImplementedError",
    "\\.\\.\\.",
]
```

### GitHub Branch Protection 설정

```
Repository Settings → Branches → mvp:
├── Require status checks to pass before merging: ON
│   ├── lint-and-type-check (required)
│   └── test (required)
├── Require branches to be up to date before merging: ON
├── Require conversation resolution before merging: ON
├── Do not allow bypassing the above settings: ON
├── Restrict who can push: OFF (1인 개발)
├── Allow force pushes: OFF
└── Allow deletions: OFF
```

---

## 4. Pre-commit Hooks

### `.pre-commit-config.yaml`

```yaml
# .pre-commit-config.yaml
repos:
  # --- Ruff (lint + format) ---
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.9
    hooks:
      - id: ruff
        name: ruff lint (fix)
        args: [--fix, --exit-non-zero-on-fix]
        types_or: [python, pyi]
      - id: ruff-format
        name: ruff format
        types_or: [python, pyi]

  # --- Conventional Commits ---
  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v4.0.0
    hooks:
      - id: conventional-pre-commit
        name: conventional commit message
        stages: [commit-msg]
        args:
          - feat
          - fix
          - refactor
          - test
          - docs
          - chore
          - ci
          - perf
          - build
          - style

  # --- General file checks ---
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
        args: [--markdown-linebreak-ext=md]
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-json
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: check-merge-conflict
      - id: debug-statements

  # --- Mypy (optional — 느리므로 local hook으로 분리) ---
  # 필요 시 `pre-commit run mypy`로 수동 실행
  - repo: local
    hooks:
      - id: mypy
        name: mypy strict (optional)
        entry: uv run mypy src/ --strict
        language: system
        types: [python]
        pass_filenames: false
        stages: [manual]
```

### 설치 및 사용

```bash
# pre-commit 설치
uv add --dev pre-commit

# hooks 설치 (git hooks 디렉토리에 등록)
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg

# 전체 파일에 대해 수동 실행
uv run pre-commit run --all-files

# mypy만 수동 실행 (optional hook)
uv run pre-commit run mypy --all-files --hook-stage manual
```

### Hook 동작 요약

| Hook | 단계 | 자동 수정 | 비고 |
|------|------|-----------|------|
| `ruff` (lint) | `pre-commit` | **Yes** (`--fix`) | 자동 수정 후 unstaged 변경이 있으면 commit 중단 |
| `ruff-format` | `pre-commit` | **Yes** | 자동 포맷 적용 |
| `conventional-pre-commit` | `commit-msg` | No | `feat:`, `fix:` 등 prefix 필수 |
| `trailing-whitespace` | `pre-commit` | **Yes** | 후행 공백 제거 |
| `end-of-file-fixer` | `pre-commit` | **Yes** | 파일 끝 개행 추가 |
| `check-yaml` | `pre-commit` | No | YAML 문법 검증 |
| `check-toml` | `pre-commit` | No | TOML 문법 검증 |
| `check-added-large-files` | `pre-commit` | No | 500KB 초과 파일 차단 |
| `check-merge-conflict` | `pre-commit` | No | merge conflict 마커 탐지 |
| `debug-statements` | `pre-commit` | No | `breakpoint()`, `pdb` 탐지 |
| `mypy` | `manual` | No | 명시적 실행 시에만 동작 (느림) |

---

## 5. Release Process

### 버전 체계

**SemVer** (Semantic Versioning) `MAJOR.MINOR.PATCH`:

| 변경 종류 | 버전 증가 | 예시 |
|-----------|-----------|------|
| Breaking API 변경 | MAJOR | `1.0.0` → `2.0.0` |
| 새 기능 (하위 호환) | MINOR | `1.0.0` → `1.1.0` |
| 버그 수정 | PATCH | `1.0.0` → `1.0.1` |
| Pre-release | suffix | `1.0.0-rc1`, `1.0.0-alpha.1` |

### 태그 명명 규칙

| 태그 | 용도 |
|------|------|
| `v1.0.0` | 정식 릴리스 |
| `v1.1.0-rc1` | Release Candidate |
| `v1.0.0-alpha.1` | Alpha (내부 테스트) |
| `v1.0.0-beta.1` | Beta (외부 피드백) |

### 릴리스 절차

```bash
# 1. 버전 업데이트 (pyproject.toml)
#    [project]
#    version = "1.0.0"

# 2. Changelog 확인
git log --oneline v0.9.0..HEAD

# 3. 버전 커밋
git add pyproject.toml
git commit -m "chore: bump version to 1.0.0"

# 4. 태그 생성
git tag -a v1.0.0 -m "v1.0.0: MVP initial release"

# 5. Push (태그 포함)
git push origin mvp --tags

# 6. GitHub Actions 자동 실행:
#    release.yml → validate → build → PyPI publish → GitHub Release
```

### PyPI 배포 (Trusted Publisher)

**사전 설정** (PyPI.org에서 한 번만):

1. PyPI에서 프로젝트 `agent-team-orchestrator` 생성
2. Settings → Publishing → Add a new publisher:
   - Owner: `{github-org-or-user}`
   - Repository: `llm-team-orchestrator`
   - Workflow name: `release.yml`
   - Environment: `pypi`
3. GitHub repo → Settings → Environments → `pypi` 생성

**빌드 명령어:**

```bash
# 로컬 빌드 테스트
uv build

# 결과 확인
ls dist/
# agent_team_orchestrator-1.0.0.tar.gz
# agent_team_orchestrator-1.0.0-py3-none-any.whl

# 로컬 설치 테스트
pip install dist/agent_team_orchestrator-1.0.0-py3-none-any.whl
```

### Changelog 생성

Conventional Commits 기반 자동 생성 (release.yml의 `Generate changelog` step):

| Commit prefix | 카테고리 |
|---------------|----------|
| `feat:` | Features |
| `fix:` | Bug Fixes |
| `refactor:` | Refactoring |
| `docs:` | Documentation |
| `test:` | Tests |
| 기타 | Other |

### Docker (향후 계획)

> v1.0은 로컬 전용이므로 Docker는 v2.0 범위. 아래는 향후 참조용 Dockerfile 명세.

```dockerfile
# Dockerfile (v2.0 참조용)
FROM python:3.12-slim AS base

WORKDIR /app

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 의존성 설치 (캐시 레이어)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# 애플리케이션 코드
COPY src/ src/
COPY presets/ presets/

# 포트 노출
EXPOSE 8000

# 실행
CMD ["uv", "run", "uvicorn", "orchestrator.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 6. Environment Matrix

| 환경 | 용도 | CLI 도구 | API 키 | Python | Node.js |
|------|------|----------|--------|--------|---------|
| **CI (unit)** | 빠른 피드백 (PR/push) | 불필요 | 불필요 | 3.12 | - |
| **CI (integration)** | CLI 실 검증 (수동) | claude, codex, gemini | Required (GitHub Secrets) | 3.12 | 20 |
| **CI (frontend)** | 프론트엔드 검증 | - | - | - | 20 |
| **CI (docs)** | 문서 검증 | - | - | - | - |
| **Development** | 로컬 개발 | All 3 CLIs (선택) | `.env` 파일 | 3.12+ | 20+ |
| **Production** | N/A (v1.0 로컬 전용) | All 3 CLIs | `.env` 파일 | 3.12+ | 20+ |

### 로컬 개발 환경 설정

```bash
# 1. 저장소 클론
git clone <repo-url>
cd llm-team-orchestrator
git checkout mvp

# 2. Python 환경
uv sync --dev

# 3. Pre-commit hooks 설치
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg

# 4. 환경 변수 (CLI 연동 시에만)
cp .env.example .env
# .env 파일에 API 키 입력

# 5. 테스트 실행
uv run pytest tests/ -m "not integration" -v

# 6. 프론트엔드 (별도)
cd frontend
npm ci
npm run dev
```

### `.env.example`

```bash
# .env.example — API keys for CLI agent integration
# Copy to .env and fill in values

# Anthropic (Claude Code)
ANTHROPIC_API_KEY=

# OpenAI (Codex CLI)
OPENAI_API_KEY=

# Google (Gemini CLI)
GEMINI_API_KEY=

# Optional: LiteLLM proxy
# LITELLM_BASE_URL=http://localhost:4000
# LITELLM_API_KEY=
```

---

## 7. Secrets Management in CI

### GitHub Secrets 목록

| Secret 이름 | 용도 | 사용 워크플로우 |
|-------------|------|-----------------|
| `ANTHROPIC_API_KEY` | Claude Code CLI 인증 | `integration.yml` |
| `OPENAI_API_KEY` | Codex CLI 인증 | `integration.yml` |
| `GEMINI_API_KEY` | Gemini CLI 인증 | `integration.yml` |
| `GITHUB_TOKEN` | PR 코멘트, Release 생성 | 자동 제공 (built-in) |

### 보안 정책

| 정책 | 설명 |
|------|------|
| **사용 범위** | API 키는 `integration.yml` (수동 트리거)에서만 사용 |
| **자동 마스킹** | GitHub Actions는 secrets를 로그에서 자동으로 `***`로 마스킹 |
| **환경 격리** | PyPI 배포용 `pypi` environment 별도 관리 |
| **PR에서 접근 불가** | Fork PR에서는 secrets에 접근할 수 없음 (기본 보안) |
| **로컬 관리** | `.env` 파일은 `.gitignore`에 포함 — 절대 커밋하지 않음 |

### `.gitignore` 필수 항목

```gitignore
# Secrets — 절대 커밋 금지
.env
.env.local
.env.*.local
credentials.json
*.pem
*.key

# Python
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/
.mypy_cache/
.ruff_cache/
.pytest_cache/
htmlcov/
coverage.xml
.coverage

# Node
frontend/node_modules/
frontend/dist/

# IDE
.idea/
.vscode/
*.swp
*.swo
```

### Secrets 등록 절차

```bash
# GitHub CLI로 secrets 등록
gh secret set ANTHROPIC_API_KEY --body "sk-ant-..."
gh secret set OPENAI_API_KEY --body "sk-..."
gh secret set GEMINI_API_KEY --body "AI..."
```

또는 GitHub 웹:

```
Repository → Settings → Secrets and variables → Actions → New repository secret
```

---

## 8. Monitoring & Alerting (CI)

### PR Status Checks

```
PR → mvp:
├── ✅ lint-and-type-check (required)
├── ✅ test (required)
├── ── frontend (required if frontend/ changed)
├── ── docs-markdown-lint (optional)
└── ── docs-link-check (optional)
```

- 모든 required check가 통과해야 merge 가능
- optional check 실패 시 merge는 가능하지만 warning 표시

### 테스트 실패 알림

| 상황 | 알림 방식 |
|------|-----------|
| PR status check 실패 | GitHub PR에 빨간 X 표시, 이메일 알림 |
| Push to `mvp` 실패 | GitHub Actions 탭에 빨간 X, 이메일 알림 |
| Integration test 실패 | workflow_dispatch 결과 확인 (수동) |
| Release 실패 | GitHub Actions 탭 + 이메일 알림 |

### Coverage Report (PR)

`ci.yml`의 `Coverage PR comment` step이 PR에 coverage diff를 자동 코멘트:

```
## Coverage Report

| Metric | Value |
|--------|-------|
| Total coverage | 82.3% |
| New lines coverage | 91.0% |
| Modified lines coverage | 85.5% |

✅ All coverage thresholds met
```

- `thresholdAll: 0.75` — 전체 coverage 75% 미만 시 warning
- `thresholdNew: 0.80` — 신규 코드 coverage 80% 미만 시 warning
- `thresholdModified: 0.75` — 수정 코드 coverage 75% 미만 시 warning

### Workflow 실행 시간 모니터링

| 워크플로우 | 예상 실행 시간 | 타임아웃 |
|------------|----------------|----------|
| `ci.yml` (lint) | 1-2분 | 10분 |
| `ci.yml` (test) | 2-5분 | 15분 |
| `integration.yml` | 5-15분 | 30분 |
| `release.yml` | 3-5분 | 10분 (validate) + 10분 (build) + 10분 (release) |
| `frontend.yml` | 1-3분 | 10분 |
| `docs.yml` | 30초-1분 | 5분 |

실행 시간이 타임아웃의 50%를 초과하면 최적화를 검토한다.

---

## 부록: 전체 파일 체크리스트

> DevOps 엔지니어가 CI/CD를 설정할 때 필요한 파일 목록.

| 파일 | 위치 | 설명 |
|------|------|------|
| `ci.yml` | `.github/workflows/ci.yml` | PR/push CI pipeline |
| `integration.yml` | `.github/workflows/integration.yml` | 수동 integration test |
| `release.yml` | `.github/workflows/release.yml` | 릴리스 pipeline |
| `frontend.yml` | `.github/workflows/frontend.yml` | 프론트엔드 CI |
| `docs.yml` | `.github/workflows/docs.yml` | 문서 검증 |
| `.pre-commit-config.yaml` | 프로젝트 루트 | pre-commit hooks |
| `.markdownlint.json` | 프로젝트 루트 | markdownlint 설정 |
| `.env.example` | 프로젝트 루트 | 환경 변수 템플릿 |
| `.gitignore` | 프로젝트 루트 | Git 제외 규칙 |
| `pyproject.toml` | 프로젝트 루트 | coverage 설정 포함 |

### GitHub Repository 설정 체크리스트

- [ ] Branch protection: `mvp` 브랜치 보호 규칙 설정
- [ ] Required status checks: `lint-and-type-check`, `test` 등록
- [ ] Auto-delete head branches: ON
- [ ] Squash merge: default merge method로 설정
- [ ] Secrets: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` 등록
- [ ] Environment: `pypi` 생성 (PyPI trusted publisher용)
- [ ] PyPI: trusted publisher 설정 (owner, repo, workflow, environment)
