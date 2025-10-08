type StatusMessage = {
  id: string;
  text: string;
  level: "info" | "error";
  timestamp: string;
};

type StatusDisplayProps = {
  messages: StatusMessage[];
};

export function StatusDisplay({ messages }: StatusDisplayProps) {
  return (
    <section className="panel">
      <header className="panel__header">
        <h2>Status</h2>
      </header>
      <div className="panel__body status-display">
        {messages.length === 0 && <p>No activity recorded yet.</p>}
        {messages.map((message) => (
          <article
            key={message.id}
            className={`status-message status-message--${message.level}`}
          >
            <header>
              <time dateTime={message.timestamp}>{message.timestamp}</time>
              <span>{message.level.toUpperCase()}</span>
            </header>
            <pre>{message.text}</pre>
          </article>
        ))}
      </div>
    </section>
  );
}

export type { StatusMessage };
