import ReactFlow, { Background, Controls, Edge, Node, OnSelectionChangeParams } from 'reactflow';
import 'reactflow/dist/style.css';
import type { GraphNodeData } from '../types';

type Props = {
  nodes: Node<GraphNodeData>[];
  edges: Edge[];
  onSelectNode: (nodeId: string | null) => void;
};

const MIN_CANVAS_HEIGHT = 720;
const MIN_CANVAS_WIDTH = 1280;
const NODE_MARGIN_X = 420;
const NODE_MARGIN_Y = 280;

export function FlowCanvas({ nodes, edges, onSelectNode }: Props) {
  const canvasSize = computeCanvasSize(nodes);

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
            nodes={nodes}
            edges={edges}
            fitView={false}
            zoomOnScroll={false}
            panOnScroll={false}
            preventScrolling={false}
            onSelectionChange={handleSelectionChange}
          >
            <Background />
            <Controls />
          </ReactFlow>
        </div>
      </div>
    </section>
  );
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
