import { useCallback, useEffect, useState } from "react";
import type { Pipeline } from "../types";
import { FileExplorer } from "./FileExplorer";
import type { SubtaskInfo } from "./SubtaskList";
import { SubtaskList } from "./SubtaskList";
import { SubtaskResultViewer } from "./SubtaskResultViewer";

interface PipelineDetailProps {
  pipeline: Pipeline;
  onClose: () => void;
}

const API_BASE = "/api";

/**
 * PipelineDetail: expands when a pipeline row is clicked.
 * Shows subtask list, selected subtask result, and file explorer.
 */
export function PipelineDetail({ pipeline, onClose }: PipelineDetailProps) {
  const [subtasks, setSubtasks] = useState<SubtaskInfo[]>([]);
  const [selectedSubtask, setSelectedSubtask] = useState<SubtaskInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchSubtasks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/tasks/${pipeline.task_id}/subtasks`);
      if (res.ok) {
        const data = await res.json();
        setSubtasks(data.subtasks || []);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [pipeline.task_id]);

  useEffect(() => {
    fetchSubtasks();
    const id = setInterval(fetchSubtasks, 3000);
    return () => clearInterval(id);
  }, [fetchSubtasks]);

  // Progress calculation
  const total = subtasks.length;
  const completed = subtasks.filter(
    (s) => s.state === "done" || s.state === "failed"
  ).length;
  const progressPct = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="panel pipeline-detail">
      <div className="panel-header" style={{ display: "flex", justifyContent: "space-between" }}>
        <span>
          Pipeline Detail: {pipeline.task.slice(0, 60)}
          <span className={`status-badge ${pipeline.status}`} style={{ marginLeft: 8 }}>
            {pipeline.status}
          </span>
        </span>
        <button className="btn btn-small" onClick={onClose}>
          Close
        </button>
      </div>

      <div className="panel-body">
        {/* Progress bar */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
            <span>Progress</span>
            <span>{completed}/{total} ({progressPct}%)</span>
          </div>
          <div
            style={{
              height: 6,
              background: "var(--bg-secondary, #333)",
              borderRadius: 3,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${progressPct}%`,
                height: "100%",
                background: pipeline.status === "failed" ? "var(--danger, #e55)" : "var(--success, #4c4)",
                transition: "width 0.3s ease",
              }}
            />
          </div>
        </div>

        {loading ? (
          <div className="empty-state">Loading subtasks...</div>
        ) : (
          <>
            <SubtaskList
              subtasks={subtasks}
              onSelect={setSelectedSubtask}
              selectedId={selectedSubtask?.id ?? null}
            />

            {selectedSubtask && (
              <div style={{ marginTop: 12 }}>
                <SubtaskResultViewer subtask={selectedSubtask} />
              </div>
            )}

            <div style={{ marginTop: 12 }}>
              <FileExplorer taskId={pipeline.task_id} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
