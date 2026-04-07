# 장애 보고서 (Post-Incident Report)

| 항목 | 내용 |
|------|------|
| **Incident ID** | INC-2026-0407-001 |
| **심각도** | **P1 — Critical** |
| **발생 일시** | 2026-04-07 09:10 UTC (전면 장애: 09:15 UTC) |
| **탐지 일시** | 2026-04-07 09:15 UTC |
| **현재 상태** | 🔴 진행 중 (Active) |
| **작성자** | Incident Commander |
| **작성 일시** | 2026-04-07 |

---

## 1. 장애 개요 (Executive Summary)

payment-api 서비스에서 **5xx 에러율이 0.1%에서 40%로 급증**하고, **P99 응답시간이 0.28초에서 15.2초로 54배 폭등**하는 전면 장애가 발생했습니다.

직접적 원인은 **payment-db의 리소스 포화**(CPU 95%, Memory 87%)로 인한 쿼리 지연이며, 이로 인해 JDBC 커넥션 풀이 고갈되고, 서킷 브레이커가 작동하면서 payment-api 전체가 서비스 불가 상태에 빠졌습니다. 하류 서비스인 **order-api**(에러율 24.4%)와 **checkout-web**(에러율 35%)까지 연쇄 장애가 전파되어, **결제 및 주문 기능 전체가 사실상 마비**된 상태입니다.

**비즈니스 영향**: 결제 처리의 약 40%가 실패하고 있어, 분당 약 57건의 결제가 유실되고 있습니다. 고객은 결제 실패, 주문 불가, 타임아웃 오류를 경험하고 있으며, 이는 직접적인 **매출 손실과 고객 이탈**로 이어지고 있습니다.

---

## 2. 근본 원인 (Root Cause Analysis)

### 2.1 확정 근본 원인

> **payment-db(PostgreSQL) StatefulSet의 리소스 포화가 근본 원인(Root Cause)이며, Istio 재시도 설정과 부적절한 리소스 리밋이 장애를 증폭시킨 복합 장애입니다.**

### 2.2 인과 관계 체인 (Causal Chain)

```
[Root Cause] payment-db CPU 95% / Memory 87% — 노드(worker-03) 리소스 독점
    │
    ▼
[1단계] DB 쿼리 응답 지연 (p99: 30s timeout) — 에러율 67%
    │
    ▼
[2단계] JDBC 커넥션 미반환 → HikariPool 고갈 (50/50, 대기 127건)
    │
    ├──▶ [증폭①] Istio VirtualService retry 3× (retryOn: 5xx)
    │     → 실패 요청이 3배로 재시도 → DB 부하 142rps → 최대 426rps
    │
    ├──▶ [증폭②] payment-api Pod 1대 OOMKill (heap 512MB 부족)
    │     → 처리 용량 3대 → 2대 (33% 상실), 잔존 Pod CPU 78~82%
    │
    ├──▶ [증폭③] 서킷 브레이커 flapping (baseEjectionTime: 30s)
    │     → 30초마다 OPEN↔HALF_OPEN 반복 → 불안정한 트래픽 패턴
    │
    ▼
[결과] payment-api 5xx 40% / p99 15.2초
    │
    ▼
[전파] order-api 24.4% 에러 / checkout-web 35% 에러
```

### 2.3 4개 분석팀 교차 검증 결과

| 분석팀 | 핵심 발견 | 근본 원인 지목 | 일치 여부 |
|--------|-----------|----------------|-----------|
| **log-analysis** | HikariPool `active=50, waiting=127, max=50` — 커넥션 풀 완전 고갈 | payment-db 성능 저하 → 커넥션 미반환 | ✅ |
| **metrics-analysis** | DB Pool 09:10에 56% → 09:15에 100% 포화. 에러율·레이턴시 급등 시점 일치 | DB 커넥션 풀 고갈이 직접 원인 | ✅ |
| **infra-analysis** | payment-db-0: CPU 95%, Mem 87%. worker-03 노드 포화. Pod 1대 OOMKill | payment-db 리소스 포화가 기점 | ✅ |
| **mesh-analysis** | retry 3× + retryOn:5xx → 트래픽 3배 증폭. 서킷 브레이커 flapping | DB 과부하 + 재시도 증폭 | ✅ |

**4개 팀 모두 `payment-db 리소스 포화`를 공통 기점으로 지목.** 분석 간 시각·수치·인과관계에 모순 없음. 근본 원인으로 **확정**.

