# Incident Report: INC-2026-0407-001

| 항목 | 내용 |
|------|------|
| **Incident ID** | INC-2026-0407-001 |
| **심각도** | **P1 — Critical** |
| **상태** | 🔴 Active (원인 분석 완료, 조치 진행 중) |
| **발생 시각** | 2026-04-07 09:10 UTC (최초 이상 감지) |
| **선언 시각** | 2026-04-07 09:15 UTC (알림 발동) |
| **Incident Commander** | 운영팀장 |
| **분석 참여** | Log Analysis, Metrics Analysis, Infra Analysis, Mesh Analysis |

---

## Executive Summary

payment-api의 백엔드 데이터베이스(payment-db)에서 응답 지연이 발생하여 DB 커넥션 풀이 고갈되었고, 이로 인해 payment-api의 500 에러율이 40%까지 급증하고 p99 응답시간이 15.2초에 도달했습니다. 서비스 메시의 과도한 재시도 정책(3회)이 장애를 3배로 증폭시켰으며, 1개 Pod의 OOM Kill로 인한 용량 감소가 상황을 악화시켰습니다. 장애는 order-api로 전파되어 주문 처리 전체에 영향을 미치고 있습니다.

**비즈니스 영향**: 결제 성공률 58%로 하락, 주문 완료율 동반 하락. 분당 약 60건의 결제가 실패하고 있으며, 이는 직접적인 매출 손실로 이어지고 있습니다.

---

## 1. 장애 타임라인

```
09:10:00  [최초 이상] payment-db 커넥션 풀 사용량 비정상 증가 시작 (12→28/50)
          payment-api p99 응답시간 미세 증가 (0.28s → 0.35s)
          ▸ 추정: payment-db에서 slow query 또는 성능 저하 시작

09:12:00  [성능 저하] DB 커넥션 풀 82% 사용 (41/50)
          payment-api p99 0.52s (baseline 대비 1.7배)
          ▸ 커넥션 반환 지연으로 풀 포화 진행 중

09:14:00  [임계점 돌파] DB 커넥션 풀 98% (49/50)
          payment-api p99 2.1s, 에러율 5.8% — Cascading Failure 시작
          ▸ Istio 재시도 정책(3회)이 실패 트래픽을 3배로 증폭

09:15:12  ★ [알림] DBConnectionPoolExhausted — 커넥션 풀 100% (50/50), 대기 127건
09:15:28  ★ [CB 트립] payment-db 방향 Circuit Breaker OPEN (연속 에러 50회)
          payment-api에서 503 Service Unavailable 반환 시작
09:15:29  HikariPool-1 커넥션 타임아웃 30,000ms 발생
09:15:30  ★ [알림] PaymentAPIHighErrorRate — 에러율 40% 돌파 (임계값 20%)
          payment-api-7b9f4-j8np Pod OOMKilled (Heap 511/512MB)
09:15:45  ★ [알림] PaymentAPIHighLatency — p99 15.2s (임계값 5s)

09:16:00  ★ [알림] PodCrashLooping — j8np Pod CrashLoopBackOff (47회 재시작)
          에러율 최고점 67.1% 도달, DB 대기큐 203건
          order-api로 장애 전파 본격화 (order-api 에러율 24.4%→40%)

09:17:00  [부분 안정] CB 효과 + 트래픽 감소로 에러율 58.9%로 소폭 하락
          잔여 2개 Pod이 전체 트래픽 감당 (CPU 78-82%)

09:20:00  [현재] payment-api 성공률 58.2%, p99 11.9s
          order-api 에러율 40%, p99 15.2s
          Pod 2/3 Running (과부하), 1/3 CrashLoopBackOff
```

---

## 2. 영향 범위

### 직접 영향 (Primary Impact)

| 서비스 | 증상 | 현재 상태 | 비즈니스 영향 |
|--------|------|-----------|---------------|
| **payment-api** | 500/503/504 에러 40%, p99 15.2s | 성공률 58.2% | **결제 실패 — 분당 ~60건 매출 손실** |
| **order-api** | 502/503 에러 24.4→40% | 요청률 -38% | **주문 완료 불가 — 고객 이탈** |

### 간접 영향 (Secondary Impact)

| 영역 | 영향 |
|------|------|
| **checkout-web** | payment-api 호출 35% 실패 → 결제 페이지 에러 표시 |
| **고객 경험** | 결제 실패, 주문 지연, 타임아웃 — CS 문의 급증 예상 |
| **인프라** | worker-01 노드 과부하(CPU 77%), worker-03 포화(CPU 95%) |

### 영향받지 않은 서비스

