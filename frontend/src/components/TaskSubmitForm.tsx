import { useState } from "react";
import { submitTask } from "../hooks/useApi";

interface TaskSubmitFormProps {
  onSubmitted: () => void;
}

/**
 * TaskSubmitForm: submit a new task with optional team_preset and target_repo.
 * Calls POST /api/tasks.
 */
export function TaskSubmitForm({ onSubmitted }: TaskSubmitFormProps) {
  const [task, setTask] = useState("");
  const [teamPreset, setTeamPreset] = useState("");
  const [targetRepo, setTargetRepo] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim()) return;

    setSubmitting(true);
    setError("");

    try {
      await submitTask(task, teamPreset || undefined, targetRepo || undefined);
      setTask("");
      setTeamPreset("");
      setTargetRepo("");
      onSubmitted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">Submit Task</div>
      <div className="panel-body">
        <form className="submit-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="task-input">Task Description</label>
            <textarea
              id="task-input"
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="Describe the coding task..."
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="preset-input">Team Preset (optional)</label>
            <input
              id="preset-input"
              type="text"
              value={teamPreset}
              onChange={(e) => setTeamPreset(e.target.value)}
              placeholder="e.g., feature-team"
            />
          </div>
          <div className="form-group">
            <label htmlFor="repo-input">Target Repo (optional)</label>
            <input
              id="repo-input"
              type="text"
              value={targetRepo}
              onChange={(e) => setTargetRepo(e.target.value)}
              placeholder="e.g., /home/user/project"
            />
          </div>
          {error && (
            <div style={{ color: "var(--accent-red)", fontSize: 12 }}>{error}</div>
          )}
          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting || !task.trim()}
          >
            {submitting ? "Submitting..." : "Submit Task"}
          </button>
        </form>
      </div>
    </div>
  );
}
