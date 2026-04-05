import type { BoardState, TaskState } from "../types";

interface KanbanBoardProps {
  board: BoardState | null;
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
 */
export function KanbanBoard({ board }: KanbanBoardProps) {
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
  const columns: Record<TaskState, Array<{ id: string; title: string; lane: string; assignedTo: string | null }>> = {
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
          columns[state as TaskState].push({
            id: task.id,
            title: task.title,
            lane: laneName,
            assignedTo: task.assigned_to,
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
                <div key={task.id} className="kanban-card">
                  <div className="kanban-card-title">
                    {task.title.length > 50 ? task.title.slice(0, 50) + "..." : task.title}
                  </div>
                  <div className="kanban-card-meta">
                    {task.lane}
                    {task.assignedTo ? ` | ${task.assignedTo}` : ""}
                  </div>
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
    </div>
  );
}
