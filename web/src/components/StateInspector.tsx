import type { Node } from 'reactflow';
import type { GraphNodeData } from '../types';

type Props = {
  node: Node<GraphNodeData> | undefined;
};

export function StateInspector({ node }: Props) {
  return (
    <section className="panel inspector-panel">
      <h2>节点详情</h2>
      {!node ? (
        <p>点击流程图中的节点查看详情。</p>
      ) : (
        <dl>
          <dt>节点</dt>
          <dd>{node.data.label}</dd>
          <dt>阶段</dt>
          <dd>{node.data.stage}</dd>
          <dt>状态</dt>
          <dd>{node.data.status ?? '-'}</dd>
          <dt>评分</dt>
          <dd>{node.data.score ?? '-'}</dd>
          <dt>摘要</dt>
          <dd>{node.data.summary ?? '-'}</dd>
          <dt>调试信息</dt>
          <dd>
            <details>
              <summary>展开内部 metadata</summary>
              <pre>{JSON.stringify(node.data.metadata ?? {}, null, 2)}</pre>
            </details>
          </dd>
        </dl>
      )}
    </section>
  );
}
