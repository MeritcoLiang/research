import type { TraceEvent } from '../types';

type Props = {
  events: TraceEvent[];
};

export function EventTimeline({ events }: Props) {
  return (
    <section className="panel timeline-panel">
      <h2>事件流</h2>
      <ol>
        {events.slice(-80).map((event) => (
          <li key={event.event_id}>
            <code>{event.event_type}</code>
            {event.stage ? <span> · {friendlyStage(event.stage)}</span> : null}
            {event.event_type === 'subtask_created' ? (
              <span> · {String(event.payload.subtask_id ?? 'subtask')}</span>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}

function friendlyStage(stage: string) {
  const map: Record<string, string> = {
    root: 'root',
    problem_decomposer: 'subtasks',
    candidate_generator: 'candidates',
    thought_normalizer: 'normalized',
    verifier_scorer: 'scored',
    aggregator: 'aggregation',
    final_validator: 'validation',
    trace_logger: 'trace',
  };
  return map[stage] ?? stage;
}
