// ★ PoC 전용 — LLM Team Orchestrator Dashboard
import { AgentStatusPanel } from "./components/AgentStatusPanel";
import { TaskSubmitForm } from "./components/TaskSubmitForm";
import { EventLog } from "./components/EventLog";
import { ArtifactViewer } from "./components/ArtifactViewer";
import { useWebSocket } from "./hooks/useWebSocket";
import "./App.css";

function App() {
  const { events, connected } = useWebSocket();

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>LLM Team Orchestrator</h1>
        <span className="version">v0.4.0-poc</span>
      </header>
      <div className="dashboard-grid">
        <div className="sidebar">
          <AgentStatusPanel />
          <TaskSubmitForm />
        </div>
        <div className="main">
          <EventLog events={events} connected={connected} />
          <ArtifactViewer />
        </div>
      </div>
    </div>
  );
}

export default App;
