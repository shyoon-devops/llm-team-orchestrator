import { useEffect, useState } from "react";
import type { AgentStatus } from "../types";

interface AgentPresetInfo {
  name: string;
  description: string;
  preferred_cli: string | null;
  tags: string[];
  persona: {
    role: string;
    goal: string;
    constraints: string[];
  };
  limits: {
    timeout: number;
    max_turns: number;
  };
}

interface AgentStatusPanelProps {
  agents: AgentStatus[];
}

/**
 * AgentStatusPanel: shows agents with their current status and preset config.
 * Data comes from GET /api/agents + GET /api/presets/agents.
 */
export function AgentStatusPanel({ agents }: AgentStatusPanelProps) {
  const [presets, setPresets] = useState<AgentPresetInfo[]>([]);
  const [expandedPreset, setExpandedPreset] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/presets/agents")
      .then((r) => r.json())
      .then((data) => setPresets(data.presets || []))
      .catch(() => {});
  }, []);

  return (
    <div className="panel">
      <div className="panel-header">Agents</div>
      <div className="panel-body">
        {/* Active workers */}
        {agents.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>
              Active Workers
            </div>
            <ul className="agent-list">
              {agents.map((agent) => (
                <li key={agent.worker_id} className="agent-item">
                  <div>
                    <span className="agent-name">{agent.worker_id}</span>
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      Lane: {agent.lane}
                    </div>
                  </div>
                  <span className={`status-badge ${agent.status}`}>
                    {agent.status}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Agent presets */}
        {presets.length > 0 && (
          <div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>
              Registered Presets
            </div>
            {presets.map((p) => (
              <div key={p.name} style={{ marginBottom: 8 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    cursor: "pointer",
                    padding: "4px 0",
                  }}
                  onClick={() =>
                    setExpandedPreset(expandedPreset === p.name ? null : p.name)
                  }
                >
                  <span style={{ fontWeight: 600 }}>{p.name}</span>
                  <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                    {p.preferred_cli || "auto"} {expandedPreset === p.name ? "▼" : "▶"}
                  </span>
                </div>
                {expandedPreset === p.name && (
                  <div
                    style={{
                      fontSize: 12,
                      padding: "8px",
                      background: "var(--bg-secondary, #1a1a2e)",
                      borderRadius: 4,
                    }}
                  >
                    <div><strong>Role:</strong> {p.persona.role}</div>
                    <div><strong>Goal:</strong> {p.persona.goal}</div>
                    <div><strong>Timeout:</strong> {p.limits.timeout}s</div>
                    <div><strong>Tags:</strong> {p.tags?.join(", ") || "-"}</div>
                    {p.persona.constraints?.length > 0 && (
                      <div style={{ marginTop: 4 }}>
                        <strong>Constraints:</strong>
                        <ul style={{ margin: "4px 0", paddingLeft: 16 }}>
                          {p.persona.constraints.map((c, i) => (
                            <li key={i} style={{ fontSize: 11 }}>{c}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {agents.length === 0 && presets.length === 0 && (
          <div className="empty-state">No agents</div>
        )}
      </div>
    </div>
  );
}
