import { FormEvent, useState } from 'react';

type Props = {
  disabled?: boolean;
  onSend: (message: string) => void;
  finalPreview?: string | null;
};

export function ChatPanel({ disabled, onSend, finalPreview }: Props) {
  const [message, setMessage] = useState('进入 Pipeline v0.2');

  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;
    onSend(trimmed);
  }

  return (
    <section className="panel chat-panel">
      <h2>对话输入</h2>
      <form onSubmit={submit}>
        <textarea value={message} onChange={(event) => setMessage(event.target.value)} rows={6} />
        <button disabled={disabled} type="submit">
          运行 Pipeline
        </button>
      </form>
      <h3>最终答案预览</h3>
      <pre>{finalPreview ?? '等待运行...'}</pre>
    </section>
  );
}
