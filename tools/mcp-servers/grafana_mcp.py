"""Mock Grafana/Prometheus MCP Server — 장애 시나리오 메트릭 데이터."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("grafana-mock")

METRICS = {
    "http_request_duration_seconds_p99": {
        "payment-api": [
            {"time": "09:00", "value": 0.28}, {"time": "09:05", "value": 0.31},
            {"time": "09:10", "value": 0.35}, {"time": "09:12", "value": 0.52},
            {"time": "09:14", "value": 2.1},  {"time": "09:15", "value": 8.7},
            {"time": "09:16", "value": 15.2}, {"time": "09:17", "value": 14.8},
            {"time": "09:18", "value": 12.3}, {"time": "09:20", "value": 11.9},
        ],
    },
    "http_requests_total_5xx_rate": {
        "payment-api": [
            {"time": "09:00", "value": 0.1}, {"time": "09:05", "value": 0.2},
            {"time": "09:10", "value": 0.3}, {"time": "09:14", "value": 5.8},
            {"time": "09:15", "value": 42.3}, {"time": "09:16", "value": 67.1},
            {"time": "09:17", "value": 58.9}, {"time": "09:18", "value": 45.2},
        ],
    },
    "db_connection_pool_active": {
        "payment-db": [
            {"time": "09:00", "value": 12}, {"time": "09:05", "value": 15},
            {"time": "09:10", "value": 28}, {"time": "09:12", "value": 41},
            {"time": "09:14", "value": 49}, {"time": "09:15", "value": 50},
            {"time": "09:16", "value": 50}, {"time": "09:17", "value": 50},
            {"time": "09:18", "value": 50}, {"time": "09:20", "value": 50},
        ],
    },
    "db_connection_pool_waiting": {
        "payment-db": [
            {"time": "09:00", "value": 0}, {"time": "09:10", "value": 0},
            {"time": "09:14", "value": 3}, {"time": "09:15", "value": 127},
            {"time": "09:16", "value": 203}, {"time": "09:17", "value": 189},
        ],
    },
}

ALERTS = [
    {"name": "PaymentAPIHighErrorRate", "severity": "critical", "status": "firing",
     "started": "09:15:30 UTC", "summary": "payment-api 5xx error rate > 20% (현재 40%)",
     "labels": {"service": "payment-api", "namespace": "production"}},
    {"name": "PaymentAPIHighLatency", "severity": "critical", "status": "firing",
     "started": "09:15:45 UTC", "summary": "payment-api p99 latency > 5s (현재 15.2s)",
     "labels": {"service": "payment-api", "namespace": "production"}},
    {"name": "DBConnectionPoolExhausted", "severity": "warning", "status": "firing",
     "started": "09:15:12 UTC", "summary": "payment-db connection pool 100% 사용 (50/50)",
     "labels": {"service": "payment-db", "namespace": "production"}},
    {"name": "PodCrashLooping", "severity": "warning", "status": "firing",
     "started": "09:16:00 UTC", "summary": "payment-api-7b9f4-j8np CrashLoopBackOff (47 restarts)",
     "labels": {"pod": "payment-api-7b9f4-j8np", "namespace": "production"}},
]


@mcp.tool()
def query_metrics(metric: str, service: str = "payment-api", time_range: str = "30m") -> dict:
    """Prometheus 메트릭을 조회한다. metric은 메트릭 이름, service는 대상 서비스."""
    data = METRICS.get(metric, {}).get(service, [])
    if not data:
        available = list(METRICS.keys())
        return {"error": f"Metric '{metric}' not found for '{service}'", "available_metrics": available}
    return {"metric": metric, "service": service, "time_range": time_range, "values": data}


@mcp.tool()
def get_active_alerts(severity: str = "all") -> dict:
    """현재 활성 알림 목록을 반환한다. severity: all, critical, warning."""
    if severity == "all":
        return {"alerts": ALERTS, "total": len(ALERTS)}
    filtered = [a for a in ALERTS if a["severity"] == severity]
    return {"alerts": filtered, "total": len(filtered), "filter": severity}


@mcp.tool()
def get_dashboard_summary(dashboard: str = "payment-overview") -> dict:
    """Grafana 대시보드의 패널 요약을 반환한다."""
    return {
        "dashboard": dashboard,
        "panels": [
            {"title": "Request Rate", "current": "142 req/s", "change": "-38% (평소 대비)"},
            {"title": "Error Rate (5xx)", "current": "40.0%", "change": "+3900% (평소 0.1%)"},
            {"title": "P99 Latency", "current": "15.2s", "change": "+5000% (평소 0.3s)"},
            {"title": "DB Pool Active", "current": "50/50", "change": "포화 상태"},
            {"title": "DB Pool Waiting", "current": "127", "change": "큐 대기 중"},
            {"title": "Circuit Breaker", "current": "OPEN", "change": "09:15:34 발동"},
        ],
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
