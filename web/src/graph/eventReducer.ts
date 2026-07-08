import type { Edge, Node } from 'reactflow';
import type { GraphNodeData, ServerMessage, TraceEvent } from '../types';

export type GraphState = {
  nodes: Node<GraphNodeData>[];
  edges: Edge[];
  events: TraceEvent[];
  selectedNodeId: string | null;
  runStatus: string;
};

export const initialGraphState: GraphState = {
  nodes: [],
  edges: [],
  events: [],
  selectedNodeId: null,
  runStatus: 'idle',
};

const X = {
  root: 0,
  subtask: 280,
  candidate: 600,
  normalized: 940,
  scored: 1280,
  improved: 1620,
  aggregation: 1960,
  validation: 2260,
};

const ROOT_Y = 620;
const GROUP_TOP = 80;
const SUBTASK_GAP = 360;
const BRANCH_GAP = 80;

export function reduceServerMessage(state: GraphState, message: ServerMessage): GraphState {
  if (message.type === 'trace_event') {
    return {
      ...state,
      events: [...state.events, message.event],
      runStatus: message.event.event_type,
    };
  }

  if (message.type === 'graph_node_upsert') {
    const raw = message.node as Record<string, any>;
    const node: Node<GraphNodeData> = {
      id: String(raw.id),
      position: semanticLayoutPosition(raw, state.nodes),
      data: {
        label: String(raw.label ?? raw.id),
        stage: String(raw.stage ?? ''),
        status: raw.status,
        score: raw.score,
        summary: raw.summary,
        metadata: raw.metadata ?? {},
      },
    };
    return {
      ...state,
      nodes: upsertNode(state.nodes, node),
    };
  }

  if (message.type === 'graph_edge_upsert') {
    const raw = message.edge as Record<string, any>;
    const edge: Edge = {
      id: String(raw.id),
      source: String(raw.source),
      target: String(raw.target),
      label: raw.edge_type ? String(raw.edge_type) : undefined,
    };
    return {
      ...state,
      edges: upsertEdge(state.edges, edge),
    };
  }

  if (message.type === 'graph_node_patch') {
    return {
      ...state,
      nodes: state.nodes.map((node) =>
        node.id === message.node_id
          ? { ...node, data: { ...node.data, ...(message.patch as Partial<GraphNodeData>) } }
          : node,
      ),
    };
  }

  if (message.type === 'pipeline_completed') {
    return {
      ...state,
      runStatus: 'pipeline_completed',
    };
  }

  if (message.type === 'error') {
    return {
      ...state,
      runStatus: `error: ${message.message}`,
    };
  }

  return state;
}

function upsertNode(nodes: Node<GraphNodeData>[], next: Node<GraphNodeData>): Node<GraphNodeData>[] {
  const exists = nodes.some((node) => node.id === next.id);
  if (!exists) return [...nodes, next];
  return nodes.map((node) => (node.id === next.id ? { ...node, ...next, position: node.position } : node));
}

function upsertEdge(edges: Edge[], next: Edge): Edge[] {
  const exists = edges.some((edge) => edge.id === next.id);
  if (!exists) return [...edges, next];
  return edges.map((edge) => (edge.id === next.id ? { ...edge, ...next } : edge));
}

function semanticLayoutPosition(raw: Record<string, any>, nodes: Node<GraphNodeData>[]) {
  const stage = String(raw.stage ?? '');
  const status = String(raw.status ?? '');
  const metadata = (raw.metadata ?? {}) as Record<string, any>;

  if (stage === 'root') return { x: X.root, y: ROOT_Y };

  if (status === 'subtask' || stage === 'problem_decomposer') {
    const idx = subtaskIndex(String(raw.id));
    return { x: X.subtask, y: GROUP_TOP + idx * SUBTASK_GAP + BRANCH_GAP * 1.5 };
  }

  if (stage === 'candidate_generator') {
    const subtask = String(metadata.subtask_id ?? 's1');
    const branch = Number(metadata.branch_index ?? 0);
    return {
      x: X.candidate,
      y: GROUP_TOP + subtaskIndex(subtask) * SUBTASK_GAP + branch * BRANCH_GAP,
    };
  }

  if (stage === 'thought_normalizer') {
    return alignWithParentOrStack(raw, nodes, X.normalized, GROUP_TOP);
  }

  if (stage === 'verifier_scorer') {
    return alignWithParentOrStack(raw, nodes, X.scored, GROUP_TOP);
  }

  if (stage === 'improver') {
    return alignWithParentOrStack(raw, nodes, X.improved, GROUP_TOP);
  }

  if (stage === 'aggregator') {
    return { x: X.aggregation, y: averageY(nodes, 'verifier_scorer') ?? ROOT_Y };
  }

  if (stage === 'final_validator') {
    return alignWithParentOrStack(raw, nodes, X.validation, ROOT_Y);
  }

  return { x: X.candidate, y: GROUP_TOP + nodes.length * 40 };
}

function alignWithParentOrStack(raw: Record<string, any>, nodes: Node<GraphNodeData>[], x: number, fallbackY: number) {
  const parentIds = Array.isArray(raw.metadata?.parent_ids) ? raw.metadata.parent_ids : [];
  const parent = nodes.find((node) => parentIds.includes(node.id));
  if (parent) return { x, y: parent.position.y };
  return { x, y: fallbackY + nodes.length * 40 };
}

function averageY(nodes: Node<GraphNodeData>[], stage: string) {
  const selected = nodes.filter((node) => node.data.stage === stage);
  if (!selected.length) return null;
  return selected.reduce((sum, node) => sum + node.position.y, 0) / selected.length;
}

function subtaskIndex(id: string) {
  const match = id.match(/s(\d+)/);
  if (!match) return 0;
  return Number(match[1]) - 1;
}
