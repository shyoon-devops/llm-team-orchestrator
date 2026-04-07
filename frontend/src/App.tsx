import { useState } from "react";
import { AgentStatusPanel } from "./components/AgentStatusPanel";
import { EventLog } from "./components/EventLog";
import { KanbanBoard } from "./components/KanbanBoard";
import { PipelineDetail } from "./components/PipelineDetail";
import { PipelineList } from "./components/PipelineList";
import { TaskSubmitForm } from "./components/TaskSubmitForm";
import { TeamPresetsPanel } from "./components/TeamPresetsPanel";
import { useAgents, useBoard, usePipelines } from "./hooks/useApi";
import { useWebSocket } from "./hooks/useWebSocket";
import type { Pipeline } from "./types";

const WS_URL =
  window.location.protocol === "https:"
    ? `wss://${window.location.host}/ws/events`
    : `ws://${window.location.host}/ws/events`;

/**
 * Root App component for the Agent Team Orchestrator dashboard.
 *
 * Layout:
 * - Top: PipelineList (full width)
 * - Below pipeline list: PipelineDetail summary (when selected)
 * - Left: KanbanBoard (main area)
 * - Right sidebar: TaskSubmitForm, TeamPresetsPanel, AgentStatusPanel, EventLog
 * - Task detail: Jira-style side panel (modal overlay from KanbanBoard)
 */
export function App() {
  const { pipelines, loading, refresh } = usePipelines();
  const { board } = useBoard();
  const { agents } = useAgents();
  const { events, outputEvents, connected, clearEvents } = useWebSocket(WS_URL);
  const [selectedPipeline, setSelectedPipeline] = useState<Pipeline | null>(null);

  return (
    <div className="app">
      <header className="header">
        <h1>Agent Team Orchestrator</h1>
        <div className="connection-status">
          <span className={`status-dot ${connected ? "connected" : "disconnected"}`} />
          {connected ? "Connected" : "Disconnected"}
        </div>
      </header>

      <div className="main-content">
        <PipelineList
          pipelines={pipelines}
          loading={loading}
          onSelect={setSelectedPipeline}
          onRefresh={refresh}
        />

        {selectedPipeline && (
          <PipelineDetail
            pipeline={selectedPipeline}
            onClose={() => setSelectedPipeline(null)}
          />
        )}

        <KanbanBoard board={board} outputEvents={outputEvents} />

        <div className="sidebar">
          <TaskSubmitForm onSubmitted={refresh} />
          <TeamPresetsPanel />
          <AgentStatusPanel agents={agents} />
          <EventLog events={events} connected={connected} onClear={clearEvents} />
        </div>
      </div>
    </div>
  );
}
