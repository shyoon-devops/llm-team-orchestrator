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
