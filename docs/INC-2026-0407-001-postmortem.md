# Incident Post-Mortem Report

> **Incident ID**: INC-2026-0407-001
> **심각도**: **P1 — Critical** (핵심 결제 서비스 장애, 매출 직접 영향)
> **상태**: Active — 복구 진행 중
> **작성일**: 2026-04-07
> **작성자**: Incident Commander (SRE/DevOps)

---

## Executive Summary

2026년 4월 7일 09:10경, **payment-db가 호스팅된 Kubernetes 노드(worker-03)의 리소스 포화**(CPU 95%, Memory 86%)로 인해 DB 쿼리 처리가 급격히 지연되었습니다. 이로 인해 payment-api의 DB 커넥션 풀(HikariPool, max=50)이 5분 만에 완전 고갈되었고, **에러율이 0.1%에서 40%로 400배 급증**, **p99 응답시간이 0.3초에서 15.2초로 50배 악화**되었습니다.

Istio 서비스 메시의 과도한 재시도 정책(3회 재시도)이 트래픽을 최대 3배로 증폭시켜 장애를 가속화했으며, payment-api Pod 1대가 OOMKilled(47회 재시작)되어 처리 용량이 33% 감소했습니다. 이 장애는 order-api로 전파되어 주문 처리의 24.4%가 실패했습니다.

**추정 비즈니스 영향**: 장애 지속 시간 동안 결제 시도의 약 40%가 실패하여, 시간당 수억 원 규모의 매출 손실이 발생한 것으로 추정됩니다.

---

## 1. 장애 개요

| 항목 | 내용 |
|------|------|
| **발생 시각** | 2026-04-07 09:10 KST (첫 이상 징후) / 09:15:28 KST (장애 임계점) |
| **감지 시각** | 2026-04-07 09:15:12 KST (DBConnectionPoolExhausted 알림) |
| **영향 서비스** | payment-api (직접), order-api (전파), checkout-web (전파) |
| **증상** | 500/503 에러 40% 급증, p99 응답시간 15.2초, Pod CrashLoopBackOff |
| **심각도** | **P1 — Critical** |
| **현재 상태** | 🔴 Active — 서킷 브레이커 OPEN, DB 풀 포화 지속 |

---

## 2. 통합 타임라인

4개 분석팀(Log, Metrics, Infra, Mesh)의 결과를 시간순으로 교차 검증하여 통합하였습니다.

### Phase 1: 전조 단계 (09:00 ~ 09:10)

| 시각 | 이벤트 | 출처 |
|------|--------|------|
| 09:00 | 정상 운영: DB Pool 12/50, p99 0.28s, 에러율 0.1% | Metrics |
| 09:05 | DB Pool 15/50으로 미세 증가, 정상 범위 | Metrics |
| **09:10** | **DB Pool 28/50 급증 (첫 이상 징후)**, worker-03 CPU 상승 시작 | Metrics, Infra |

> **교훈**: 09:10의 DB 풀 급증이 최초 이상 신호였으나, 이 시점에는 알림이 발생하지 않았습니다. 풀 사용률 60% 이상에 대한 사전 경고(early warning) 알림이 없었습니다.

### Phase 2: 급속 악화 (09:10 ~ 09:15)

| 시각 | 이벤트 | 출처 |
|------|--------|------|
| 09:12 | DB Pool 41/50 (82%), p99 0.52s 상승 시작 | Metrics |
| 09:14 | DB Pool 49/50 (98%), p99 2.1s, 에러율 5.8% 돌파 | Metrics |
| **09:15:00** | **DB Pool 50/50 완전 포화**, 대기열 127건 적체 시작 | Metrics, Log |
| 09:15:12 | 🚨 **첫 번째 알림**: DBConnectionPoolExhausted (Warning) | Metrics |

