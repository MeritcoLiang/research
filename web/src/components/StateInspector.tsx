import { useState } from 'react';
import type { Node } from 'reactflow';
import type { GraphNodeData } from '../types';

type Props = {
  node: Node<GraphNodeData> | undefined;
};

type Metadata = Record<string, unknown>;

type KeyValue = {
  label: string;
  value: unknown;
};

type ModalPayload = {
  title: string;
  value: unknown;
};

const STAGE_LABELS: Record<string, string> = {
  root: 'Root / 用户输入',
  expert_router: '专家选择',
  problem_decomposer: '问题拆解',
  candidate_generator: '候选生成',
  thought_normalizer: '规范化',
  verifier_scorer: '验证评分',
  improver: '改进',
  aggregator: '聚合',
  final_validator: '最终验证',
};

export function StateInspector({ node }: Props) {
  const [modal, setModal] = useState<ModalPayload | null>(null);
  const metadata = (node?.data.metadata ?? {}) as Metadata;
  const validation = asRecord(metadata.validation);
  const handoff = asRecord(metadata.handoff);

  if (!node) {
    return (
      <section className="panel inspector-panel">
        <h2>节点详情</h2>
        <p className="empty-hint">点击流程图中的节点查看输入、输出、评分和关键元信息。</p>
      </section>
    );
  }

  const llmInput = metadata.llm_input ?? metadata.prompt_full ?? metadata.prompt ?? metadata.prompt_preview;
  const llmOutput = metadata.llm_output ?? metadata.raw_model_output ?? metadata.raw_model_preview;
  const operatorInput = metadata.operator_input;
  const operatorOutput = metadata.operator_output;
  const noLlmReason = metadata.no_llm_reason;

  const inputItems: KeyValue[] = [
    { label: '父节点', value: shortIdList(readStringList(metadata.parent_ids)) },
    { label: 'Subtask', value: metadata.subtask_id },
    { label: '分支', value: metadata.branch_type ?? metadata.generation_strategy },
    { label: 'Prompt ID', value: metadata.prompt_id },
    { label: 'Operator 类型', value: metadata.operator_kind },
  ];

  const outputItems: KeyValue[] = [
    { label: 'Claims', value: metadata.claim_count },
    { label: 'Critique', value: metadata.critique_count },
    { label: '选中 subtasks', value: readStringList(metadata.selected_subtask_ids) },
    { label: '选中分支', value: readStringList(metadata.selected_branch_types) },
    { label: '策略', value: metadata.aggregation_policy },
  ];

  const validationItems: KeyValue[] = validation
    ? [
        { label: 'Pass', value: validation.pass },
        { label: 'Confidence', value: validation.confidence },
        { label: 'Blocking', value: readStringList(validation.blocking_issues) },
        { label: 'Required edits', value: readStringList(validation.required_edits) },
        { label: 'Warnings', value: readStringList(validation.non_blocking_issues) },
      ]
    : [];

  const handoffItems: KeyValue[] = handoff
    ? [
        { label: '专家', value: handoff.selected_expert },
        { label: '标的/市场', value: handoff.asset_or_market },
        { label: '周期', value: handoff.time_horizon },
        { label: '意图', value: handoff.user_intent },
        { label: '缺失信息', value: readStringList(handoff.missing_context) },
      ]
    : [];

  const subtaskItems: KeyValue[] = [
    { label: 'Required outputs', value: readStringList(metadata.required_outputs) },
    { label: 'Dependencies', value: readStringList(metadata.dependencies) },
    { label: 'Evidence needed', value: readStringList(metadata.evidence_needed) },
  ];

  const modelItems: KeyValue[] = [
    { label: 'Prompt preview', value: metadata.prompt_preview },
    { label: 'Raw model preview', value: metadata.raw_model_preview },
  ];

  const otherItems = remainingMetadata(metadata, [
    'internal_id',
    'parent_ids',
    'subtask_id',
    'branch_type',
    'generation_strategy',
    'branch_index',
    'prompt_id',
    'operator_kind',
    'operator_input',
    'operator_output',
    'no_llm_reason',
    'llm_input',
    'llm_output',
    'prompt_full',
    'prompt',
    'raw_model_output',
    'claim_count',
    'critique_count',
    'selected_subtask_ids',
    'selected_branch_types',
    'selected_state_ids',
    'aggregation_policy',
    'validation',
    'handoff',
    'required_outputs',
    'dependencies',
    'evidence_needed',
    'prompt_preview',
    'raw_model_preview',
  ]);

  return (
    <section className="panel inspector-panel">
      <h2>节点详情</h2>

      <section className="detail-section">
        <h3>概览</h3>
        <div className="node-title">{node.data.label}</div>
        <KeyValueGrid
          items={[
            { label: '阶段', value: stageLabel(node.data.stage) },
            { label: '状态', value: node.data.status },
            { label: '评分', value: formatScore(node.data.score) },
            { label: '内部 ID', value: shortId(String(metadata.internal_id ?? node.id)) },
          ]}
        />
      </section>

      <section className="detail-section">
        <h3>输入</h3>
        <KeyValueGrid items={inputItems} compact />
        <TextBlock title="Operator 输入预览" value={operatorInput} />
        {hasValue(operatorInput) && (
          <button className="link-button" type="button" onClick={() => setModal({ title: '完整 Operator 输入', value: operatorInput })}>
            查看完整输入
          </button>
        )}
      </section>

      <section className="detail-section">
        <h3>输出</h3>
        <TextBlock title="摘要 / 输出预览" value={node.data.summary} />
        <TextBlock title="Operator 输出预览" value={operatorOutput} />
        <KeyValueGrid items={outputItems} compact />
        {hasValue(operatorOutput) && (
          <button className="link-button" type="button" onClick={() => setModal({ title: '完整 Operator 输出', value: operatorOutput })}>
            查看完整输出
          </button>
        )}
      </section>

      {handoffItems.length > 0 && (
        <section className="detail-section">
          <h3>专家选择</h3>
          <TextBlock title="Handoff reason" value={String(handoff?.handoff_reason ?? '')} />
          <KeyValueGrid items={handoffItems} compact />
        </section>
      )}

      {hasAnyValue(subtaskItems) && (
        <section className="detail-section">
          <h3>Subtask</h3>
          <KeyValueGrid items={subtaskItems} compact />
        </section>
      )}

      {validationItems.length > 0 && hasAnyValue(validationItems) && (
        <section className="detail-section">
          <h3>验证结果</h3>
          <KeyValueGrid items={validationItems} compact />
        </section>
      )}

      <section className="detail-section">
        <h3>LLM 调用</h3>
        {hasAnyValue(modelItems) || hasValue(llmInput) || hasValue(llmOutput) ? (
          <>
            <TextBlock title="Prompt preview" value={metadata.prompt_preview} />
            <TextBlock title="Raw model preview" value={metadata.raw_model_preview} />
            <div className="button-row">
              {hasValue(llmInput) && (
                <button className="link-button" type="button" onClick={() => setModal({ title: '完整 LLM 输入 / Prompt', value: llmInput })}>
                  查看完整 LLM 输入
                </button>
              )}
              {hasValue(llmOutput) && (
                <button className="link-button" type="button" onClick={() => setModal({ title: '完整 LLM 输出', value: llmOutput })}>
                  查看完整 LLM 输出
                </button>
              )}
            </div>
          </>
        ) : (
          <p className="empty-hint">{String(noLlmReason ?? '该节点没有直接调用 LLM。')}</p>
        )}
      </section>

      {otherItems.length > 0 && (
        <section className="detail-section">
          <details>
            <summary>其他元信息</summary>
            <KeyValueGrid items={otherItems} compact />
          </details>
        </section>
      )}

      <details className="raw-metadata">
        <summary>调试：原始 metadata</summary>
        <pre>{JSON.stringify(metadata, null, 2)}</pre>
      </details>

      {modal && <FullInfoModal payload={modal} onClose={() => setModal(null)} />}
    </section>
  );
}

