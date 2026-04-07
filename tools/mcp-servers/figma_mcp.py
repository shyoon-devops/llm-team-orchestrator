"""Mock Figma MCP Server — 디자이너 에이전트용."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("figma-mock")

MOCK_COMPONENTS = [
    {"id": "comp-001", "name": "LoginForm", "type": "Frame", "width": 400, "height": 520,
     "children": ["EmailInput", "PasswordInput", "LoginButton", "ForgotPasswordLink"]},
    {"id": "comp-002", "name": "Dashboard", "type": "Frame", "width": 1440, "height": 900,
     "children": ["Sidebar", "HeaderBar", "MetricsGrid", "RecentActivityList"]},
    {"id": "comp-003", "name": "PricingCard", "type": "Component", "width": 320, "height": 480,
     "children": ["PlanName", "PriceTag", "FeatureList", "CTAButton"]},
]

DESIGN_SYSTEM = {
    "colors": {"primary": "#2563EB", "secondary": "#7C3AED", "success": "#059669",
               "warning": "#D97706", "error": "#DC2626", "bg": "#F9FAFB", "text": "#111827"},
    "typography": {"heading": "Inter Bold 24px", "subheading": "Inter SemiBold 18px",
                   "body": "Inter Regular 14px", "caption": "Inter Regular 12px"},
    "spacing": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32},
    "borderRadius": {"sm": 4, "md": 8, "lg": 12, "full": 9999},
}


@mcp.tool()
def get_design_system() -> dict:
    """프로젝트의 디자인 시스템(컬러, 타이포그래피, 스페이싱)을 반환한다."""
    return DESIGN_SYSTEM


@mcp.tool()
def list_components(page: str = "all") -> dict:
    """Figma 파일의 컴포넌트 목록을 반환한다."""
    return {"components": MOCK_COMPONENTS, "total": len(MOCK_COMPONENTS)}


@mcp.tool()
def get_component(component_id: str) -> dict:
    """특정 컴포넌트의 상세 정보를 반환한다."""
    comp = next((c for c in MOCK_COMPONENTS if c["id"] == component_id), None)
    if not comp:
        return {"error": f"Component {component_id} not found"}
    return comp


@mcp.tool()
def export_component_css(component_id: str) -> dict:
    """컴포넌트의 CSS 스타일을 추출한다."""
    return {
        "component": component_id,
        "css": {
            "display": "flex", "flex-direction": "column", "gap": "16px",
            "padding": "24px", "border-radius": "12px",
            "background": DESIGN_SYSTEM["colors"]["bg"],
            "font-family": "Inter, sans-serif",
        }
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
