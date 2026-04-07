import { useEffect, useRef, useState, useCallback } from "react";
import type { WSEvent } from "../types";
import type { OutputLine } from "../lib/streamParser";
import { parseStreamLine } from "../lib/streamParser";

interface LiveOutputProps {
  events: WSEvent[];
  taskId?: string;
  subtaskId?: string;
}

/* ── Component ── */

export function LiveOutput({ events, taskId, subtaskId }: LiveOutputProps) {
  const [lines, setLines] = useState<OutputLine[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const lastIndexRef = useRef(0);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      if (containerRef.current) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight;
      }
    });
  }, []);

  useEffect(() => {
    const newEvents = events.slice(lastIndexRef.current);
    lastIndexRef.current = events.length;

    const newLines: OutputLine[] = [];
    for (const event of newEvents) {
      if (event.type !== "agent.output") continue;

      const p = event.payload || {};
      if (taskId && p.pipeline_id !== taskId) continue;
      if (subtaskId && p.subtask_id !== subtaskId) continue;

      const rawLine = String(p.line || "");
      if (!rawLine.trim()) continue;

      const parsed = parseStreamLine(rawLine);
      if (parsed) {
        parsed.lane = String(p.lane || "");
        parsed.timestamp = event.timestamp;
        newLines.push(parsed);
      }
    }

    if (newLines.length > 0) {
      setLines((prev) => {
        const next = [...prev, ...newLines];
        return next.length > 500 ? next.slice(-500) : next;
      });
      scrollToBottom();
    }
  }, [events, taskId, subtaskId, scrollToBottom]);

  return (
    <div className="panel">
      <div className="panel-header">
        <span>Live Output ({lines.length})</span>
        <button
          className="btn btn-small"
          onClick={() => { setLines([]); lastIndexRef.current = 0; }}
        >
          Clear
        </button>
      </div>
      <div className="panel-body">
        {!taskId ? (
          <div style={{ color: "var(--text-muted)", fontSize: 12, padding: "12px" }}>
            Select a pipeline to see live output
          </div>
        ) : (
          <div
            ref={containerRef}
            style={{
              backgroundColor: "var(--bg-primary)",
              color: "var(--text-primary)",
              fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              fontSize: "12px",
              padding: "8px 12px",
              borderRadius: "6px",
              maxHeight: "400px",
              overflowY: "auto",
              lineHeight: 1.6,
            }}
          >
            {lines.length === 0 ? (
              <div style={{ color: "var(--text-muted)" }}>Waiting for agent output...</div>
            ) : (
              lines.map((l, i) => (
                <div key={i} style={{
                  display: "flex",
                  gap: "6px",
                  padding: "1px 0",
                  borderBottom: "1px solid var(--border)",
                  alignItems: "baseline",
                }}>
                  {l.lane && (
                    <span style={{
                      color: "var(--text-secondary)",
                      fontSize: "10px",
                      minWidth: "70px",
                      flexShrink: 0,
                    }}>
                      {l.lane}
                    </span>
                  )}
                  <span style={{ flexShrink: 0 }}>{l.icon}</span>
                  {l.label && (
                    <span style={{
                      color: "var(--text-secondary)",
                      fontSize: "11px",
                      minWidth: "40px",
                      flexShrink: 0,
                    }}>
                      {l.label}
                    </span>
                  )}
                  <span style={{
                    color: l.color,
                    wordBreak: "break-all",
                    whiteSpace: "pre-wrap",
                    fontFamily: l.text.includes("\n") ? "'JetBrains Mono', monospace" : "inherit",
                    fontSize: l.text.includes("\n") ? "11px" : "12px",
                  }}>
                    {l.text}
                  </span>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
