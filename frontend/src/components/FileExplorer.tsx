import { useCallback, useEffect, useState } from "react";

interface FileEntry {
  path: string;
  change_type: "added" | "modified" | "deleted";
  subtask_id: string;
}

interface FileDetail {
  path: string;
  change_type: string;
  content: string;
  subtask_id: string;
}

interface FileExplorerProps {
  taskId: string;
}

const API_BASE = "/api";

/**
 * FileExplorer: file tree + content viewer for pipeline artifacts.
 * Fetches from GET /api/tasks/{id}/files and GET /api/tasks/{id}/files/{path}.
 */
export function FileExplorer({ taskId }: FileExplorerProps) {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [selectedFile, setSelectedFile] = useState<FileDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchFiles = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}/files`);
      if (res.ok) {
        const data = await res.json();
        setFiles(data.files || []);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const handleSelect = async (path: string) => {
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}/files/${path}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedFile(data);
      }
    } catch {
      // ignore
    }
  };

  if (loading) {
    return <div className="empty-state">Loading files...</div>;
  }

  if (files.length === 0) {
    return <div className="empty-state">No files changed</div>;
  }

  const changeTypeColor: Record<string, string> = {
    added: "var(--success, #4c4)",
    modified: "var(--warning, #cc4)",
    deleted: "var(--danger, #e55)",
  };

  return (
    <div className="file-explorer" style={{ display: "flex", gap: 12 }}>
      <div className="file-tree" style={{ minWidth: 220 }}>
        <div className="panel-header">Files ({files.length})</div>
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {files.map((f) => (
            <li
              key={f.path}
              onClick={() => handleSelect(f.path)}
              style={{
                cursor: "pointer",
                padding: "4px 8px",
                fontSize: 13,
                fontFamily: "monospace",
                borderLeft: selectedFile?.path === f.path ? "3px solid var(--primary, #88f)" : "3px solid transparent",
              }}
            >
              <span style={{ color: changeTypeColor[f.change_type], marginRight: 6 }}>
                {f.change_type === "added" ? "+" : f.change_type === "deleted" ? "-" : "~"}
              </span>
              {f.path}
            </li>
          ))}
        </ul>
      </div>

      {selectedFile && (
        <div className="file-viewer" style={{ flex: 1 }}>
          <div className="panel-header">
            {selectedFile.path}
            <span style={{ color: changeTypeColor[selectedFile.change_type], marginLeft: 8, fontSize: 12 }}>
              ({selectedFile.change_type})
            </span>
          </div>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: 12, fontFamily: "monospace" }}>
            {selectedFile.content || "(empty)"}
          </pre>
        </div>
      )}
    </div>
  );
}