### 2.4 기여도 순위

| 순위 | 원인 | 유형 | 기여도 |
|------|------|------|--------|
| 1 | **payment-db 리소스 포화** (CPU 95%, Mem 87%) | 근본 원인 (Trigger) | **60%** |
| 2 | **Istio 재시도 3회** (retryOn: 5xx) → 트래픽 3배 증폭 | 설정 결함 (Amplifier) | **20%** |
| 3 | **메모리 리밋 512MB** → OOMKill → 용량 33% 상실 | 리소스 설정 미흡 | **10%** |
| 4 | **서킷 브레이커 flapping** (30s ejection, 100% max) | 메시 설정 결함 | **10%** |

---

## 3. 영향 범위 (Impact Assessment)

### 3.1 영향받은 서비스

| 서비스 | 에러율 | P99 지연 | 영향 수준 | 설명 |
|--------|--------|----------|-----------|------|
| **payment-api** | **40.0%** (3,452/8,631) | **15.2초** | 🔴 Critical | 결제 처리 직접 장애 |
| **payment-db** | 67% (쿼리 실패) | 30초 (timeout) | 🔴 Critical | 근본 원인 서비스 |
| **order-api** | **24.4%** (512/2,100) | 미측정 | 🔴 High | 결제 호출 실패 전파 |
| **checkout-web** | **35%** | 미측정 | 🟠 High | 프론트엔드 사용자 직접 노출 |
| notification-api | 0% | 0.1초 | 🟢 정상 | 영향 없음 |

### 3.2 사용자 영향

| 영향 항목 | 수치 | 설명 |
|-----------|------|------|
| **결제 실패율** | ~40% | 10건 중 4건 결제 불가 |
| **분당 실패 건수** | ~57건/분 | 142 rps × 40% = 약 57건 |
| **사용자 체감** | 15초+ 대기 후 에러 | 결제 버튼 클릭 후 장시간 로딩 → 실패 |
| **주문 실패율** | ~24% | order-api 연쇄 영향 |
| **프론트엔드 에러** | ~35% | checkout-web에서 에러 페이지 노출 |

### 3.3 장애 지속 시간

| 구간 | 시각 (UTC) | 경과 |
|------|-----------|------|
| 잠복 시작 | 09:10 | T+0 |
| 전면 장애 | 09:15 | T+5분 |
| 현재 (보고서 작성 시점) | 진행 중 | **T+10분 이상** |
| 예상 복구 (즉시 조치 후) | 즉시 조치 시행 후 5~10분 | — |

---

## 4. 장애 타임라인 (Timeline)

```
시각(UTC)     이벤트                                              출처
─────────────────────────────────────────────────────────────────────────
09:00         정상 운영. P99=0.28s, 에러율=0.1%, DB Pool=12/50     metrics
              ↓
09:10         [잠복기 시작] DB 쿼리 지연 감지. DB Pool 28/50 (56%)   metrics
              payment-db CPU 상승 시작                              infra
              ↓
09:12         DB Pool 41/50 (82%), P99=0.52s                       metrics
              ↓
09:14         DB Pool 49/50 (98%), P99=2.1s, 에러율 5.8%            metrics
              대기 큐 3건 발생                                       metrics
              ↓
09:15:28      ██ 전면 장애 ██                                      
              HikariPool 50/50 포화, 대기 127건                      ELK
              DB Pool 완전 고갈                                     metrics
              에러율 42.3%로 수직 상승                                metrics
              ↓
09:15:29      커넥션 획득 타임아웃 (30초) → 500 에러 대량 발생          ELK
              ↓
09:15:34      Alert: PaymentDBCircuitBreakerOpen (Critical)          metrics
09:15:35      서킷 브레이커 OPEN → 503 응답 전환                      ELK/mesh
              ↓
09:15:45      Alert: PaymentAPIHighErrorRate (Critical)              metrics
09:15:50      Alert: PaymentAPIHighLatency (Warning)                 metrics
              ↓
09:16:01      order-api에서 payment-api 503 수신 시작                 ELK
              ↓
09:16:30      payment-api Pod 1대 OOMKill (heap 511/512MB)           infra
              PaymentProcessor.retryPending() 메모리 누적             infra
              ↓
09:16         P99 최고점 15.2s, 에러율 최고점 67.1%, 대기 큐 203건     metrics
              ↓
09:17:01      HALF_OPEN 복구 시도 → 5초 타임아웃 → 다시 OPEN          ELK
              ↓
09:17~20      Pod CrashLoopBackOff 47회 반복                         infra
              잔존 2대 Pod CPU 78~82% — 과부하 지속                   infra
              서킷 브레이커 flapping 지속 (30초 주기)                  mesh
              ↓
현재          장애 진행 중. 에러율 ~40% 유지                           all
```

