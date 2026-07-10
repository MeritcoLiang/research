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
  expert: 150,
  subtask: 320,
  candidate: 520,
  normalized: 720,
  scored: 920,
  improved: 1120,
  aggregation: 1320,
  validation: 1500,
};

const ROOT_Y = 260;
const GROUP_TOP = 28;
const BRANCH_GAP = 32;
const MIN_GROUP_HEIGHT = 88;
const GROUP_PADDING_Y = 56;

const STAGE_ORDER: Record<string, number> = {
  root: 0,
  expert_router: 1,
  problem_decomposer: 2,
  candidate_generator: 3,
  thought_normalizer: 4,
  verifier_scorer: 5,
  improver: 6,
  aggregator: 7,
  final_validator: 8,
};

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
    const node = graphNodeFromRaw(message.node);
    return {
      ...state,
      nodes: recomputeGraphLayout(upsertNode(state.nodes, node)),
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
      nodes: recomputeGraphLayout(
        state.nodes.map((node) =>
          node.id === message.node_id
            ? { ...node, data: { ...node.data, ...(message.patch as Partial<GraphNodeData>) } }
            : node,
        ),
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
  const nodes = recomputeGraphLayout(rawNodes.map(graphNodeFromRaw));

  const rawEdges = Array.isArray(snapshot.edges) ? snapshot.edges : [];
  const edges = rawEdges.map(graphEdgeFromRaw);

  return {
    ...state,
    nodes,
    edges,
    runStatus,
  };
}

function graphNodeFromRaw(raw: Record<string, unknown>): Node<GraphNodeData> {
  const stage = String(raw.stage ?? '');
  return {
    id: String(raw.id),
    position: { x: 0, y: 0 },
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
  return nodes.map((node) => (node.id === next.id ? { ...node, ...next } : node));
}

function upsertEdge(edges: Edge[], next: Edge): Edge[] {
  const exists = edges.some((edge) => edge.id === next.id);
  if (!exists) return [...edges, next];
  return edges.map((edge) => (edge.id === next.id ? { ...edge, ...next } : edge));
}

function recomputeGraphLayout(nodes: Node<GraphNodeData>[]): Node<GraphNodeData>[] {
  if (!nodes.length) return nodes;

  const subtaskIds = discoverSubtaskIds(nodes);
  const groupMetrics = computeGroupMetrics(nodes, subtaskIds);
  const centerY = computeGraphCenterY(groupMetrics);
  const positionById = new Map<string, { x: number; y: number }>();

  const ordered = [...nodes].sort((a, b) => {
    const aStage = a.data.stage ?? '';
    const bStage = b.data.stage ?? '';
    return (STAGE_ORDER[aStage] ?? 99) - (STAGE_ORDER[bStage] ?? 99) || a.id.localeCompare(b.id);
  });

  for (const node of ordered) {
    const stage = node.data.stage ?? '';
    const status = node.data.status ?? '';
    const metadata = isRecord(node.data.metadata) ? node.data.metadata : {};
    let position = { x: X.candidate, y: GROUP_TOP + positionById.size * 28 };

    if (stage === 'root') {
      position = { x: X.root, y: centerY };
    } else if (stage === 'expert_router') {
      position = { x: X.expert, y: centerY };
    } else if (status === 'subtask' || stage === 'problem_decomposer') {
      const metrics = groupMetrics.get(node.id) ?? groupMetrics.get(subtaskIds[0]);
      position = { x: X.subtask, y: metrics ? metrics.subtaskY : centerY };
    } else if (stage === 'candidate_generator') {
      const subtask = String(metadata.subtask_id ?? subtaskIds[0] ?? 's1');
      const branch = Number(metadata.branch_index ?? 0);
      const metrics = groupMetrics.get(subtask) ?? groupMetrics.get(subtaskIds[0]);
      position = {
        x: X.candidate,
        y: (metrics?.top ?? GROUP_TOP) + branch * BRANCH_GAP,
      };
    } else if (stage === 'thought_normalizer') {
      position = alignWithParent(metadata, positionById, X.normalized, centerY);
    } else if (stage === 'verifier_scorer') {
      position = alignWithParent(metadata, positionById, X.scored, centerY);
    } else if (stage === 'improver') {
      position = alignWithParent(metadata, positionById, X.improved, centerY);
    } else if (stage === 'aggregator') {
      position = { x: X.aggregation, y: averagePositionY(positionById, nodes, 'verifier_scorer') ?? centerY };
    } else if (stage === 'final_validator') {
      position = alignWithParent(metadata, positionById, X.validation, centerY);
    }

    positionById.set(node.id, position);
  }

  return nodes.map((node) => ({ ...node, position: positionById.get(node.id) ?? node.position }));
}

function discoverSubtaskIds(nodes: Node<GraphNodeData>[]) {
  const ids = new Set<string>();
  for (const node of nodes) {
    if (node.data.status === 'subtask' || node.data.stage === 'problem_decomposer') ids.add(node.id);
    const metadata = isRecord(node.data.metadata) ? node.data.metadata : {};
    if (typeof metadata.subtask_id === 'string') ids.add(metadata.subtask_id);
  }
  return [...ids].sort((a, b) => subtaskIndex(a) - subtaskIndex(b) || a.localeCompare(b));
}

function computeGroupMetrics(nodes: Node<GraphNodeData>[], subtaskIds: string[]) {
  const metrics = new Map<string, { top: number; height: number; subtaskY: number }>();
  const branchCounts = new Map<string, number>();
  for (const id of subtaskIds) branchCounts.set(id, 1);

  for (const node of nodes) {
    if (node.data.stage !== 'candidate_generator') continue;
    const metadata = isRecord(node.data.metadata) ? node.data.metadata : {};
    const subtask = String(metadata.subtask_id ?? subtaskIds[0] ?? 's1');
    const branch = Number(metadata.branch_index ?? 0);
    branchCounts.set(subtask, Math.max(branchCounts.get(subtask) ?? 1, branch + 1));
  }

  let top = GROUP_TOP;
  for (const id of subtaskIds) {
    const branchCount = Math.max(1, branchCounts.get(id) ?? 1);
    const height = Math.max(MIN_GROUP_HEIGHT, branchCount * BRANCH_GAP + GROUP_PADDING_Y);
    const subtaskY = top + Math.max(18, ((branchCount - 1) * BRANCH_GAP) / 2);
    metrics.set(id, { top, height, subtaskY });
    top += height;
  }
  return metrics;
}

function computeGraphCenterY(metrics: Map<string, { top: number; height: number }>) {
  const groups = [...metrics.values()];
  if (!groups.length) return ROOT_Y;
  const first = groups[0];
  const last = groups[groups.length - 1];
  return (first.top + last.top + last.height) / 2;
}

function alignWithParent(
  metadata: Record<string, unknown>,
  positionById: Map<string, { x: number; y: number }>,
  x: number,
  fallbackY: number,
) {
  const parentIds = Array.isArray(metadata.parent_ids) ? metadata.parent_ids.map(String) : [];
  const parent = parentIds.map((id) => positionById.get(id)).find(Boolean);
  if (parent) return { x, y: parent.y };
  return { x, y: fallbackY };
}

function averagePositionY(positionById: Map<string, { x: number; y: number }>, nodes: Node<GraphNodeData>[], stage: string) {
  const ys = nodes
    .filter((node) => node.data.stage === stage)
    .map((node) => positionById.get(node.id)?.y)
    .filter((value): value is number => typeof value === 'number');
  if (!ys.length) return null;
  return ys.reduce((sum, y) => sum + y, 0) / ys.length;
}

function subtaskIndex(id: string) {
  const match = id.match(/s(\d+)/);
  if (!match) return 0;
  return Number(match[1]) - 1;
}

function compactNodeWidth(stage: string) {
  if (stage === 'root') return 86;
  if (stage === 'expert_router') return 112;
  if (stage === 'candidate_generator') return 120;
  if (stage === 'aggregator' || stage === 'final_validator') return 104;
  return 96;
}

function compactLabel(label: string) {
  return label
    .replace('SecondaryMarketAnalyst', 'Secondary\nMarket')
    .replace('candidate\n', 'cand\n')
    .replace('normalized', 'norm')
    .replace('aggregation', 'agg')
    .replace('validation', 'valid')
    .replace('scored', 'score')
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
