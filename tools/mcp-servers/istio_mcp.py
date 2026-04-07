"""Mock Istio Service Mesh MCP Server — 장애 시나리오 메시 데이터."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("istio-mock")

VIRTUAL_SERVICES = [
    {"name": "payment-api-vs", "namespace": "production",
     "hosts": ["payment-api.production.svc.cluster.local"],
     "http_routes": [
         {"match": [{"uri": {"prefix": "/api/v1/payments"}}],
          "route": [{"destination": {"host": "payment-api", "port": 8080}, "weight": 100}],
          "timeout": "30s",
          "retries": {"attempts": 3, "perTryTimeout": "10s", "retryOn": "5xx,reset,connect-failure"}},
     ]},
    {"name": "order-api-vs", "namespace": "production",
     "hosts": ["order-api.production.svc.cluster.local"],
     "http_routes": [
         {"match": [{"uri": {"prefix": "/api/orders"}}],
          "route": [{"destination": {"host": "order-api", "port": 8080}, "weight": 100}],
          "timeout": "15s"},
     ]},
]

DESTINATION_RULES = {
    "payment-api": {
        "name": "payment-api-dr", "namespace": "production",
        "host": "payment-api",
        "traffic_policy": {
            "connectionPool": {
                "tcp": {"maxConnections": 100, "connectTimeout": "5s"},
                "http": {"h2UpgradePolicy": "DEFAULT", "maxRequestsPerConnection": 100},
            },
            "outlierDetection": {
                "consecutiveErrors": 5,
                "interval": "10s",
                "baseEjectionTime": "30s",
                "maxEjectionPercent": 50,
            },
        },
    },
    "payment-db": {
        "name": "payment-db-dr", "namespace": "production",
        "host": "payment-db",
        "traffic_policy": {
            "connectionPool": {
                "tcp": {"maxConnections": 50, "connectTimeout": "10s"},
            },
            "outlierDetection": {
                "consecutiveErrors": 3,
                "interval": "5s",
                "baseEjectionTime": "60s",
                "maxEjectionPercent": 100,
            },
        },
    },
}

SERVICE_METRICS = {
    "payment-api": {
        "inbound": {
            "success_rate": "58.2%",
            "rps": 142,
            "p50": "1.2s", "p99": "15.2s",
            "sources": [
                {"service": "order-api", "rps": 89, "error_rate": "43%"},
                {"service": "checkout-web", "rps": 53, "error_rate": "35%"},
            ],
        },
        "outbound": {
            "destinations": [
                {"service": "payment-db", "rps": 142, "error_rate": "67%", "p99": "30s (timeout)"},
                {"service": "notification-api", "rps": 12, "error_rate": "0%", "p99": "0.1s"},
            ],
        },
    },
}

CIRCUIT_BREAKER = {
    "payment-api": {
        "service": "payment-api",
        "upstream": "payment-db",
        "state": "OPEN",
        "triggered_at": "2026-04-07T09:15:28Z",
        "consecutive_errors": 50,
        "threshold": 5,
        "ejection_time": "30s",
        "max_ejection_percent": 100,
        "ejected_hosts": [
            {"address": "10.0.3.15:5432", "ejected_at": "09:15:28", "times_ejected": 3},
        ],
        "pending_requests": 127,
        "overflow_count": 2847,
    },
}


@mcp.tool()
def get_virtual_services(namespace: str = "production") -> dict:
    """네임스페이스의 Istio VirtualService 목록을 반환한다."""
    vs = [v for v in VIRTUAL_SERVICES if v["namespace"] == namespace]
    return {"namespace": namespace, "virtual_services": vs, "total": len(vs)}


@mcp.tool()
def get_destination_rules(service: str = "payment-api") -> dict:
    """서비스의 Istio DestinationRule (트래픽 정책, circuit breaker 설정)을 반환한다."""
    dr = DESTINATION_RULES.get(service)
    if not dr:
        return {"error": f"No DestinationRule found for '{service}'", "available": list(DESTINATION_RULES.keys())}
    return dr


@mcp.tool()
def get_service_metrics(service: str = "payment-api", time_range: str = "30m") -> dict:
    """서비스의 Istio 메시 메트릭 (요청률, 에러율, 레이턴시)을 반환한다."""
    metrics = SERVICE_METRICS.get(service)
    if not metrics:
        return {"error": f"No metrics for '{service}'", "available": list(SERVICE_METRICS.keys())}
    return {"service": service, "time_range": time_range, **metrics}


@mcp.tool()
def get_circuit_breaker_status(service: str = "payment-api") -> dict:
    """서비스의 Istio circuit breaker 상태를 반환한다."""
    cb = CIRCUIT_BREAKER.get(service)
    if not cb:
        return {"service": service, "state": "CLOSED", "message": "No circuit breaker active"}
    return cb


if __name__ == "__main__":
    mcp.run(transport="stdio")
