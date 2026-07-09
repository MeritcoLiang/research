import { useEffect, useMemo, useReducer, useState } from 'react';
import type { Node } from 'reactflow';
import { ChatPanel, type LLMProvider } from './components/ChatPanel';
import { FlowCanvas } from './components/FlowCanvas';
import { StateInspector } from './components/StateInspector';
import { initialGraphState, reduceServerMessage } from './graph/eventReducer';
import type { GraphNodeData, GraphSnapshot, ServerMessage } from './types';
import './style.css';

const API_BASE = import.meta.env.VITE_API_BASE ?? '';
const WS_BASE = import.meta.env.VITE_WS_BASE ?? API_BASE.replace(/^http/, 'ws');
const SESSION_KEY = 'tsgo_session_id';
const GRAPH_KEY = 'tsgo_latest_graph';
const SUMMARY_KEY = 'tsgo_latest_summary';

function wsUrl(path: string) {
  if (WS_BASE) return `${WS_BASE}${path}`;
  return `${window.location.origin.replace(/^http/, 'ws')}${path}`;
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [graphState, dispatchGraph] = useReducer(reduceServerMessage, initialGraphState);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [finalPreview, setFinalPreview] = useState<string | null>(null);

  useEffect(() => {
    const cachedSessionId = window.localStorage.getItem(SESSION_KEY);
    if (cachedSessionId) {
      setSessionId(cachedSessionId);
    } else {
      createSession();
    }

    const cachedGraph = window.localStorage.getItem(GRAPH_KEY);
    if (cachedGraph) {
      try {
        const graph = JSON.parse(cachedGraph) as GraphSnapshot;
        dispatchGraph({ type: 'client_graph_snapshot', graph });
      } catch {
        window.localStorage.removeItem(GRAPH_KEY);
      }
    }

    const cachedSummary = window.localStorage.getItem(SUMMARY_KEY);
    if (cachedSummary) {
      try {
        const summary = JSON.parse(cachedSummary) as Record<string, unknown>;
        setFinalPreview(String(summary.final_draft_preview ?? ''));
      } catch {
        window.localStorage.removeItem(SUMMARY_KEY);
      }
    }
  }, []);

  function createSession() {
    fetch(`${API_BASE}/api/sessions`, { method: 'POST' })
      .then((response) => response.json())
      .then((payload) => {
        setSessionId(payload.session_id);
        window.localStorage.setItem(SESSION_KEY, payload.session_id);
      })
      .catch((error) => setFinalPreview(`创建 session 失败：${String(error)}`));
  }

  const selectedNode = useMemo(
    () => graphState.nodes.find((node: Node<GraphNodeData>) => node.id === selectedNodeId),
    [graphState.nodes, selectedNodeId],
  );

  function sendMessage(message: string, llmProvider: LLMProvider) {
    if (!sessionId) return;
    const numBranches = llmProvider === 'stage_flow' ? 6 : 1;
    setRunning(true);
    setFinalPreview(`任务已发送：${providerLabel(llmProvider)}，branches=${numBranches}。`);
    setSelectedNodeId(null);
    window.localStorage.removeItem(GRAPH_KEY);
    window.localStorage.removeItem(SUMMARY_KEY);
    dispatchGraph({ type: 'client_reset' });

    const socket = new WebSocket(wsUrl(`/ws/sessions/${sessionId}`));
    socket.onopen = () => {
      socket.send(
        JSON.stringify({
          type: 'user_message',
          content: message,
          num_branches: numBranches,
          llm_provider: llmProvider,
        }),
      );
    };
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as ServerMessage;
      dispatchGraph(payload);
      if (payload.type === 'run_started') {
        setFinalPreview(`后端已接收任务：${payload.llm_provider}，branches=${payload.num_branches}。`);
      }
      if (payload.type === 'pipeline_completed') {
        const summary = payload.summary as Record<string, unknown>;
        setFinalPreview(String(summary.final_draft_preview ?? ''));
        window.localStorage.setItem(GRAPH_KEY, JSON.stringify(payload.graph));
        window.localStorage.setItem(SUMMARY_KEY, JSON.stringify(summary));
        setRunning(false);
        socket.close();
      }
      if (payload.type === 'error') {
        setFinalPreview(payload.message);
        setRunning(false);
        socket.close();
        if (payload.message.includes('未知 session_id')) {
          window.localStorage.removeItem(SESSION_KEY);
          createSession();
        }
      }
    };
    socket.onerror = () => {
      setFinalPreview('WebSocket 连接失败。');
      setRunning(false);
      socket.close();
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
    </main>
  );
}

function providerLabel(provider: LLMProvider) {
  const labels: Record<LLMProvider, string> = {
    stage_flow: 'Stage Flow',
    azure_openai: 'Azure OpenAI',
    deepseek: 'DeepSeek',
  };
  return labels[provider];
}
