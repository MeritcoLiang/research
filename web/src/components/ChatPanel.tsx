import { FormEvent, useState } from 'react';

export type LLMProvider = 'stage_flow' | 'azure_openai' | 'deepseek';

type Props = {
  disabled?: boolean;
  onSend: (message: string, llmProvider: LLMProvider) => void;
  finalPreview?: string | null;
};

export function ChatPanel({ disabled, onSend, finalPreview }: Props) {
  const [message, setMessage] = useState('请用二级市场分析师视角分析 AAPL 的中期机会和风险。');
  const [llmProvider, setLlmProvider] = useState<LLMProvider>('stage_flow');

  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;
    onSend(trimmed, llmProvider);
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
      <h3>最终答案预览</h3>
      <pre>{finalPreview ?? '等待运行...'}</pre>
    </section>
  );
}
