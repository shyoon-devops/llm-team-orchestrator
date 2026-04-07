import { useEffect, useRef, useState } from "react";
import type { WSEvent } from "../types";

interface OutputLine {
  icon: string;
  label: string;
  text: string;
  color: string;
  lane: string;
  timestamp: string;
}

interface LiveOutputProps {
  events: WSEvent[];
  taskId?: string;
  subtaskId?: string;
}

/* ── CLI JSONL 이벤트 → 사람이 읽을 수 있는 형태로 변환 ── */

function formatClaudeEvent(ev: Record<string, unknown>): OutputLine | null {
  const t = ev.type as string;

  if (t === "system") return null; // init 이벤트 무시

  if (t === "assistant") {
    const msg = ev.message as Record<string, unknown> | undefined;
    const content = (msg?.content ?? []) as Array<Record<string, unknown>>;
    for (const c of content) {
      if (c.type === "text" && c.text) {
        return { icon: "💬", label: "응답", text: String(c.text), color: "#e0e0e0", lane: "", timestamp: "" };
      }
      if (c.type === "thinking" && c.thinking) {
        const thought = String(c.thinking);
        return { icon: "🧠", label: "사고", text: thought.length > 150 ? thought.slice(0, 150) + "…" : thought, color: "#888", lane: "", timestamp: "" };
      }
      if (c.type === "tool_use") {
        const name = String(c.name || "tool");
        const input = c.input as Record<string, unknown> | undefined;
        let detail = "";
        if (input?.file_path) detail = String(input.file_path);
        else if (input?.command) detail = String(input.command).slice(0, 80);
        else if (input?.pattern) detail = String(input.pattern);
        return { icon: "🔧", label: name, text: detail, color: "#7ecfff", lane: "", timestamp: "" };
      }
    }
    return null;
  }

  if (t === "user") {
    const msg = ev.message as Record<string, unknown> | undefined;
    const content = (msg?.content ?? []) as Array<Record<string, unknown>>;
    for (const c of content) {
      if (c.type === "tool_result") {
        const txt = String(c.content || "").slice(0, 120);
        return { icon: "✅", label: "결과", text: txt, color: "#6fdc6f", lane: "", timestamp: "" };
      }
    }
    return null;
  }

  if (t === "result") {
    const isErr = ev.is_error as boolean;
    if (isErr) {
      return { icon: "❌", label: "에러", text: String(ev.result || ""), color: "#ff6b6b", lane: "", timestamp: "" };
    }
    return { icon: "🏁", label: "완료", text: String(ev.result || "").slice(0, 200), color: "#6fdc6f", lane: "", timestamp: "" };
  }

  if (t === "rate_limit_event") return null;

  return null;
}

function formatCodexEvent(ev: Record<string, unknown>): OutputLine | null {
  const t = ev.type as string;

  if (t === "thread.started" || t === "turn.started") return null;

  if (t === "item.completed" || t === "item.started") {
    const item = ev.item as Record<string, unknown> | undefined;
    if (!item) return null;
    const itemType = item.type as string;

    if (itemType === "agent_message") {
      return { icon: "💬", label: "응답", text: String(item.text || ""), color: "#e0e0e0", lane: "", timestamp: "" };
    }
    if (itemType === "command_execution") {
      const cmd = String(item.command || "").replace(/^\/usr\/bin\/zsh -lc /, "").slice(0, 80);
      if (t === "item.started") {
        return { icon: "⚡", label: "실행", text: `$ ${cmd}`, color: "#ffd700", lane: "", timestamp: "" };
      }
      const output = String(item.aggregated_output || "").trim().slice(0, 120);
      const code = item.exit_code as number;
      const statusIcon = code === 0 ? "✅" : "❌";
      return { icon: statusIcon, label: `exit ${code}`, text: output || cmd, color: code === 0 ? "#6fdc6f" : "#ff6b6b", lane: "", timestamp: "" };
    }
    if (itemType === "file_change") {
      const changes = (item.changes ?? []) as Array<Record<string, unknown>>;
      const files = changes.map(c => {
        const p = String(c.path || "").split("/").slice(-2).join("/");
        return `${c.kind === "add" ? "+" : "~"}${p}`;
      }).join(", ");
      const icon = t === "item.started" ? "📝" : "✅";
      return { icon, label: "파일", text: files, color: "#7ecfff", lane: "", timestamp: "" };
    }
    return null;
  }

  if (t === "turn.completed") {
    const usage = ev.usage as Record<string, unknown> | undefined;
    if (usage) {
      const inp = usage.input_tokens ?? 0;
      const out = usage.output_tokens ?? 0;
      return { icon: "🏁", label: "완료", text: `tokens: ${inp}→${out}`, color: "#888", lane: "", timestamp: "" };
    }
    return { icon: "🏁", label: "완료", text: "", color: "#888", lane: "", timestamp: "" };
  }

  if (t === "error") {
    return { icon: "❌", label: "에러", text: String(ev.message || ""), color: "#ff6b6b", lane: "", timestamp: "" };
  }
  if (t === "turn.failed") {
    const err = ev.error as Record<string, unknown> | undefined;
    return { icon: "❌", label: "실패", text: String(err?.message || ""), color: "#ff6b6b", lane: "", timestamp: "" };
  }

  return null;
}

