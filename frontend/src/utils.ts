/**
 * Format elapsed time between two timestamps as a human-readable string.
 */
export function formatElapsed(started: string | null, completed: string | null): string {
  if (!started) return "--";
  const start = new Date(started).getTime();
  if (isNaN(start)) return "--";
  const end = completed ? new Date(completed).getTime() : Date.now();
  const sec = Math.max(0, Math.round((end - start) / 1000));
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`;
  return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
}

/**
 * Calculate checklist progress (done count / total count).
 */
export function checklistProgress(checklist: Array<{ status: string }> | undefined): { done: number; total: number } {
  if (!checklist || checklist.length === 0) return { done: 0, total: 0 };
  return {
    done: checklist.filter(c => c.status === "done").length,
    total: checklist.length,
  };
}

/**
 * Extract a short display title from a potentially long description.
 * Takes the first line, then cuts at the first period+space or at 60 chars.
 */
export function extractTitle(description: string): string {
  const firstLine = description.split("\n")[0] || "";
  const periodIdx = firstLine.indexOf(". ");
  const title =
    periodIdx > 0 && periodIdx < 60
      ? firstLine.slice(0, periodIdx + 1)
      : firstLine.slice(0, 60);
  return title + (description.length > title.length ? "..." : "");
}
