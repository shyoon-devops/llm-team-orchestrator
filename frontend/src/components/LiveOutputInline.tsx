import { useEffect, useRef, useState, useCallback } from "react";
import type { WSEvent } from "../types";

interface OutputLine {
  icon: string;
  label: string;
  text: string;
  color: string;
  lane: string;
  timestamp: string;
}

interface LiveOutputInlineProps {
  events: WSEvent[];
  subtaskId: string;
}

/* ── CLI JSONL event parsing (shared logic with LiveOutput) ── */

function formatClaudeEvent(ev: Record<string, unknown>): OutputLine | null {
  const t = ev.type as string;
  if (t === "system") return null;
  if (t === "assistant") {
    const msg = ev.message as Record<string, unknown> | undefined;
    const content = (msg?.content ?? []) as Array<Record<string, unknown>>;
    for (const c of content) {
      if (c.type === "text" && c.text) {
        return { icon: "\uD83D\uDCAC", label: "resp", text: String(c.text), color: "#e0e0e0", lane: "", timestamp: "" };
      }
      if (c.type === "thinking" && c.thinking) {
        const thought = String(c.thinking);
        return { icon: "\uD83E\uDDE0", label: "think", text: thought.length > 150 ? thought.slice(0, 150) + "\u2026" : thought, color: "#888", lane: "", timestamp: "" };
      }
      if (c.type === "tool_use") {
        const name = String(c.name || "tool");
        const input = c.input as Record<string, unknown> | undefined;
        let detail = "";
        if (input?.file_path) detail = String(input.file_path);
        else if (input?.command) detail = String(input.command).slice(0, 80);
        else if (input?.pattern) detail = String(input.pattern);
        return { icon: "\uD83D\uDD27", label: name, text: detail, color: "#7ecfff", lane: "", timestamp: "" };
      }
    }
    return null;
  }
  if (t === "user") {
    const msg = ev.message as Record<string, unknown> | undefined;
    const content = (msg?.content ?? []) as Array<Record<string, unknown>>;
    for (const c of content) {
      if (c.type === "tool_result") {
        const raw = String(c.content || "");
        const txt = tryPrettyJson(raw.slice(0, 500));
        return { icon: "\u2705", label: "result", text: txt, color: "#6fdc6f", lane: "", timestamp: "" };
      }
    }
    return null;
  }
  if (t === "result") {
    const isErr = ev.is_error as boolean;
    if (isErr) {
      return { icon: "\u274C", label: "error", text: String(ev.result || ""), color: "#ff6b6b", lane: "", timestamp: "" };
    }
    return { icon: "\uD83C\uDFC1", label: "done", text: String(ev.result || "").slice(0, 200), color: "#6fdc6f", lane: "", timestamp: "" };
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
      return { icon: "\uD83D\uDCAC", label: "resp", text: String(item.text || ""), color: "#e0e0e0", lane: "", timestamp: "" };
    }
    if (itemType === "command_execution") {
      const cmd = String(item.command || "").replace(/^\/usr\/bin\/zsh -lc /, "").slice(0, 80);
      if (t === "item.started") {
        return { icon: "\u26A1", label: "exec", text: `$ ${cmd}`, color: "#ffd700", lane: "", timestamp: "" };
      }
      const rawOutput = String(item.aggregated_output || "").trim();
      const output = tryPrettyJson(rawOutput.slice(0, 500));
      const code = item.exit_code as number;
      const statusIcon = code === 0 ? "\u2705" : "\u274C";
      return { icon: statusIcon, label: `exit ${code}`, text: output || cmd, color: code === 0 ? "#6fdc6f" : "#ff6b6b", lane: "", timestamp: "" };
    }
    if (itemType === "file_change") {
      const changes = (item.changes ?? []) as Array<Record<string, unknown>>;
      const files = changes.map(c => {
        const p = String(c.path || "").split("/").slice(-2).join("/");
        return `${c.kind === "add" ? "+" : "~"}${p}`;
      }).join(", ");
      const icon = t === "item.started" ? "\uD83D\uDCDD" : "\u2705";
      return { icon, label: "file", text: files, color: "#7ecfff", lane: "", timestamp: "" };
    }
    return null;
  }
  if (t === "turn.completed") {
    const usage = ev.usage as Record<string, unknown> | undefined;
    if (usage) {
      const inp = usage.input_tokens ?? 0;
      const out = usage.output_tokens ?? 0;
      return { icon: "\uD83C\uDFC1", label: "done", text: `tokens: ${inp}\u2192${out}`, color: "#888", lane: "", timestamp: "" };
    }
    return { icon: "\uD83C\uDFC1", label: "done", text: "", color: "#888", lane: "", timestamp: "" };
  }
  if (t === "error") {
    return { icon: "\u274C", label: "error", text: String(ev.message || ""), color: "#ff6b6b", lane: "", timestamp: "" };
  }
  if (t === "turn.failed") {
    const err = ev.error as Record<string, unknown> | undefined;
    return { icon: "\u274C", label: "fail", text: String(err?.message || ""), color: "#ff6b6b", lane: "", timestamp: "" };
  }
  return null;
}

