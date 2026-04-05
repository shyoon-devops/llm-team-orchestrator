// ★ PoC 전용
import { useEffect, useRef, useState, useCallback } from "react";
import type { OrchestratorEvent } from "../types/api";

const WS_URL = "ws://localhost:3000/ws/events";

export function useWebSocket() {
  const [events, setEvents] = useState<OrchestratorEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      setTimeout(connect, 3000); // auto-reconnect
    };
    ws.onmessage = (e) => {
      const event: OrchestratorEvent = JSON.parse(e.data);
      setEvents((prev) => [...prev, event]);
    };

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  return { events, connected };
}
