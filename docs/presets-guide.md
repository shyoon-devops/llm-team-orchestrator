# 프리셋 작성 가이드

> v1.0 | 2026-04-05
> SPEC.md 기준 작성

---

## 1. 에이전트 프리셋 YAML 스키마

에이전트 프리셋은 단일 에이전트의 정체성, 실행 방식, 도구 접근, 제약을 정의한다.

### 1.1 전체 스키마

```yaml
# 에이전트 프리셋 전체 스키마
# 필수 필드: name, persona.role, persona.goal

# --- 기본 정보 ---
name: ""                         # str, 필수, 프리셋 고유 이름 (영문 kebab-case)
description: ""                  # str, 선택, 프리셋 설명
version: "1.0"                   # str, 선택, 프리셋 버전

# --- 페르소나 ---
persona:
  role: ""                       # str, 필수, 에이전트 역할 (예: "시니어 백엔드 아키텍트")
  goal: ""                       # str, 필수, 목표 (예: "확장 가능한 API 설계")
  backstory: ""                  # str, 선택, 배경 설명 (LLM 프롬프트에 포함)
  constraints:                   # list[str], 선택, 행동 제약 조건
    - ""                         # 예: "테스트 없이 코드를 제출하지 않는다"

# --- 실행 설정 ---
execution:
  mode: "cli"                    # str, "cli" | "mcp", 실행 모드
  preferred_cli: "claude"        # str, "claude" | "codex" | "gemini", CLI 모드 시 사용할 CLI 도구
  fallback_cli: ""               # str, 선택, 기본 CLI 실패 시 대체 CLI
  model_override: ""             # str, 선택, CLI 도구의 모델 오버라이드 (예: "claude-opus-4-20250514")

# --- MCP 서버 (execution.mode == "mcp" 일 때) ---
mcp_servers:                     # dict[str, MCPServerConfig], MCP 서버 설정
  server_name:                   # str, MCP 서버 식별자
    command: ""                  # str, 필수, 서버 실행 명령어
    args:                        # list[str], 선택, 명령어 인자
      - ""
    env:                         # dict[str, str], 선택, 환경변수
      KEY: "value"
    url: ""                      # str, 선택, SSE/Streamable HTTP URL (command 대신 사용)
    transport: "stdio"           # str, "stdio" | "sse" | "streamable-http"
    trusted: true                # bool, 신뢰 여부 (보안 검증)

# --- 도구 접근 ---
tools:
  file_access:                   # 파일시스템 접근 권한
    read: true                   # bool, 파일 읽기 허용
    write: true                  # bool, 파일 쓰기 허용
    patterns:                    # list[str], 선택, 허용 파일 패턴 (glob)
      - "**/*.py"
      - "**/*.md"
    deny_patterns:               # list[str], 선택, 차단 파일 패턴
      - "**/.env"
      - "**/secrets/**"
  shell_access: false            # bool, 셸 명령어 실행 허용
  network_access: false          # bool, 네트워크 접근 허용
  git_access: true               # bool, git 명령어 허용

# --- 실행 제한 ---
limits:
  timeout: 300                   # int, 초, 최대 실행 시간
  max_output_chars: 50000        # int, 최대 출력 문자 수
  max_retries: 3                 # int, 최대 재시도 횟수

# --- 프롬프트 템플릿 ---
prompt:
  system_prefix: ""              # str, 선택, 시스템 프롬프트 앞에 추가할 텍스트
  system_suffix: ""              # str, 선택, 시스템 프롬프트 뒤에 추가할 텍스트
  task_template: ""              # str, 선택, 태스크 프롬프트 템플릿 ({task} 변수 사용)
  output_format: ""              # str, 선택, 출력 형식 지시 (예: "JSON으로 응답")

# --- 메타데이터 ---
metadata:                        # dict[str, str], 선택, 사용자 정의 메타데이터
  author: ""
  tags:                          # list[str], 검색/필터 용
    - ""
```

### 1.2 필드 상세

#### `name`

