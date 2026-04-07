import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ResultViewer } from "./ResultViewer";
import type { Pipeline } from "../types";

const mockPipeline: Pipeline = {
  task_id: "pipeline-001",
  task: "Build JWT middleware",
  status: "completed",
  team_preset: "feature-team",
  target_repo: "",
  subtasks: [],
  results: [
    {
      subtask_id: "sub-001",
      executor_type: "cli",
      cli: "claude",
      output: "Implementation complete",
      files_changed: [],
      tokens_used: 1000,
      duration_ms: 5000,
      error: "",
    },
  ],
  synthesis: "## Summary\nAll tasks completed successfully.",
  workspace_paths: {},
  merged: false,
  error: "",
  started_at: "2026-04-05T14:30:00Z",
  completed_at: "2026-04-05T14:35:00Z",
};

describe("ResultViewer", () => {
  it("renders nothing when no pipeline selected", () => {
    const { container } = render(
      <ResultViewer pipeline={null} onClose={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders synthesis report", () => {
    render(<ResultViewer pipeline={mockPipeline} onClose={vi.fn()} />);
    expect(
      screen.getByText("## Summary\nAll tasks completed successfully."),
    ).toBeInTheDocument();
  });

  it("renders subtask results", () => {
    render(<ResultViewer pipeline={mockPipeline} onClose={vi.fn()} />);
    expect(screen.getByText("Implementation complete")).toBeInTheDocument();
    expect(screen.getByText(/sub-001/)).toBeInTheDocument();
  });

  it("renders close button", () => {
    render(<ResultViewer pipeline={mockPipeline} onClose={vi.fn()} />);
    expect(screen.getByText("Close")).toBeInTheDocument();
  });
});
