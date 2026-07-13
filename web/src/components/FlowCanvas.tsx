import ReactFlow, { Background, Controls, Edge, MarkerType, Node, OnSelectionChangeParams } from 'reactflow';
import 'reactflow/dist/style.css';
import type { GraphNodeData } from '../types';

type Props = {
  nodes: Node<GraphNodeData>[];
  edges: Edge[];
  onSelectNode: (nodeId: string | null) => void;
};

const MIN_CANVAS_HEIGHT = 460;
const MIN_CANVAS_WIDTH = 900;
const NODE_MARGIN_X = 180;
const NODE_MARGIN_Y = 120;

export function FlowCanvas({ nodes, edges, onSelectNode }: Props) {
  const visibleGraph = collapseFixedExpertProfile(nodes, edges);
  const canvasSize = computeCanvasSize(visibleGraph.nodes);

  function handleSelectionChange(params: OnSelectionChangeParams) {
    onSelectNode(params.nodes[0]?.id ?? null);
  }

  return (
    <section className="panel flow-panel">
      <h2>实时调用流程图</h2>
      <div className="flow-canvas-scroll" aria-label="thought graph canvas scroll area">
        <div
          className="flow-canvas"
          style={{
            height: `${canvasSize.height}px`,
            minWidth: `${canvasSize.width}px`,
          }}
        >
          <ReactFlow
            nodes={visibleGraph.nodes}
            edges={visibleGraph.edges}
            fitView={false}
            zoomOnScroll={false}
            panOnScroll={false}
            preventScrolling={false}
            onSelectionChange={handleSelectionChange}
          >
            <Background gap={18} size={0.8} />
            <Controls />
          </ReactFlow>
        </div>
      </div>
    </section>
  );
}

/**
 * SecondaryMarketAnalyst is currently the only expert profile, so displaying it
 * as a routing choice adds a node without adding execution information. Keep the
 * handoff in trace metadata, but collapse the fixed profile in the visible graph
 * and reconnect its predecessor directly to its successors.
 */
function collapseFixedExpertProfile(nodes: Node<GraphNodeData>[], edges: Edge[]) {
  const expertIds = new Set(nodes.filter((node) => node.data.stage === 'expert_router').map((node) => node.id));
  if (!expertIds.size) return { nodes, edges };

  const visibleNodes = nodes.filter((node) => !expertIds.has(node.id));
  const visibleNodeIds = new Set(visibleNodes.map((node) => node.id));
  const incomingByExpert = new Map<string, string[]>();

  for (const edge of edges) {
    if (!expertIds.has(edge.target)) continue;
    const incoming = incomingByExpert.get(edge.target) ?? [];
    incoming.push(edge.source);
    incomingByExpert.set(edge.target, incoming);
  }

  const visibleEdges: Edge[] = [];
  const seen = new Set<string>();

  function appendEdge(edge: Edge) {
    if (!visibleNodeIds.has(edge.source) || !visibleNodeIds.has(edge.target)) return;
    const key = `${edge.source}->${edge.target}`;
    if (seen.has(key)) return;
    seen.add(key);
    visibleEdges.push(edge);
  }

  for (const edge of edges) {
    if (expertIds.has(edge.target)) continue;
    if (!expertIds.has(edge.source)) {
      appendEdge(edge);
      continue;
    }

    for (const predecessor of incomingByExpert.get(edge.source) ?? []) {
      appendEdge({
        ...edge,
        id: `${predecessor}->${edge.target}`,
        source: predecessor,
        markerEnd: edge.markerEnd ?? { type: MarkerType.ArrowClosed, width: 12, height: 12 },
        data: { ...(edge.data ?? {}), collapsedExpertId: edge.source },
      });
    }
  }

  return { nodes: visibleNodes, edges: visibleEdges };
}

function computeCanvasSize(nodes: Node<GraphNodeData>[]) {
  if (!nodes.length) {
    return { height: MIN_CANVAS_HEIGHT, width: MIN_CANVAS_WIDTH };
  }

  const maxX = Math.max(...nodes.map((node) => node.position.x));
  const maxY = Math.max(...nodes.map((node) => node.position.y));

  return {
    height: Math.max(MIN_CANVAS_HEIGHT, maxY + NODE_MARGIN_Y),
    width: Math.max(MIN_CANVAS_WIDTH, maxX + NODE_MARGIN_X),
  };
}
