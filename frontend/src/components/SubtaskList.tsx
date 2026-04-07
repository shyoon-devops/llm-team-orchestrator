import type { ChecklistItem, TaskState } from "../types";
import { extractTitle } from "../utils";

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
  checklist?: ChecklistItem[];
}

interface SubtaskListProps {
  subtasks: SubtaskInfo[];
  onSelect: (subtask: SubtaskInfo) => void;
  selectedId: string | null;
}

function formatElapsed(started: string | null, completed: string | null, _state: string): string {
  if (!started) return "--";
  const start = new Date(started).getTime();
  if (isNaN(start)) return "--";
  const end = completed ? new Date(completed).getTime() : Date.now();
  const sec = Math.max(0, Math.round((end - start) / 1000));
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`;
  return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
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
          <th>Checklist</th>
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
            <td>{extractTitle(st.description)}</td>
            <td>
              <span className={`status-badge ${st.state}`}>{st.state}</span>
            </td>
            <td style={{ fontSize: 11, color: "var(--text-muted)" }}>
              {st.checklist?.length ? `${st.checklist.filter(c => c.status === "done").length}/${st.checklist.length}` : ""}
            </td>
            <td style={{ fontSize: 12, color: "var(--text-muted)" }}>
              {st.state === "in_progress" && <span className="subtask-spinner" />}
              {formatElapsed(st.started_at, st.completed_at, String(st.state))}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