> 09:10 ~ 09:15, 단 5분 만에 DB 풀이 12/50에서 50/50으로 포화되었습니다. worker-03 노드(payment-db 호스팅)의 CPU가 95%에 도달하면서 DB 쿼리 처리 지연 → 커넥션 반환 지연 → 풀 고갈의 악순환이 발생했습니다.

### Phase 3: 연쇄 장애 (09:15 ~ 09:17)

| 시각 | 이벤트 | 출처 |
|------|--------|------|
| 09:15:28 | payment-api: `Connection pool exhausted: active=50, waiting=127` | Log |
| 09:15:28 | **Istio 서킷 브레이커 OPEN** (payment-api → payment-db), 50회 연속 에러 | Mesh |
| 09:15:29 | HikariPool 타임아웃 30s 도달, SQLTransientConnectionException | Log |
| 09:15:30 | HTTP 500 반환 시작 (DataAccessResourceFailureException) | Log |
| 09:15:30 | 🚨 **두 번째 알림**: PaymentAPIHighErrorRate >20% (Critical) | Metrics |
| 09:15:31 | 진행 중 트랜잭션 강제 롤백 시작 | Log |
| 09:15:34 | 서킷 브레이커 OPEN 확정 → 이후 요청 즉시 503 반환 | Log, Mesh |
| 09:15:45 | 🚨 **세 번째 알림**: PaymentAPIHighLatency p99 >5s (Critical) | Metrics |
| 09:16:00 | 🚨 **네 번째 알림**: PodCrashLoopBackOff (47회 재시작) | Metrics, Infra |
| 09:16:01 | **order-api로 장애 전파** (payment-api 503 → order-api 전파) | Log |
| 09:16:30 | Pod `j8np` OOMKilled: 재시도 큐 메모리 누적 → 힙 511/512MB 폭발 | Infra |

### Phase 4: 지속적 장애 (09:17 ~ 현재)

| 시각 | 이벤트 | 출처 |
|------|--------|------|
| 09:17:01 | 서킷 브레이커 HALF_OPEN 시도 → 실패 → OPEN 유지 | Log |
| 09:16~09:20 | p99 피크 15.2s, 에러율 피크 67.1%, 대기열 피크 203건 | Metrics |
| 09:20 | DB 풀 여전히 50/50 포화, 자동 복구 없음 | Metrics |
| **현재** | **장애 지속 중** — DB 노드 리소스 포화 미해소 | 전체 |

---

## 3. 근본 원인 분석 (Root Cause Analysis)

### 확정된 근본 원인

> **payment-db를 호스팅하는 Kubernetes 노드(worker-03)의 리소스 포화(CPU 95%, Memory 86%)로 인한 DB 쿼리 처리 지연, 이에 따른 payment-api DB 커넥션 풀 고갈 및 Istio 재시도 폭풍에 의한 연쇄 장애**

### 4개 팀 교차 검증 결과

| # | 증거 | 확인 팀 | 판정 |
|---|------|---------|------|
| 1 | worker-03 CPU 95%, Memory 86% — DB 노드 리소스 포화 | **Infra** | ✅ 진원지 |
| 2 | payment-db → payment-api: 67% 에러율, p99 30초(타임아웃) | **Mesh** | ✅ DB 응답 불가 확인 |
| 3 | HikariPool active=50/50, waiting=127 — 커넥션 반환 안 됨 | **Log** | ✅ 풀 고갈 확인 |
| 4 | DB Pool Exhausted 알림이 최초(09:15:12), 다른 알림은 후속 | **Metrics** | ✅ 시간 순서상 DB가 최초 |
| 5 | payment-db 서킷 브레이커 OPEN(09:15:28), 50회 연속 에러 | **Mesh** | ✅ DB 장애 확정 |
| 6 | order-api는 자체 장애 없음, payment-api 503 전파만 수신 | **Log, Mesh** | ✅ 피해 서비스 |

### 장애 증폭 요인 (Contributing Factors)

