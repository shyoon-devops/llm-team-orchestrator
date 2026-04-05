import { useCallback, useEffect, useRef, useState } from "react";
import type { WSEvent } from "../types";

const MAX_RECONNECT_DELAY = 30_000;
const MAX_EVENTS = 200;

interface UseWebSocketReturn {
  events: WSEvent[];
  connected: boolean;
  clearEvents: () => void;
}

/**
 * WebSocket hook for real-time event streaming.
 *
 * Connects to ws://host/ws/events and provides:
 * - events: rolling list of recent events (max 200)
 * - connected: connection status
 * - clearEvents: clears the event buffer
 *
 * Implements exponential backoff reconnection per the protocol spec.
 */
export function useWebSocket(url: string): UseWebSocketReturn {
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const mountedRef = useRef(true);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    function connect() {
      if (!mountedRef.current) return;

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setConnected(true);
        attemptRef.current = 0;
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const data = JSON.parse(event.data) as WSEvent;
          setEvents((prev) => {
            const next = [...prev, data];
            return next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next;
          });
        } catch {
          // Ignore non-JSON messages (ping, etc.)
        }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setConnected(false);
        wsRef.current = null;

        // Exponential backoff reconnect
        attemptRef.current += 1;
        const delay = Math.min(
          Math.pow(2, attemptRef.current - 1) * 1000,
          MAX_RECONNECT_DELAY,
        );
        setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      mountedRef.current = false;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [url]);

  return { events, connected, clearEvents };
}
