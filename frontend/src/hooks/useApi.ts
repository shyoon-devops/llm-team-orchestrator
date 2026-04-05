import { useCallback, useEffect, useState } from "react";
import type { AgentStatus, BoardState, Pipeline } from "../types";

const API_BASE = "/api";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

/** Fetch pipeline list, auto-refreshes on interval. */
export function usePipelines(refreshInterval = 3000) {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchJson<{ items: Pipeline[] }>("/tasks");
      setPipelines(data.items);
    } catch {
      // Silently ignore fetch errors (server may be down)
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, refreshInterval);
    return () => clearInterval(id);
  }, [refresh, refreshInterval]);

  return { pipelines, loading, refresh };
}

/** Fetch board state. */
export function useBoard(refreshInterval = 3000) {
  const [board, setBoard] = useState<BoardState | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchJson<BoardState>("/board");
      setBoard(data);
    } catch {
      // Silently ignore
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, refreshInterval);
    return () => clearInterval(id);
  }, [refresh, refreshInterval]);

  return { board, refresh };
}

/** Fetch agent list. */
export function useAgents(refreshInterval = 3000) {
  const [agents, setAgents] = useState<AgentStatus[]>([]);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchJson<{ agents: AgentStatus[] }>("/agents");
      setAgents(data.agents);
    } catch {
      // Silently ignore
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, refreshInterval);
    return () => clearInterval(id);
  }, [refresh, refreshInterval]);

  return { agents, refresh };
}

/** Submit a new task. */
export async function submitTask(
  task: string,
  teamPreset?: string,
  targetRepo?: string,
): Promise<Pipeline> {
  return fetchJson<Pipeline>("/tasks", {
    method: "POST",
    body: JSON.stringify({
      task,
      team_preset: teamPreset || null,
      target_repo: targetRepo || null,
    }),
  });
}

/** Resume a failed/paused pipeline. */
export async function resumeTask(taskId: string): Promise<Pipeline> {
  return fetchJson<Pipeline>(`/tasks/${taskId}/resume`, {
    method: "POST",
  });
}

/** Cancel a pipeline. */
export async function cancelTask(taskId: string): Promise<void> {
  await fetch(`${API_BASE}/tasks/${taskId}`, { method: "DELETE" });
}
