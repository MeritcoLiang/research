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
            {event.stage ? <span> · {event.stage}</span> : null}
            {event.state_id ? <span> · {event.state_id}</span> : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