---

## 5. 즉시 조치 (Immediate Actions)

> ⚡ 아래 조치를 **우선순위 순서대로 즉시 실행**하십시오.

| 순위 | 조치 | 담당 | 예상 효과 | 소요 시간 |
|------|------|------|-----------|-----------|
| **1** | **Istio VirtualService retry 비활성화** | mesh팀 | DB 향 트래픽 3배 → 1배로 즉시 감소. 가장 빠른 부하 경감 | 1분 |
|  | `payment-api-vs`의 `retries.attempts: 0` 또는 `retryOn`에서 `5xx` 제거 | | | |
| **2** | **payment-db Pod 리소스 증설** | infra팀 | CPU/Memory 여유 확보 → 쿼리 정상화 | 2~3분 |
|  | CPU request/limit 상향 + worker-03 노드에 리소스 여유 확인, 필요 시 노드 추가 | | | |
| **3** | **payment-api HPA 또는 수동 스케일아웃** | infra팀 | Pod 2대 → 4~5대로 처리 용량 회복 | 2~3분 |
|  | `kubectl scale deployment payment-api --replicas=5 -n production` | | | |
| **4** | **payment-api 메모리 리밋 상향** | infra팀 | OOMKill 중단 → CrashLoopBackOff 해소 | 3분 |
|  | `resources.limits.memory: 512Mi → 1536Mi` (Java 앱 최소 권장) | | | |
| **5** | **서킷 브레이커 설정 조정** | mesh팀 | flapping 중단, 안정적 복구 전환 | 1분 |
|  | `baseEjectionTime: 30s → 300s`, `maxEjectionPercent: 100% → 50%` | | | |
| **6** | **VirtualService timeout 단축** | mesh팀 | 대기 요청 빠른 해소, P99 개선 | 1분 |
|  | `timeout: 30s → 5s`, `perTryTimeout: 10s → 3s` | | | |

**예상 복구 시나리오**: 조치 1~2 수행 후 2~3분 내 DB 부하 감소 → 커넥션 풀 정상화 → 서킷 브레이커 자동 CLOSE → 에러율 정상 복귀. 전체 복구까지 약 5~10분 예상.

---

## 6. 재발 방지 (Prevention Plan)

### 6.1 단기 개선 (Short-term: 1~2주)

| # | 개선 사항 | 담당 | 근거 |
|---|-----------|------|------|
| S1 | **HikariPool `max` 50 → 100으로 상향** 및 `connectionTimeout` 30s → 5s로 단축 | Backend팀 | 풀 고갈 임계점 상향 + 빠른 실패(fail-fast) 유도 |
| S2 | **Istio retry 정책 전면 검토** — `retryOn`에서 `5xx` 제거, 멱등성 있는 요청만 재시도 | Platform팀 | 장애 시 트래픽 증폭 방지 |
| S3 | **payment-api 메모리 리밋 1.5Gi 이상으로 고정 배포** | infra팀 | OOMKill 재발 방지 |
| S4 | **DB 커넥션 풀 포화 알림 추가** — active/max > 80% 시 Warning, > 95% 시 Critical | SRE팀 | 잠복기(09:10~09:15)에 선제 탐지 가능 |
| S5 | **payment-db 슬로우 쿼리 분석 및 인덱스 최적화** | DBA팀 | 근본 원인인 DB 과부하의 원인 규명 |

### 6.2 장기 개선 (Long-term: 1~3개월)