| 서비스 | 상태 |
|--------|------|
| notification-api | 정상 (에러율 0%, p99 0.1s) |
| order-api Pod 자체 | 인프라 레벨 정상 (CPU 34%, Memory 45%) |

---

## 3. 근본 원인 분석 (Root Cause Analysis)

### 3.1 인과 관계 체인 (Causal Chain)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      ROOT CAUSE (추정)                               │
│         payment-db 응답 지연 (slow query / DB 성능 저하)              │
│         ▸ 에러율 67%, p99 30s timeout                                │
│         ▸ 원인 상세 조사 필요 (DB팀 에스컬레이션)                      │
└──────────────────────────┬──────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AMPLIFIER #1: Istio 재시도 폭풍 (Retry Storm)                       │
│  ▸ VirtualService retries=3, retryOn=5xx                            │
│  ▸ 실패 요청이 3배로 증폭 → 이미 과부하인 DB를 더 압박                  │
│  ▸ perTryTimeout=10s × 3회 = 최대 30초간 커넥션 점유                  │
└──────────────────────────┬──────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AMPLIFIER #2: DB 커넥션 풀 고갈                                     │
│  ▸ HikariCP max=50, 30초 타임아웃으로 커넥션 장기 점유                 │
│  ▸ active=50, waiting=127→203, overflow=2,847                       │
│  ▸ Circuit Breaker OPEN (09:15:28) → 503 즉시 반환                   │
└──────────────────────────┬──────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AMPLIFIER #3: Pod OOM Kill + 용량 감소                              │
│  ▸ j8np Pod: PaymentProcessor.retryPending()에서 Heap 512MB 소진     │
│  ▸ OOMKilled → CrashLoopBackOff (47회 재시작)                        │
│  ▸ 3→2 Pod로 용량 33% 감소 → 잔여 Pod CPU 78-82% 과부하              │
│  ▸ xk2m Pod Readiness probe 503 실패 89회 → 라우팅 불안정             │
└──────────────────────────┬──────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  CASCADE: order-api 장애 전파                                        │
│  ▸ payment-api 성공률 58.2% → order-api 43% 에러율                   │
│  ▸ order-api에 DestinationRule/CB 미설정 → 무방비 전파                │
│  ▸ 주문 흐름 전체 장애                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 근본 원인 판정

| 구분 | 내용 |
|------|------|
| **Trigger (방아쇠)** | payment-db의 응답 지연/성능 저하 (원인 상세 조사 필요) |
| **Direct Cause (직접 원인)** | DB 커넥션 풀 고갈 (HikariCP max=50, 대기 127건) |
| **Amplifiers (증폭 요인)** | ① Istio 재시도 3회 → 트래픽 3배 증폭 ② 30초 타임아웃 → 커넥션 장기 점유 ③ Pod OOMKill → 용량 33% 감소 |
| **Propagation (전파 원인)** | order-api에 Circuit Breaker / DestinationRule 미설정 |

### 3.3 "왜 평소에는 문제없었나?"

- 정상 시 DB 응답시간 ~10ms → 커넥션 빠른 반환 → 50개 풀로 충분
- DB 지연 발생 시 커넥션 반환이 느려지면서 풀이 급속 포화
- 재시도 정책이 평소에는 transient error 복구에 도움이 되지만, 지속적 장애 시 역효과 (재시도 폭풍)

---

## 4. 조치 사항

### 4.1 즉시 조치 (Immediate — 지금 당장)

| # | 조치 | 담당 | 상태 | 기대 효과 |
|---|------|------|------|-----------|
| I-1 | **payment-api VirtualService 재시도 비활성화** (`retries.attempts: 0`) | Mesh팀 | 🔴 미착수 | 재시도 폭풍 즉시 차단, DB 부하 66% 감소 |
| I-2 | **payment-api VirtualService 타임아웃 단축** (30s → 3s) | Mesh팀 | 🔴 미착수 | Fail-fast로 커넥션 점유 시간 10배 단축 |
| I-3 | **payment-api Pod Memory Limit 증설** (512MB → 1024MB) + 재배포 | Infra팀 | 🔴 미착수 | OOMKill 해소, 용량 3/3 복원 |
| I-4 | **payment-db 상태 긴급 확인** (slow query log, active sessions, disk I/O) | DB팀 | 🔴 에스컬레이션 필요 | 근본 원인 트리거 해소 |
| I-5 | **HikariCP 커넥션 타임아웃 단축** (30s → 5s) | 개발팀 | 🔴 미착수 | 빠른 실패로 대기큐 축소 |

### 4.2 단기 개선 (Short-term — 1~2주 내)

