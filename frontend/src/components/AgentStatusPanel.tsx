// ★ PoC 전용
import { useEffect, useState } from "react";
import type { Agent } from "../types/api";
import { fetchJson } from "../hooks/useApi";

const statusColors: Record<string, string> = {
  idle: "#888",
  working: "#4caf50",
  waiting: "#ff9800",
  error: "#f44336",
  completed: "#2196f3",
};

export function AgentStatusPanel() {
  const [agents, setAgents] = useState<Agent[]>([]);

  useEffect(() => {
    const load = () => fetchJson<Agent[]>("/agents").then(setAgents);
    load();
    const interval = setInterval(load, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="panel">
      <h2>Agents</h2>
      {agents.map((agent) => (
        <div key={agent.id} className="agent-card">
          <span
            className="status-dot"
            style={{ backgroundColor: statusColors[agent.status] || "#888" }}
          />
          <span className="agent-name">{agent.id}</span>
          <span className="agent-provider">{agent.provider}</span>
          <span className="agent-status">{agent.status}</span>
        </div>
      ))}
    </div>
  );
}
