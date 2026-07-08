import ReactFlow, { Background, Controls, Edge, Node, OnSelectionChangeParams } from 'reactflow';
import 'reactflow/dist/style.css';
import type { GraphNodeData } from '../types';

type Props = {
  nodes: Node<GraphNodeData>[];
  edges: Edge[];
  onSelectNode: (nodeId: string | null) => void;
};

export function FlowCanvas({ nodes, edges, onSelectNode }: Props) {
  function handleSelectionChange(params: OnSelectionChangeParams) {
    onSelectNode(params.nodes[0]?.id ?? null);
  }

  return (
    <section className="panel flow-panel">
      <h2>实时调用流程图</h2>
      <ReactFlow nodes={nodes} edges={edges} fitView onSelectionChange={handleSelectionChange}>
        <Background />
        <Controls />
      </ReactFlow>
    </section>
  );
}
