import { useEffect, useRef, useState } from "react";
import type { WSEvent } from "../types";

interface OutputLine {
  line: string;
  stream: string;
  lane: string;
  timestamp: string;
}

interface LiveOutputProps {
  events: WSEvent[];
  taskId?: string;
  subtaskId?: string;
}

/**
 * LiveOutput: CLI 실시간 출력 스트리밍 뷰.
 * WebSocket agent.output 이벤트를 필터링하여 터미널 스타일로 표시한다.
 */
export function LiveOutput({ events, taskId, subtaskId }: LiveOutputProps) {
  const [lines, setLines] = useState<OutputLine[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevCountRef = useRef(0);

  useEffect(() => {
    // 새로 추가된 이벤트만 처리
    const newEvents = events.slice(prevCountRef.current);
    prevCountRef.current = events.length;

    const newLines: OutputLine[] = [];
    for (const event of newEvents) {
      if (event.type !== "agent.output") continue;
      const p = event.payload || {};
      if (taskId && p.pipeline_id !== taskId) continue;
      if (subtaskId && p.subtask_id !== subtaskId) continue;

      const line = String(p.line || "");
      if (!line.trim()) continue;

      newLines.push({
        line,
        stream: String(p.stream || "stdout"),
        lane: String(p.lane || ""),
        timestamp: event.timestamp,
      });
    }

    if (newLines.length > 0) {
      setLines((prev) => {
        const next = [...prev, ...newLines];
        return next.length > 500 ? next.slice(-500) : next;
      });
    }
  }, [events, taskId, subtaskId]);

  // 자동 스크롤
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <div className="panel">
      <div className="panel-header">
        <span>Live Output ({lines.length} lines)</span>
        <button
          className="btn btn-small"
          onClick={() => {
            setLines([]);
            prevCountRef.current = 0;
          }}
        >
          Clear
        </button>
      </div>
      <div className="panel-body">
        <div
          style={{
            backgroundColor: "#1a1a2e",
            color: "#e0e0e0",
            fontFamily: "monospace",
            fontSize: "12px",
            padding: "8px",
            borderRadius: "4px",
            maxHeight: "400px",
            overflowY: "auto",
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
          }}
        >
          {lines.length === 0 ? (
            <div style={{ color: "#666" }}>
              Waiting for agent output...
            </div>
          ) : (
            lines.map((l, i) => {
              // stream-json 라인에서 유용한 정보 추출
              let displayLine = l.line;
              try {
                const parsed = JSON.parse(l.line);
                if (parsed.type === "assistant" && parsed.message?.content) {
                  const texts = parsed.message.content
                    .filter((c: { type: string }) => c.type === "text")
                    .map((c: { text: string }) => c.text);
                  if (texts.length > 0) {
                    displayLine = texts.join("");
                  }
                } else if (parsed.type === "result" && parsed.result) {
                  displayLine = `[RESULT] ${parsed.result}`;
                } else if (parsed.type === "user") {
                  const toolResults = parsed.message?.content
                    ?.filter((c: { type: string }) => c.type === "tool_result")
                    ?.map((c: { content: string }) => c.content);
                  if (toolResults?.length > 0) {
                    displayLine = toolResults.join("\n");
                  }
                }
              } catch {
                // Not JSON, display as-is
              }

              return (
                <div
                  key={i}
                  style={{
                    color: l.stream === "stderr" ? "#ffd700" : "#e0e0e0",
                    borderBottom: "1px solid #2a2a3e",
                    padding: "2px 0",
                  }}
                >
                  {l.lane && (
                    <span style={{ color: "#7b68ee", marginRight: "8px" }}>
                      [{l.lane}]
                    </span>
                  )}
                  {displayLine}
                </div>
              );
            })
          )}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}
