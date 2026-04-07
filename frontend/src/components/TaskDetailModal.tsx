import { useEffect, useRef, useState, useCallback } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChecklistItem, WSEvent } from "../types";
import { extractTitle, formatElapsed } from "../utils";
import { LiveOutputInline } from "./LiveOutputInline";

interface TaskDetail {
  id: string;
  title: string;
  description: string;
  lane: string;
  state: string;
  priority: number;
  depends_on: string[];
  assigned_to: string | null;
  result: string;
  error: string;
  retry_count: number;
  max_retries: number;
  pipeline_id: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  pipeline_task: string;
  checklist?: ChecklistItem[];
}

interface TaskDetailModalProps {
  taskId: string;
  outputEvents: WSEvent[];
  onClose: () => void;
}


/**
 * TaskDetailModal: Jira-style side panel for task details.
 * Slides in from the right. Shows metadata, checklist, live output, and result.
 */
export function TaskDetailModal({ taskId, outputEvents, onClose }: TaskDetailModalProps) {
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const panelRef = useRef<HTMLDivElement>(null);

  const fetchDetail = useCallback(() => {
    fetch(`/api/board/tasks/${taskId}`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        return r.json();
      })
      .then((data) => setDetail(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [taskId]);

  const detailRef = useRef(detail);
  detailRef.current = detail;

  useEffect(() => {
    setLoading(true);
    setError("");
    fetchDetail();
    // Refresh while not in terminal state
    const id = setInterval(() => {
      if (detailRef.current && ["done", "failed"].includes(detailRef.current.state)) return;
      fetchDetail();
    }, 3000);
    return () => clearInterval(id);
  }, [fetchDetail]);

  const checklistDone = detail?.checklist?.filter(c => c.status === "done").length ?? 0;
  const checklistTotal = detail?.checklist?.length ?? 0;

  return (
    <div className="task-modal-overlay" onClick={onClose}>
      <div
        ref={panelRef}
        className="task-modal"
        onClick={(e) => e.stopPropagation()}
      >
        {loading && !detail && (
          <div className="empty-state">Loading...</div>
        )}
        {error && !detail && (
          <div className="task-modal-error">{error}</div>
        )}
        {detail && (
          <>
            {/* Header */}
            <div className="task-modal-header">
              <h3>{extractTitle(detail.title)}</h3>
              <span className={`status-badge ${detail.state}`}>{detail.state}</span>
              <button className="task-modal-close" onClick={onClose}>&times;</button>
            </div>

            <div className="task-modal-body">
              {/* Metadata grid */}
              <div className="task-meta-grid">
                <div>
                  <label>Lane</label>
                  <span>{detail.lane}</span>
                </div>
                <div>
                  <label>Agent</label>
                  <span>{detail.assigned_to || "-"}</span>
                </div>
                <div>
                  <label>Depends on</label>
                  <span>{detail.depends_on.length > 0 ? detail.depends_on.join(", ") : "None"}</span>
                </div>
                <div>
                  <label>Elapsed</label>
                  <span>{formatElapsed(detail.started_at, detail.completed_at)}</span>
                </div>
                <div>
                  <label>Priority</label>
                  <span>{detail.priority}</span>
                </div>
                <div>
                  <label>Retries</label>
                  <span>{detail.retry_count} / {detail.max_retries}</span>
                </div>
              </div>

              {/* Description */}
              {detail.description && (
                <div className="task-section">
                  <h4>Description</h4>
                  <div className="task-description markdown-content">
                    <Markdown remarkPlugins={[remarkGfm]}>{detail.description}</Markdown>
                  </div>
                </div>
              )}

              {/* Checklist */}
              {checklistTotal > 0 && (
                <div className="task-section">
                  <h4>Checklist ({checklistDone}/{checklistTotal})</h4>
                  <div className="task-checklist">
                    {detail.checklist!.map((item, idx) => (
                      <div
                        key={item.id || idx}
                        className={`checklist-item ${item.status}`}
                      >
                        <span className="checklist-icon">
                          {item.status === "done" ? "\u2705" : item.status === "in_progress" ? "\uD83D\uDD04" : "\u2B1C"}
                        </span>
                        <span className="checklist-text">{item.title}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Live Output — filtered to this subtask */}
              {detail.state === "in_progress" && (
                <div className="task-section">
                  <h4>Live Output</h4>
                  <div className="task-live-output">
                    <LiveOutputInline events={outputEvents} subtaskId={taskId} />
                  </div>
                </div>
              )}

              {/* Result */}
              {detail.result && (
                <div className="task-section">
                  <h4>Result</h4>
                  <div className="task-result markdown-content">
                    <Markdown remarkPlugins={[remarkGfm]}>{detail.result}</Markdown>
                  </div>
                </div>
              )}

              {/* Error */}
              {detail.error && (
                <div className="task-section">
                  <h4 className="task-error-label">Error</h4>
                  <div className="task-error-content">
                    {detail.error}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
