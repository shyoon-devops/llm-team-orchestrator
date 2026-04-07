"""Mock Finance/Spreadsheet MCP Server — 재무 에이전트용."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("finance-mock")

REVENUE_DATA = {
    "monthly": [
        {"month": "2026-01", "revenue": 1200000, "cost": 850000, "profit": 350000},
        {"month": "2026-02", "revenue": 1450000, "cost": 920000, "profit": 530000},
        {"month": "2026-03", "revenue": 1680000, "cost": 980000, "profit": 700000},
    ],
    "currency": "KRW (만원)",
    "yoy_growth": "23.5%",
}

BUDGET = {
    "departments": {
        "engineering": {"allocated": 5000000, "spent": 3200000, "remaining": 1800000},
        "marketing": {"allocated": 2000000, "spent": 1500000, "remaining": 500000},
        "sales": {"allocated": 1500000, "spent": 900000, "remaining": 600000},
        "operations": {"allocated": 800000, "spent": 650000, "remaining": 150000},
    },
    "total_allocated": 9300000,
    "total_spent": 6250000,
    "burn_rate": "67.2%",
}

PRICING_MODELS = [
    {"plan": "Starter", "price_monthly": 29, "price_annual": 290, "features": 5, "target": "개인/소규모"},
    {"plan": "Professional", "price_monthly": 79, "price_annual": 790, "features": 15, "target": "중소기업"},
    {"plan": "Enterprise", "price_monthly": 199, "price_annual": 1990, "features": "Unlimited", "target": "대기업"},
]


@mcp.tool()
def get_revenue_report(period: str = "monthly") -> dict:
    """매출/비용/이익 보고서를 반환한다."""
    return REVENUE_DATA


@mcp.tool()
def get_budget_status(department: str = "all") -> dict:
    """부서별 예산 현황을 반환한다."""
    if department != "all" and department in BUDGET["departments"]:
        return {"department": department, **BUDGET["departments"][department]}
    return BUDGET


@mcp.tool()
def calculate_pricing_roi(plan: str = "Professional", customers: int = 100, months: int = 12) -> dict:
    """가격 모델별 예상 수익을 계산한다."""
    model = next((p for p in PRICING_MODELS if p["plan"] == plan), PRICING_MODELS[1])
    monthly_rev = model["price_monthly"] * customers
    annual_rev = monthly_rev * months
    return {
        "plan": plan, "customers": customers, "months": months,
        "monthly_revenue": f"${monthly_rev:,}",
        "total_revenue": f"${annual_rev:,}",
        "pricing_models": PRICING_MODELS,
    }


@mcp.tool()
def get_cost_breakdown(category: str = "all") -> dict:
    """비용 항목별 분석을 반환한다."""
    return {
        "categories": {
            "인건비": {"amount": 4500000, "pct": "72%"},
            "인프라/클라우드": {"amount": 800000, "pct": "13%"},
            "마케팅": {"amount": 500000, "pct": "8%"},
            "사무실/기타": {"amount": 450000, "pct": "7%"},
        },
        "total": 6250000,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