| 항목 | 값 |
|------|-----|
| 타입 | `str` |
| 필수 | **예** |
| 형식 | 영문 kebab-case (`architect`, `elk-analyst`, `security-auditor`) |
| 고유성 | 검색 경로 내 고유해야 함 (동명 시 우선순위 규칙 적용) |

#### `persona`

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `role` | `str` | **예** | - | 에이전트의 역할/직함 |
| `goal` | `str` | **예** | - | 에이전트가 달성해야 할 목표 |
| `backstory` | `str` | 아니오 | `""` | 에이전트의 배경 이야기 (프롬프트에 포함) |
| `constraints` | `list[str]` | 아니오 | `[]` | 행동 제약 조건 (프롬프트에 포함) |

#### `execution`

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `mode` | `str` | 아니오 | `"cli"` | `"cli"`: CLI subprocess, `"mcp"`: LLM + MCP tools |
| `preferred_cli` | `str` | 아니오 | `"claude"` | `"claude"`, `"codex"`, `"gemini"` |
| `fallback_cli` | `str` | 아니오 | `""` | 기본 CLI 실패 시 대체 CLI |
| `model_override` | `str` | 아니오 | `""` | CLI 도구의 LLM 모델 오버라이드 |

#### `mcp_servers`

MCP 모드(`execution.mode == "mcp"`)에서 사용할 MCP 서버 목록이다.

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `command` | `str` | 조건부 | - | 서버 실행 명령어 (`url` 미사용 시 필수) |
| `args` | `list[str]` | 아니오 | `[]` | 명령어 인자 |
| `env` | `dict[str, str]` | 아니오 | `{}` | 서버에 전달할 환경변수 |
| `url` | `str` | 조건부 | `""` | SSE/HTTP URL (`command` 미사용 시 필수) |
| `transport` | `str` | 아니오 | `"stdio"` | `"stdio"`, `"sse"`, `"streamable-http"` |
| `trusted` | `bool` | 아니오 | `true` | 신뢰 여부 (`false`면 보안 검증 추가) |

#### `tools`

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `file_access.read` | `bool` | `true` | 파일 읽기 |
| `file_access.write` | `bool` | `true` | 파일 쓰기 |
| `file_access.patterns` | `list[str]` | `["**/*"]` | 허용 glob 패턴 |
| `file_access.deny_patterns` | `list[str]` | `["**/.env", "**/secrets/**"]` | 차단 glob 패턴 |
| `shell_access` | `bool` | `false` | 셸 명령어 실행 |
| `network_access` | `bool` | `false` | 네트워크 접근 |
| `git_access` | `bool` | `true` | git 명령어 실행 |

#### `limits`

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `timeout` | `int` | `300` | 초 단위 최대 실행 시간 |
| `max_output_chars` | `int` | `50000` | 최대 출력 문자 수 |
| `max_retries` | `int` | `3` | 최대 재시도 횟수 |

---

## 2. 팀 프리셋 YAML 스키마

팀 프리셋은 여러 에이전트를 조합하고 워크플로우를 정의한다.

### 2.1 전체 스키마

```yaml
# 팀 프리셋 전체 스키마
# 필수 필드: name, agents, tasks

# --- 기본 정보 ---
name: ""                         # str, 필수, 팀 프리셋 고유 이름 (영문 kebab-case)
description: ""                  # str, 선택, 팀 설명
version: "1.0"                   # str, 선택

# --- 에이전트 구성 ---
agents:                          # dict[str, TeamAgentDef], 필수, 팀에 참여하는 에이전트
  agent_alias:                   # str, 에이전트 별칭 (팀 내 고유)
    preset: ""                   # str, 필수, 에이전트 프리셋 이름 참조
    overrides:                   # dict, 선택, 프리셋 필드 오버라이드
      limits:
        timeout: 600
      persona:
        constraints:
          - "추가 제약"

# --- 태스크 정의 ---
tasks:                           # dict[str, TeamTaskDef], 필수, 팀 워크플로우의 태스크 목록
  task_alias:                    # str, 태스크 별칭
    description: ""              # str, 필수, 태스크 설명
    agent: ""                    # str, 필수, 담당 에이전트 별칭 (agents 키 참조)
    depends_on:                  # list[str], 선택, 의존 태스크 별칭 (완료 후 실행)
      - ""
    context_from:                # list[str], 선택, 컨텍스트로 전달받을 태스크 별칭
      - ""
    prompt_template: ""          # str, 선택, 태스크 전용 프롬프트 ({task}, {context} 변수)

# --- 워크플로우 ---
workflow: "parallel"             # str, "parallel" | "sequential" | "dag"
                                 # parallel: 의존 없는 태스크 동시 실행
                                 # sequential: tasks 순서대로 실행
                                 # dag: depends_on 기반 DAG 실행

# --- 결과 종합 ---
synthesis:
  strategy: "narrative"          # str, "narrative" | "structured" | "checklist"
  prompt_template: ""            # str, 선택, 종합 프롬프트 ({task}, {results} 변수)
  model: ""                      # str, 선택, Synthesizer 모델 오버라이드

# --- 메타데이터 ---
metadata:
  author: ""
  tags:
    - ""
  domain: ""                     # str, 선택, "coding" | "ops" | "analysis" | "general"
```

