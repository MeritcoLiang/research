import type { Node } from 'reactflow';
import type { GraphNodeData } from '../types';

type Props = {
  node: Node<GraphNodeData> | undefined;
};

export function StateInspector({ node }: Props) {
  return (
    <section className="panel inspector-panel">
      <h2>状态详情</h2>
      {!node ? (
        <p>点击流程图中的节点查看详情。</p>
      ) : (
        <dl>
          <dt>state_id</dt>
          <dd>{node.id}</dd>
          <dt>stage</dt>
          <dd>{node.data.stage}</dd>
          <dt>status</dt>
          <dd>{node.data.status ?? '-'}</dd>
          <dt>score</dt>
          <dd>{node.data.score ?? '-'}</dd>
          <dt>summary</dt>
          <dd>{node.data.summary ?? '-'}</dd>
          <dt>metadata</dt>
          <dd>
            <pre>{JSON.stringify(node.data.metadata ?? {}, null, 2)}</pre>
          </dd>
        </dl>
      )}
    </section>
  );
}
