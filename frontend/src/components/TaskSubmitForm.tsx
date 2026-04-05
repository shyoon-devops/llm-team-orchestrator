// ★ PoC 전용
import { useState } from "react";
import { postJson } from "../hooks/useApi";

interface TaskResponse {
  task_id: string;
  task: string;
  status: string;
}

export function TaskSubmitForm() {
  const [task, setTask] = useState("");
  const [submitted, setSubmitted] = useState<TaskResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim()) return;
    setLoading(true);
    try {
      const result = await postJson<TaskResponse>("/tasks", { task });
      setSubmitted(result);
      setTask("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel">
      <h2>Submit Task</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="Describe the task..."
          className="task-input"
          disabled={loading}
        />
        <button type="submit" className="submit-btn" disabled={loading || !task.trim()}>
          {loading ? "Submitting..." : "Run Pipeline"}
        </button>
      </form>
      {submitted && (
        <div className="submitted-info">
          Task <code>{submitted.task_id}</code> — {submitted.status}
        </div>
      )}
    </div>
  );
}