function formatGeminiEvent(ev: Record<string, unknown>): OutputLine | null {
  const t = ev.type as string;

  if (t === "init") {
    return { icon: "🚀", label: "시작", text: `model: ${ev.model || "gemini"}`, color: "#888", lane: "", timestamp: "" };
  }
  if (t === "message") {
    const role = ev.role as string;
    if (role === "assistant") {
      return { icon: "💬", label: "응답", text: String(ev.content || ""), color: "#e0e0e0", lane: "", timestamp: "" };
    }
    return null; // user 메시지 무시
  }
  if (t === "result") {
    const stats = ev.stats as Record<string, unknown> | undefined;
    const dur = stats?.duration_ms ? `${Math.round(Number(stats.duration_ms) / 1000)}s` : "";
    const tok = stats?.total_tokens || "";
    return { icon: "🏁", label: "완료", text: `${dur} ${tok ? `(${tok} tokens)` : ""}`.trim(), color: "#6fdc6f", lane: "", timestamp: "" };
  }

  return null;
}

function parseStreamLine(rawLine: string): OutputLine | null {
  let ev: Record<string, unknown>;
  try {
    ev = JSON.parse(rawLine);
  } catch {
    // 비JSON 라인 — plain text로 표시
    if (rawLine.trim()) {
      return { icon: "📄", label: "", text: rawLine, color: "#e0e0e0", lane: "", timestamp: "" };
    }
    return null;
  }

  const t = ev.type as string;

  // Claude: system, assistant, user, result, rate_limit_event
  if (t === "system" || t === "assistant" || t === "rate_limit_event" ||
      (t === "user" && ev.message) ||
      (t === "result" && "is_error" in ev)) {
    return formatClaudeEvent(ev);
  }

  // Codex: thread.started, turn.started, item.*, turn.completed, error, turn.failed
  if (t === "thread.started" || t === "turn.started" || t === "turn.completed" ||
      t === "item.completed" || t === "item.started" ||
      t === "error" || t === "turn.failed") {
    return formatCodexEvent(ev);
  }

  // Gemini: init, message, result
  if (t === "init" || t === "message" || (t === "result" && "stats" in ev)) {
    return formatGeminiEvent(ev);
  }

  // 알 수 없는 JSON 이벤트
  return { icon: "❓", label: t, text: rawLine.slice(0, 100), color: "#666", lane: "", timestamp: "" };
}

/* ── 컴포넌트 ── */

export function LiveOutput({ events, taskId, subtaskId }: LiveOutputProps) {
  const [lines, setLines] = useState<OutputLine[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevCountRef = useRef(0);

  useEffect(() => {
    const newEvents = events.slice(prevCountRef.current);
    prevCountRef.current = events.length;

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
    }
  }, [events, taskId, subtaskId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <div className="panel">
      <div className="panel-header">
        <span>Live Output ({lines.length})</span>
        <button
          className="btn btn-small"
          onClick={() => { setLines([]); prevCountRef.current = 0; }}
        >
          Clear
        </button>
      </div>
      <div className="panel-body">
        <div style={{
          backgroundColor: "#0d1117",
          color: "#e6edf3",
          fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
          fontSize: "12px",
          padding: "8px 12px",
          borderRadius: "6px",
          maxHeight: "400px",
          overflowY: "auto",
          lineHeight: 1.6,
        }}>
          {lines.length === 0 ? (
            <div style={{ color: "#484f58" }}>Waiting for agent output...</div>
          ) : (
            lines.map((l, i) => (
              <div key={i} style={{
                display: "flex",
                gap: "6px",
                padding: "1px 0",
                borderBottom: "1px solid #21262d",
                alignItems: "baseline",
              }}>
                {l.lane && (
                  <span style={{
                    color: "#8b949e",
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
                    color: "#8b949e",
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
                }}>
                  {l.text}
                </span>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}