### 2.2 필드 상세

#### `agents`

팀에 참여하는 에이전트를 정의한다. 키는 팀 내 별칭이다.

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `preset` | `str` | **예** | - | 에이전트 프리셋 이름 (`architect`, `elk-analyst` 등) |
| `overrides` | `dict` | 아니오 | `{}` | 프리셋 필드 오버라이드 (deep merge) |

#### `tasks`

워크플로우의 태스크를 정의한다.

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `description` | `str` | **예** | - | 태스크 설명 |
| `agent` | `str` | **예** | - | 담당 에이전트 별칭 |
| `depends_on` | `list[str]` | 아니오 | `[]` | 선행 태스크 (완료 후 실행) |
| `context_from` | `list[str]` | 아니오 | `[]` | 결과를 컨텍스트로 전달받을 태스크 |
| `prompt_template` | `str` | 아니오 | `""` | 태스크 프롬프트 템플릿 |

#### `workflow`

| 값 | 동작 |
|-----|------|
| `"parallel"` | `depends_on`이 없는 모든 태스크를 동시 실행, `depends_on` 있으면 대기 |
| `"sequential"` | `tasks` 딕셔너리 정의 순서대로 하나씩 실행 |
| `"dag"` | `depends_on` 기반 DAG 위상 정렬 실행 |

#### `synthesis`

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `strategy` | `str` | 아니오 | `"narrative"` | `"narrative"`: 자유 형식 보고서, `"structured"`: 섹션별 구조화, `"checklist"`: 체크리스트 |
| `prompt_template` | `str` | 아니오 | `""` | 종합 프롬프트 ({task}, {results} 변수) |
| `model` | `str` | 아니오 | `""` | Synthesizer LLM 모델 오버라이드 |

---

## 3. 예제 프리셋

### 3.1 `architect.yaml` — 코딩 설계 (Claude)

```yaml
# presets/agents/architect.yaml
name: architect
description: "소프트웨어 설계 전문 에이전트 — 아키텍처, API 설계, 코드 구조 결정"
version: "1.0"

persona:
  role: "시니어 소프트웨어 아키텍트"
  goal: "확장 가능하고 유지보수하기 쉬운 소프트웨어 설계를 생성한다"
  backstory: |
    15년 경력의 소프트웨어 아키텍트로, 대규모 분산 시스템 설계 경험이 풍부하다.
    SOLID 원칙, 클린 아키텍처, DDD에 정통하며,
    실용적이고 팀이 즉시 구현할 수 있는 설계를 지향한다.
  constraints:
    - "구현 코드를 직접 작성하지 않는다 — 설계 문서와 인터페이스만 제공한다"
    - "모든 설계 결정에 근거(trade-off 분석)를 포함한다"
    - "다이어그램은 Mermaid 형식으로 작성한다"
    - "기존 코드베이스 구조를 존중하고 점진적 개선을 제안한다"

execution:
  mode: cli
  preferred_cli: claude
  fallback_cli: gemini
  model_override: ""

tools:
  file_access:
    read: true
    write: true
    patterns:
      - "**/*.py"
      - "**/*.md"
      - "**/*.yaml"
      - "**/*.toml"
      - "**/Dockerfile"
    deny_patterns:
      - "**/.env"
      - "**/secrets/**"
      - "**/*.key"
  shell_access: false
  network_access: false
  git_access: true

limits:
  timeout: 600
  max_output_chars: 100000
  max_retries: 2

prompt:
  system_suffix: |
    설계 결과물은 다음 형식으로 작성한다:
    1. 개요 (1-2문장)
    2. 아키텍처 다이어그램 (Mermaid)
    3. 인터페이스 정의 (Python ABC/Protocol)
    4. 데이터 모델 (Pydantic)
    5. 디렉토리 구조
    6. Trade-off 분석
  output_format: "Markdown"

metadata:
  author: "orchestrator-team"
  tags:
    - coding
    - architecture
    - design
  domain: coding
```