function formatGeminiEvent(ev: Record<string, unknown>): OutputLine | null {
  const t = ev.type as string;
  if (t === "init") {
    return { icon: "\uD83D\uDE80", label: "init", text: `model: ${ev.model || "gemini"}`, color: "#888", lane: "", timestamp: "" };
  }
  if (t === "message") {
    const role = ev.role as string;
    if (role === "assistant") {
      return { icon: "\uD83D\uDCAC", label: "resp", text: String(ev.content || ""), color: "#e0e0e0", lane: "", timestamp: "" };
    }
    return null;
  }
  if (t === "result") {
    const stats = ev.stats as Record<string, unknown> | undefined;
    const dur = stats?.duration_ms ? `${Math.round(Number(stats.duration_ms) / 1000)}s` : "";
    const tok = stats?.total_tokens || "";
    return { icon: "\uD83C\uDFC1", label: "done", text: `${dur} ${tok ? `(${tok} tokens)` : ""}`.trim(), color: "#6fdc6f", lane: "", timestamp: "" };
  }
  return null;
}

function tryPrettyJson(text: string): string {
  if (text.startsWith("{") || text.startsWith("[")) {
    try {
      return JSON.stringify(JSON.parse(text), null, 2);
    } catch { /* not valid JSON */ }
  }
  return text;
}

function parseStreamLine(rawLine: string): OutputLine | null {
  let ev: Record<string, unknown>;
  try {
    ev = JSON.parse(rawLine);
  } catch {
    if (rawLine.trim()) {
      return { icon: "\uD83D\uDCC4", label: "", text: rawLine, color: "#e0e0e0", lane: "", timestamp: "" };
    }
    return null;
  }
  const t = ev.type as string;
  if (t === "system" || t === "assistant" || t === "rate_limit_event" ||
      (t === "user" && ev.message) ||
      (t === "result" && "is_error" in ev)) {
    return formatClaudeEvent(ev);
  }
  if (t === "thread.started" || t === "turn.started" || t === "turn.completed" ||
      t === "item.completed" || t === "item.started" ||
      t === "error" || t === "turn.failed") {
    return formatCodexEvent(ev);
  }
  if (t === "init" || t === "message" || (t === "result" && "stats" in ev)) {
    return formatGeminiEvent(ev);
  }
  return { icon: "\uD83D\uDCCB", label: t || "json", text: JSON.stringify(ev, null, 2), color: "#8b949e", lane: "", timestamp: "" };
}

/**
 * LiveOutputInline: renders live output filtered by subtask ID.
 * Used inside TaskDetailModal. No panel wrapper — just the output lines.
 */
export function LiveOutputInline({ events, subtaskId }: LiveOutputInlineProps) {
  const [lines, setLines] = useState<OutputLine[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const processedRef = useRef(new Set<string>());

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      if (containerRef.current) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight;
      }
    });
  }, []);

  useEffect(() => {
    const newLines: OutputLine[] = [];
    for (const event of events) {
      if (event.type !== "agent.output") continue;

      const eventKey = `${event.timestamp}-${(event.payload || {}).subtask_id || ""}-${String((event.payload || {}).line || "").slice(0, 50)}`;
      if (processedRef.current.has(eventKey)) continue;
      processedRef.current.add(eventKey);

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

    if (processedRef.current.size > 2000) {
      const arr = Array.from(processedRef.current);
      processedRef.current = new Set(arr.slice(-1000));
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
