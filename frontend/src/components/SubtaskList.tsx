import type { TaskState } from "../types";

export interface SubtaskInfo {
  id: string;
  description: string;
  assigned_preset: string;
  assigned_cli: string | null;
  priority: number;
  depends_on: string[];
  state: TaskState | string;
  result: string;
  error: string;
  started_at: string | null;
  completed_at: string | null;
}

interface SubtaskListProps {
  subtasks: SubtaskInfo[];
  onSelect: (subtask: SubtaskInfo) => void;
  selectedId: string | null;
}

function formatElapsed(started: string | null, completed: string | null): string {
  if (!started) return "--";
  const start = new Date(started).getTime();
  const end = completed ? new Date(completed).getTime() : Date.now();
  const sec = Math.round((end - start) / 1000);
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m ${sec % 60}s`;
}

/**
 * SubtaskList: displays subtasks within a pipeline with status badges.
 */
export function SubtaskList({ subtasks, onSelect, selectedId }: SubtaskListProps) {
  if (subtasks.length === 0) {
    return <div className="empty-state">No subtasks</div>;
  }

  return (
    <table className="pipeline-table subtask-table">
      <thead>
        <tr>
          <th>Lane</th>
          <th>Description</th>
          <th>Status</th>
          <th>Elapsed</th>
        </tr>
      </thead>
      <tbody>
        {subtasks.map((st) => (
          <tr
            key={st.id}
            onClick={() => onSelect(st)}
            style={{
              cursor: "pointer",
              backgroundColor: st.id === selectedId ? "var(--bg-hover, #2a2a3e)" : undefined,
            }}
          >
            <td style={{ fontWeight: 600 }}>{st.assigned_preset || "default"}</td>
            <td>{(st.description.split("\n")[0] || "").slice(0, 80) + (st.description.length > 80 ? "..." : "")}</td>
            <td>
              <span className={`status-badge ${st.state}`}>{st.state}</span>
            </td>
            <td style={{ fontSize: 12, color: "var(--text-muted)" }}>
              {formatElapsed(st.started_at, st.completed_at)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
