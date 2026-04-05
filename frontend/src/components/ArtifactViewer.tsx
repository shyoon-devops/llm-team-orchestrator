// ★ PoC 전용
import { useEffect, useState } from "react";
import { fetchJson } from "../hooks/useApi";

interface ArtifactContent {
  key: string;
  content: string;
}

export function ArtifactViewer() {
  const [artifacts, setArtifacts] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");

  useEffect(() => {
    const load = () => fetchJson<string[]>("/artifacts").then(setArtifacts);
    load();
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, []);

  const viewArtifact = async (key: string) => {
    setSelected(key);
    const data = await fetchJson<ArtifactContent>(`/artifacts/${key}`);
    setContent(data.content || "");
  };

  return (
    <div className="panel">
      <h2>Artifacts</h2>
      <div className="artifact-list">
        {artifacts.length === 0 && <div className="empty">No artifacts yet</div>}
        {artifacts.map((key) => (
          <button
            key={key}
            className={`artifact-btn ${selected === key ? "active" : ""}`}
            onClick={() => viewArtifact(key)}
          >
            {key}
          </button>
        ))}
      </div>
      {selected && (
        <pre className="artifact-content">{content}</pre>
      )}
    </div>
  );
}
