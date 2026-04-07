import { useState } from "react";
import type { BoardState, TaskState } from "../types";
import { extractTitle } from "../utils";
import { TaskDetailModal } from "./TaskDetailModal";

interface KanbanBoardProps {
  board: BoardState | null;
}

const LANE_COLORS: Record<string, string> = {
  ceo: '#f85149',
  architect: '#bc8cff',
  implementer: '#58a6ff',
  reviewer: '#3fb950',
  tester: '#d29922',
  designer: '#f778ba',
  planner: '#79c0ff',
  finance: '#7ee787',
  sales: '#d2a8ff',
  infra: '#ffa657',
  'ops-lead': '#ff7b72',
  'elk-analyst': '#ffa657',
  'metrics-analyst': '#79c0ff',
  'k8s-analyst': '#7ee787',
  'istio-analyst': '#d2a8ff',
};

function getLaneColor(lane: string): string {
  return LANE_COLORS[lane] || '#8b949e';
}

const COLUMNS: { key: TaskState; label: string }[] = [
  { key: "backlog", label: "Backlog" },
  { key: "todo", label: "Todo" },
  { key: "in_progress", label: "In Progress" },
  { key: "done", label: "Done" },
  { key: "failed", label: "Failed" },
];

/**
 * KanbanBoard: visualizes TaskBoard state with 5 columns.
 * Data comes from GET /api/board.
 * Clicking a task card opens a detail modal.
 */
export function KanbanBoard({ board }: KanbanBoardProps) {
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  if (!board) {
    return (
      <div className="panel kanban-board">
        <div className="panel-header">Task Board</div>
        <div className="panel-body">
          <div className="empty-state">No board data</div>
        </div>
      </div>
    );
  }

  // Flatten all tasks from all lanes into columns by state
  const columns: Record<TaskState, Array<{ id: string; title: string; lane: string; assignedTo: string | null; state: TaskState; checklistDone: number; checklistTotal: number }>> = {
    backlog: [],
    todo: [],
    in_progress: [],
    done: [],
    failed: [],
  };

  for (const [laneName, laneData] of Object.entries(board.lanes)) {
    for (const [state, tasks] of Object.entries(laneData)) {
      if (state in columns && Array.isArray(tasks)) {
        for (const task of tasks) {
          const cl = task.checklist || [];
          columns[state as TaskState].push({
            id: task.id,
            title: task.title,
            lane: laneName,
            assignedTo: task.assigned_to,
            state: state as TaskState,
            checklistDone: cl.filter((c: { status: string }) => c.status === "done").length,
            checklistTotal: cl.length,
          });
        }
      }
    }
  }

  return (
    <div className="panel kanban-board">
      <div className="panel-header">
        <span>Task Board</span>
        <span style={{ fontSize: 12, fontWeight: 400 }}>
          Total: {board.summary.total}
        </span>
      </div>
      <div className="panel-body">
        <div className="kanban-columns">
          {COLUMNS.map((col) => (
            <div key={col.key} className="kanban-column">
              <div className="kanban-column-header">
                <span>{col.label}</span>
                <span className="kanban-count">{columns[col.key].length}</span>
              </div>
              {columns[col.key].map((task) => (
                <div
                  key={task.id}
                  className="kanban-card"
                  style={{
                    cursor: "pointer",
                    borderLeft: `3px solid ${getLaneColor(task.lane)}`,
                  }}
                  onClick={() => setSelectedTaskId(task.id)}
                >
                  <div className="kanban-card-title">
                    {task.state === "in_progress" && <span className="kanban-card-spinner" style={{ marginRight: 6 }} />}
                    {extractTitle(task.title)}
                  </div>
                  <div className="kanban-card-meta">
                    {task.lane}
                    {task.assignedTo ? ` | ${task.assignedTo}` : ""}
                  </div>
                  {task.checklistTotal > 0 && (
                    <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
                      {"\u2705"} {task.checklistDone}/{task.checklistTotal}
                    </div>
                  )}
                </div>
              ))}
              {columns[col.key].length === 0 && (
                <div className="empty-state" style={{ padding: 12 }}>
                  --
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {selectedTaskId && (
        <TaskDetailModal
          taskId={selectedTaskId}
          onClose={() => setSelectedTaskId(null)}
        />
      )}
    </div>
  );
}
