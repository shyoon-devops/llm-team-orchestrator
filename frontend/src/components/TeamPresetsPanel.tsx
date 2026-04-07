import { useEffect, useState } from "react";

interface TeamAgentDef {
  preset: string;
  overrides: Record<string, unknown>;
}

interface TeamTaskDef {
  description: string;
  agent: string;
  depends_on: string[];
}

interface TeamPresetInfo {
  name: string;
  description: string;
  agents: Record<string, TeamAgentDef>;
  tasks: Record<string, TeamTaskDef>;
  workflow: string;
  synthesis_strategy: string;
}

/**
 * TeamPresetsPanel: shows registered team presets with accordion detail.
 * Data comes from GET /api/presets/teams.
 * Collapsible panel — collapsed by default.
 */
export function TeamPresetsPanel() {
  const [presets, setPresets] = useState<TeamPresetInfo[]>([]);
  const [panelOpen, setPanelOpen] = useState(false);
  const [expandedTeam, setExpandedTeam] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/presets/teams")
      .then((r) => r.json())
      .then((data) => setPresets(data.presets || []))
      .catch(() => {});
  }, []);

  return (
    <div className="panel">
      <div
        className="panel-header"
        style={{ cursor: "pointer", userSelect: "none" }}
        onClick={() => setPanelOpen(!panelOpen)}
      >
        <span>Teams</span>
        <span style={{ fontSize: 12, fontWeight: 400 }}>
          {presets.length} preset{presets.length !== 1 ? "s" : ""} {panelOpen ? "\u25BC" : "\u25B6"}
        </span>
      </div>
      {panelOpen && (
        <div className="panel-body">
          {presets.length === 0 ? (
            <div className="empty-state">No team presets</div>
          ) : (
            presets.map((team) => {
              const agentCount = Object.keys(team.agents).length;
              const taskCount = Object.keys(team.tasks).length;
              const isExpanded = expandedTeam === team.name;
              return (
                <div key={team.name} style={{ marginBottom: 8 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      cursor: "pointer",
                      padding: "4px 0",
                    }}
                    onClick={() =>
                      setExpandedTeam(isExpanded ? null : team.name)
                    }
                  >
                    <div>
                      <span style={{ fontWeight: 600 }}>{team.name}</span>
                      {team.description && (
                        <span
                          style={{
                            fontSize: 11,
                            color: "var(--text-muted)",
                            marginLeft: 8,
                          }}
                        >
                          {team.description}
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      {agentCount}A / {taskCount}T / {team.workflow}{" "}
                      {isExpanded ? "\u25BC" : "\u25B6"}
                    </span>
                  </div>
                  {isExpanded && (
                    <div
                      style={{
                        fontSize: 12,
                        padding: "8px",
                        background: "var(--bg-secondary, #1a1a2e)",
                        borderRadius: 4,
                      }}
                    >
                      {/* Agents */}
                      <div style={{ marginBottom: 8 }}>
                        <strong>Agents:</strong>
                        <ul style={{ margin: "4px 0", paddingLeft: 16 }}>
                          {Object.entries(team.agents).map(([name, def]) => (
                            <li key={name} style={{ fontSize: 11 }}>
                              <strong>{name}</strong> (preset: {def.preset})
                            </li>
                          ))}
                        </ul>
                      </div>
                      {/* Tasks */}
                      <div>
                        <strong>Tasks:</strong>
                        <ul style={{ margin: "4px 0", paddingLeft: 16 }}>
                          {Object.entries(team.tasks).map(([name, def]) => (
                            <li key={name} style={{ fontSize: 11 }}>
                              <strong>{name}</strong>
                              {" \u2192 "}
                              {def.agent}
                              {def.depends_on.length > 0 && (
                                <span style={{ color: "var(--text-muted)" }}>
                                  {" "}
                                  (deps: {def.depends_on.join(", ")})
                                </span>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
