"""Mock Elasticsearch MCP Server — 장애 시나리오 로그 데이터."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("elastic-mock")

# ── 인시던트 시나리오: payment-api DB connection pool 고갈 ──

MOCK_LOGS = [
    {"timestamp": "2026-04-07T09:14:58Z", "service": "payment-api", "level": "WARN", "message": "HikariPool-1 - Connection pool stats: active=48, idle=2, waiting=0, max=50"},
    {"timestamp": "2026-04-07T09:15:12Z", "service": "payment-api", "level": "WARN", "message": "HikariPool-1 - Connection pool stats: active=50, idle=0, waiting=12, max=50"},
    {"timestamp": "2026-04-07T09:15:28Z", "service": "payment-api", "level": "ERROR", "message": "Connection pool exhausted: active=50, waiting=127, max=50. All connections are in use."},
    {"timestamp": "2026-04-07T09:15:29Z", "service": "payment-api", "level": "ERROR", "message": "java.sql.SQLTransientConnectionException: HikariPool-1 - Connection is not available, request timed out after 30000ms"},
    {"timestamp": "2026-04-07T09:15:30Z", "service": "payment-api", "level": "ERROR", "message": "POST /api/v1/payments/process failed: org.springframework.dao.DataAccessResourceFailureException: Unable to acquire JDBC Connection"},
    {"timestamp": "2026-04-07T09:15:31Z", "service": "payment-api", "level": "ERROR", "message": "TransactionManager: rollback on timeout, txId=PAY-20260407-091531-4829"},
    {"timestamp": "2026-04-07T09:15:34Z", "service": "payment-api", "level": "WARN", "message": "Circuit breaker 'paymentDB' state changed: CLOSED -> OPEN (failure rate: 92%)"},
    {"timestamp": "2026-04-07T09:15:35Z", "service": "payment-api", "level": "ERROR", "message": "Returning 503 Service Unavailable: circuit breaker is OPEN for payment-db"},
    {"timestamp": "2026-04-07T09:16:01Z", "service": "order-api", "level": "ERROR", "message": "POST /api/payments returned 503: upstream connect error or disconnect/reset before headers"},
    {"timestamp": "2026-04-07T09:16:02Z", "service": "order-api", "level": "WARN", "message": "Payment service unavailable, order ORD-48291 payment deferred"},
    {"timestamp": "2026-04-07T09:16:15Z", "service": "notification-api", "level": "ERROR", "message": "Failed to send payment confirmation for order ORD-48291: payment status unknown"},
    {"timestamp": "2026-04-07T09:17:00Z", "service": "payment-api", "level": "INFO", "message": "Circuit breaker 'paymentDB' state changed: OPEN -> HALF_OPEN (testing with 1 request)"},
    {"timestamp": "2026-04-07T09:17:01Z", "service": "payment-api", "level": "ERROR", "message": "HALF_OPEN test failed: connection timeout after 5000ms"},
    {"timestamp": "2026-04-07T09:17:01Z", "service": "payment-api", "level": "WARN", "message": "Circuit breaker 'paymentDB' state changed: HALF_OPEN -> OPEN (will retry in 60s)"},
]

ERROR_SUMMARY = {
    "payment-api": {
        "500": 1247,
        "503": 1893,
        "504": 312,
        "total_errors": 3452,
        "total_requests": 8631,
        "error_rate": "40.0%",
    },
    "order-api": {
        "502": 89,
        "503": 423,
        "total_errors": 512,
        "total_requests": 2100,
        "error_rate": "24.4%",
    },
    "notification-api": {
        "500": 67,
        "total_errors": 67,
        "total_requests": 890,
        "error_rate": "7.5%",
    },
}


@mcp.tool()
def search_logs(query: str = "*", index: str = "app-logs", time_range: str = "30m") -> dict:
    """Elasticsearch에서 로그를 검색한다. query는 Lucene 구문, index는 인덱스 패턴, time_range는 시간 범위."""
    q = query.lower()
    filtered = [
        log for log in MOCK_LOGS
        if q == "*" or q in log["message"].lower() or q in log["service"].lower() or q in log["level"].lower()
    ]
    return {"hits": filtered, "total": len(filtered), "query": query, "index": index, "time_range": time_range}


@mcp.tool()
def get_error_summary(service: str = "all", time_range: str = "30m") -> dict:
    """서비스별 에러 코드 카운트 요약을 반환한다."""
    if service != "all" and service in ERROR_SUMMARY:
        return {"service": service, "time_range": time_range, "errors": ERROR_SUMMARY[service]}
    return {"time_range": time_range, "services": ERROR_SUMMARY}


@mcp.tool()
def get_log_sample(service: str = "payment-api", level: str = "ERROR", limit: int = 5) -> dict:
    """특정 서비스/레벨의 로그 샘플을 반환한다."""
    filtered = [log for log in MOCK_LOGS if log["service"] == service and log["level"] == level]
    return {"service": service, "level": level, "samples": filtered[:limit], "total_matching": len(filtered)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
