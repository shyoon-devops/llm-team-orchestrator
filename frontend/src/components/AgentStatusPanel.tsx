import type { AgentStatus } from "../types";

interface AgentStatusPanelProps {
  agents: AgentStatus[];
}

/**
 * AgentStatusPanel: shows agents with their current status.
 * Data comes from GET /api/agents.
 */
export function AgentStatusPanel({ agents }: AgentStatusPanelProps) {
  return (
    <div className="panel">
      <div className="panel-header">Agents</div>
      <div className="panel-body">
        {agents.length === 0 ? (
          <div className="empty-state">No active agents</div>
        ) : (
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
        )}
      </div>
    </div>
  );
}
