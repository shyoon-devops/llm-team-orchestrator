import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PipelineList } from "./PipelineList";
import type { Pipeline } from "../types";

const mockPipeline: Pipeline = {
  task_id: "pipeline-test-001",
  task: "JWT auth middleware implementation",
  status: "running",
  team_preset: "feature-team",
  target_repo: "/home/user/project",
  subtasks: [],
  results: [],
  synthesis: "",
  merged: false,
  error: "",
  started_at: "2026-04-05T14:30:00Z",
  completed_at: null,
};

describe("PipelineList", () => {
  it("renders loading state", () => {
    render(
      <PipelineList
        pipelines={[]}
        loading={true}
        onSelect={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    render(
      <PipelineList
        pipelines={[]}
        loading={false}
        onSelect={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(
      screen.getByText("No pipelines yet. Submit a task to get started."),
    ).toBeInTheDocument();
  });

  it("renders pipeline row", () => {
    render(
      <PipelineList
        pipelines={[mockPipeline]}
        loading={false}
        onSelect={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(
      screen.getByText("JWT auth middleware implementation"),
    ).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("feature-team")).toBeInTheDocument();
  });

  it("shows resume button for failed pipelines", () => {
    const failedPipeline = { ...mockPipeline, status: "failed" as const };
    render(
      <PipelineList
        pipelines={[failedPipeline]}
        loading={false}
        onSelect={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(screen.getByText("Resume")).toBeInTheDocument();
  });

  it("shows cancel button for running pipelines", () => {
    render(
      <PipelineList
        pipelines={[mockPipeline]}
        loading={false}
        onSelect={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });
});