### 3.2 `implementer.yaml` — 코딩 구현 (Codex)

```yaml
# presets/agents/implementer.yaml
name: implementer
description: "코드 구현 전문 에이전트 — 설계에 따른 구현 코드 작성 및 테스트"
version: "1.0"

persona:
  role: "시니어 백엔드 개발자"
  goal: "설계 명세에 따라 프로덕션 품질의 코드를 구현한다"
  backstory: |
    10년 경력의 백엔드 개발자로, Python과 TypeScript에 능숙하다.
    테스트 주도 개발을 실천하며, 깔끔하고 읽기 쉬운 코드를 작성한다.
    코드 리뷰에서 자주 칭찬받는 개발자다.
  constraints:
    - "모든 public 함수에 타입 힌트를 추가한다"
    - "구현 코드에 대한 단위 테스트를 반드시 작성한다"
    - "기존 코드 스타일과 컨벤션을 따른다"
    - "불필요한 의존성을 추가하지 않는다"
    - "TODO 주석을 남기지 않는다 — 완전히 구현하거나 명확히 범위를 제한한다"

execution:
  mode: cli
  preferred_cli: codex
  fallback_cli: claude
  model_override: ""

tools:
  file_access:
    read: true
    write: true
    patterns:
      - "**/*.py"
      - "**/*.ts"
      - "**/*.tsx"
      - "**/*.json"
      - "**/*.yaml"
      - "**/*.toml"
    deny_patterns:
      - "**/.env"
      - "**/secrets/**"
      - "**/*.key"
      - "**/node_modules/**"
  shell_access: true
  network_access: false
  git_access: true

limits:
  timeout: 300
  max_output_chars: 50000
  max_retries: 3

prompt:
  system_suffix: |
    구현 시 다음 규칙을 따른다:
    1. from __future__ import annotations 필수
    2. Google style docstring 사용
    3. structlog 로깅 사용 (print 금지)
    4. 테스트 파일은 tests/ 디렉토리에 test_*.py 형식
    5. Pydantic v2 모델 사용
  output_format: "코드 파일(diff 형식 우선)"

metadata:
  author: "orchestrator-team"
  tags:
    - coding
    - implementation
    - testing
  domain: coding
```

### 3.3 `elk-analyst.yaml` — ELK 로그 분석 (MCP)