| # | 개선 사항 | 담당 | 근거 |
|---|-----------|------|------|
| L1 | **payment-db Read Replica 도입** — 읽기 트래픽 분산 | DBA/Infra팀 | 단일 DB 인스턴스 SPOF 해소 |
| L2 | **payment-api 비동기 처리 아키텍처 도입** — 결제 요청을 메시지 큐(Kafka/RabbitMQ)로 버퍼링 | Architecture팀 | DB 직접 부하 감소, 트래픽 스파이크 흡수 |
| L3 | **Graceful Degradation 패턴 구현** — 결제 실패 시 "잠시 후 재시도" 안내 + 자동 재시도 큐 | Backend팀 | 사용자 경험 개선, 무한 재시도 방지 |
| L4 | **DB 오토스케일링 또는 PgBouncer 커넥션 풀러 도입** | DBA/Infra팀 | 커넥션 관리 효율화, 풀 고갈 근본 방지 |
| L5 | **Chaos Engineering 도입** — 정기적 DB 장애 시뮬레이션 | SRE팀 | 서킷 브레이커/retry/timeout 설정값 사전 검증 |
| L6 | **payment-db 전용 노드 풀(Node Pool) 분리** | Infra팀 | worker-03 리소스 경합 제거, DB 워크로드 격리 |

---

## 7. 심각도 판정 (Severity Classification)

### 판정: **P1 — Critical**

| 판정 기준 | 평가 | 충족 여부 |
|-----------|------|-----------|
| **사용자 영향 범위** | 결제·주문·체크아웃 3개 핵심 서비스 동시 장애 | ✅ 전사 핵심 기능 |
| **에러율** | payment-api 40%, order-api 24%, checkout-web 35% | ✅ 다수 사용자 직접 영향 |
| **매출 영향** | 결제 40% 실패 → 분당 ~57건 매출 유실 | ✅ 직접적 매출 손실 |
| **자동 복구 가능성** | 서킷 브레이커 flapping으로 자동 복구 불가 | ✅ 수동 개입 필수 |
| **연쇄 장애** | 3개 이상 서비스에 전파 | ✅ Cascading failure |

**P1 근거 요약**: 핵심 비즈니스 기능(결제)이 40% 실패하며, 다수 사용자에게 직접 영향을 미치고, 자동 복구가 불가능한 상태입니다. 분당 약 57건의 결제가 유실되어 **직접적인 매출 손실**이 발생 중이며, 수동 개입 없이는 장애가 지속됩니다.

---

## 8. 교훈 (Lessons Learned)

| # | 교훈 | 카테고리 |
|---|------|----------|
| 1 | **Istio 재시도 정책이 장애를 증폭시킬 수 있다.** 5xx 에러에 대한 무조건적 재시도는 과부하 상황에서 트래픽을 N배로 증가시켜 장애를 악화시킨다. | 설정 관리 |
| 2 | **Java 앱의 컨테이너 메모리 리밋 512MB는 프로덕션에 부적절하다.** 특히 retry 큐가 메모리에 누적되는 구조에서는 OOMKill이 필연적이다. | 리소스 관리 |
| 3 | **DB 커넥션 풀 모니터링이 핵심 선행 지표다.** 에러율이 급등하기 5분 전(09:10)에 이미 풀 사용률이 56%로 비정상 상승했으나, 이를 탐지할 알림이 없었다. | 모니터링 |
| 4 | **단일 DB 인스턴스는 SPOF다.** Read Replica 없이 모든 트래픽이 단일 Pod에 집중되어, 리소스 포화 시 전체 결제 기능이 마비된다. | 아키텍처 |
| 5 | **서킷 브레이커의 ejection 설정이 실제 토폴로지와 맞아야 한다.** 단일 호스트 환경에서 `maxEjectionPercent: 100%`는 전면 차단과 동일하다. | 설정 관리 |

---

## 부록: 분석팀별 보고서 참조

| 분석팀 | 주요 도구 | 핵심 발견 |
|--------|-----------|-----------|
| **log-analysis** (ELK) | search_logs, get_error_summary, get_log_sample | HikariPool 고갈 로그, 에러 인과 체인 확인 |
| **metrics-analysis** (Grafana) | query_metrics, get_dashboard_summary, get_active_alerts | P99/에러율/커넥션 풀 시계열 추이, 알림 타임라인 |
| **infra-analysis** (K8s) | list_pods, describe_resource, get_pod_logs, get_node_status | OOMKill Pod, DB Pod 리소스 포화, 노드 상태 |
| **mesh-analysis** (Istio) | get_circuit_breaker_status, get_virtual_services, get_destination_rules, get_service_metrics | 재시도 증폭, 서킷 브레이커 flapping, 트래픽 흐름 |

---

*이 보고서는 장애 진행 중에 작성되었으며, 복구 완료 후 최종 업데이트될 예정입니다.*
*모든 시각은 UTC 기준입니다.*
