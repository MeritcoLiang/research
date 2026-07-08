export type TraceEvent = {
  event_id: string;
  trace_id: string;
  session_id: string | null;
  event_type: string;
  stage: string | null;
  state_id: string | null;
  parent_ids: string[];
  payload: Record<string, unknown>;
  timestamp: string;
};

export type GraphNodeData = {
  label: string;
  stage: string | null;
  status?: string;
  score?: number | null;
  summary?: string | null;
  metadata?: Record<string, unknown>;
};

export type GraphSnapshot = {
  trace_id?: string;
  nodes?: Record<string, unknown>[];
  edges?: Record<string, unknown>[];
};

export type ServerMessage =
  | { type: "client_reset" }
  | { type: "client_graph_snapshot"; graph: GraphSnapshot }
  | { type: "trace_event"; event: TraceEvent }
  | { type: "graph_node_upsert"; trace_id: string; node: Record<string, unknown> }
  | { type: "graph_edge_upsert"; trace_id: string; edge: Record<string, unknown> }
  | { type: "graph_node_patch"; trace_id: string; node_id: string; patch: Record<string, unknown> }
  | { type: "pipeline_completed"; summary: Record<string, unknown>; graph: GraphSnapshot }
  | { type: "error"; message: string };
