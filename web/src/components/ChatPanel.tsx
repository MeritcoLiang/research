import { FormEvent, useState } from 'react';
import type { HistoryTraceItem } from '../types';

export type LLMProvider = 'stage_flow' | 'azure_openai' | 'deepseek';

type Props = {
  disabled?: boolean;
  onSend: (message: string, llmProvider: LLMProvider) => void;
  onLoadHistory: (historyId: string) => void;
  onRefreshHistory: () => void;
  histories: HistoryTraceItem[];
  finalPreview?: string | null;
};

export function ChatPanel({ disabled, onSend, onLoadHistory, onRefreshHistory, histories, finalPreview }: Props) {
  const [message, setMessage] = useState('请用二级市场分析师视角分析 AAPL 的中期机会和风险。');
  const [llmProvider, setLlmProvider] = useState<LLMProvider>('stage_flow');
  const [historyId, setHistoryId] = useState('');

  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;
    onSend(trimmed, llmProvider);
  }

  function loadSelectedHistory() {
    if (!historyId) return;
    onLoadHistory(historyId);
  }

  return (
    <section className="panel chat-panel">
      <h2>对话输入</h2>
      <form onSubmit={submit}>
        <label className="field-label" htmlFor="llm-provider">
          LLM / Operator 实现
        </label>
        <select
          id="llm-provider"
          value={llmProvider}
          onChange={(event) => setLlmProvider(event.target.value as LLMProvider)}
        >
          <option value="stage_flow">Stage Flow（无真实 LLM）</option>
          <option value="azure_openai">Azure OpenAI（az login）</option>
          <option value="deepseek">DeepSeek</option>
        </select>
        <textarea value={message} onChange={(event) => setMessage(event.target.value)} rows={6} />
        <button disabled={disabled} type="submit">
          发送任务
        </button>
      </form>

      <section className="history-box">
        <h3>历史 Session</h3>
        <select value={historyId} onChange={(event) => setHistoryId(event.target.value)}>
          <option value="">选择历史 trace...</option>
          {histories.map((item) => (
            <option key={item.history_id} value={item.history_id}>
              {historyLabel(item)}
            </option>
          ))}
        </select>
        <div className="history-actions">
          <button disabled={!historyId || disabled} type="button" onClick={loadSelectedHistory}>
            加载流程图
          </button>
          <button disabled={disabled} type="button" onClick={onRefreshHistory}>
            刷新列表
          </button>
        </div>
      </section>

      <h3>最终答案预览</h3>
      <pre>{finalPreview ?? '等待运行...'}</pre>
    </section>
  );
}

function historyLabel(item: HistoryTraceItem) {
  const provider = item.llm_provider ?? 'unknown';
  const status = item.final_status ?? 'unknown';
  const session = item.session_id ?? item.history_id.replace('.jsonl', '');
  const query = item.user_query_preview ? ` · ${truncate(item.user_query_preview, 28)}` : '';
  return `${provider} · ${status} · ${session}${query}`;
}

function truncate(value: string, maxLength: number) {
  return value.length > maxLength ? `${value.slice(0, maxLength)}…` : value;
}
