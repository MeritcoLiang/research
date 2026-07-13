import { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import type { Node } from 'reactflow';
import { ChatPanel, type LLMProvider } from './components/ChatPanel';
import { FlowCanvas } from './components/FlowCanvas';
import { StateInspector } from './components/StateInspector';
import { initialGraphState, reduceServerMessage } from './graph/eventReducer';
import type { GraphNodeData, GraphSnapshot, HistoryTraceItem, ServerMessage } from './types';
import './style.css';

const API_BASE = import.meta.env.VITE_API_BASE ?? '';
const WS_BASE = import.meta.env.VITE_WS_BASE ?? API_BASE.replace(/^http/, 'ws');
const SESSION_KEY = 'tsgo_session_id';
const GRAPH_KEY = 'tsgo_latest_graph_v2';
const SUMMARY_KEY = 'tsgo_latest_summary_v2';
const LEGACY_KEYS = ['tsgo_latest_graph', 'tsgo_latest_summary'];

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
  const [histories, setHistories] = useState<HistoryTraceItem[]>([]);
  const activeSocketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    LEGACY_KEYS.forEach(removeStorageItem);

    const cachedSessionId = readStorageItem(SESSION_KEY);
    if (cachedSessionId) {
      setSessionId(cachedSessionId);
    } else {
      createSession();
    }

    const cachedGraph = readJsonStorage<GraphSnapshot>(GRAPH_KEY);
    if (isGraphSnapshot(cachedGraph)) {
      dispatchGraph({ type: 'client_graph_snapshot', graph: cachedGraph });
    } else if (cachedGraph !== null) {
      removeStorageItem(GRAPH_KEY);
    }

    const cachedSummary = readJsonStorage<Record<string, unknown>>(SUMMARY_KEY);
    if (cachedSummary) {
      setFinalPreview(String(cachedSummary.final_draft_preview ?? ''));
    }

    refreshHistory();
    return () => {
      activeSocketRef.current?.close();
      activeSocketRef.current = null;
    };
  }, []);

  function createSession() {
    fetch(`${API_BASE}/api/sessions`, { method: 'POST' })
      .then(assertOk)
      .then((response) => response.json())
      .then((payload) => {
        const nextSessionId = String(payload.session_id ?? '');
        if (!nextSessionId) throw new Error('后端未返回 session_id');
        setSessionId(nextSessionId);
        writeStorageItem(SESSION_KEY, nextSessionId);
      })
      .catch((error) => setFinalPreview(`创建 session 失败：${String(error)}`));
  }

  function refreshHistory() {
    fetch(`${API_BASE}/api/history`)
      .then(assertOk)
      .then((response) => response.json())
      .then((payload) => setHistories(Array.isArray(payload.items) ? payload.items : []))
      .catch((error) => setFinalPreview(`加载历史列表失败：${String(error)}`));
  }

  function loadHistory(historyId: string) {
    setRunning(true);
    setSelectedNodeId(null);
    fetch(`${API_BASE}/api/history/${encodeURIComponent(historyId)}`)
      .then(assertOk)
      .then((response) => response.json())
      .then((payload) => {
        const graph = payload.graph as GraphSnapshot;
        const summary = payload.summary as HistoryTraceItem;
        if (!isGraphSnapshot(graph)) throw new Error('历史 trace 的 graph 结构无效');
        dispatchGraph({ type: 'client_graph_snapshot', graph });
        setFinalPreview(summary.final_draft_preview ?? '历史 trace 已加载。');
        writeJsonStorage(GRAPH_KEY, graph);
        writeJsonStorage(SUMMARY_KEY, { final_draft_preview: summary.final_draft_preview });
      })
      .catch((error) => setFinalPreview(`加载历史 trace 失败：${String(error)}`))
      .finally(() => setRunning(false));
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
    removeStorageItem(GRAPH_KEY);
    removeStorageItem(SUMMARY_KEY);
    dispatchGraph({ type: 'client_reset' });

    activeSocketRef.current?.close();
    const socket = new WebSocket(wsUrl(`/ws/sessions/${sessionId}`));
    activeSocketRef.current = socket;

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
      try {
        const payload = JSON.parse(event.data) as ServerMessage;
        dispatchGraph(payload);
        if (payload.type === 'run_started') {
          setFinalPreview(`后端已接收任务：${payload.llm_provider}，branches=${payload.num_branches}。`);
        }
        if (payload.type === 'pipeline_completed') {
          const summary = payload.summary as Record<string, unknown>;
          setFinalPreview(String(summary.final_draft_preview ?? ''));
          writeJsonStorage(GRAPH_KEY, payload.graph);
          writeJsonStorage(SUMMARY_KEY, summary);
          setRunning(false);
          socket.close();
          refreshHistory();
        }
        if (payload.type === 'error') {
          setFinalPreview(payload.message);
          setRunning(false);
          socket.close();
          if (payload.message.includes('未知 session_id') || payload.message.includes('非法 session_id')) {
            removeStorageItem(SESSION_KEY);
            createSession();
          }
        }
      } catch (error) {
        setFinalPreview(`收到无法解析的服务端消息：${String(error)}`);
        setRunning(false);
        socket.close();
      }
    };

    socket.onerror = () => {
      setFinalPreview('WebSocket 连接失败。');
      setRunning(false);
      socket.close();
    };

    socket.onclose = () => {
      if (activeSocketRef.current === socket) activeSocketRef.current = null;
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
        <ChatPanel
          disabled={running || !sessionId}
          onSend={sendMessage}
          finalPreview={finalPreview}
          histories={histories}
          onLoadHistory={loadHistory}
          onRefreshHistory={refreshHistory}
        />
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

function assertOk(response: Response) {
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response;
}

function isGraphSnapshot(value: unknown): value is GraphSnapshot {
  if (!value || typeof value !== 'object') return false;
  const graph = value as Partial<GraphSnapshot>;
  return Array.isArray(graph.nodes) && Array.isArray(graph.edges);
}

function readStorageItem(key: string) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function readJsonStorage<T>(key: string): T | null {
  const raw = readStorageItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    removeStorageItem(key);
    return null;
  }
}

function writeStorageItem(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    removeStorageItem(key);
  }
}

function writeJsonStorage(key: string, value: unknown) {
  try {
    writeStorageItem(key, JSON.stringify(value));
  } catch {
    removeStorageItem(key);
  }
}

function removeStorageItem(key: string) {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Storage can be unavailable in hardened browser contexts; the UI should still run.
  }
}