function KeyValueGrid({ items, compact = false }: { items: KeyValue[]; compact?: boolean }) {
  const visibleItems = items.filter((item) => hasValue(item.value));
  if (!visibleItems.length) return <p className="empty-hint">无</p>;
  return (
    <dl className={compact ? 'kv-grid compact' : 'kv-grid'}>
      {visibleItems.map((item) => (
        <div className="kv-row" key={item.label}>
          <dt>{item.label}</dt>
          <dd>{renderValue(item.value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function TextBlock({ title, value }: { title: string; value: unknown }) {
  if (!hasValue(value)) return null;
  return (
    <div className="text-block">
      <div className="text-block-title">{title}</div>
      <p>{truncate(formatShortValue(value), 900)}</p>
    </div>
  );
}

function FullInfoModal({ payload, onClose }: { payload: ModalPayload; onClose: () => void }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="modal-panel" role="dialog" aria-modal="true" aria-label={payload.title} onClick={(event) => event.stopPropagation()}>
        <header className="modal-header">
          <h3>{payload.title}</h3>
          <button type="button" onClick={onClose}>
            关闭
          </button>
        </header>
        <pre className="modal-content">{formatFullValue(payload.value)}</pre>
      </section>
    </div>
  );
}

function renderValue(value: unknown) {
  if (Array.isArray(value)) {
    if (!value.length) return '-';
    return (
      <div className="pill-list">
        {value.slice(0, 12).map((item, index) => (
          <span className="pill" key={`${String(item)}-${index}`}>
            {truncate(String(item), 64)}
          </span>
        ))}
        {value.length > 12 && <span className="pill muted">+{value.length - 12}</span>}
      </div>
    );
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (isRecord(value)) return summarizeRecord(value);
  return truncate(String(value ?? '-'), 140);
}

function stageLabel(stage: string | null) {
  if (!stage) return '-';
  return STAGE_LABELS[stage] ?? stage;
}

function formatScore(score: number | null | undefined) {
  if (typeof score !== 'number') return '-';
  return score.toFixed(3);
}

function shortId(value: string) {
  if (!value) return '-';
  const parts = value.split('_');
  if (parts.length >= 2) return `${parts[0]}_${parts[1].slice(0, 8)}`;
  return value.length > 14 ? `${value.slice(0, 14)}…` : value;
}

function shortIdList(values: string[]) {
  return values.map(shortId);
}

function readStringList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  if (typeof value === 'string' && value.trim()) return [value];
  return [];
}

function asRecord(value: unknown): Metadata | null {
  return isRecord(value) ? value : null;
}

function isRecord(value: unknown): value is Metadata {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasValue(value: unknown) {
  if (value === null || value === undefined || value === '') return false;
  if (Array.isArray(value) && value.length === 0) return false;
  return true;
}

function hasAnyValue(items: KeyValue[]) {
  return items.some((item) => hasValue(item.value));
}

function summarizeRecord(value: Metadata) {
  const entries = Object.entries(value).filter(([, item]) => hasValue(item));
  if (!entries.length) return '-';
  return entries
    .slice(0, 4)
    .map(([key, item]) => `${key}: ${Array.isArray(item) ? item.length : truncate(String(item), 40)}`)
    .join(' · ');
}

function remainingMetadata(metadata: Metadata, hiddenKeys: string[]): KeyValue[] {
  const hidden = new Set(hiddenKeys);
  return Object.entries(metadata)
    .filter(([key, value]) => !hidden.has(key) && hasValue(value))
    .slice(0, 18)
    .map(([key, value]) => ({ label: labelize(key), value }));
}

function labelize(key: string) {
  return key
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function truncate(value: string, maxLength: number) {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength)}…`;
}

function formatShortValue(value: unknown) {
  if (typeof value === 'string') return value;
  return formatFullValue(value);
}

function formatFullValue(value: unknown) {
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
