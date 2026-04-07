"""Mock Kubernetes MCP Server — 장애 시나리오 클러스터 데이터."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("k8s-mock")

PODS = [
    {"name": "payment-api-7b9f4-xk2m", "namespace": "production", "status": "Running",
     "ready": "1/1", "restarts": 12, "age": "3d", "cpu": "78%", "memory": "62%",
     "node": "worker-01", "labels": {"app": "payment-api", "version": "v2.3.1"}},
    {"name": "payment-api-7b9f4-j8np", "namespace": "production", "status": "CrashLoopBackOff",
     "ready": "0/1", "restarts": 47, "age": "3d", "cpu": "0%", "memory": "0%",
     "node": "worker-02", "labels": {"app": "payment-api", "version": "v2.3.1"},
     "last_termination": {"reason": "OOMKilled", "exit_code": 137, "time": "09:16:45 UTC"}},
    {"name": "payment-api-7b9f4-m3qr", "namespace": "production", "status": "Running",
     "ready": "1/1", "restarts": 8, "age": "3d", "cpu": "82%", "memory": "71%",
     "node": "worker-01", "labels": {"app": "payment-api", "version": "v2.3.1"}},
    {"name": "payment-db-0", "namespace": "production", "status": "Running",
     "ready": "1/1", "restarts": 0, "age": "14d", "cpu": "95%", "memory": "87%",
     "node": "worker-03", "labels": {"app": "payment-db", "role": "primary"},
     "volumes": [{"name": "data", "type": "PVC", "size": "100Gi", "used": "73Gi"}]},
    {"name": "order-api-5c8d2-k4wn", "namespace": "production", "status": "Running",
     "ready": "1/1", "restarts": 0, "age": "5d", "cpu": "34%", "memory": "45%",
     "node": "worker-02", "labels": {"app": "order-api"}},
]

POD_LOGS = {
    "payment-api-7b9f4-j8np": [
        "09:16:30 ERROR [main] o.s.b.SpringApplication - Application run failed",
        "09:16:30 ERROR [main] Caused by: java.lang.OutOfMemoryError: Java heap space",
        "09:16:30 ERROR [main]   at com.payment.service.PaymentProcessor.processQueue(PaymentProcessor.java:127)",
        "09:16:30 ERROR [main]   at com.payment.service.PaymentProcessor.retryPending(PaymentProcessor.java:89)",
        "09:16:30 INFO  [main] Shutting down due to OOM. Heap: max=512MB, used=511MB",
        "09:16:45 INFO  [main] Container killed by OOMKiller (exit code 137)",
    ],
    "payment-db-0": [
        "09:15:00 LOG  connection received: host=10.0.1.15 port=45892",
        "09:15:01 LOG  connection authorized: user=payment_app database=payments",
        "09:15:12 WARNING  too many clients already (max_connections=50, current=50)",
        "09:15:12 FATAL  remaining connection slots are reserved for superuser",
        "09:15:28 LOG  checkpoint starting: time",
        "09:15:28 WARNING  checkpoints are occurring too frequently (every 30s)",
        "09:15:30 LOG  slow query: duration=12847ms SELECT p.*, t.* FROM payments p JOIN transactions t ON p.id = t.payment_id WHERE p.status = 'pending' AND p.created_at > now() - interval '1 hour'",
    ],
}

EVENTS = [
    {"type": "Warning", "reason": "BackOff", "object": "pod/payment-api-7b9f4-j8np",
     "message": "Back-off restarting failed container", "count": 47, "first": "09:15:00", "last": "09:20:00"},
    {"type": "Warning", "reason": "OOMKilling", "object": "pod/payment-api-7b9f4-j8np",
     "message": "Memory cgroup out of memory: Killed process 1 (java)", "count": 12, "first": "09:15:00", "last": "09:20:00"},
    {"type": "Warning", "reason": "Unhealthy", "object": "pod/payment-api-7b9f4-xk2m",
     "message": "Readiness probe failed: HTTP probe failed with statuscode: 503", "count": 89, "first": "09:15:30", "last": "09:20:00"},
    {"type": "Normal", "reason": "ScalingReplicaSet", "object": "deployment/payment-api",
     "message": "Scaled up replica set payment-api-7b9f4 to 3", "count": 1, "first": "09:00:00", "last": "09:00:00"},
]

NODES = [
    {"name": "worker-01", "status": "Ready", "cpu_capacity": "8", "cpu_used": "6.2", "cpu_pct": "77%",
     "mem_capacity": "32Gi", "mem_used": "24Gi", "mem_pct": "75%", "pods": 12},
    {"name": "worker-02", "status": "Ready", "cpu_capacity": "8", "cpu_used": "5.1", "cpu_pct": "64%",
     "mem_capacity": "32Gi", "mem_used": "21Gi", "mem_pct": "66%", "pods": 10},
    {"name": "worker-03", "status": "Ready", "cpu_capacity": "16", "cpu_used": "15.2", "cpu_pct": "95%",
     "mem_capacity": "64Gi", "mem_used": "55Gi", "mem_pct": "86%", "pods": 8},
]


@mcp.tool()
def list_pods(namespace: str = "production", label_selector: str = "") -> dict:
    """네임스페이스의 Pod 목록을 반환한다."""
    pods = [p for p in PODS if p["namespace"] == namespace]
    if label_selector:
        key, _, val = label_selector.partition("=")
        pods = [p for p in pods if p.get("labels", {}).get(key) == val]
    return {"namespace": namespace, "pods": pods, "total": len(pods)}


@mcp.tool()
def get_pod_logs(pod: str, namespace: str = "production", tail: int = 20) -> dict:
    """Pod의 최근 로그를 반환한다."""
    logs = POD_LOGS.get(pod, [f"No logs available for pod {pod}"])
    return {"pod": pod, "namespace": namespace, "logs": logs[-tail:], "total_lines": len(logs)}


@mcp.tool()
def describe_resource(kind: str = "pod", name: str = "", namespace: str = "production") -> dict:
    """Kubernetes 리소스 상세 정보를 반환한다. events 포함."""
    if kind == "pod":
        pod = next((p for p in PODS if p["name"] == name), None)
        if pod:
            pod_events = [e for e in EVENTS if name in e["object"]]
            return {"kind": kind, "metadata": pod, "events": pod_events}
    if kind == "deployment" and "payment-api" in name:
        return {
            "kind": "deployment", "name": name,
            "spec": {"replicas": 3, "strategy": "RollingUpdate", "maxSurge": 1, "maxUnavailable": 0},
            "status": {"ready": 2, "available": 2, "unavailable": 1, "updated": 3},
            "events": [e for e in EVENTS if "deployment" in e["object"]],
        }
    return {"error": f"Resource {kind}/{name} not found"}


@mcp.tool()
def get_node_status() -> dict:
    """클러스터 노드 리소스 사용량을 반환한다."""
    return {"nodes": NODES, "total": len(NODES)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
