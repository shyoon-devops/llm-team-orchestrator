import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AgentStatusPanel } from "./AgentStatusPanel";
import type { AgentStatus } from "../types";

describe("AgentStatusPanel", () => {
  it("renders empty state", () => {
    render(<AgentStatusPanel agents={[]} />);
    expect(screen.getByText("No active agents")).toBeInTheDocument();
  });

  it("renders agent list", () => {
    const agents: AgentStatus[] = [
      {
        worker_id: "worker-abc-implementer",
        lane: "implementer",
        status: "running",
        current_task: "task-001",
      },
    ];
    render(<AgentStatusPanel agents={agents} />);
    expect(screen.getByText("worker-abc-implementer")).toBeInTheDocument();
    expect(screen.getByText("Lane: implementer")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
  });
});