| # | 조치 | 담당 | 기대 효과 |
|---|------|------|-----------|
| S-1 | **order-api에 DestinationRule + Circuit Breaker 추가** | Mesh팀 | 장애 전파 차단 |
| S-2 | **payment-api HPA 스케일아웃** (replica 3→5) + 클러스터 노드 추가 | Infra팀 | 용량 여유 확보 |
| S-3 | **Pod Anti-Affinity 설정** (worker-01 편중 해소) | Infra팀 | SPOF 제거 |
| S-4 | **payment-api 재시도 정책 재설계** (exponential backoff + jitter, retry budget) | Mesh팀+개발팀 | 재시도 폭풍 방지 |
| S-5 | **`PaymentProcessor.retryPending()` 메모리 누수 점검** | 개발팀 | OOM 근본 원인 해소 |
| S-6 | **DB 커넥션 풀 사이징 재검토** (HikariCP max 50→적정값 산출) | 개발팀+DB팀 | 풀 고갈 임계점 상향 |

### 4.3 장기 개선 (Long-term — 1~3개월)

| # | 조치 | 담당 | 기대 효과 |
|---|------|------|-----------|
| L-1 | **전체 서비스에 Circuit Breaker / Bulkhead 패턴 표준화** | Platform팀 | Cascade failure 방지 |
| L-2 | **Graceful Degradation 전략 수립** (결제 실패 시 주문 보류 큐) | 아키텍처팀 | 부분 장애 시 고객 경험 보호 |
| L-3 | **DB 커넥션 풀 모니터링 대시보드 + 사전 알림** (80% 임계 경고) | SRE팀 | 조기 감지 |
| L-4 | **Chaos Engineering 도입** (DB 지연 주입 테스트) | SRE팀 | 복원력 사전 검증 |
| L-5 | **서비스 메시 타임아웃/재시도 정책 거버넌스** (팀별 리뷰 프로세스) | Platform팀 | 설정 오류 방지 |
| L-6 | **worker-03 노드 용량 계획** (CPU 95% 포화 해소) | Infra팀 | 클러스터 안정성 |

---

## 5. 메트릭 증거 요약

### 알림 발동 순서 (인과관계 확인)

| 순서 | 시각 | 알림 | 의미 |
|------|------|------|------|
| 1st | 09:15:12 | DBConnectionPoolExhausted | **선행 원인** — DB 풀 고갈이 먼저 |
| 2nd | 09:15:28 | Circuit Breaker OPEN | DB 방향 CB 트립 |
| 3rd | 09:15:30 | PaymentAPIHighErrorRate | **후행 결과** — 에러율 급증 |
| 4th | 09:15:45 | PaymentAPIHighLatency | 응답시간 임계 초과 |
| 5th | 09:16:00 | PodCrashLooping | OOM에 의한 Pod 반복 재시작 |

### 핵심 수치

| 메트릭 | 정상값 | 장애 시 최고값 | 이탈 배수 |
|--------|--------|---------------|-----------|
| payment-api 5xx 에러율 | 0.1% | 67.1% | **671x** |
| payment-api p99 응답시간 | 0.28s | 15.2s | **54x** |
| DB 커넥션 풀 사용률 | 24% (12/50) | 100% (50/50) + 대기 203 | **포화** |
| Istio 오버플로 카운트 | 0 | 2,847 | **∞** |
| Pod 가용률 | 3/3 (100%) | 2/3 (66%) | **-33%** |
| order-api 에러율 | 0.1% | 40% | **400x** |

---

## 6. 교훈 (Lessons Learned)

### 잘된 점 (What Went Well)
- Circuit Breaker가 09:15:28에 정상 작동하여 payment-db에 대한 추가 부하를 차단함
- 알림 체계가 장애 발생 후 약 30초 내에 4건의 알림을 발동하여 빠른 감지 가능
- 4개 분석팀 병렬 투입으로 10분 내 근본 원인 분석 완료

### 개선 필요 (What Needs Improvement)
- **재시도 폭풍 방지 미비**: 재시도 정책이 장애 시 역효과를 발생시키는 구조적 문제
- **order-api 방어체계 부재**: Circuit Breaker / DestinationRule 미설정으로 무방비 전파
- **OOM 사전 감지 부재**: Heap 사용률 모니터링 및 알림이 없었음
- **커넥션 풀 사전 경고 부재**: 80% 도달 시 경고 알림이 있었으면 5분 일찍 대응 가능
- **Pod Anti-Affinity 미설정**: payment-api Pod 2개가 같은 노드에 편중

---

## 7. 후속 조치 추적

