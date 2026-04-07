import { useCallback, useEffect, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Pipeline } from "../types";
import { formatElapsed } from "../utils";

interface PipelineDetailProps {
  pipeline: Pipeline;
  onClose: () => void;
}

interface SubtaskSummary {
  total: number;
  done: number;
  in_progress: number;
  failed: number;
}

const API_BASE = "/api";

/**
 * PipelineDetail: brief summary panel above the kanban board.
 * Shows status, progress bar, elapsed time, workspace paths, and synthesis.
 * No subtask table (kanban board already shows that).
 */
export function PipelineDetail({ pipeline, onClose }: PipelineDetailProps) {
  const [summary, setSummary] = useState<SubtaskSummary>({ total: 0, done: 0, in_progress: 0, failed: 0 });
  const [synthOpen, setSynthOpen] = useState(false);

  const fetchSubtasks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/tasks/${pipeline.task_id}/subtasks`);
      if (res.ok) {
        const data = await res.json();
        const subtasks = data.subtasks || [];
        setSummary({
          total: subtasks.length,
          done: subtasks.filter((s: { state: string }) => s.state === "done").length,
          in_progress: subtasks.filter((s: { state: string }) => s.state === "in_progress").length,
          failed: subtasks.filter((s: { state: string }) => s.state === "failed").length,
        });
      }
    } catch {
      // ignore
    }
  }, [pipeline.task_id]);

  useEffect(() => {
    fetchSubtasks();
    const id = setInterval(fetchSubtasks, 3000);
    return () => clearInterval(id);
  }, [fetchSubtasks]);

  const progressPct = summary.total > 0
    ? Math.round(((summary.done + summary.failed) / summary.total) * 100)
    : 0;

  const workspacePaths = pipeline.workspace_paths || {};
  const hasWorkspacePaths = Object.keys(workspacePaths).length > 0;

  return (
    <div className="pipeline-summary">
      <div className="pipeline-summary-header">
        <h3>{pipeline.task.slice(0, 80)}{pipeline.task.length > 80 ? "..." : ""}</h3>
        <span className={`status-badge ${pipeline.status}`}>{pipeline.status}</span>
        <button className="btn btn-small" onClick={onClose}>Close</button>
      </div>
      <div className="pipeline-summary-body">
        {/* Progress bar */}
        <div className="pipeline-progress">
          <div className="pipeline-progress-bar">
            <div
              className="pipeline-progress-fill"
              style={{
                width: `${progressPct}%`,
                background: pipeline.status === "failed"
                  ? "var(--accent-red)"
                  : pipeline.status === "completed"
                    ? "var(--accent-green)"
                    : "var(--accent-blue)",
              }}
            />
          </div>
          <span className="pipeline-progress-label">{progressPct}%</span>
        </div>

        {/* Key stats */}
        <div className="pipeline-stats">
          <span>Team: <strong>{pipeline.team_preset || "auto"}</strong></span>
          <span>Progress: <strong>{summary.done}/{summary.total}</strong></span>
          {summary.in_progress > 0 && (
            <span>Running: <strong>{summary.in_progress}</strong></span>
          )}
          {summary.failed > 0 && (
            <span className="pipeline-stat-failed">Failed: <strong>{summary.failed}</strong></span>
          )}
          <span>Elapsed: <strong>{formatElapsed(pipeline.started_at, pipeline.completed_at)}</strong></span>
        </div>

        {/* Workspace paths */}
        {hasWorkspacePaths && (
          <div className="workspace-paths">
            <span className="workspace-paths-label">Workspace:</span>
            {Object.entries(workspacePaths).map(([lane, path]) => (
              <code key={lane}>{lane}: {path}</code>
            ))}
          </div>
        )}

        {/* Synthesis (collapsible) */}
        {pipeline.synthesis && (
          <div className="pipeline-synthesis">
            <button
              className="pipeline-synthesis-toggle"
              onClick={() => setSynthOpen(!synthOpen)}
            >
              <span className="pipeline-synthesis-arrow">{synthOpen ? "\u25BC" : "\u25B6"}</span>
              Synthesis Report
            </button>
            {synthOpen && (
              <div className="pipeline-synthesis-content markdown-content">
                <Markdown remarkPlugins={[remarkGfm]}>{pipeline.synthesis}</Markdown>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