| 요인 | 상세 | 영향도 |
|------|------|--------|
| **Istio 재시도 폭풍** | VirtualService 재시도 3회 설정 → 트래픽 최대 3배 증폭 (142→426 rps) | 🔴 높음 |
| **과도한 타임아웃** | payment-api 타임아웃 30초 → 느린 실패, 리소스 장기 점유 | 🔴 높음 |
| **Pod OOMKill** | 재시도 큐 메모리 누적 → 힙 512MB 초과 → 처리 용량 33% 감소 | 🟠 중간 |
| **DB 단일 호스트** | payment-db 인스턴스 1대, maxEjectionPercent 100% 추방 가능 | 🔴 높음 |
| **사전 경고 부재** | DB 풀 사용률 60%에 대한 early warning 알림 없음 | 🟠 중간 |

### 장애 전파 경로 (Failure Cascade)

```
[1단계: 진원지]
  worker-03 노드 리소스 포화 (CPU 95%, Mem 86%)
       ↓
  payment-db 쿼리 처리 지연 → 67% 에러율, p99 30초
       ↓
[2단계: 1차 피해]
  payment-api HikariPool 커넥션 50개 전량 점유 (반환 불가)
  + Istio 재시도 3회 → 트래픽 3배 증폭 → 악순환
       ↓
  에러율 40%, p99 15.2초, 서킷 브레이커 OPEN
       ↓
[3단계: 2차 피해]
  Pod j8np OOMKilled → 처리 용량 33% 감소
       ↓
[4단계: 전파]
  order-api, checkout-web → payment-api 호출 실패 (24~43% 에러율)
```

---

## 4. 영향 범위

### 서비스 영향

| 서비스 | 에러율 | p99 레이턴시 | 영향 요약 |
|--------|--------|-------------|-----------|
| **payment-api** | 40.0% (정상: 0.1%) | 15.2s (정상: 0.3s) | 결제 처리 직접 장애 |
| **order-api** | 24.4% (정상: <1%) | 간접 영향 | 주문→결제 호출 실패 전파 |
| **checkout-web** | 35% 에러율 | 간접 영향 | 웹 결제 페이지 실패 |
| **payment-db** | CPU 95%, Mem 87% | 30s (타임아웃) | 진원지, 리소스 포화 |

### 사용자 영향

| 항목 | 추정치 | 산출 근거 |
|------|--------|-----------|
| 실패한 결제 시도 | **~3,452건** (장애 시작 후 누적) | Log 분석 — 에러 로그 건수 |
| 영향받은 주문 | **~512건** | Log 분석 — order-api 에러 건수 |
| 영향받은 사용자 | **수천 명** (결제 시도 사용자) | 요청량 기반 추정 |
| 사용자 체감 | 결제 실패, 15초 이상 대기 후 에러 페이지 | p99 15.2초 |

### 매출 영향 추정

| 항목 | 추정 |
|------|------|
| 결제 실패율 | 40% (시간당 ~3,400건 실패 기준) |
| 장애 지속 시간 | 현재까지 약 10분+ (진행 중) |
| 추정 매출 손실 | **건당 평균 결제 금액 × 3,452건** (정확한 금액은 비즈니스팀 확인 필요) |
| 간접 손실 | 사용자 이탈, 신뢰도 하락, CS 인입 급증 예상 |

> ⚠️ **장애가 지속되는 매 분마다 손실이 누적되고 있습니다. 즉시 복구 조치가 최우선입니다.**

---

## 5. 즉시 조치 사항 (Immediate Actions)

> 🚨 아래 조치를 **즉시, 순서대로** 실행해야 합니다.

### Action 1: payment-db 노드 부하 경감 (최우선)

```bash
# 1-1. payment-db Pod을 여유 있는 노드로 긴급 이동 (worker-01 또는 worker-02)
kubectl cordon worker-03                    # 신규 스케줄링 차단
kubectl drain worker-03 --ignore-daemonsets --delete-emptydir-data  # Pod 이동

# 1-2. 또는 DB 리소스 제한 긴급 상향
kubectl patch statefulset payment-db -p '{"spec":{"template":{"spec":{"containers":[{"name":"payment-db","resources":{"requests":{"cpu":"8","memory":"32Gi"},"limits":{"cpu":"12","memory":"48Gi"}}}]}}}}'
```