```yaml
# presets/agents/elk-analyst.yaml
name: elk-analyst
description: "ELK(Elasticsearch) 기반 로그 분석 에이전트 — 에러 패턴 식별, 로그 검색"
version: "1.0"

persona:
  role: "ELK 로그 분석 전문가"
  goal: "Elasticsearch 로그에서 문제의 근본 원인을 식별하고 분석 보고서를 작성한다"
  backstory: |
    SRE 팀에서 5년간 ELK 스택을 운영한 엔지니어로,
    복잡한 분산 시스템의 로그에서 문제를 빠르게 추적하는 능력이 뛰어나다.
    Kibana 대시보드 없이도 Elasticsearch 쿼리만으로 문제를 진단할 수 있다.
  constraints:
    - "최근 1시간 로그만 우선 분석하고, 필요 시 범위를 확장한다"
    - "5xx 에러와 timeout 로그에 집중한다"
    - "분석 결과에 반드시 관련 로그 샘플을 포함한다"
    - "Elasticsearch 쿼리를 가독성 있게 작성한다"
    - "민감한 데이터(개인정보, 토큰)는 마스킹한다"

execution:
  mode: mcp
  preferred_cli: ""
  model_override: ""

mcp_servers:
  elasticsearch:
    command: "npx"
    args:
      - "-y"
      - "@modelcontextprotocol/server-elasticsearch"
    env:
      ELASTICSEARCH_URL: "${ELASTICSEARCH_URL}"
      ELASTICSEARCH_API_KEY: "${ELASTICSEARCH_API_KEY}"
    transport: stdio
    trusted: true

tools:
  file_access:
    read: false
    write: false
  shell_access: false
  network_access: false
  git_access: false

limits:
  timeout: 120
  max_output_chars: 80000
  max_retries: 2

prompt:
  system_suffix: |
    분석 보고서는 다음 형식으로 작성한다:
    1. 요약 (1-2문장)
    2. 영향 범위 (서비스, 시간대, 에러 수)
    3. 에러 패턴 분석 (유형별 분류, 빈도)
    4. 근본 원인 추정
    5. 관련 로그 샘플 (최대 5건)
    6. 권장 조치
  output_format: "Markdown 보고서"

metadata:
  author: "orchestrator-team"
  tags:
    - ops
    - elk
    - log-analysis
    - incident
  domain: analysis
```

### 3.4 `security-auditor.yaml` — 보안 감사 (Claude)

```yaml
# presets/agents/security-auditor.yaml
name: security-auditor
description: "코드 보안 감사 에이전트 — OWASP 기반 취약점 분석, 보안 리뷰"
version: "1.0"

persona:
  role: "시니어 보안 감사자"
  goal: "코드베이스에서 보안 취약점을 식별하고 수정 방안을 제시한다"
  backstory: |
    애플리케이션 보안 분야 8년 경력의 전문가로,
    OWASP Top 10, CWE/SANS Top 25에 정통하다.
    펜테스팅과 코드 보안 리뷰 모두 수행한 경험이 있으며,
    개발자가 이해하고 즉시 적용할 수 있는 실용적 보안 권고를 작성한다.
  constraints:
    - "OWASP Top 10 기준으로 분류한다"
    - "각 취약점에 심각도(Critical/High/Medium/Low)를 부여한다"
    - "취약점마다 구체적인 수정 코드 예시를 제공한다"
    - "False positive를 최소화한다 — 확신이 없으면 '잠재적 위험'으로 표시"
    - "보안 관련 파일(.env, credentials 등)의 내용을 출력하지 않는다"

execution:
  mode: cli
  preferred_cli: claude
  fallback_cli: ""
  model_override: ""

tools:
  file_access:
    read: true
    write: false
    patterns:
      - "**/*.py"
      - "**/*.ts"
      - "**/*.js"
      - "**/*.yaml"
      - "**/*.toml"
      - "**/*.json"
      - "**/Dockerfile"
      - "**/*.sql"
    deny_patterns:
      - "**/.env"
      - "**/secrets/**"
      - "**/*.key"
      - "**/*.pem"
      - "**/*.p12"
  shell_access: false
  network_access: false
  git_access: true

limits:
  timeout: 600
  max_output_chars: 100000
  max_retries: 2

prompt:
  system_suffix: |
    보안 감사 보고서는 다음 형식으로 작성한다:
    1. 감사 요약 (전체 심각도 분포)
    2. Critical/High 취약점 (즉시 수정 필요)
    3. Medium/Low 취약점 (개선 권고)
    4. 각 취약점:
       - CWE ID
       - 파일 경로 + 라인 번호
       - 설명
       - PoC (가능한 경우)
       - 수정 코드 예시
    5. 보안 모범 사례 권고
  output_format: "Markdown 보고서"

metadata:
  author: "orchestrator-team"
  tags:
    - security
    - audit
    - owasp
    - code-review
  domain: coding
```

### 3.5 `incident-analysis-team.yaml` — 인시던트 분석 팀 (ELK + Grafana + K8s)

