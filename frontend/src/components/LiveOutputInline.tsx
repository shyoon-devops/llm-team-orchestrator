import { useEffect, useRef, useState, useCallback } from "react";
import type { WSEvent } from "../types";
import type { OutputLine } from "../lib/streamParser";
import { parseStreamLine } from "../lib/streamParser";

interface LiveOutputInlineProps {
  events: WSEvent[];
  subtaskId: string;
}

/**
 * LiveOutputInline: renders live output filtered by subtask ID.
 * Used inside TaskDetailModal. No panel wrapper -- just the output lines.
 */
export function LiveOutputInline({ events, subtaskId }: LiveOutputInlineProps) {
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
      if (p.subtask_id !== subtaskId) continue;

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
  }, [events, subtaskId, scrollToBottom]);

  return (
    <div ref={containerRef} className="live-output-lines">
      {lines.length === 0 ? (
        <div className="live-output-waiting">Waiting for agent output...</div>
      ) : (
        lines.map((l, i) => (
          <div key={i} className="live-output-line">
            {l.lane && <span className="live-output-lane">{l.lane}</span>}
            <span className="live-output-icon">{l.icon}</span>
            {l.label && <span className="live-output-label">{l.label}</span>}
            <span className="live-output-text" style={{ color: l.color }}>{l.text}</span>
          </div>
        ))
      )}
    </div>
  );
}