**담당**: Infra팀 | **예상 소요**: 5~10분 | **효과**: DB 쿼리 처리 정상화 → 근본 원인 해소

### Action 2: CrashLoopBackOff Pod 복구

```bash
# 2-1. OOMKilled Pod 삭제 → 새로운 Pod 자동 생성
kubectl delete pod payment-api-7b9f4-j8np -n production

# 2-2. JVM 힙 메모리 긴급 상향 (512MB → 1024MB)
kubectl set env deployment/payment-api JAVA_OPTS="-Xmx1024m -Xms512m"
```

**담당**: Platform팀 | **예상 소요**: 2~3분 | **효과**: 처리 용량 33% 복구

### Action 3: Istio 재시도 비활성화 (트래픽 증폭 차단)

```bash
# 3-1. payment-api VirtualService 재시도 제거
kubectl patch virtualservice payment-api-vs --type='json' \
  -p='[{"op":"remove","path":"/spec/http/0/retries"}]'

# 3-2. 타임아웃 30초 → 5초로 단축 (빠른 실패 유도)
kubectl patch virtualservice payment-api-vs --type='json' \
  -p='[{"op":"replace","path":"/spec/http/0/timeout","value":"5s"}]'
```

**담당**: Mesh팀 | **예상 소요**: 1분 | **효과**: 트래픽 3배 증폭 즉시 해소

### Action 4: 서킷 브레이커 수동 리셋 (DB 정상화 확인 후)

```bash
# DB 정상화 확인 후 수행
kubectl delete pod -l app=payment-api -n production  # 전체 Pod 롤링 재시작
```

**담당**: SRE팀 | **예상 소요**: 3~5분 | **전제**: Action 1 완료 후

### Action 5: 모니터링 강화 (복구 확인)

- 실시간 대시보드 감시: payment-overview, order-overview
- 에러율 < 1%, p99 < 1초 달성 시 복구 선언
- 30분간 안정성 관찰 후 Incident 클로즈

---

## 6. 재발 방지 대책 (Prevention)

### 단기 개선 (Short-term) — 1~2주 내

| # | 개선 항목 | 상세 | 담당 | 우선순위 |
|---|----------|------|------|----------|
| S1 | **DB 풀 사전 경고 알림 추가** | 풀 사용률 60% 시 Warning, 80% 시 Critical 알림 | SRE | 🔴 높음 |
| S2 | **Istio 재시도 정책 재설계** | 재시도 횟수 1회로 축소, retryOn 조건을 `gateway-error`만으로 제한, perTryTimeout 3초 | Mesh팀 | 🔴 높음 |
| S3 | **VirtualService 타임아웃 단축** | payment-api 30초 → 5초, 빠른 실패(fail-fast) 전략 적용 | Mesh팀 | 🔴 높음 |
| S4 | **Pod 메모리 제한 상향** | payment-api JVM 힙 512MB → 1024MB, 컨테이너 limit 조정 | Platform | 🟠 중간 |
| S5 | **HikariPool 설정 최적화** | max 50 → 100, connectionTimeout 30s → 10s, idleTimeout 조정 | Backend | 🟠 중간 |
| S6 | **payment-db 노드 전용화** | worker-03을 DB 전용 노드로 지정 (taint/toleration), 다른 워크로드 격리 | Infra | 🟠 중간 |

### 장기 개선 (Long-term) — 1~3개월

