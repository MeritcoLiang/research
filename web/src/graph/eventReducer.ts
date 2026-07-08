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
      position: layoutPosition(state.nodes.length),
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

function layoutPosition(index: number) {
  const column = index % 4;
  const row = Math.floor(index / 4);
  return { x: column * 260, y: row * 140 };
}
