import type { WSEvent } from "../types";

interface EventLogProps {
  events: WSEvent[];
  connected: boolean;
  onClear: () => void;
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString();
  } catch {
    return iso;
  }
}

/**
 * EventLog: real-time WebSocket event stream display.
 * Events arrive via ws://host/ws/events.
 */
export function EventLog({ events, connected, onClear }: EventLogProps) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span>
          Event Log
          {connected ? "" : " (disconnected)"}
        </span>
        <button className="btn btn-small" onClick={onClear}>
          Clear
        </button>
      </div>
      <div className="panel-body">
        <div className="event-log">
          {events.length === 0 ? (
            <div className="empty-state">
              {connected ? "Waiting for events..." : "WebSocket disconnected"}
            </div>
          ) : (
            [...events].reverse().map((event, idx) => (
              <div key={`${event.timestamp}-${idx}`} className="event-item">
                <div>
                  <span className="event-type">{event.type}</span>
                </div>
                <div className="event-time">{formatTimestamp(event.timestamp)}</div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
