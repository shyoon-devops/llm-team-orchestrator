"""Mock Sales/CRM MCP Server — 영업 에이전트용."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sales-mock")

PIPELINE = [
    {"id": "DEAL-001", "company": "테크스타트업A", "value": 50000, "stage": "negotiation", "probability": 70, "contact": "김대표"},
    {"id": "DEAL-002", "company": "대기업B", "value": 200000, "stage": "proposal", "probability": 40, "contact": "이부장"},
    {"id": "DEAL-003", "company": "중소기업C", "value": 30000, "stage": "closed_won", "probability": 100, "contact": "박사장"},
    {"id": "DEAL-004", "company": "스타트업D", "value": 15000, "stage": "discovery", "probability": 20, "contact": "최CTO"},
]

CUSTOMERS = [
    {"name": "기존고객1", "plan": "Professional", "mrr": 79, "since": "2025-06", "health": "green", "nps": 9},
    {"name": "기존고객2", "plan": "Enterprise", "mrr": 199, "since": "2025-09", "health": "yellow", "nps": 6},
    {"name": "기존고객3", "plan": "Starter", "mrr": 29, "since": "2026-01", "health": "green", "nps": 8},
]

MARKET = {
    "tam": "$2.5B", "sam": "$500M", "som": "$50M",
    "competitors": [
        {"name": "CompetitorX", "market_share": "35%", "strength": "브랜드 인지도", "weakness": "높은 가격"},
        {"name": "CompetitorY", "market_share": "20%", "strength": "기술력", "weakness": "UX 부족"},
    ],
    "target_segments": ["SMB SaaS", "Enterprise DevOps", "스타트업"],
}


@mcp.tool()
def get_sales_pipeline(stage: str = "all") -> dict:
    """영업 파이프라인을 반환한다."""
    deals = PIPELINE if stage == "all" else [d for d in PIPELINE if d["stage"] == stage]
    total_value = sum(d["value"] for d in deals)
    weighted = sum(d["value"] * d["probability"] / 100 for d in deals)
    return {"deals": deals, "total_value": f"${total_value:,}", "weighted_value": f"${weighted:,.0f}"}


@mcp.tool()
def get_customer_health() -> dict:
    """고객 건강 지표를 반환한다."""
    total_mrr = sum(c["mrr"] for c in CUSTOMERS)
    return {"customers": CUSTOMERS, "total_mrr": f"${total_mrr}/mo", "avg_nps": sum(c["nps"] for c in CUSTOMERS) / len(CUSTOMERS)}


@mcp.tool()
def get_market_analysis() -> dict:
    """시장 분석 데이터를 반환한다."""
    return MARKET


@mcp.tool()
def get_gtm_metrics() -> dict:
    """Go-to-Market 지표를 반환한다."""
    return {
        "cac": "$1,200", "ltv": "$9,480", "ltv_cac_ratio": "7.9x",
        "conversion_rates": {"lead_to_trial": "12%", "trial_to_paid": "25%", "paid_to_enterprise": "8%"},
        "channels": {"organic": "40%", "paid": "25%", "referral": "20%", "outbound": "15%"},
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
