import { useState } from "react";
import { AgentStatusPanel } from "./components/AgentStatusPanel";
import { EventLog } from "./components/EventLog";
import { KanbanBoard } from "./components/KanbanBoard";
import { LiveOutput } from "./components/LiveOutput";
import { PipelineDetail } from "./components/PipelineDetail";
import { PipelineList } from "./components/PipelineList";
import { ResultViewer } from "./components/ResultViewer";
import { TaskSubmitForm } from "./components/TaskSubmitForm";
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
 * - Left: KanbanBoard
 * - Right sidebar: TaskSubmitForm, AgentStatusPanel, EventLog
 * - Bottom (conditional): ResultViewer for selected pipeline
 */
export function App() {
  const { pipelines, loading, refresh } = usePipelines();
  const { board } = useBoard();
  const { agents } = useAgents();
  const { events, connected, clearEvents } = useWebSocket(WS_URL);
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

        <KanbanBoard board={board} />

        <div className="sidebar">
          <TaskSubmitForm onSubmitted={refresh} />
          <AgentStatusPanel agents={agents} />
          <EventLog events={events} connected={connected} onClear={clearEvents} />
          <LiveOutput
            events={events}
            taskId={selectedPipeline?.task_id}
          />
        </div>

        {selectedPipeline && (
          <PipelineDetail
            pipeline={selectedPipeline}
            onClose={() => setSelectedPipeline(null)}
          />
        )}

        {selectedPipeline && selectedPipeline.synthesis && (
          <ResultViewer
            pipeline={selectedPipeline}
            onClose={() => setSelectedPipeline(null)}
          />
        )}
      </div>
    </div>
  );
}
