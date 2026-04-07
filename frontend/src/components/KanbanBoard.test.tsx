import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KanbanBoard } from "./KanbanBoard";
import type { BoardState } from "../types";

describe("KanbanBoard", () => {
  it("renders empty state when board is null", () => {
    render(<KanbanBoard board={null} />);
    expect(screen.getByText("No board data")).toBeInTheDocument();
  });

  it("renders column headers", () => {
    const emptyBoard: BoardState = {
      lanes: {},
      summary: { total: 0, by_state: { backlog: 0, todo: 0, in_progress: 0, done: 0, failed: 0 } },
    };
    render(<KanbanBoard board={emptyBoard} />);
    expect(screen.getByText("Backlog")).toBeInTheDocument();
    expect(screen.getByText("Todo")).toBeInTheDocument();
    expect(screen.getByText("In Progress")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("renders task cards in correct columns", () => {
    const board: BoardState = {
      lanes: {
        implementer: {
          backlog: [],
          todo: [
            {
              id: "task-001",
              title: "Implement JWT module",
              description: "",
              lane: "implementer",
              state: "todo",
              priority: 0,
              depends_on: [],
              assigned_to: null,
              result: "",
              error: "",
              retry_count: 0,
              max_retries: 3,
              pipeline_id: "pipe-001",
              checklist: [],
            },
          ],
          in_progress: [],
          done: [],
          failed: [],
        },
      },
      summary: { total: 1, by_state: { backlog: 0, todo: 1, in_progress: 0, done: 0, failed: 0 } },
    };
    render(<KanbanBoard board={board} />);
    expect(screen.getByText("Implement JWT module")).toBeInTheDocument();
    expect(screen.getByText("Total: 1")).toBeInTheDocument();
  });
});
