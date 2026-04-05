// ★ PoC 전용
import type { OrchestratorEvent } from "../types/api";

interface Props {
  events: OrchestratorEvent[];
  connected: boolean;
}

const typeColors: Record<string, string> = {
  "node.started": "#4caf50",
  "node.completed": "#2196f3",
  "node.failed": "#f44336",
  "pipeline.started": "#ff9800",
  "pipeline.completed": "#4caf50",
  "pipeline.failed": "#f44336",
};

export function EventLog({ events, connected }: Props) {
  return (
    <div className="panel">
      <h2>
        Events{" "}
        <span className={`ws-status ${connected ? "connected" : "disconnected"}`}>
          {connected ? "LIVE" : "DISCONNECTED"}
        </span>
      </h2>
      <div className="event-list">
        {events.length === 0 && <div className="empty">No events yet</div>}
        {events
          .slice(-50)
          .reverse()
          .map((event, i) => (
            <div key={i} className="event-item">
              <span
                className="event-type"
                style={{ color: typeColors[event.type] || "#aaa" }}
              >
                {event.type}
              </span>
              {event.node && <span className="event-node">[{event.node}]</span>}
              <span className="event-time">
                {new Date(event.timestamp * 1000).toLocaleTimeString()}
              </span>
            </div>
          ))}
      </div>
    </div>
  );
}