```yaml
# presets/teams/incident-analysis-team.yaml
name: incident-analysis-team
description: "프로덕션 인시던트 분석 팀 — ELK 로그, Grafana 메트릭, K8s 상태를 병렬 분석하여 종합 보고서 생성"
version: "1.0"

agents:
  elk:
    preset: elk-analyst
    overrides:
      limits:
        timeout: 180
      persona:
        constraints:
          - "최근 30분 로그에 집중한다"
          - "5xx 에러, timeout, connection refused 패턴을 우선 분석한다"

  grafana:
    preset: grafana-monitor
    overrides:
      limits:
        timeout: 120

  k8s:
    preset: k8s-operator
    overrides:
      limits:
        timeout: 120
      persona:
        constraints:
          - "Pod restart, OOMKilled, CrashLoopBackOff 이벤트에 집중한다"
          - "최근 1시간 이벤트만 확인한다"

tasks:
  log-analysis:
    description: |
      ELK에서 에러 로그를 분석한다.
      대상: {task}와 관련된 서비스의 에러 패턴, 빈도, 타임라인을 파악한다.
    agent: elk
    depends_on: []
    context_from: []

  metric-analysis:
    description: |
      Grafana에서 시스템 메트릭을 확인한다.
      대상: CPU, 메모리, 네트워크, 에러율, 응답시간 이상 징후를 파악한다.
    agent: grafana
    depends_on: []
    context_from: []

  infra-check:
    description: |
      Kubernetes 클러스터 상태를 점검한다.
      대상: Pod 상태, 이벤트, 리소스 사용량, 최근 배포 이력을 확인한다.
    agent: k8s
    depends_on: []
    context_from: []

workflow: parallel

synthesis:
  strategy: structured
  prompt_template: |
    다음 3개 분석 결과를 종합하여 인시던트 보고서를 작성해 주세요.

    원래 문제: {task}

    === 분석 결과 ===
    {results}

    보고서 형식:
    1. 인시던트 요약 (1-2문장)
    2. 타임라인 (시간순 이벤트)
    3. 근본 원인 분석 (Root Cause Analysis)
    4. 영향 범위 (서비스, 사용자, 시간)
    5. 즉시 조치 사항
    6. 재발 방지 대책
    7. 각 분석 소스별 핵심 발견사항

metadata:
  author: "orchestrator-team"
  tags:
    - ops
    - incident
    - analysis
    - sre
  domain: analysis
```

---

## 4. 프리셋 검색 경로

프리셋은 다음 경로에서 순서대로 검색된다. 동일 이름의 프리셋이 여러 경로에 존재하면 **앞선 경로가 우선**한다.

### 4.1 검색 순서

```
1. 프로젝트 로컬      .orchestrator/presets/agents/
                      .orchestrator/presets/teams/

2. 사용자 전역        ~/.config/orchestrator/presets/agents/
                      ~/.config/orchestrator/presets/teams/

3. 시스템 번들        <package>/presets/agents/
                      <package>/presets/teams/

4. 추가 경로          YAML 설정의 presets.search_paths
```

### 4.2 디렉토리 구조

```
# 프로젝트 로컬
my-project/
├── .orchestrator/
│   └── presets/
│       ├── agents/
│       │   └── custom-agent.yaml
│       └── teams/
│           └── custom-team.yaml
├── src/
└── ...

# 사용자 전역
~/.config/orchestrator/
└── presets/
    ├── agents/
    │   ├── my-analyst.yaml
    │   └── my-reviewer.yaml
    └── teams/
        └── my-dev-team.yaml

# 시스템 번들 (패키지 설치 시 제공)
site-packages/orchestrator/
└── presets/
    ├── agents/
    │   ├── architect.yaml
    │   ├── implementer.yaml
    │   ├── elk-analyst.yaml
    │   ├── grafana-monitor.yaml
    │   ├── k8s-operator.yaml
    │   └── security-auditor.yaml
    └── teams/
        ├── feature-team.yaml
        ├── incident-analysis-team.yaml
        └── deploy-team.yaml
```

### 4.3 우선순위 예시

