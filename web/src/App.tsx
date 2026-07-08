import { useEffect, useMemo, useReducer, useState } from 'react';
import type { Node } from 'reactflow';
import { ChatPanel } from './components/ChatPanel';
import { EventTimeline } from './components/EventTimeline';
import { FlowCanvas } from './components/FlowCanvas';
import { StateInspector } from './components/StateInspector';
import { initialGraphState, reduceServerMessage } from './graph/eventReducer';
import type { GraphNodeData, ServerMessage } from './types';
import './style.css';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';
const WS_BASE = API_BASE.replace(/^http/, 'ws');

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [graphState, dispatchGraph] = useReducer(reduceServerMessage, initialGraphState);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [finalPreview, setFinalPreview] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/sessions`, { method: 'POST' })
      .then((response) => response.json())
      .then((payload) => setSessionId(payload.session_id))
      .catch((error) => setFinalPreview(`创建 session 失败：${String(error)}`));
  }, []);

  const selectedNode = useMemo(
    () => graphState.nodes.find((node: Node<GraphNodeData>) => node.id === selectedNodeId),
    [graphState.nodes, selectedNodeId],
  );

  function sendMessage(message: string) {
    if (!sessionId) return;
    setRunning(true);
    setFinalPreview(null);

    const socket = new WebSocket(`${WS_BASE}/ws/sessions/${sessionId}`);
    socket.onopen = () => {
      socket.send(JSON.stringify({ type: 'user_message', content: message, num_branches: 4 }));
    };
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as ServerMessage;
      dispatchGraph(payload);
      if (payload.type === 'pipeline_completed') {
        const summary = payload.summary as Record<string, unknown>;
        setFinalPreview(String(summary.final_draft_preview ?? ''));
        setRunning(false);
        socket.close();
      }
      if (payload.type === 'error') {
        setFinalPreview(payload.message);
        setRunning(false);
      }
    };
    socket.onerror = () => {
      setFinalPreview('WebSocket 连接失败。');
      setRunning(false);
    };
  }

  return (
    <main>
      <header>
        <h1>Thought-State Graph Orchestration UI</h1>
        <p>
          session: <code>{sessionId ?? 'creating...'}</code> · status:{' '}
          <code>{graphState.runStatus}</code>
        </p>
      </header>
      <div className="layout">
        <ChatPanel disabled={running || !sessionId} onSend={sendMessage} finalPreview={finalPreview} />
        <FlowCanvas nodes={graphState.nodes} edges={graphState.edges} onSelectNode={setSelectedNodeId} />
        <StateInspector node={selectedNode} />
      </div>
      <EventTimeline events={graphState.events} />
    </main>
  );
}
