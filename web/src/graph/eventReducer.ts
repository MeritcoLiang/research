import { MarkerType, Position, type Edge, type Node } from 'reactflow';
import type { GraphNodeData, GraphSnapshot, ServerMessage, TraceEvent } from '../types';

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
  expert: 180,
  subtask: 380,
  candidate: 620,
  normalized: 850,
  scored: 1080,
  improved: 1310,
  aggregation: 1540,
  validation: 1760,
};

const ROOT_Y = 360;
const GROUP_TOP = 40;
const SUBTASK_GAP = 250;
const BRANCH_GAP = 44;

export function reduceServerMessage(state: GraphState, message: ServerMessage): GraphState {
  if (message.type === 'client_reset') {
    return initialGraphState;
  }

  if (message.type === 'client_graph_snapshot') {
    return hydrateGraphSnapshot(state, message.graph, 'snapshot_loaded');
  }

  if (message.type === 'run_started') {
    return {
      ...state,
      runStatus: `run_started:${message.llm_provider}`,
    };
  }

  if (message.type === 'trace_event') {
    return {
      ...state,
      events: [...state.events, message.event],
      runStatus: message.event.event_type,
    };
  }

  if (message.type === 'graph_node_upsert') {
    const node = graphNodeFromRaw(message.node, state.nodes);
    return {
      ...state,
      nodes: upsertNode(state.nodes, node),
    };
  }

  if (message.type === 'graph_edge_upsert') {
    const edge = graphEdgeFromRaw(message.edge);
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
    return hydrateGraphSnapshot(state, message.graph, 'pipeline_completed');
  }

  if (message.type === 'error') {
    return {
      ...state,
      runStatus: `error: ${message.message}`,
    };
  }

  return state;
}

function hydrateGraphSnapshot(state: GraphState, snapshot: GraphSnapshot, runStatus: string): GraphState {
  const rawNodes = Array.isArray(snapshot.nodes) ? snapshot.nodes : [];
  const nodes: Node<GraphNodeData>[] = [];
  for (const raw of rawNodes) {
    nodes.push(graphNodeFromRaw(raw, nodes));
  }

  const rawEdges = Array.isArray(snapshot.edges) ? snapshot.edges : [];
  const edges = rawEdges.map(graphEdgeFromRaw);

  return {
    ...state,
    nodes,
    edges,
    runStatus,
  };
}

function graphNodeFromRaw(raw: Record<string, unknown>, existingNodes: Node<GraphNodeData>[]): Node<GraphNodeData> {
  const stage = String(raw.stage ?? '');
  return {
    id: String(raw.id),
    position: semanticLayoutPosition(raw, existingNodes),
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    className: `compact-flow-node stage-${stage.replaceAll('_', '-') || 'unknown'}`,
    style: { width: compactNodeWidth(stage) },
    data: {
      label: compactLabel(String(raw.label ?? raw.id)),
      stage,
      status: typeof raw.status === 'string' ? raw.status : undefined,
      score: typeof raw.score === 'number' ? raw.score : null,
      summary: typeof raw.summary === 'string' ? raw.summary : null,
      metadata: isRecord(raw.metadata) ? raw.metadata : {},
    },
  };
}

function graphEdgeFromRaw(raw: Record<string, unknown>): Edge {
  return {
    id: String(raw.id),
    source: String(raw.source),
    target: String(raw.target),
    type: 'default',
    markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12 },
    style: { strokeWidth: 1.2 },
    data: { edgeType: raw.edge_type ? String(raw.edge_type) : 'parent' },
  };
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

function semanticLayoutPosition(raw: Record<string, unknown>, nodes: Node<GraphNodeData>[]) {
  const stage = String(raw.stage ?? '');
  const status = String(raw.status ?? '');
  const metadata = isRecord(raw.metadata) ? raw.metadata : {};

  if (stage === 'root') return { x: X.root, y: ROOT_Y };

  if (stage === 'expert_router') {
    return { x: X.expert, y: ROOT_Y };
  }

  if (status === 'subtask' || stage === 'problem_decomposer') {
    const idx = subtaskIndex(String(raw.id));
    return { x: X.subtask, y: GROUP_TOP + idx * SUBTASK_GAP + BRANCH_GAP };
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

  return { x: X.candidate, y: GROUP_TOP + nodes.length * 32 };
}

function alignWithParentOrStack(raw: Record<string, unknown>, nodes: Node<GraphNodeData>[], x: number, fallbackY: number) {
  const metadata = isRecord(raw.metadata) ? raw.metadata : {};
  const parentIds = Array.isArray(metadata.parent_ids) ? metadata.parent_ids.map(String) : [];
  const parent = nodes.find((node) => parentIds.includes(node.id));
  if (parent) return { x, y: parent.position.y };
  return { x, y: fallbackY + nodes.length * 32 };
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

function compactNodeWidth(stage: string) {
  if (stage === 'root') return 92;
  if (stage === 'expert_router') return 124;
  if (stage === 'candidate_generator') return 134;
  if (stage === 'aggregator' || stage === 'final_validator') return 116;
  return 104;
}

function compactLabel(label: string) {
  return label
    .replace('SecondaryMarketAnalyst', 'Secondary\nMarket')
    .replace('candidate\n', 'cand\n')
    .replace('normalized', 'norm')
    .replace('aggregation', 'agg')
    .replace('validation', 'valid')
    .replace('technical flow', 'technical')
    .replace('catalyst driven', 'catalyst')
    .replace('risk first', 'risk')
    .replace('direct expert', 'direct')
    .replace('counterfactual', 'counter')
    .replace('first principles', 'principles');
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