`architect` 프리셋이 3곳에 있는 경우:

```
.orchestrator/presets/agents/architect.yaml     ← 이것이 사용됨 (1순위)
~/.config/orchestrator/presets/agents/architect.yaml  (무시)
<package>/presets/agents/architect.yaml               (무시)
```

프로젝트 로컬 프리셋으로 시스템 번들 프리셋을 **오버라이드**할 수 있다.

---

## 5. 오버라이드 규칙

### 5.1 Deep Merge 동작

팀 프리셋의 `overrides`는 에이전트 프리셋에 **deep merge**로 적용된다.

#### Deep Merge 규칙

| 타입 | 동작 | 예시 |
|------|------|------|
| 스칼라 (`str`, `int`, `bool`) | 오버라이드 값으로 **대체** | `timeout: 300` → `timeout: 600` |
| `dict` | **재귀적 merge** | 키가 없으면 추가, 있으면 재귀 적용 |
| `list` | **대체** (merge 아님) | `constraints: [A, B]` → `constraints: [C, D]` |

#### 예시

**에이전트 프리셋 (architect.yaml):**

```yaml
persona:
  role: "시니어 소프트웨어 아키텍트"
  goal: "확장 가능한 소프트웨어 설계"
  constraints:
    - "구현 코드를 직접 작성하지 않는다"
    - "Mermaid 다이어그램 사용"
limits:
  timeout: 600
  max_retries: 2
```

**팀 프리셋에서 오버라이드:**

```yaml
agents:
  designer:
    preset: architect
    overrides:
      persona:
        constraints:            # list → 대체 (기존 제약 사라짐)
          - "보안 관점에서 설계한다"
          - "성능 요구사항을 명시한다"
      limits:
        timeout: 900            # 스칼라 → 대체
                                # max_retries는 변경되지 않음 (2 유지)
```

**결과 (merge 후):**

```yaml
persona:
  role: "시니어 소프트웨어 아키텍트"   # 유지
  goal: "확장 가능한 소프트웨어 설계"   # 유지
  constraints:                          # 대체됨
    - "보안 관점에서 설계한다"
    - "성능 요구사항을 명시한다"
limits:
  timeout: 900                          # 대체됨
  max_retries: 2                        # 유지됨
```

### 5.2 오버라이드 불가 필드

다음 필드는 오버라이드할 수 없다:

| 필드 | 이유 |
|------|------|
| `name` | 프리셋 식별자 — 변경 불가 |
| `version` | 프리셋 버전 — 변경 불가 |
| `execution.mode` | 실행 모드 변경은 프리셋 재정의 필요 |

오버라이드에 위 필드가 포함되면 **경고 로그**를 출력하고 무시한다.

---

## 6. 커스텀 프리셋 작성 튜토리얼

### Step 1: 에이전트 프리셋 작성

`my-reviewer.yaml` — 코드 리뷰 에이전트를 만든다.

```yaml
# ~/.config/orchestrator/presets/agents/my-reviewer.yaml
name: my-reviewer
description: "내 프로젝트 코드 리뷰어"
version: "1.0"

persona:
  role: "코드 리뷰어"
  goal: "코드 품질, 가독성, 잠재적 버그를 검토한다"
  backstory: "꼼꼼한 코드 리뷰로 유명한 시니어 개발자"
  constraints:
    - "nitpick과 중요한 이슈를 구분한다"
    - "리뷰 코멘트에 구체적인 개선 코드를 포함한다"
    - "칭찬할 부분도 언급한다"

execution:
  mode: cli
  preferred_cli: claude

tools:
  file_access:
    read: true
    write: false
  shell_access: false
  network_access: false
  git_access: true

limits:
  timeout: 300
  max_retries: 2

prompt:
  system_suffix: |
    리뷰 결과를 다음 형식으로 작성한다:
    ## 요약
    ## Critical Issues (반드시 수정)
    ## Suggestions (권장)
    ## Good Points (잘한 점)
  output_format: "Markdown"

metadata:
  tags:
    - coding
    - review
```

### Step 2: 프리셋 검증

