/** Pipeline status enum matching backend PipelineStatus. */
export type PipelineStatus =
  | "pending"
  | "planning"
  | "running"
  | "synthesizing"
  | "completed"
  | "partial_failure"
  | "failed"
  | "cancelled";

/** Task state on the kanban board. */
export type TaskState = "backlog" | "todo" | "in_progress" | "done" | "failed";

/** SubTask within a pipeline. */
export interface SubTask {
  id: string;
  task_id: string;
  description: string;
  assigned_cli: string | null;
  assigned_preset: string;
  priority: number;
  depends_on: string[];
  status: PipelineStatus;
}

/** Worker execution result. */
export interface WorkerResult {
  subtask_id: string;
  executor_type: string;
  cli: string | null;
  output: string;
  files_changed: FileChange[];
  tokens_used: number;
  duration_ms: number;
  error: string;
}

/** File change info. */
export interface FileChange {
  path: string;
  change_type: "added" | "modified" | "deleted";
  content: string;
}

/** Pipeline model. */
export interface Pipeline {
  task_id: string;
  task: string;
  status: PipelineStatus;
  team_preset: string;
  target_repo: string;
  subtasks: SubTask[];
  results: WorkerResult[];
  synthesis: string;
  merged: boolean;
  error: string;
  started_at: string | null;
  completed_at: string | null;
}

/** TaskItem on the kanban board. */
export interface TaskItem {
  id: string;
  title: string;
  description: string;
  lane: string;
  state: TaskState;
  priority: number;
  depends_on: string[];
  assigned_to: string | null;
  result: string;
  error: string;
  retry_count: number;
  max_retries: number;
  pipeline_id: string;
}

/** Agent worker status. */
export interface AgentStatus {
  worker_id: string;
  lane: string;
  status: string;
  current_task: string | null;
}

/** WebSocket event from server. */
export interface WSEvent {
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

/** Board state from GET /api/board. */
export interface BoardState {
  lanes: Record<string, Record<TaskState, TaskItem[]>>;
  summary: {
    total: number;
    by_state: Record<TaskState, number>;
  };
}