| Action Item | 담당 | 기한 | JIRA |
|-------------|------|------|------|
| payment-db 근본 원인 확인 (slow query / lock) | DB팀 | 즉시 | TBD |
| VirtualService 재시도/타임아웃 수정 | Mesh팀 | 즉시 | TBD |
| Pod Memory Limit 증설 + 재배포 | Infra팀 | 즉시 | TBD |
| order-api DestinationRule 추가 | Mesh팀 | 1주 내 | TBD |
| retryPending() 메모리 누수 점검 | 개발팀 | 1주 내 | TBD |
| 전사 서비스 CB 표준화 | Platform팀 | 1개월 내 | TBD |
| Chaos Engineering 파일럿 | SRE팀 | 2개월 내 | TBD |

---

## 부록: 분석 팀별 상세 보고

<details>
<summary>A. Log Analysis 팀 보고 (클릭하여 펼치기)</summary>

### 에러 분포

**payment-api** (총 3,452 에러 / 8,631 요청, 에러율 40.0%):
- 503 Service Unavailable: 1,893건 (54.8%) — Circuit Breaker OPEN
- 500 Internal Server Error: 1,247건 (36.1%) — DB 커넥션 획득 실패
- 504 Gateway Timeout: 312건 (9.0%) — 30초 타임아웃

**order-api** (총 512 에러 / 2,100 요청, 에러율 24.4%):
- 503 Service Unavailable: 423건 (82.6%) — payment-api CB OPEN 전파
- 502 Bad Gateway: 89건 (17.4%) — 커넥션 리셋

### 핵심 로그 체인
```
09:15:28 Connection pool exhausted: active=50, waiting=127, max=50
09:15:29 HikariPool-1 - Connection timed out after 30000ms
09:15:30 POST /api/v1/payments/process failed: Unable to acquire JDBC Connection
09:15:31 TransactionManager: rollback on timeout, txId=PAY-20260407-091531-4829
09:15:35 Circuit breaker is OPEN for payment-db → 503
```

</details>

<details>
<summary>B. Metrics Analysis 팀 보고 (클릭하여 펼치기)</summary>

### 에러율 추이 (payment-api)
| 시각 | 에러율 | p99 응답시간 | DB 풀 사용률 |
|------|--------|-------------|-------------|
| 09:00 | 0.1% | 0.28s | 24% |
| 09:10 | 0.3% | 0.35s | 56% |
| 09:12 | - | 0.52s | 82% |
| 09:14 | 5.8% | 2.1s | 98% |
| 09:15 | 42.3% | 8.7s | 100% |
| 09:16 | 67.1% | 15.2s | 100%+203대기 |
| 09:20 | ~40% | 11.9s | 100% |

</details>

<details>
<summary>C. Infra Analysis 팀 보고 (클릭하여 펼치기)</summary>

### Pod 상태
| Pod | 상태 | CPU | Memory | 재시작 |
|-----|------|-----|--------|--------|
| payment-api-7b9f4-xk2m | Running | 78% | 62% | 12회 |
| payment-api-7b9f4-j8np | CrashLoopBackOff | - | - | 47회 (OOMKilled) |
| payment-api-7b9f4-m3qr | Running | 82% | 71% | 8회 |
| order-api-5c8d2-k4wn | Running | 34% | 45% | 0회 |

### 노드 상태
| 노드 | CPU | Memory | 위험도 |
|------|-----|--------|--------|
| worker-01 | 77% | 75% | 높음 (payment-api 편중) |
| worker-02 | 64% | 66% | 보통 |
| worker-03 | 95% | 86% | 위험 (포화) |

</details>

<details>
<summary>D. Mesh Analysis 팀 보고 (클릭하여 펼치기)</summary>

### Circuit Breaker 상태
- payment-api → payment-db: **OPEN** (09:15:28 트립, 연속 에러 50회)
- order-api: **CB 미설정** (무방비)

### 장애 증폭 요인
1. **재시도 폭풍**: retries=3 × perTryTimeout=10s = 최대 30초, 트래픽 3배 증폭
2. **과도한 타임아웃**: 30초 → 커넥션 장기 점유
3. **커넥션 풀 오버플로**: 2,847건 overflow

### 트래픽 흐름
- order-api → payment-api: 89 rps, 에러율 43%
- checkout-web → payment-api: 53 rps, 에러율 35%
- payment-api → payment-db: 142 rps, 에러율 67%, p99 30s

</details>

---

*Report generated: 2026-04-07 | Incident Commander: 운영팀장*
*Analysis teams: Log Analysis, Metrics Analysis, Infrastructure Analysis, Service Mesh Analysis*