```bash
orchestrator presets validate ~/.config/orchestrator/presets/agents/my-reviewer.yaml
```

출력:

```
✓ Schema validation passed
✓ Required fields: name, persona.role, persona.goal
✓ CLI 'claude' is available
✓ No conflicting preset name found
```

### Step 3: 프리셋 확인

```bash
orchestrator presets list

# 출력:
# Agent Presets:
#   architect        [system]   시니어 소프트웨어 아키텍트
#   implementer      [system]   시니어 백엔드 개발자
#   elk-analyst      [system]   ELK 로그 분석 전문가
#   security-auditor [system]   시니어 보안 감사자
#   my-reviewer      [user]     코드 리뷰어

orchestrator presets show my-reviewer
```

### Step 4: 팀 프리셋에 포함

```yaml
# .orchestrator/presets/teams/my-dev-team.yaml
name: my-dev-team
description: "내 개발 팀: 설계 → 구현 → 리뷰"

agents:
  designer:
    preset: architect
  coder:
    preset: implementer
  reviewer:
    preset: my-reviewer
    overrides:
      persona:
        constraints:
          - "Python 코드에 집중한다"
          - "ruff 규칙 준수 여부를 확인한다"

tasks:
  design:
    description: "기능 설계 및 인터페이스 정의"
    agent: designer
    depends_on: []

  implement:
    description: "설계에 따른 코드 구현"
    agent: coder
    depends_on: [design]
    context_from: [design]

  review:
    description: "구현된 코드 리뷰"
    agent: reviewer
    depends_on: [implement]
    context_from: [implement]

workflow: dag

synthesis:
  strategy: structured

metadata:
  tags:
    - coding
    - development
  domain: coding
```

### Step 5: 실행

```bash
orchestrator run "사용자 인증 미들웨어 구현" --team my-dev-team --repo ./my-project --wait
```

### Step 6: 프로젝트별 프리셋

프로젝트에 고유한 프리셋은 프로젝트 로컬에 저장한다:

```bash
# 프로젝트 디렉토리에서
mkdir -p .orchestrator/presets/agents
mkdir -p .orchestrator/presets/teams

# 프로젝트 전용 에이전트 프리셋 작성
cat > .orchestrator/presets/agents/project-expert.yaml << 'EOF'
name: project-expert
description: "이 프로젝트 전문가"
persona:
  role: "프로젝트 전문가"
  goal: "이 프로젝트의 규칙과 패턴에 맞는 코드를 작성한다"
  constraints:
    - "이 프로젝트는 FastAPI + Pydantic v2를 사용한다"
    - "모든 API는 async def로 작성한다"
    - "에러 응답은 RFC 7807 형식을 따른다"
execution:
  mode: cli
  preferred_cli: claude
limits:
  timeout: 300
EOF

# 검증
orchestrator presets validate .orchestrator/presets/agents/project-expert.yaml

# git에 포함
git add .orchestrator/presets/
git commit -m "chore: add project-specific agent preset"
```

### Step 7: MCP 에이전트 프리셋

MCP 서버를 사용하는 에이전트 프리셋 작성:

```yaml
# ~/.config/orchestrator/presets/agents/github-analyst.yaml
name: github-analyst
description: "GitHub 이슈/PR 분석 에이전트"

persona:
  role: "GitHub 분석가"
  goal: "GitHub 이슈와 PR을 분석하여 프로젝트 상태를 파악한다"
  constraints:
    - "최근 7일간 활동에 집중한다"
    - "미해결 이슈를 우선순위별로 분류한다"

execution:
  mode: mcp

mcp_servers:
  github:
    command: "npx"
    args:
      - "-y"
      - "@modelcontextprotocol/server-github"
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
    transport: stdio
    trusted: true

tools:
  file_access:
    read: false
    write: false
  shell_access: false
  network_access: false
  git_access: false

limits:
  timeout: 180

metadata:
  tags:
    - github
    - analysis
```

> **참고:** MCP 서버 환경변수에서 `${VAR_NAME}` 문법을 사용하면 시스템 환경변수로 치환된다. 프리셋 YAML에 API 키를 직접 작성하지 않는다.