| # | 개선 항목 | 상세 | 담당 | 우선순위 |
|---|----------|------|------|----------|
| L1 | **payment-db 이중화** | Primary-Replica 구성으로 단일 장애점(SPOF) 해소, 읽기 부하 분산 | DBA/Infra | 🔴 높음 |
| L2 | **결제 서비스 비동기화** | 결제 요청을 메시지 큐(Kafka/RabbitMQ)로 비동기 처리, DB 직접 의존도 감소 | Backend | 🟠 중간 |
| L3 | **Auto-scaling 정책 수립** | payment-api HPA 설정, DB 커넥션 풀 사용률 기반 스케일링 | Platform | 🟠 중간 |
| L4 | **Graceful Degradation 구현** | 결제 실패 시 사용자에게 "잠시 후 재시도" 안내 + 자동 재결제 큐 | Backend/FE | 🟡 보통 |
| L5 | **Chaos Engineering 도입** | 정기적으로 DB 지연/장애를 시뮬레이션하여 복원력 사전 검증 | SRE | 🟡 보통 |
| L6 | **Observability 강화** | DB 커넥션 풀, 노드 리소스, 서킷 브레이커 상태를 통합 대시보드로 구성 | SRE | 🟠 중간 |

---

## 7. 4개 분석팀 결과 요약

| 분석팀 | 핵심 발견 | 근본 원인 지목 |
|--------|-----------|---------------|
| **Log Analysis** | DB 커넥션 풀 고갈 → 500 에러 → 서킷 브레이커 OPEN → order-api 전파 | payment-db 응답 지연 |
| **Metrics Analysis** | DB 풀 고갈 알림이 최초 발생(09:15:12), 이후 연쇄 알림 cascade | payment-db가 장애 진원지 |
| **Infra Analysis** | worker-03 (DB 노드) CPU 95%, Mem 86% 포화, Pod OOMKilled | worker-03 노드 리소스 포화 |
| **Mesh Analysis** | 서킷 브레이커 OPEN, 재시도 3회로 트래픽 3배 증폭, DB 67% 에러 | payment-db 장애 + 재시도 폭풍 |

> **4개 팀 모두 payment-db / worker-03 노드를 장애 진원지로 지목** — 교차 검증 완료, 근본 원인 확정.

---

## 8. 교훈 (Lessons Learned)

1. **사전 경고가 없었다**: DB 풀이 60% 이상 사용되는 시점에 경고가 있었다면 09:10에 대응을 시작할 수 있었다 (5분 조기 대응 가능)
2. **재시도 정책이 장애를 악화시켰다**: 서킷 브레이커가 트립되기 전, Istio 재시도가 트래픽을 3배로 증폭하여 DB와 API 모두에 추가 부하를 가중시켰다
3. **단일 DB 호스트가 SPOF였다**: payment-db 인스턴스가 1대뿐이어서, 서킷 브레이커의 outlier detection이 사실상 전체 DB를 차단하는 결과를 초래했다
4. **타임아웃이 너무 길었다**: 30초 타임아웃은 장애 시 리소스를 장기간 점유하게 하여 연쇄 장애를 촉진했다
5. **메모리 제한이 부족했다**: 장애 시 재시도 큐가 메모리에 누적되는 패턴이 고려되지 않았다

---

## Appendix: 장애 메트릭 스냅샷

### 정상 상태 vs 장애 상태 비교

| 지표 | 정상 (09:00) | 장애 피크 (09:16) | 변화율 |
|------|-------------|-------------------|--------|
| 에러율 | 0.1% | 40.0% | **+39,900%** |
| p99 레이턴시 | 0.28s | 15.2s | **+5,329%** |
| DB Pool Active | 12/50 | 50/50 | 포화 |
| DB Pool Waiting | 0 | 203 | — |
| Request Rate | ~230 rps | 142 rps | -38% (CB 차단) |
| Pod Restarts | 0 | 47 | — |
| worker-03 CPU | ~60% | 95% | +58% |

---

*이 보고서는 4개 분석팀(Log, Metrics, Infra, Mesh)의 병렬 분석 결과를 교차 검증하여 작성되었습니다.*
*장애 복구 후 24시간 이내에 최종 사후 분석(Final Post-Mortem) 미팅을 진행할 것을 권고합니다.*
