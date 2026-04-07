import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AgentStatusPanel } from "./AgentStatusPanel";
import type { AgentStatus } from "../types";

describe("AgentStatusPanel", () => {
  it("renders collapsed by default with header", () => {
    render(<AgentStatusPanel agents={[]} />);
    expect(screen.getByText("Agents")).toBeInTheDocument();
    // Panel body should NOT be visible (collapsed)
    expect(screen.queryByText("No agents")).not.toBeInTheDocument();
  });

  it("shows empty state when expanded with no agents", () => {
    render(<AgentStatusPanel agents={[]} />);
    // Click header to expand
    fireEvent.click(screen.getByText("Agents"));
    expect(screen.getByText("No agents")).toBeInTheDocument();
  });

  it("renders agent list when expanded", () => {
    const agents: AgentStatus[] = [
      {
        worker_id: "worker-abc-implementer",
        lane: "implementer",
        status: "running",
        current_task: "task-001",
      },
    ];
    render(<AgentStatusPanel agents={agents} />);
    // Click header to expand
    fireEvent.click(screen.getByText("Agents"));
    expect(screen.getByText("worker-abc-implementer")).toBeInTheDocument();
    expect(screen.getByText("Lane: implementer")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
  });
});
