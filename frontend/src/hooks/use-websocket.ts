import { useEffect, useCallback } from "react";

export function useWebSocket(onEvent: (event: string, data: unknown) => void) {
  const connect = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws`);

    ws.onmessage = (msg) => {
      try {
        const { event, data } = JSON.parse(msg.data);
        onEvent(event, data);
      } catch {
        // ignore
      }
    };

    ws.onclose = () => {
      setTimeout(connect, 5000);
    };

    return ws;
  }, [onEvent]);

  useEffect(() => {
    const ws = connect();
    return () => ws.close();
  }, [connect]);
}
