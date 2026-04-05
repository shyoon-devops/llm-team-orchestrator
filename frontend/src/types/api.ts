// ★ PoC 전용

export type AgentStatus = "idle" | "working" | "waiting" | "error" | "completed";
export type TaskStatus = "pending" | "running" | "completed" | "failed";

export interface Agent {
  id: string;
  provider: string;
  status: AgentStatus;
}

export interface PipelineStatus {
  task_id: string;
  task: string;
  status: TaskStatus;
  agents: Agent[];
  artifacts: string[];
  messages: Record<string, unknown>[];
  error: string;
}

export interface OrchestratorEvent {
  type: string;
  timestamp: number;
  node: string;
  data: Record<string, unknown>;
}

export interface Artifact {
  key: string;
  content: string;
}
