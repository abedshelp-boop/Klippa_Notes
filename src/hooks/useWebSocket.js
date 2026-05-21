import { useState, useEffect, useRef } from 'react';
import { debug } from '../lib/debug';

const WS_URL = 'ws://localhost:8765/ws';
const RECONNECT_DELAY = 3000;

export default function useWebSocket(onNote, onNoteUpdated) {
  const [status, setStatus] = useState('disconnected');
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const onNoteRef = useRef(onNote);
  const onNoteUpdatedRef = useRef(onNoteUpdated);
  const mountedRef = useRef(true);

  onNoteRef.current = onNote;
  onNoteUpdatedRef.current = onNoteUpdated;

  useEffect(() => {
    mountedRef.current = true;

    function connect() {
      if (!mountedRef.current) return;
      if (wsRef.current?.readyState === WebSocket.OPEN ||
          wsRef.current?.readyState === WebSocket.CONNECTING) {
        return;
      }

      try {
        const ws = new WebSocket(WS_URL);

        ws.onopen = () => {
          if (!mountedRef.current) { ws.close(); return; }
          setStatus('listening');
        };

        ws.onmessage = (event) => {
          if (!mountedRef.current) return;
          try {
            const message = JSON.parse(event.data);
            if (message.type === 'status') {
              setStatus(message.status);
            } else if (message.type === 'note') {
              onNoteRef.current?.(message.note);
            } else if (message.type === 'note_updated') {
              onNoteUpdatedRef.current?.(message.note);
            }
          } catch (err) {
            debug.error('WS', 'parse error', err);
          }
        };

        ws.onclose = () => {
          if (!mountedRef.current) return;
          setStatus('disconnected');
          wsRef.current = null;
          clearTimeout(reconnectTimer.current);
          reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
        };

        ws.onerror = () => {
          ws.close();
        };

        wsRef.current = ws;
      } catch {
        if (!mountedRef.current) return;
        setStatus('disconnected');
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
      }
    }

    connect();

    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  return { status };
}
