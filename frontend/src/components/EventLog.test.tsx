import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EventLog } from "./EventLog";
import type { WSEvent } from "../types";

describe("EventLog", () => {
  it("renders empty state when connected with no events", () => {
    render(<EventLog events={[]} connected={true} onClear={vi.fn()} />);
    expect(screen.getByText("Waiting for events...")).toBeInTheDocument();
  });

  it("renders disconnected message", () => {
    render(<EventLog events={[]} connected={false} onClear={vi.fn()} />);
    expect(screen.getByText("WebSocket disconnected")).toBeInTheDocument();
  });

  it("renders event items", () => {
    const events: WSEvent[] = [
      {
        type: "pipeline.started",
        timestamp: "2026-04-05T14:30:00.000Z",
        payload: { pipeline_id: "test-001" },
      },
    ];
    render(<EventLog events={events} connected={true} onClear={vi.fn()} />);
    expect(screen.getByText("pipeline.started")).toBeInTheDocument();
  });

  it("renders clear button", () => {
    render(<EventLog events={[]} connected={true} onClear={vi.fn()} />);
    expect(screen.getByText("Clear")).toBeInTheDocument();
  });
});
